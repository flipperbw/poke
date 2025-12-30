import argparse
import json
import re
import typing as tp
import os
import hashlib

import numpy as np
import pandas as pd
from line_profiler import profile
from tabulate import tabulate

# Bump this when cache format/columns change
CACHE_VERSION = 1


def _file_sig(path: str) -> dict:
    try:
        st = os.stat(path)
        return {'path': os.path.normpath(path), 'mtime': int(st.st_mtime), 'size': int(st.st_size)}
    except Exception:
        return {'path': os.path.normpath(path), 'mtime': 0, 'size': 0}


def _cache_key_for_score(
    *,
    pokes_path: str,
    moves_path: str,
    top_n: int,
    bias_mode: str,
    no_stab_bonus: bool,
    per_type: bool,
    moves_per: int,
    prefer_stab: bool,
    coverage_slots: int,
    allow_boost: bool,
    allow_legends: bool,
    allow_megas: bool,
    blocked_moves: tp.Optional[set[str]],
) -> str:
    # Stable dict to hash
    payload = {
        'v': CACHE_VERSION,
        'pokes': _file_sig(pokes_path),
        'moves': _file_sig(moves_path),
        'top_n': int(top_n),
        'bias_mode': str(bias_mode),
        'no_stab_bonus': bool(no_stab_bonus),
        'per_type': bool(per_type),
        'moves_per': int(moves_per),
        'prefer_stab': bool(prefer_stab),
        'coverage_slots': int(coverage_slots),
        'allow_boost': bool(allow_boost),
        'allow_legends': bool(allow_legends),
        'allow_megas': bool(allow_megas),
        'blocked_moves': sorted([str(x) for x in (blocked_moves or [])]),
    }
    raw = json.dumps(payload, sort_keys=True).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()[:24]


def _cache_paths(cache_dir: str, key: str) -> str:
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f'score_cache_{key}.csv.gz')

# In-code default move blocklist (edit here as desired)
BLOCKED_MOVES: set[str] = {
    'swagger', 'future-sight', 'misty-explosion',
    'outrage', 'icicle-spear', 'draco-meteor', 'dream-eater', 'first-impression', 'steel-beam', 'acid-armor',
    'superpower', 'water-spout'
}

# Comprehensive list of common offensive boosting moves (name-based)
# Used to robustly identify boost moves even when move metadata is sparse.
BOOST_NAME_SET: set[str] = {
    # Pure status offensive boosters
    'swords-dance', 'nasty-plot', 'calm-mind', 'bulk-up', 'quiver-dance',
    'work-up', 'dragon-dance', 'tail-glow', 'hone-claws', 'howl', 'growth',
    'meditate', 'sharpen', 'victory-dance', 'no-retreat', 'coil', 'shift-gear',
    'clangorous-soul',
    # Mixed/stat-raising with offensive component
    'curse', 'shell-smash', 'agility',  # agility helps kills via speed, optional
    # Attacking moves that raise SpA/Atk
    'torch-song', 'fiery-dance', 'charge-beam', 'power-up-punch',
}


def _load_moves(path: str) -> pd.DataFrame:
    """Load ZA moves and compute a simple effectiveness score per move.

    Score formula (matches src/moves.py analyze() logic):
      tot = power * avg_hits * (accuracy/100) / (2 if dead_turn else 1)
    For status/raising moves, `mv_score` is 0 but we retain them to allow
    selecting setup/utility moves.
    """
    df = pd.read_json(path, orient='index')

    # Derived columns for score
    df['dead_turn'] = df['effect_short'].str.contains(
        r'turn to charge before attacking|next turn to recharge', na=False
    )
    df['avg_hits'] = ((df['min_hits'] + df['max_hits']) / 2).fillna(1)
    # Some moves may have NaN power/accuracy; treat as 0 power
    df['power'] = df['power'].fillna(0)
    df['accuracy'] = df['accuracy'].fillna(100)
    # For non-status, compute score; for status, 0
    is_status = df['class'] == 'status'
    mv_score = (df['power'] * df['avg_hits'] * (df['accuracy'] / 100.0)) / (
        df['dead_turn'].astype(int) + 1
    )
    df['mv_score'] = mv_score.where(~is_status, 0.0)

    # Flag self-KO (e.g., "User faints") moves to exclude them later
    df['effect_long'] = df.get('effect_long', '')
    df['suicide'] = (
        df['effect_short'].str.contains('user faints', case=False, na=False)
        | df['effect_long'].astype(str).str.contains('user faints', case=False, na=False)
    )

    # Keep essential columns used later
    keep_cols = [
        'class', 'type', 'pp', 'target', 'mv_score', 'stat_changes',
        'effect_short', 'effect_long', 'suicide', 'category'
    ]
    return df[keep_cols]


# --- Type effectiveness helpers (for coverage logic) ---
_TYPE_OFFENSE: dict[str, set[str]] | None = None


def _load_type_offense(typs_path: str = 'src/data/typs.json') -> dict[str, set[str]]:
    """Load offensive strong targets for each regular type.

    Returns a mapping: move_type -> set of defender types this type hits super effectively.
    Only regular single types are included as keys, and defender entries are also single types.
    """
    global _TYPE_OFFENSE
    if _TYPE_OFFENSE is not None:
        return _TYPE_OFFENSE
    try:
        data: dict = json.load(open(typs_path, 'r'))
    except Exception:
        _TYPE_OFFENSE = {}
        return _TYPE_OFFENSE
    ret: dict[str, set[str]] = {}
    for tname, tv in data.items():
        if '_' in tname:
            continue  # skip dual-type keys
        try:
            strong_list = tv['to_a']['data']['strong']['typs']
        except Exception:
            strong_list = []
        ret[tname] = {x for x in strong_list if isinstance(x, str) and '_' not in x}
    _TYPE_OFFENSE = ret
    return ret


def _tier(row: pd.Series) -> str:
    if row.get('is_mythical'):
        return 'Mythical'
    if row.get('is_legendary'):
        return 'Legendary'
    return 'Regular'


def _stab_multiplier(move_type: str, poke_type: str) -> float:
    # poke_type is like 'fire' or 'fire_water'
    typs = set(str(poke_type).split('_'))
    return 1.5 if move_type in typs else 1.0


def _attack_bias(atk_type: str) -> tp.Literal['physical', 'special', 'any']:
    if atk_type == 'Atk':
        return 'physical'
    if atk_type == 'SpA':
        return 'special'
    return 'any'

def score_pokemon(
    pokes_path: str,
    moves_path: str,
    top_n: int = 50,
    bias_mode: tp.Literal['auto', 'atk', 'spa', 'any'] = 'auto',
    no_stab_bonus: bool = False,
    per_type: bool = False,
    moves_per: int = 4,
    prefer_stab: bool = True,
    coverage_slots: int = 1,
    allow_boost: bool = True,
    allow_legends: bool = True,
    allow_megas: bool = True,
    blocked_moves: tp.Optional[set[str]] = None,
    use_cache: bool = True,
    cache_dir: str | None = 'cache',
) -> pd.DataFrame:
    # Resolve blocklist defaults first (used in cache key)
    if blocked_moves is None:
        blocked_moves = BLOCKED_MOVES

    # Try cache
    if use_cache and cache_dir:
        try:
            key = _cache_key_for_score(
                pokes_path=pokes_path,
                moves_path=moves_path,
                top_n=top_n,
                bias_mode=bias_mode,
                no_stab_bonus=no_stab_bonus,
                per_type=per_type,
                moves_per=moves_per,
                prefer_stab=prefer_stab,
                coverage_slots=coverage_slots,
                allow_boost=allow_boost,
                allow_legends=allow_legends,
                allow_megas=allow_megas,
                blocked_moves=blocked_moves,
            )
            cache_path = _cache_paths(cache_dir, key)
            if os.path.exists(cache_path):
                # Use pandas to read
                cached = pd.read_csv(cache_path)
                return cached
        except Exception:
            # Ignore cache errors
            pass

    # Load data
    pokes = pd.read_json(pokes_path, orient='index')
    moves = _load_moves(moves_path)

    # Optionally filter out Mega forms entirely
    if not allow_megas and 'name' in pokes.columns:
        name_series = pokes['name'].astype(str).str.lower()
        mega_mask = name_series.str.endswith(('-mega', '-mega-x', '-mega-y', '-mega-z'))
        pokes = pokes[~mega_mask]

    # Precompute mapping move_name -> row for quick join
    mv = moves.copy()
    mv.index.name = 'move_name'

    # Explode Pokémon moves to rows and attach move metadata
    pk = pokes[['name', 'dex', 'type', 'atk_type', 'tot', 'tot_b', 'is_legendary', 'is_mythical', 'moves', 'attack', 'special-attack']].copy()
    # Ensure moves list
    pk['moves'] = pk['moves'].apply(lambda xs: xs if isinstance(xs, list) else [])
    # Filter out tutor moves (not available in ZA)
    pk['moves'] = pk['moves'].apply(lambda xs: [m for m in xs if isinstance(m, dict) and m.get('how') != 'tutor'])

    # --- Mega fallback: if a Mega form has an empty moveset, use its base form's moves ---
    def _base_name(n: str) -> str:
        s = str(n).lower()
        for suf in ('-mega-x', '-mega-y', '-mega-z', '-mega'):
            if s.endswith(suf):
                return s[: -len(suf)]
        return s

    # Build mapping base_name -> representative non-mega moves list (prefer non-empty; prefer exact base name)
    names_lower = pokes['name'].astype(str).str.lower()
    is_mega_mask = names_lower.str.endswith(('-mega', '-mega-x', '-mega-y', '-mega-z'))
    base_names = names_lower.map(_base_name)
    # Create a DataFrame to pick best base record per base name
    pick_df = pokes.copy()
    pick_df = pick_df.assign(
        name_lower=names_lower,
        base_name=base_names,
        is_mega=is_mega_mask,
        moves_list=pokes['moves'].apply(lambda xs: xs if isinstance(xs, list) else []),
        moves_len=pokes['moves'].apply(lambda xs: len(xs) if isinstance(xs, list) else 0),
    )
    # Prefer non-mega rows; among them prefer the exact base-name match, then longest moves list
    non_megas = pick_df[~pick_df['is_mega']].copy()

    def _pref_score(row):
        exact = 1 if row['name_lower'] == row['base_name'] else 0
        return (exact, row['moves_len'])

    if not non_megas.empty:
        non_megas['_pref'] = non_megas.apply(_pref_score, axis=1)
        # For each base_name, get row with max _pref (tuple compares lexicographically)
        idxs = non_megas.groupby('base_name')['_pref'].idxmax()
        base_moves_map: dict[str, list] = {}
        for idx in idxs:
            r = non_megas.loc[idx]
            base_moves_map[str(r['base_name'])] = r['moves_list'] if isinstance(r['moves_list'], list) else []
    else:
        base_moves_map = {}

    # Apply fallback to pk moves: for any Mega row with empty moves, substitute base moves
    def _fallback_moves(row: pd.Series) -> list:
        nm = str(row['name']).lower()
        mv = row['moves'] if isinstance(row['moves'], list) else []
        if mv:
            return mv
        # empty moves -> if mega form, try base
        if nm.endswith(('-mega', '-mega-x', '-mega-y', '-mega-z')):
            b = _base_name(nm)
            bm = base_moves_map.get(b, [])
            # ensure dict structure and filter tutor again defensively
            bm = [m for m in bm if isinstance(m, dict) and m.get('how') != 'tutor']
            return bm
        return mv

    pk['moves'] = pk.apply(_fallback_moves, axis=1)
    exploded = pk.explode('moves')
    # Extract move name from dicts
    exploded['move_name'] = exploded['moves'].apply(lambda m: m.get('name') if isinstance(m, dict) else None)
    exploded = exploded.drop(columns=['moves'])
    # Apply move blocklist (by exact move name)
    if blocked_moves:
        exploded = exploded[~exploded['move_name'].isin(blocked_moves)]

    # Join move details (ensure we keep both Pokémon typing and move typing)
    exploded = exploded.merge(
        mv,
        left_on='move_name',
        right_index=True,
        how='left',
        suffixes=('_poke', '_move'),
    )

    # Drop rows without a move name (keep status + attacks; mv_score may be 0 for status)
    exploded = exploded.dropna(subset=['move_name'])
    # Exclude self-KO moves (e.g., "User faints")
    if 'suicide' in exploded.columns:
        # Avoid FutureWarning about silent downcasting on fillna by inferring objects explicitly
        s = exploded['suicide'].infer_objects(copy=False).fillna(False)
        # try:
        #     s = s.infer_objects(copy=False)  # pandas >= 2.1
        # except Exception:
        #     pass
        exploded = exploded[~s.astype(bool)]

    # Compute STAB-adjusted score
    if no_stab_bonus:
        exploded['eff_score'] = exploded['mv_score']
    else:
        # STAB if move type is one of the Pokémon's types
        exploded['eff_score'] = exploded.apply(
            lambda r: r['mv_score'] * _stab_multiplier(
                str(r.get('type_move')),
                r.get('type_poke', r.get('type'))
            ),
            axis=1,
        )

    # Determine move class bias
    # Normalize columns following join: moves DataFrame has column 'class'
    exploded.rename(columns={'class': 'move_class'}, inplace=True)
    # After merge with suffixes, move type is under 'type_move'
    if 'type_move' not in exploded.columns:
        exploded['type_move'] = np.nan

    # Apply bias filter per Pokémon
    # Compute strict offensive bias per Pokémon: match higher of Attack vs Sp. Atk
    # Attach per-row bias to each exploded move row
    def choose_bias_row(row: pd.Series) -> str:
        # Explicit overrides
        if bias_mode == 'atk':
            return 'physical'
        if bias_mode == 'spa':
            return 'special'
        if bias_mode == 'any':
            return 'any'
        # Auto/strict: pick based on higher base stat
        try:
            atk = float(row.get('attack'))
            spa = float(row.get('special-attack'))
            return 'physical' if atk >= spa else 'special'
        except Exception:
            # Fallback to previous heuristic based on atk_type if stats missing
            return _attack_bias(str(row.get('atk_type')))

    exploded['bias'] = exploded.apply(choose_bias_row, axis=1)

    def bias_match(row: pd.Series) -> bool:
        if row['bias'] == 'any':
            return True
        if row['bias'] == 'physical':
            return row['move_class'] == 'physical'
        if row['bias'] == 'special':
            return row['move_class'] == 'special'
        return True

    exploded['bias_ok'] = exploded.apply(bias_match, axis=1)

    # Helper flags
    exploded['is_status'] = exploded['move_class'] == 'status'
    # STAB flag for selection prefs
    exploded['is_stab'] = exploded.apply(
        lambda r: _stab_multiplier(str(r.get('type_move')), r.get('type_poke', r.get('type'))) > 1.0,
        axis=1,
    )

    # Boosting move detection: robust name-driven first, then meta/text heuristics
    def is_boost_row(r: pd.Series) -> bool:
        if not allow_boost:
            return False
        # 0) Name whitelist always counts as boosting
        name = str(r.get('move_name', '')).lower()
        if name in BOOST_NAME_SET:
            return True
        # 1) Meta/text-based (requires status)
        if r.get('is_status') is not True:
            # allow certain attacking self-boosters even if not status
            return name in {'torch-song', 'fiery-dance', 'charge-beam', 'power-up-punch'}
        # For status moves, ensure the move targets the user (or allies) before considering it a boost
        tgt = str(r.get('target', '')).lower()
        is_self_target = any(k in tgt for k in ('user', 'ally', 'allies'))
        # Treat move meta category as authoritative when available, but only if self-targeting
        cat = str(r.get('category') or '').lower()
        if cat == 'net-good-stats' and is_self_target:
            return True
        sc = r.get('stat_changes')
        try:
            # stat_changes is list of dicts: {'amt': int, 'type': 'attack'|'special-attack'|...}
            if is_self_target and any((d.get('amt', 0) or 0) > 0 and d.get('type') in ('attack', 'special-attack') for d in sc or []):
                return True
        except Exception:
            pass

        # Fallback to effect text heuristics
        es = str(r.get('effect_short', ''))
        el = str(r.get('effect_long', ''))
        text = f"{es}\n{el}".lower()
        # Common phrasing patterns indicating offensive stat boosts
        boost_patterns = [
            r"raises the user's attack",
            r"raises the user's special attack",
            r"raises the user's sp\. atk",
            r"sharply raises the user's attack",
            r"sharply raises the user's special attack",
            r"drastically raises the user's attack",
            r"drastically raises the user's special attack",
            r"boosts the user's attack",
            r"boosts the user's special attack",
            r"sharply boosts the user's attack",
            r"sharply boosts the user's special attack",
        ]
        if any(re.search(p, text) for p in boost_patterns):
            return True

        # Do NOT treat generic self-target status as boost unless one of the above conditions matched
        return False

    exploded['is_boost'] = exploded.apply(is_boost_row, axis=1)
    # Ensure known boosting move names are always flagged, even if metadata is sparse
    exploded.loc[exploded['move_name'].isin(BOOST_NAME_SET), 'is_boost'] = True

    # For each Pokémon, select up to `moves_per` moves: prefer STAB attacks, add coverage of other types, optionally one boost.
    def select_moves(group: pd.DataFrame) -> pd.Series:
        g = group.copy()
        # Separate
        atk = g[g['is_status'] == False].copy()
        # Enforce bias-aligned attacking class first; fallback to any if none
        bias_val = g['bias'].iloc[0] if not g.empty else 'any'
        atk_bias = atk[atk['bias_ok']] if bias_val != 'any' else atk
        if atk_bias.empty:
            atk_bias = atk
        # Prefer STAB, then eff_score within the bias-filtered set
        if prefer_stab:
            atk_bias = atk_bias.sort_values(['is_stab', 'eff_score'], ascending=[False, False])
        else:
            atk_bias = atk_bias.sort_values(['eff_score'], ascending=[False])

        chosen: list[pd.Series] = []

        # 1) Optionally include one boosting move aligning with bias if available
        boost_pick = None
        if allow_boost:
            boosts = g[g['is_boost']]
            # Prefer boosts that match bias (attack vs spa)
            pref = None
            if g['bias'].iloc[0] == 'physical':
                pref = boosts[boosts['effect_short'].str.contains('attack', case=False, na=False)]
            elif g['bias'].iloc[0] == 'special':
                pref = boosts[boosts['effect_short'].str.contains('special', case=False, na=False)]
            if pref is not None and not pref.empty:
                boost_pick = pref.iloc[0].copy()
                boost_pick['is_boost'] = True
            elif not boosts.empty:
                boost_pick = boosts.iloc[0].copy()
                boost_pick['is_boost'] = True
            else:
                # Fallback: name-based boost detection even if metadata failed to flag is_boost
                try:
                    names_lower = g['move_name'].astype(str).str.lower()
                    present_boosts = [n for n in names_lower.tolist() if n in BOOST_NAME_SET]
                    if present_boosts:
                        # pick the first present boost by name
                        cand_name = present_boosts[0]
                        gb = g[names_lower == cand_name]
                        if not gb.empty:
                            boost_pick = gb.iloc[0].copy()
                            boost_pick['is_boost'] = True
                except Exception:
                    pass

        # 2) Pick STAB attacks from bias-matching set
        stab_attacks = atk_bias[atk_bias['is_stab']]
        # Ensure unique move types first; grab up to 2
        stab_selected: list[pd.Series] = []
        seen_types: set[str] = set()
        for _, row in stab_attacks.iterrows():
            t = str(row.get('type_move'))
            if t in seen_types:
                continue
            stab_selected.append(row)
            seen_types.add(t)
            if len(stab_selected) >= 2:
                break

        # 3) Coverage attacks (non-STAB), up to coverage_slots, distinct types
        coverage_selected: list[pd.Series] = []
        coverage_attacks = atk_bias[~atk_bias['is_stab']].copy()

        # Build coverage map from type chart
        type_off = _load_type_offense()
        # Determine already covered defender types from chosen STAB types
        stab_types = {str(r.get('type_move')) for r in stab_selected if pd.notna(r.get('type_move'))}
        covered_targets: set[str] = set()
        for st in stab_types:
            covered_targets |= type_off.get(st, set())

        # Compute coverage gain for each candidate type
        def cov_gain_for(row: pd.Series) -> int:
            mt = str(row.get('type_move'))
            strong_set = type_off.get(mt, set())
            return len(strong_set - covered_targets)

        # Score candidates by coverage gain, bias, and eff_score
        if not coverage_attacks.empty:
            coverage_attacks['cov_gain'] = coverage_attacks.apply(cov_gain_for, axis=1)
            # Dynamic threshold for allowing zero-gain Normal as coverage (very strong only)
            try:
                strong_threshold = max(60.0, float(np.nanpercentile(coverage_attacks['eff_score'], 95)))
            except Exception:
                strong_threshold = 100.0

            # Sort candidates
            coverage_attacks.sort_values(['cov_gain', 'bias_ok', 'eff_score'], ascending=[False, False, False], inplace=True)

            cov_seen: set[str] = set()
            for _, row in coverage_attacks.iterrows():
                t = str(row.get('type_move'))
                if t in cov_seen:
                    continue
                gain = int(row.get('cov_gain', 0))
                if gain <= 0:
                    # Avoid Normal as coverage unless exceptionally strong
                    if t == 'normal' and float(row.get('eff_score', 0.0)) < strong_threshold:
                        continue
                    # For other types with no new coverage, accept only if we still need slots and it's quite strong
                    if float(row.get('eff_score', 0.0)) < strong_threshold:
                        continue
                coverage_selected.append(row)
                cov_seen.add(t)
                if len(coverage_selected) >= max(0, coverage_slots):
                    break

        # Combine picks and fill remaining with next best attacks
        for r in stab_selected:
            chosen.append(r)
        for r in coverage_selected:
            chosen.append(r)
        if boost_pick is not None:
            chosen.append(boost_pick)

        # Fill with best remaining attacks (excluding already chosen moves), still respecting bias when possible
        needed = max(0, moves_per - len(chosen))
        if needed > 0:
            chosen_names = {c['move_name'] for c in chosen}
            # Try remaining bias-matching first
            rest_bias = atk_bias[~atk_bias['move_name'].isin(chosen_names)]
            rest = rest_bias if not rest_bias.empty else atk[~atk['move_name'].isin(chosen_names)]
            rest = rest.sort_values(['eff_score'], ascending=[False])
            for _, row in rest.head(needed).iterrows():
                chosen.append(row)

        # Truncate to moves_per
        chosen = chosen[:moves_per]

        # Compute attack score as the AVERAGE of selected attacking moves to avoid penalizing
        # Pokémon that include status/boost moves in the 4-slot set
        atk_scores = [float(c['eff_score']) for c in chosen if c.get('is_status') is not True]
        atk_sum = float(np.mean(atk_scores)) if len(atk_scores) > 0 else 0.0

        # Best single move for backward compatibility columns
        best_att = atk.sort_values('eff_score', ascending=False).iloc[0] if not atk.empty else None
        best_move_name = best_att['move_name'] if best_att is not None else None
        best_move_type = best_att['type_move'] if best_att is not None else None
        best_move_class = best_att['move_class'] if best_att is not None else None
        best_move_score = float(best_att['eff_score']) if best_att is not None else 0.0

        return pd.Series(
            {
                'best_move': best_move_name,
                'best_move_type': best_move_type,
                'best_move_class': best_move_class,
                'best_move_score': best_move_score,
                'moves4': ', '.join(str(c['move_name']) for c in chosen),
                # Use boolean truthiness instead of identity checks to avoid NumPy bool issues
                'stab_moves': ', '.join(
                    str(c['move_name'])
                        for c in chosen
                        if (not bool(c.get('is_status', False))) and bool(c.get('is_stab', False))
                ),
                'coverage_moves': ', '.join(
                    str(c['move_name'])
                        for c in chosen
                        if (not bool(c.get('is_status', False))) and (not bool(c.get('is_stab', False)))
                ),
                'boost_moves': ', '.join(
                    str(c['move_name'])
                        for c in chosen
                        if (bool(c.get('is_boost', False)) or str(c.get('move_name', '')).lower() in BOOST_NAME_SET)
                ),
                'attack_sum': atk_sum,
            }
        )

    best = exploded.groupby(level=0).apply(select_moves)

    # Ensure every Pokémon appears in result; fill defaults for those with no eligible moves
    default_vals = {
        # Use empty strings for text fields to avoid pandas fillna(None) error
        'best_move': '',
        'best_move_type': '',
        'best_move_class': '',
        'best_move_score': 0.0,
        'moves4': '',
        'stab_moves': '',
        'coverage_moves': '',
        'boost_moves': '',
        'attack_sum': 0.0,
    }
    best = best.reindex(pk.index)
    for col, val in default_vals.items():
        if col not in best.columns:
            best[col] = val
    best = best.fillna(value=default_vals)

    # Merge back to Pokémon base
    out = pk.drop(columns=['moves']).join(best)

    # Tier and final score
    out['tier'] = out.apply(_tier, axis=1)

    # Optionally exclude Legendary/Mythical before computing final ranks
    if not allow_legends:
        out = out[~out['tier'].isin(['Legendary', 'Mythical'])]
    # Composite: include Speed (tot) + sum of selected attacking move scores
    out['score'] = out['tot'] + out['attack_sum'].fillna(0)

    # Sort overall
    out = out.sort_values(['score', 'tot_b'], ascending=False)

    # Output selection
    cols = [
        'name', 'dex', 'type', 'tier', 'atk_type', 'tot', 'tot_b',
        'moves4', 'stab_moves', 'coverage_moves', 'boost_moves', 'attack_sum', 'score',
    ]
    out = out[cols]

    if per_type:
        # pick best per primary type (first type in combo)
        out = out.copy()
        out['primary_type'] = out['type'].apply(lambda s: str(s).split('_')[0])
        out = (
            out.sort_values('score', ascending=False)
            .groupby('primary_type', as_index=False)
            .head(top_n)
        )
    else:
        out = out.head(top_n)

    # Save cache
    if use_cache and cache_dir:
        try:
            if 'primary_type' in out.columns:
                # Keep for symmetry; we store as-is
                pass
            key = _cache_key_for_score(
                pokes_path=pokes_path,
                moves_path=moves_path,
                top_n=top_n,
                bias_mode=bias_mode,
                no_stab_bonus=no_stab_bonus,
                per_type=per_type,
                moves_per=moves_per,
                prefer_stab=prefer_stab,
                coverage_slots=coverage_slots,
                allow_boost=allow_boost,
                allow_legends=allow_legends,
                allow_megas=allow_megas,
                blocked_moves=blocked_moves,
            )
            cache_path = _cache_paths(cache_dir, key)
            out.to_csv(cache_path, index=False, compression='infer')
        except Exception:
            pass

    return out


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Score Pokémon for Legends: Z-A using raw stats and moves.')
    p.add_argument('--pokes', default='src/data/pokes-all-za.json', help='Path to pokes-all-za.json')
    p.add_argument('--moves', default='src/data/moves-za.json', help='Path to moves-za.json')
    p.add_argument('--top', type=int, default=100, help='How many to show (or per type when --per-type)')
    p.add_argument('--per-type', action='store_true', help='Show top per primary type instead of global top')
    p.add_argument('--no-stab-bonus', action='store_true', help='Disable STAB bonus in move scoring')
    p.add_argument('--bias', choices=['auto', 'atk', 'spa', 'any'], default='auto', help='Move class bias mode')
    p.add_argument('--format', choices=['table', 'csv'], default='table', help='Console output format (default: table)')
    p.add_argument('--no-legends', action='store_true', help='Exclude Legendary and Mythical Pokémon from results')
    p.add_argument('--no-mega', action='store_true', help='Exclude Mega forms (e.g., -mega, -mega-x, -mega-y) from results')
    p.add_argument('--block-move', action='append', help='Move name to exclude (repeatable). Also see BLOCKED_MOVES in code.')
    # Caching
    p.add_argument('--no-cache', action='store_true', help='Disable caching of score_pokemon results')
    p.add_argument('--cache-dir', default='cache', help='Directory to store cache files (default: cache)')
    p.add_argument('--csv', help='Write results to CSV at this path')
    return p.parse_args()


if __name__ == '__main__':
    args = _parse_args()

    # Merge CLI-provided block moves
    cli_blocked = set(m.strip() for m in (args.block_move or []) if isinstance(m, str))
    blocked_moves = BLOCKED_MOVES | cli_blocked
    df = score_pokemon(
        pokes_path=args.pokes,
        moves_path=args.moves,
        top_n=args.top,
        bias_mode=tp.cast(tp.Literal['auto', 'atk', 'spa', 'any'], args.bias),
        no_stab_bonus=args.no_stab_bonus,
        per_type=args.per_type,
        allow_legends=not args.no_legends,
        allow_megas=not args.no_mega,
        blocked_moves=blocked_moves,
        use_cache=not args.no_cache,
        cache_dir=args.cache_dir,
    )
    if args.csv:
        df.to_csv(args.csv, index=False)
        print(f'Wrote {args.csv} ({len(df)} rows)')
    else:
        if args.format == 'csv':
            print(df.to_csv(index=False))
        else:
            # Pretty table formatting for console
            show = df.copy()
            # Rank column (overall or per-type)
            if 'primary_type' in show.columns:
                show['rank'] = show.groupby('primary_type').cumcount() + 1
                # Move rank near the front
                cols = ['rank', 'primary_type'] + [c for c in show.columns if c not in ('rank', 'primary_type')]
                show = show[cols]
            else:
                show.insert(0, 'rank', range(1, len(show) + 1))

            # Numeric formatting
            for c in ('tot', 'tot_b'):
                if c in show.columns:
                    show[c] = show[c].astype(int)
            for c in ('best_move_score', 'score'):
                if c in show.columns:
                    show[c] = show[c].map(lambda x: f"{x:.1f}")

            # Hide raw moves4 column in tabular output per request
            if 'moves4' in show.columns:
                show = show.drop(columns=['moves4'])

            print(tabulate(show, headers='keys', tablefmt='grid', showindex=False))  # simple_grid
