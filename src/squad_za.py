import argparse
import itertools
import json
import typing as tp

import numpy as np
import pandas as pd
from tabulate import tabulate
from line_profiler import profile
from functools import lru_cache

# We reuse the scoring and move selection from score_za
from score_za import _load_type_offense, score_pokemon

# In-code defaults you can edit
BLOCKED_POKEMON: set[str] = {
    'Kyogre-primal', 'Groudon-primal', 'Hoopa-unbound', 'greninja-battle-bond',
    'zygarde-complete', 'zygarde-50', 'zygarde-50-power-construct', 'zygarde-10-power-construct',
    'keldeo-resolute', 'magearna-original', 'meloetta-pirouette', 'mimikyu-disguised',
    # morpeko-full-belly,morpeko-hangry
}
MUST_INCLUDE: set[str] = set()


def _load_moves_map(path: str) -> dict:
    """Map move name -> metadata dict (class, type, etc.)."""
    with open(path, 'r') as f:
        data = json.load(f)
    return data


def _load_typs(path: str) -> dict:
    with open(path, 'r') as f:
        return json.load(f)


def _base_name(name: str) -> str:
    """Normalize a Pokémon name to its base form (strip Mega suffixes)."""
    n = str(name).lower()
    for suf in ('-mega-x', '-mega-y', '-mega-z', '-mega'):
        if n.endswith(suf):
            return n[: -len(suf)]
    return n


def _load_pokes_map(path: str) -> dict[str, dict]:
    """Load pokes-all-za.json and return name->row mapping (lowercased).

    Also includes entries for base names (strip -mega/-mega-x/-mega-y), preferring the base form if present.
    """
    with open(path, 'r') as f:
        data: dict = json.load(f)
    out: dict[str, dict] = {}
    for name, row in data.items():
        n = str(name).lower()
        out[n] = row
        # Map base name too
        bn = _base_name(n)
        if bn not in out:
            out[bn] = row
    return out


def _format_moveset(moves4: str, moves_map: dict) -> str:
    """Pretty format a 4-move set with type/class annotations.

    Example: "moonblast (fairy/special), focus-blast (fighting/special), calm-mind (psychic/status), thunderbolt (electric/special)"
    """
    if not isinstance(moves4, str) or not moves4.strip():
        return ''
    parts = [p.strip() for p in moves4.split(',') if p.strip()]
    pretty: list[str] = []
    for name in parts:
        meta = moves_map.get(name, {})
        mtyp = meta.get('type') or '?'
        mcls = meta.get('class') or '?'
        pretty.append(f"{name} ({mtyp}/{mcls})")
    return '/'.join(pretty)


def _defensive_weak_types(typs_json: dict, combo_name: str) -> set[str]:
    """Return set of single types this typing is WEAK to (i.e., takes >1x from).

    We consider weaknesses as the union of `from.double.typs` and `from.quad.typs`.
    """
    entry = typs_json.get(combo_name)
    if not entry:
        return set()
    try:
        double = entry['from']['double']['typs'] if 'double' in entry['from'] else []
        quad = entry['from']['quad']['typs'] if 'quad' in entry['from'] else []
        return set(t for t in list(double) + list(quad) if isinstance(t, str) and '_' not in t)
    except Exception:
        return set()


def _defensive_profile(typs_json: dict, combo_name: str) -> tuple[set[str], set[str], set[str]]:
    """Return (weak_to, resist_to, immune_to) sets for a given typing combo name.

    All sets contain only regular single types.
    """
    entry = typs_json.get(combo_name)
    if not entry:
        return set(), set(), set()
    try:
        weak = set(t for t in entry['from'].get('double', {}).get('typs', []) if isinstance(t, str) and '_' not in t)
        weak |= set(t for t in entry['from'].get('quad', {}).get('typs', []) if isinstance(t, str) and '_' not in t)
    except Exception:
        weak = set()
    try:
        resist = set(t for t in entry['from'].get('half', {}).get('typs', []) if isinstance(t, str) and '_' not in t)
        resist |= set(t for t in entry['from'].get('quarter', {}).get('typs', []) if isinstance(t, str) and '_' not in t)
    except Exception:
        resist = set()
    try:
        immune = set(t for t in entry['from'].get('none', {}).get('typs', []) if isinstance(t, str) and '_' not in t)
    except Exception:
        immune = set()
    return weak, resist, immune


def _offensive_coverage_for_moves(moves_str: str, moves_map: dict, type_offense: dict[str, set[str]]) -> tuple[set[str], set[str]]:
    """Given a comma-separated moves string, return (attacking_move_types, covered_defender_types)."""
    if not isinstance(moves_str, str):
        return set(), set()
    mv_names = [m.strip() for m in moves_str.split(',') if m.strip()]
    atk_types: set[str] = set()
    for name in mv_names:
        meta = moves_map.get(name)
        if not meta:
            continue
        if meta.get('class') == 'status':
            continue
        mtyp = meta.get('type')
        if isinstance(mtyp, str):
            atk_types.add(mtyp)
    covered: set[str] = set()
    for t in atk_types:
        covered |= type_offense.get(t, set())
    return atk_types, covered


def _normalize(series: pd.Series) -> pd.Series:
    s = series.fillna(0).astype(float)
    if len(s) == 0:
        return s
    lo, hi = float(s.min()), float(s.max())
    if hi <= lo:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - lo) / (hi - lo)


@profile
def build_squads(
    pokes_path: str,
    moves_path: str,
    typs_path: str,
    k_candidates: int = 60,
    top_teams: int = 5,
    team_size: int = 3,
    allow_legends: bool = True,
    allow_megas: bool = True,
    prefer_non_overlap: bool = True,
    coverage_weight: float = 1.0,
    power_weight: float = 0.8,
    bulk_weight: float = 0.6,
    weakness_weight: float = 0.4,
    weakness_overlap_weight: float = 0.7,
    max_megas_per_team: int = 1,
    blocked_pokemon: tp.Optional[set[str]] = None,
    banned_types: tp.Optional[set[str]] = None,
    must_include: tp.Optional[set[str]] = None,
    counters: tp.Optional[set[str]] = None,
    counter_def_pct: float = 0.6,
    require_screen_setter: bool = False,
    unique_across_teams: bool = True,
) -> pd.DataFrame:
    # Score individuals using existing ZA logic (includes selected moves4, attack_sum, tot)
    scored = score_pokemon(
        pokes_path=pokes_path,
        moves_path=moves_path,
        top_n=10_000,  # get all, we'll trim below
        per_type=False,
        allow_legends=allow_legends,
        allow_megas=allow_megas,
    )

    # Optionally filter out legends/mythicals
    if not allow_legends:
        mask = ~scored['tier'].isin(['Legendary', 'Mythical'])
        scored = scored[mask]

    # Keep top K by individual score to keep combination search tractable
    candidates = scored.head(k_candidates).copy()
    # Apply Pokémon blocklist (by base name, lowercased)
    if blocked_pokemon:
        def _base(n: str) -> str:
            s = str(n).lower()
            for suf in ('-mega-x', '-mega-y', '-mega-z', '-mega'):
                if s.endswith(suf):
                    return s[: -len(suf)]
            return s

        base_block = {_base(n) for n in blocked_pokemon}
        candidates = candidates[~candidates['name'].str.lower().map(_base).isin(base_block)]

    # Load helpers
    moves_map = _load_moves_map(moves_path)
    typs_json = _load_typs(typs_path)
    type_offense = _load_type_offense(typs_path)
    pokes_map = _load_pokes_map(pokes_path)

    # Optional: filter out banned types (single types ban any combo containing it;
    # combo like "bug_steel" bans exact combo)
    if banned_types:
        banned_lc = {str(x).strip().lower() for x in banned_types if isinstance(x, str)}

        def _type_is_banned(t: str) -> bool:
            s = str(t).lower()
            if s in banned_lc:
                return True
            parts = s.split('_') if s else []
            return any(p in banned_lc for p in parts)

        candidates = candidates[~candidates['type'].astype(str).map(_type_is_banned)]

    # Precompute each candidate's attack types, coverage types, and weaknesses
    atk_types_list: list[set[str]] = []
    coverage_list: list[set[str]] = []
    weak_list: list[set[str]] = []
    for _, row in candidates.iterrows():
        atk_types, covered = _offensive_coverage_for_moves(row.get('moves4', ''), moves_map, type_offense)
        atk_types_list.append(atk_types)
        coverage_list.append(covered)
        weak_list.append(_defensive_weak_types(typs_json, row.get('type')))

    candidates = candidates.assign(
        atk_types=atk_types_list,
        cover_types=coverage_list,
        weak_types=weak_list,
    )

    # Normalized numeric features for team objective
    candidates['power_norm'] = _normalize(candidates['attack_sum'])
    candidates['bulk_norm'] = _normalize(candidates['tot_b'])

    # Helpers for Mega handling and base-name equivalence
    def _is_mega(name: str) -> bool:
        n = str(name).lower()
        return n.endswith('-mega') or n.endswith('-mega-x') or n.endswith('-mega-y') or n.endswith('-mega-z')

    # --- Countering logic ---
    # Normalize list of targets to counter (base names)
    counter_targets: list[dict] = []
    if counters:
        seen_ct: set[str] = set()
        for t in counters:
            tname = _base_name(str(t))
            if tname in seen_ct:
                continue
            seen_ct.add(tname)
            targ = pokes_map.get(tname)
            if not targ:
                # try exact lookup if base mapping failed
                targ = pokes_map.get(str(t).lower())
            if not targ:
                continue
            # Target metadata
            t_type = str(targ.get('type'))
            t_atk = float(targ.get('attack', 0))
            t_spa = float(targ.get('special-attack', 0))
            # STAB set (split combo)
            stab_set = set(str(t_type).split('_'))
            # Weaknesses of target
            t_weak = _defensive_weak_types(typs_json, t_type)
            # Offensive bias of target: choose defense stat to check on the counter
            prefers_physical = t_atk >= t_spa
            counter_targets.append(
                {
                    'name': tname,
                    'type': t_type,
                    'stab': stab_set,
                    'weak': t_weak,
                    'prefers_physical': prefers_physical,
                }
            )

    # Precompute defense percentiles among candidates for thresholding
    if counter_targets:
        try:
            def_vals = candidates['defense'].astype(float)
            spd_vals = candidates['special-defense'].astype(float)
        except Exception:
            # Ensure columns exist by pulling from pokes_map if missing
            # Join these stats from pokes_map
            def get_stat(name: str, stat: str) -> float:
                row = pokes_map.get(str(name).lower(), {})
                return float(row.get(stat, 0))

            candidates = candidates.copy()
            candidates['defense'] = candidates['name'].apply(lambda n: get_stat(n, 'defense'))
            candidates['special-defense'] = candidates['name'].apply(lambda n: get_stat(n, 'special-defense'))
            def_vals = candidates['defense'].astype(float)
            spd_vals = candidates['special-defense'].astype(float)
        def_threshold = float(np.nanpercentile(def_vals, counter_def_pct * 100.0)) if len(def_vals) else 0.0
        spd_threshold = float(np.nanpercentile(spd_vals, counter_def_pct * 100.0)) if len(spd_vals) else 0.0
    else:
        def_threshold = spd_threshold = 0.0

    # Evaluate all team-size combinations
    records: list[dict] = []
    idx_list = list(candidates.index)
    n_cand = len(idx_list)
    # Pre-extract hot fields into arrays/lists for index-based access in the hot loop
    names: list[str] = candidates['name'].astype(str).tolist()
    names_lower: list[str] = [s.lower() for s in names]
    def _base_from_name(n: str) -> str:
        return _base_name(n)
    base_names: list[str] = [_base_from_name(n) for n in names_lower]
    # Fast mega flag per candidate to avoid recomputing in hot loop
    is_mega_arr = np.fromiter((_is_mega(n) for n in names_lower), dtype=np.int8)
    types_arr: list[str] = candidates['type'].astype(str).tolist()
    # Primary types (no longer enforced to be distinct, kept for potential display/metrics)
    primary_types: list[str] = [t.split('_')[0] for t in types_arr]
    tiers_arr: list[str] = candidates['tier'].astype(str).tolist()
    moves4_arr: list[str] = candidates['moves4'].astype(str).tolist()
    cover_types_list: list[set] = candidates['cover_types'].tolist()
    weak_types_list: list[set] = candidates['weak_types'].tolist()
    atk_types_list_loc: list[set] = candidates['atk_types'].tolist()
    # Build type→bit mapping from observed types in cover/weak/atk
    observed_types: set[str] = set()
    for s in cover_types_list:
        observed_types.update(s)
    for s in weak_types_list:
        observed_types.update(s)
    for s in atk_types_list_loc:
        observed_types.update(s)
    type_list = sorted(observed_types)
    type_to_bit = {t: i for i, t in enumerate(type_list)}
    # Precompute bitmasks and per-candidate counts
    def _mask_for(s: set[str]) -> int:
        m = 0
        for t in s:
            b = type_to_bit.get(t)
            if b is not None:
                m |= (1 << b)
        return m
    cover_mask = [ _mask_for(s) for s in cover_types_list ]
    weak_mask = [ _mask_for(s) for s in weak_types_list ]
    atk_mask = [ _mask_for(s) for s in atk_types_list_loc ]
    cover_cnt_arr = np.fromiter((len(s) for s in cover_types_list), dtype=np.int16, count=n_cand)
    weak_cnt_arr = np.fromiter((len(s) for s in weak_types_list), dtype=np.int16, count=n_cand)
    atk_cnt_arr = np.fromiter((len(s) for s in atk_types_list_loc), dtype=np.int16, count=n_cand)
    pnorm = candidates['power_norm'].astype(float).to_numpy()
    bnorm = candidates['bulk_norm'].astype(float).to_numpy()
    atk_sum_arr = candidates['attack_sum'].astype(float).to_numpy()
    tot_b_arr = candidates['tot_b'].astype(int).to_numpy()
    # Optional stats for counters
    if 'defense' in candidates.columns:
        def_arr = candidates['defense'].astype(float).to_numpy()
    else:
        def_arr = np.full(n_cand, np.nan, dtype=float)
    if 'special-defense' in candidates.columns:
        spd_arr = candidates['special-defense'].astype(float).to_numpy()
    else:
        spd_arr = np.full(n_cand, np.nan, dtype=float)
    # Basic guard
    try:
        team_size_int = int(team_size)
    except Exception:
        team_size_int = 3
    if team_size_int < 1:
        team_size_int = 1
    if team_size_int > len(idx_list):
        team_size_int = len(idx_list)
    # Normalize must-include set to base names (lowercase)
    must_bases: set[str] = set()
    if must_include:
        for n in must_include:
            nn = str(n).lower()
            for suf in ('-mega-x', '-mega-y', '-mega-z', '-mega'):
                if nn.endswith(suf):
                    nn = nn[: -len(suf)]
                    break
            must_bases.add(nn)

    # --- Caches/helpers used in the hot loop ---
    # Cache defensive type profiles by type string

    @lru_cache(maxsize=None)
    def _def_prof_cached(type_str: str):
        return _defensive_profile(typs_json, type_str)

    # Cache formatted moveset by moves4 string (used later for post-selection enrichment)
    @lru_cache(maxsize=None)
    def _fmt_cached(moves4_str: str):
        return _format_moveset(moves4_str, moves_map)

    # Precompute screen-setter capability per candidate to avoid repeated pokes_map lookups in hot loops
    def _knows_both_screens_by_name(mon_name: str) -> bool:
        def _has_moves(row_obj: dict) -> bool:
            mv_list = row_obj.get('moves') if isinstance(row_obj, dict) else None
            if not isinstance(mv_list, list):
                return False
            names_ = {m.get('name') for m in mv_list if isinstance(m, dict) and m.get('how') != 'tutor'}
            return 'light-screen' in names_ and 'reflect' in names_
        nm = str(mon_name).lower()
        base_nm = _base_name(nm)
        row_exact = pokes_map.get(nm)
        row_base = pokes_map.get(base_nm)
        return (_has_moves(row_exact) or _has_moves(row_base))

    screen_setter_arr = [
        _knows_both_screens_by_name(nm) for nm in names
    ] if require_screen_setter else [False] * n_cand

    if team_size_int == 3:
        for comb in itertools.combinations(range(n_cand), 3):
            i, j, k = comb
            # Unique names fast-path
            ni, nj, nk = names_lower[i], names_lower[j], names_lower[k]
            if not (ni != nj and ni != nk and nj != nk):
                continue
            # Mega constraint
            if max_megas_per_team >= 0:
                if int(is_mega_arr[i]) + int(is_mega_arr[j]) + int(is_mega_arr[k]) > max_megas_per_team:
                    continue
            # Base-equivalence: all three bases must differ
            bi, bj, bk = base_names[i], base_names[j], base_names[k]
            if not (bi != bj and bi != bk and bj != bk):
                continue
            # Must-include bases
            if must_bases:
                bases_set = {bi, bj, bk}
                if not must_bases.issubset(bases_set):
                    continue
            # Screen setter requirement
            if require_screen_setter:
                if not (screen_setter_arr[i] or screen_setter_arr[j] or screen_setter_arr[k]):
                    continue
            # Counters logic
            def member_counters_target_idx(idx: int, target: dict) -> bool:
                if not (cover_types_list[idx] & target['weak']):
                    return False
                if target['prefers_physical']:
                    mem_def = float(def_arr[idx])
                    if not (mem_def == mem_def and mem_def >= def_threshold):
                        return False
                else:
                    mem_spd = float(spd_arr[idx])
                    if not (mem_spd == mem_spd and mem_spd >= spd_threshold):
                        return False
                m_type = types_arr[idx]
                weak_set, resist_set, immune_set = _def_prof_cached(m_type)
                stab = target['stab']
                if any(t in weak_set for t in stab):
                    return False
                if not (stab & (resist_set | immune_set)):
                    return False
                return True
            if counter_targets:
                ok_for_all = True
                for targ in counter_targets:
                    if not (member_counters_target_idx(i, targ) or member_counters_target_idx(j, targ) or member_counters_target_idx(k, targ)):
                        ok_for_all = False
                        break
                if not ok_for_all:
                    continue
            # Coverage/weakness counts via bitmasks
            cov_union = cover_mask[i] | cover_mask[j] | cover_mask[k]
            cov_count = int(cov_union.bit_count())
            w1m, w2m, w3m = weak_mask[i], weak_mask[j], weak_mask[k]
            weak_union = w1m | w2m | w3m
            weak_count = int(weak_union.bit_count())
            # Approx overlap penalty for size 3 (exact via intersections):
            w12 = (w1m & w2m).bit_count(); w13 = (w1m & w3m).bit_count(); w23 = (w2m & w3m).bit_count()
            w123 = (w1m & w2m & w3m).bit_count()
            count_exactly2 = (w12 + w13 + w23) - 3 * w123
            overlap_penalty = float(count_exactly2 * 1 + w123 * 4)
            # Redundancy penalty using attack masks
            redundancy_pen = 0.0
            if prefer_non_overlap:
                total_atk_types = int(atk_cnt_arr[i] + atk_cnt_arr[j] + atk_cnt_arr[k])
                if total_atk_types > 0:
                    union_atk = atk_mask[i] | atk_mask[j] | atk_mask[k]
                    union_sz = int(union_atk.bit_count())
                    redundancy = 1.0 - (union_sz / float(total_atk_types))
                    redundancy_pen = 0.3 * float(redundancy)
            # Team power/bulk: direct sums
            team_power = float(pnorm[i] + pnorm[j] + pnorm[k])
            team_bulk = float(bnorm[i] + bnorm[j] + bnorm[k])
            score = (
                coverage_weight * cov_count
                + power_weight * team_power
                + bulk_weight * team_bulk
                - weakness_weight * weak_count
                - redundancy_pen
                - weakness_overlap_weight * overlap_penalty
            )
            records.append(
                dict(
                    idxs=comb,
                    cov_count=cov_count,
                    weak_count=weak_count,
                    power_sum=float(atk_sum_arr[i] + atk_sum_arr[j] + atk_sum_arr[k]),
                    bulk_sum=int(tot_b_arr[i] + tot_b_arr[j] + tot_b_arr[k]),
                    team_score=float(score),
                )
            )
    elif team_size_int == 6:
        # Parameters for size-6 search
        k_threshold_for_beam = 160
        mitm_partial_cap = 80000
        mitm_bucket_cap = 200
        beam_width = 300

        n = n_cand
        use_mitm = n <= k_threshold_for_beam

        # Precompute can_counter bitmask per candidate if needed
        target_bits = {}
        if counter_targets:
            for t_idx, targ in enumerate(counter_targets):
                target_bits[id(targ)] = t_idx
        can_counter_mask = [0] * n
        if counter_targets:
            # Reuse member_counters_target_idx logic components inlined for speed
            def can_counter(idx: int, targ: dict) -> bool:
                if not (cover_types_list[idx] & targ['weak']):
                    return False
                if targ['prefers_physical']:
                    mem_def = float(def_arr[idx])
                    if not (mem_def == mem_def and mem_def >= def_threshold):
                        return False
                else:
                    mem_spd = float(spd_arr[idx])
                    if not (mem_spd == mem_spd and mem_spd >= spd_threshold):
                        return False
                m_type = types_arr[idx]
                weak_set, resist_set, immune_set = _def_prof_cached(m_type)
                stab = targ['stab']
                if any(t in weak_set for t in stab):
                    return False
                if not (stab & (resist_set | immune_set)):
                    return False
                return True
            for i in range(n):
                mask = 0
                for t_idx, targ in enumerate(counter_targets):
                    if can_counter(i, targ):
                        mask |= (1 << t_idx)
                can_counter_mask[i] = mask

        # Helper: evaluate score from masks/sums quickly
        def eval_score(cov_m: int, weak_m: int, pwr: float, blk: float,
                       total_weak_counts: int, atk_union: int, total_atk_counts: int) -> float:
            cov_count = cov_m.bit_count()
            weak_count = weak_m.bit_count()
            # Approximate weakness overlap penalty: total individual weak counts minus union size
            overlap_proxy = max(0, total_weak_counts - weak_count)
            redundancy_pen = 0.0
            if prefer_non_overlap and total_atk_counts > 0:
                union_sz = atk_union.bit_count()
                redundancy = 1.0 - (union_sz / float(total_atk_counts))
                redundancy_pen = 0.3 * float(redundancy)
            return (
                coverage_weight * cov_count
                + power_weight * pwr
                + bulk_weight * blk
                - weakness_weight * weak_count
                - redundancy_pen
                - weakness_overlap_weight * overlap_proxy
            )

        if use_mitm:
            # If we must keep teams unique across the final selection, widen partial caps
            # to preserve diversity; otherwise the post filter can end up with too few teams.
            if unique_across_teams and top_teams and top_teams > 1:
                mitm_bucket_cap = max(mitm_bucket_cap, 1000)
                mitm_partial_cap = max(mitm_partial_cap, 200000)
            # Generate 3-member partials with pruning buckets
            from collections import defaultdict
            buckets = defaultdict(list)  # key: (mega_count, cov_bin)
            partials = []
            for i in range(n):
                ni = names_lower[i]
                bi = base_names[i]
                mi = int(is_mega_arr[i])
                for j in range(i+1, n):
                    nj = names_lower[j]
                    bj = base_names[j]
                    if ni == nj or bi == bj:
                        continue
                    mj = mi + int(is_mega_arr[j])
                    for k in range(j+1, n):
                        nk = names_lower[k]
                        bk = base_names[k]
                        if nk == nj or nk == ni:
                            continue
                        if bk == bj or bk == bi:
                            continue
                        mm = mj + int(is_mega_arr[k])
                        if max_megas_per_team >= 0 and mm > max_megas_per_team:
                            continue
                        idxs = (i, j, k)
                        cov_m = cover_mask[i] | cover_mask[j] | cover_mask[k]
                        weak_m = weak_mask[i] | weak_mask[j] | weak_mask[k]
                        atk_m = atk_mask[i] | atk_mask[j] | atk_mask[k]
                        pwr = float(pnorm[i] + pnorm[j] + pnorm[k])
                        blk = float(bnorm[i] + bnorm[j] + bnorm[k])
                        atk_cnt_sum = int(atk_cnt_arr[i] + atk_cnt_arr[j] + atk_cnt_arr[k])
                        weak_cnt_sum = int(weak_cnt_arr[i] + weak_cnt_arr[j] + weak_cnt_arr[k])
                        scr = (screen_setter_arr[i] or screen_setter_arr[j] or screen_setter_arr[k])
                        cnt_mask = 0
                        if counter_targets:
                            cnt_mask = can_counter_mask[i] | can_counter_mask[j] | can_counter_mask[k]
                        # Upper bound heuristic for pruning
                        ub = eval_score(cov_m, weak_m, pwr, blk, weak_cnt_sum, atk_m, atk_cnt_sum)
                        item = (ub, idxs, cov_m, weak_m, atk_m, pwr, blk, atk_cnt_sum, weak_cnt_sum, mm, scr, cnt_mask)
                        # Bucket by mega count and coarse coverage bin to encourage diversity
                        cov_bin = (cov_m.bit_count() // 3)
                        buckets[(mm, cov_bin)].append(item)
                        partials.append(item)
            # Cap per-bucket and globally by UB
            capped = []
            for key, lst in buckets.items():
                lst.sort(key=lambda x: x[0], reverse=True)
                capped.extend(lst[:mitm_bucket_cap])
            capped.sort(key=lambda x: x[0], reverse=True)
            capped = capped[:mitm_partial_cap]

            left = capped
            right = capped

            import heapq
            # Use a deterministic, fully-orderable key in the heap to avoid comparing dicts when scores tie.
            # Store (score, idxs_tuple, record) so ties on score break by team indices.
            heap = []  # min-heap of (score, idxs_tuple, record)
            # If we must keep teams unique across the final selection, we need a larger
            # and more diverse candidate pool; otherwise, most top candidates will
            # share members and the post-filter may yield too few teams.
            if unique_across_teams and top_teams and top_teams > 1:
                # Generous, adaptive cap to preserve diversity; bounded to avoid blowup.
                # Scale with both requested team count and candidate pool size.
                heap_cap = min(max(top_teams * 1000, max(10000, n * 50)), 100000)
            else:
                heap_cap = max(top_teams * 10, 50)

            # Precompute base and name sets for fast disjoint checks
            def base_set(idxs):
                return {base_names[a] for a in idxs}
            def name_set(idxs):
                return {names_lower[a] for a in idxs}

            left_meta = [(item, base_set(item[1]), name_set(item[1])) for item in left]
            right_meta = [(item, base_set(item[1]), name_set(item[1])) for item in right]

            for (ubL, idxsL, covL, weakL, atkL, pL, bL, atkCntL, weakCntL, mL, scrL, cntL), bsetL, nsetL in left_meta:
                for (ubR, idxsR, covR, weakR, atkR, pR, bR, atkCntR, weakCntR, mR, scrR, cntR), bsetR, nsetR in right_meta:
                    # Disjoint indices
                    if set(idxsL) & set(idxsR):
                        continue
                    # Base/name uniqueness across 6
                    if bsetL & bsetR:
                        continue
                    if nsetL & nsetR:
                        continue
                    # Mega cap
                    if max_megas_per_team >= 0 and (mL + mR) > max_megas_per_team:
                        continue
                    # Screen requirement
                    if require_screen_setter and not (scrL or scrR):
                        continue
                    # Counters requirement
                    if counter_targets:
                        # All targets must be covered by at least one member overall
                        all_targets_mask = (cntL | cntR)
                        if all_targets_mask != ((1 << len(counter_targets)) - 1):
                            continue
                    # Must-include bases (apply before scoring/push to heap)
                    if must_bases:
                        combined_bases = bsetL | bsetR
                        if not must_bases.issubset(combined_bases):
                            continue
                    cov_m = covL | covR
                    weak_m = weakL | weakR
                    atk_m = atkL | atkR
                    pwr = pL + pR
                    blk = bL + bR
                    atk_cnt_sum = atkCntL + atkCntR
                    weak_cnt_sum = weakCntL + weakCntR
                    score = eval_score(cov_m, weak_m, pwr, blk, weak_cnt_sum, atk_m, atk_cnt_sum)
                    rec = dict(
                        idxs=tuple(sorted(idxsL + idxsR)),
                        cov_count=int(cov_m.bit_count()),
                        weak_count=int(weak_m.bit_count()),
                        power_sum=float(atk_sum_arr[list(idxsL)].sum() + atk_sum_arr[list(idxsR)].sum()),
                        bulk_sum=int(tot_b_arr[list(idxsL)].sum() + tot_b_arr[list(idxsR)].sum()),
                        team_score=float(score),
                    )
                    idxs_key = rec['idxs']
                    if len(heap) < heap_cap:
                        heapq.heappush(heap, (score, idxs_key, rec))
                    else:
                        if score > heap[0][0]:
                            heapq.heapreplace(heap, (score, idxs_key, rec))

            # Drain heap to records with de-duplication by idxs
            seen_idxs: set[tp.Tuple[int, ...]] = set()
            for _, __, rec in heap:
                key = rec['idxs']
                if key in seen_idxs:
                    continue
                seen_idxs.add(key)
                # Safety: enforce must-bases again at drain time
                if must_bases:
                    base_equiv = {base_names[i] for i in key}
                    if not must_bases.issubset(base_equiv):
                        continue
                records.append(rec)
        else:
            # Beam search fallback (approximate)
            import heapq
            B = beam_width
            # State: (neg_estimated_score, cov_mask, weak_mask, atk_mask, pwr, blk, atk_cnt_sum, weak_cnt_sum, mega_count, has_screen, used_indices_tuple)
            # Seed with singles
            beam = []
            for i in range(n):
                if max_megas_per_team >= 0 and int(is_mega_arr[i]) > max_megas_per_team:
                    continue
                cov_m = cover_mask[i]
                weak_m = weak_mask[i]
                atk_m = atk_mask[i]
                pwr = float(pnorm[i])
                blk = float(bnorm[i])
                atk_cnt_sum = int(atk_cnt_arr[i])
                weak_cnt_sum = int(weak_cnt_arr[i])
                scr = bool(screen_setter_arr[i])
                est = eval_score(cov_m, weak_m, pwr, blk, weak_cnt_sum, atk_m, atk_cnt_sum)
                heapq.heappush(beam, (-est, cov_m, weak_m, atk_m, pwr, blk, atk_cnt_sum, weak_cnt_sum, int(is_mega_arr[i]), scr, (i,)))
                if len(beam) > B:
                    heapq.heappop(beam)
            # Extend to 6
            for size in range(2, 7):
                next_beam = []
                while beam:
                    (_ne, cov_m, weak_m, atk_m, pwr, blk, atk_cnt_sum, weak_cnt_sum, mega_c, scr, used) = heapq.heappop(beam)
                    used_set = set(used)
                    last = used[-1]
                    for idx in range(last+1, n):
                        if idx in used_set:
                            continue
                        # Name/base uniqueness
                        nm = names_lower[idx]
                        if nm in {names_lower[u] for u in used}:
                            continue
                        bn = base_names[idx]
                        if bn in {base_names[u] for u in used}:
                            continue
                        mmega = mega_c + int(is_mega_arr[idx])
                        if max_megas_per_team >= 0 and mmega > max_megas_per_team:
                            continue
                        cov2 = cov_m | cover_mask[idx]
                        weak2 = weak_m | weak_mask[idx]
                        atk2 = atk_m | atk_mask[idx]
                        pwr2 = pwr + float(pnorm[idx])
                        blk2 = blk + float(bnorm[idx])
                        atk_cnt2 = atk_cnt_sum + int(atk_cnt_arr[idx])
                        weak_cnt2 = weak_cnt_sum + int(weak_cnt_arr[idx])
                        scr2 = scr or bool(screen_setter_arr[idx])
                        est2 = eval_score(cov2, weak2, pwr2, blk2, weak_cnt2, atk2, atk_cnt2)
                        heapq.heappush(next_beam, (-est2, cov2, weak2, atk2, pwr2, blk2, atk_cnt2, weak_cnt2, mmega, scr2, used + (idx,)))
                        if len(next_beam) > B:
                            heapq.heappop(next_beam)
                beam = next_beam
                if size == 6:
                    # Collect final states
                    finals = sorted([(-ne, cov_m, weak_m, atk_m, pwr, blk, atk_cnt_sum, weak_cnt_sum, mega_c, scr, used) for (ne, cov_m, weak_m, atk_m, pwr, blk, atk_cnt_sum, weak_cnt_sum, mega_c, scr, used) in beam], reverse=True)
                    seen_idxs: set[tp.Tuple[int, ...]] = set()
                    # If uniqueness across teams is required, widen the finals slice to
                    # keep enough diversity for the post-selection disjointness filter.
                    if unique_across_teams and top_teams and top_teams > 1:
                        # Keep many more finals to ensure we can form multiple disjoint teams
                        # after post-selection uniqueness filtering.
                        finals_limit = min(max(top_teams * 200, max(5000, n * 50)), 50000)
                    else:
                        finals_limit = max(top_teams * 5, 50)
                    for est, cov_m, weak_m, atk_m, pwr, blk, atk_cnt_sum, weak_cnt_sum, mega_c, scr, used in finals[:finals_limit]:
                        if require_screen_setter and not scr:
                            continue
                        if must_bases:
                            base_equiv = {base_names[i] for i in used}
                            if not must_bases.issubset(base_equiv):
                                continue
                        if used in seen_idxs:
                            continue
                        seen_idxs.add(used)
                        score = eval_score(cov_m, weak_m, pwr, blk, weak_cnt_sum, atk_m, atk_cnt_sum)
                        records.append(dict(
                            idxs=tuple(used),
                            cov_count=int(cov_m.bit_count()),
                            weak_count=int(weak_m.bit_count()),
                            power_sum=float(atk_sum_arr[list(used)].sum()),
                            bulk_sum=int(tot_b_arr[list(used)].sum()),
                            team_score=float(score),
                        ))
    else:
        for comb in itertools.combinations(range(n_cand), team_size_int):
            # Ensure unique Pokémon within the team (by name)
            if len({names_lower[i] for i in comb}) < team_size_int:
                continue
            # Mega constraint
            if max_megas_per_team >= 0:
                if sum(int(is_mega_arr[i]) for i in comb) > max_megas_per_team:
                    continue
            base_equiv = {base_names[i] for i in comb}
            if len(base_equiv) < team_size_int:
                continue
            if must_bases and not must_bases.issubset(base_equiv):
                continue
            if require_screen_setter:
                if not any(screen_setter_arr[i] for i in comb):
                    continue
            def member_counters_target_idx(idx: int, target: dict) -> bool:
                if not (cover_types_list[idx] & target['weak']):
                    return False
                if target['prefers_physical']:
                    mem_def = float(def_arr[idx])
                    if not (mem_def == mem_def and mem_def >= def_threshold):
                        return False
                else:
                    mem_spd = float(spd_arr[idx])
                    if not (mem_spd == mem_spd and mem_spd >= spd_threshold):
                        return False
                m_type = types_arr[idx]
                weak_set, resist_set, immune_set = _def_prof_cached(m_type)
                stab = target['stab']
                if any(t in weak_set for t in stab):
                    return False
                if not (stab & (resist_set | immune_set)):
                    return False
                return True
            if counter_targets:
                ok_for_all = True
                for targ in counter_targets:
                    if not any(member_counters_target_idx(i, targ) for i in comb):
                        ok_for_all = False
                        break
                if not ok_for_all:
                    continue
            # Bitmask unions and counts
            cov_union = 0
            weak_union = 0
            atk_union = 0
            total_atk_types = 0
            total_weak_counts = 0
            for i in comb:
                cov_union |= cover_mask[i]
                weak_union |= weak_mask[i]
                atk_union |= atk_mask[i]
                total_atk_types += int(atk_cnt_arr[i])
                total_weak_counts += int(weak_cnt_arr[i])
            cov_count = int(cov_union.bit_count())
            weak_count = int(weak_union.bit_count())
            # Approximate weakness overlap penalty
            overlap_penalty = float(max(0, total_weak_counts - weak_count))
            redundancy_pen = 0.0
            if prefer_non_overlap:
                if total_atk_types > 0:
                    redundancy = 1.0 - (atk_union.bit_count() / float(total_atk_types))
                    redundancy_pen = 0.3 * float(redundancy)
            team_power = float(pnorm[list(comb)].sum())
            team_bulk = float(bnorm[list(comb)].sum())
            score = (
                coverage_weight * cov_count
                + power_weight * team_power
                + bulk_weight * team_bulk
                - weakness_weight * weak_count
                - redundancy_pen
                - weakness_overlap_weight * overlap_penalty
            )
            records.append(
                dict(
                    idxs=comb,
                    cov_count=cov_count,
                    weak_count=weak_count,
                    power_sum=float(atk_sum_arr[list(comb)].sum()),
                    bulk_sum=int(tot_b_arr[list(comb)].sum()),
                    team_score=float(score),
                )
            )

    df = pd.DataFrame.from_records(records)
    if df.empty:
        return df
    df.sort_values('team_score', ascending=False, inplace=True)

    # Helper to enrich the small final selection with display fields only
    def _enrich_df(df_part: pd.DataFrame) -> pd.DataFrame:
        # Ensure we have team/types/tiers/moves built from indices if not present;
        # also coerce/repair any malformed (NaN) entries that may have slipped in.
        need_copy = False
        cols_needed = ('team', 'types', 'tiers', 'moves')
        if any(c not in df_part.columns for c in cols_needed):
            need_copy = True
            df_part = df_part.copy()
            if 'team' not in df_part.columns:
                df_part['team'] = df_part['idxs'].apply(lambda idxs: tuple(names[i] for i in idxs))
            if 'types' not in df_part.columns:
                df_part['types'] = df_part['idxs'].apply(lambda idxs: tuple(types_arr[i] for i in idxs))
            if 'tiers' not in df_part.columns:
                df_part['tiers'] = df_part['idxs'].apply(lambda idxs: tuple(tiers_arr[i] for i in idxs))
            if 'moves' not in df_part.columns:
                df_part['moves'] = df_part['idxs'].apply(lambda idxs: tuple(moves4_arr[i] for i in idxs))
        # Coerce existing columns to proper tuple types and repair NaNs using idxs
        # This is safe because the selection here is small (top-K rows).
        # Repair 'team'
        if 'team' in df_part.columns:
            if not need_copy:
                df_part = df_part.copy()
                need_copy = True
            def _fix_team(row):
                t = row.get('team')
                if isinstance(t, (list, tuple)):
                    return tuple(t)
                # If not iterable or NaN, rebuild from idxs
                idxs = row.get('idxs')
                if isinstance(idxs, (list, tuple)):
                    return tuple(names[i] for i in idxs)
                return tuple()
            df_part['team'] = df_part.apply(_fix_team, axis=1)
        # Repair 'types'
        if 'types' in df_part.columns:
            def _fix_types(row):
                t = row.get('types')
                if isinstance(t, (list, tuple)):
                    return tuple(t)
                idxs = row.get('idxs')
                if isinstance(idxs, (list, tuple)):
                    return tuple(types_arr[i] for i in idxs)
                return tuple()
            df_part['types'] = df_part.apply(_fix_types, axis=1)
        # Repair 'tiers'
        if 'tiers' in df_part.columns:
            def _fix_tiers(row):
                t = row.get('tiers')
                if isinstance(t, (list, tuple)):
                    return tuple(t)
                idxs = row.get('idxs')
                if isinstance(idxs, (list, tuple)):
                    return tuple(tiers_arr[i] for i in idxs)
                return tuple()
            df_part['tiers'] = df_part.apply(_fix_tiers, axis=1)
        # Repair 'moves'
        if 'moves' in df_part.columns:
            def _fix_moves(row):
                m = row.get('moves')
                if isinstance(m, (list, tuple)):
                    return tuple(m)
                idxs = row.get('idxs')
                if isinstance(idxs, (list, tuple)):
                    return tuple(moves4_arr[i] for i in idxs)
                return tuple()
            df_part['moves'] = df_part.apply(_fix_moves, axis=1)
        # Reconstruct cov/weak sets if absent (cost only on small selection)
        if 'cov' not in df_part.columns:
            if not need_copy:
                df_part = df_part.copy()
                need_copy = True
            df_part['cov'] = df_part['idxs'].apply(lambda idxs: frozenset(set().union(*(cover_types_list[i] for i in idxs))))
        if 'weak' not in df_part.columns:
            if not need_copy:
                df_part = df_part.copy()
                need_copy = True
            df_part['weak'] = df_part['idxs'].apply(lambda idxs: frozenset(set().union(*(weak_types_list[i] for i in idxs))))
        if 'moves_detailed' not in df_part.columns:
            if not need_copy:
                df_part = df_part.copy()
            df_part['moves_detailed'] = df_part['moves'].apply(lambda tup: tuple(_fmt_cached(mv) for mv in tup))
        # Convert cov/weak sets into sorted, capitalized strings for display
        if 'cov_sorted' not in df_part.columns and 'cov' in df_part.columns:
            df_part['cov_sorted'] = df_part['cov'].apply(lambda s: ' '.join(sorted(t.capitalize() for t in s)))
        if 'weak_sorted' not in df_part.columns and 'weak' in df_part.columns:
            df_part['weak_sorted'] = df_part['weak'].apply(lambda s: ' '.join(sorted(t.capitalize() for t in s)))
        return df_part

    # When multiple teams are requested, optionally ensure no Pokémon (by base-equivalence) appears in more than one team
    if unique_across_teams and top_teams and top_teams > 1:
        selected_rows: list[tp.Hashable] = []
        used_bases: set[str] = set()
        used_idxs_sets: set[tp.Tuple[int, ...]] = set()
        for idx, row in df.iterrows():
            # Derive team names and idxs
            if 'team' in df.columns:
                team = row['team']
            else:
                idxs = row['idxs']
                team = tuple(names[i] for i in idxs)
            idxs = row['idxs'] if 'idxs' in df.columns else tuple(names.index(n) for n in team)
            bases = {_base_name(str(n)) for n in team}
            # Exempt must-include base names from cross-team uniqueness
            if must_bases:
                bases_for_uniqueness = bases - must_bases
            else:
                bases_for_uniqueness = bases
            # If any base already used in previous teams, skip
            if bases_for_uniqueness & used_bases:
                continue
            if tuple(sorted(idxs)) in used_idxs_sets:
                continue
            selected_rows.append(idx)
            used_idxs_sets.add(tuple(sorted(idxs)))
            used_bases |= bases_for_uniqueness
            if len(selected_rows) >= top_teams:
                break
        # If we couldn't gather enough teams, run a quick supplemental beam search
        # that forbids already-used bases to fill the remainder.
        remaining = top_teams - len(selected_rows)
        if remaining > 0:
            # Helper to pick one best disjoint team via a constrained beam
            def _beam_best_excluding(blocked_bases: set[str]) -> tp.Optional[dict]:
                import heapq
                B = 200
                # Allowed indices (exclude blocked bases)
                allow = [i for i in range(n_cand) if base_names[i] not in blocked_bases]
                if len(allow) < team_size_int:
                    return None
                # Beam state: (neg_est, cov, weak, atk, pwr, blk, atk_cnt, weak_cnt, mega_c, scr, used_tuple)
                beam_local = []
                for i in allow:
                    if max_megas_per_team >= 0 and int(is_mega_arr[i]) > max_megas_per_team:
                        continue
                    ne = -eval_score(cover_mask[i], weak_mask[i], float(pnorm[i]), float(bnorm[i]), int(weak_cnt_arr[i]), atk_mask[i], int(atk_cnt_arr[i]))
                    heapq.heappush(beam_local, (ne, cover_mask[i], weak_mask[i], atk_mask[i], float(pnorm[i]), float(bnorm[i]), int(atk_cnt_arr[i]), int(weak_cnt_arr[i]), int(is_mega_arr[i]), bool(screen_setter_arr[i]), (i,)))
                    if len(beam_local) > B:
                        heapq.heappop(beam_local)
                for size in range(2, team_size_int + 1):
                    next_beam = []
                    while beam_local:
                        ne, cov_m, weak_m, atk_m, pwr, blk, atk_cnt_sum, weak_cnt_sum, mega_c, scr, used = heapq.heappop(beam_local)
                        used_set = set(used)
                        used_bases_local = {base_names[x] for x in used}
                        for idx in allow:
                            if idx in used_set:
                                continue
                            # Enforce base/name uniqueness within team
                            if base_names[idx] in used_bases_local or names_lower[idx] in {names_lower[x] for x in used_set}:
                                continue
                            mmega = mega_c + int(is_mega_arr[idx])
                            if max_megas_per_team >= 0 and mmega > max_megas_per_team:
                                continue
                            cov2 = cov_m | cover_mask[idx]
                            weak2 = weak_m | weak_mask[idx]
                            atk2 = atk_m | atk_mask[idx]
                            pwr2 = pwr + float(pnorm[idx])
                            blk2 = blk + float(bnorm[idx])
                            atk_cnt2 = atk_cnt_sum + int(atk_cnt_arr[idx])
                            weak_cnt2 = weak_cnt_sum + int(weak_cnt_arr[idx])
                            scr2 = scr or bool(screen_setter_arr[idx])
                            est2 = eval_score(cov2, weak2, pwr2, blk2, weak_cnt2, atk2, atk_cnt2)
                            heapq.heappush(next_beam, (-est2, cov2, weak2, atk2, pwr2, blk2, atk_cnt2, weak_cnt2, mmega, scr2, used + (idx,)))
                            if len(next_beam) > B:
                                heapq.heappop(next_beam)
                    beam_local = next_beam
                # Choose best final satisfying optional constraints
                finals = sorted([(-ne, cov_m, weak_m, atk_m, pwr, blk, atk_cnt_sum, weak_cnt_sum, mega_c, scr, used) for (ne, cov_m, weak_m, atk_m, pwr, blk, atk_cnt_sum, weak_cnt_sum, mega_c, scr, used) in beam_local], reverse=True)
                for est, cov_m, weak_m, atk_m, pwr, blk, atk_cnt_sum, weak_cnt_sum, mega_c, scr, used in finals:
                    if require_screen_setter and not scr:
                        continue
                    if counter_targets:
                        # Ensure each target has a counter in the team
                        mask = 0
                        for u in used:
                            mask |= can_counter_mask[u]
                        if mask != ((1 << len(counter_targets)) - 1):
                            continue
                    if must_bases:
                        base_equiv = {base_names[i] for i in used}
                        if not must_bases.issubset(base_equiv):
                            continue
                    idxs = tuple(sorted(used))
                    cov_count = int(cov_m.bit_count())
                    weak_count = int(weak_m.bit_count())
                    power_sum = float(sum(atk_sum_arr[list(idxs)]))
                    bulk_sum = int(sum(tot_b_arr[list(idxs)]))
                    score = eval_score(cov_m, weak_m, pwr, blk, weak_cnt_sum, atk_m, atk_cnt_sum)
                    return dict(idxs=idxs, cov_count=cov_count, weak_count=weak_count, power_sum=power_sum, bulk_sum=bulk_sum, team_score=float(score))
                return None

            # Try to fill remaining slots greedily
            while remaining > 0:
                rec = _beam_best_excluding(used_bases)
                if rec is None:
                    break
                # Convert rec to a temporary one-row DataFrame for enrichment
                tmp_df = pd.DataFrame([rec])
                tmp_df = _enrich_df(tmp_df)
                # Compute bases for uniqueness and append to selection
                team = tmp_df.iloc[0]['team']
                bases = {_base_name(str(n)) for n in team}
                bases_for_uniqueness = bases - must_bases if must_bases else bases
                if bases_for_uniqueness & used_bases:
                    # Shouldn’t happen, but guard anyway
                    break
                used_bases |= bases_for_uniqueness
                # Append to df and to selected_rows via concatenation
                df = pd.concat([df, tmp_df], ignore_index=True)
                selected_rows.append(df.index[-1])
                remaining -= 1
        if selected_rows:
            return _enrich_df(df.loc[selected_rows])
        # Fallback if we somehow didn't select any (shouldn't happen)
        return _enrich_df(df.head(top_teams))
    else:
        return _enrich_df(df.head(top_teams))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Suggest a Pokémon squad for Legends: Z-A battle royale.')
    p.add_argument('--pokes', default='src/data/pokes-all-za.json', help='Path to pokes-all-za.json')
    p.add_argument('--moves', default='src/data/moves-za.json', help='Path to moves-za.json')
    p.add_argument('--typs', default='src/data/typs.json', help='Path to typs.json')
    p.add_argument('--k', type=int, default=60, help='Candidate pool size (top K individuals)')
    p.add_argument('--teams', type=int, default=5, help='How many top team suggestions to show')
    p.add_argument('--team-size', type=int, default=3, help='Number of Pokémon per team (default: 3)')
    p.add_argument('--no-legends', action='store_true', help='Exclude Legendary/Mythical Pokémon')
    p.add_argument('--no-mega', action='store_true', help='Exclude Mega forms (e.g., -mega, -mega-x, -mega-y)')
    p.add_argument(
        '--max-megas', type=int, default=1, help='Maximum number of Mega forms allowed per team (default: 1; use 0 to forbid, -1 for unlimited)'
    )
    p.add_argument('--block', action='append', help='Pokémon name to block from selection (repeatable). Also see BLOCKED_POKEMON in code.')
    p.add_argument(
        '--ban-type', action='append',
        help='Type to exclude from candidates (repeatable). Example: --ban-type normal --ban-type bug_steel. Matches exact combos or any member type.'
    )
    p.add_argument(
        '--must', action='append', help='Pokémon name that MUST be included in every team (repeatable). Ignored if not present among candidates.'
    )
    p.add_argument('--format', choices=['json', 'table', 'csv'], default='table', help='Output format (default: table)')
    # Team composition options
    p.add_argument(
        '--require-screens', action='store_true',
        help='Require that every team includes at least one screen-setter (knows both Light Screen and Reflect)'
    )
    p.add_argument('--no-unique-across-teams', action='store_true', help='Allow reusing the same Pokémon across multiple teams (default is no reuse)')
    # Countering options
    p.add_argument(
        '--counter', action='append', help='Pokémon name to counter (repeatable). Team must include at least one member that counters each target.'
    )
    p.add_argument(
        '--counter-def-pct', type=float, default=0.6,
        help='Defense percentile threshold [0..1] a counter must meet for the appropriate defense stat (default: 0.6 = 60th percentile)'
    )
    return p.parse_args()


if __name__ == '__main__':
    args = _parse_args()

    # Merge CLI lists (case-insensitive; keep original strings for display not needed here)
    cli_block = set(x.strip() for x in (args.block or []) if isinstance(x, str))
    # Support comma-separated entries inside a single argument for convenience
    ban_raw = []
    if getattr(args, 'ban_type', None):
        for x in args.ban_type:
            if isinstance(x, str):
                ban_raw.extend([p.strip() for p in x.split(',') if p.strip()])
    cli_ban_types = set(ban_raw)
    cli_must = set(x.strip() for x in (args.must or []) if isinstance(x, str))
    blocked_set = BLOCKED_POKEMON | cli_block
    must_set = MUST_INCLUDE | cli_must
    out = build_squads(
        pokes_path=args.pokes,
        moves_path=args.moves,
        typs_path=args.typs,
        k_candidates=args.k,
        top_teams=args.teams,
        team_size=args.team_size,
        allow_legends=not args.no_legends,
        allow_megas=not args.no_mega,
        max_megas_per_team=args.max_megas,
        blocked_pokemon=blocked_set,
        banned_types=cli_ban_types if cli_ban_types else None,
        must_include=must_set,
        counters=set(args.counter) if args.counter else None,
        counter_def_pct=float(args.counter_def_pct),
        require_screen_setter=bool(args.require_screens),
        unique_across_teams=not bool(args.no_unique_across_teams),
    )
    if args.format == 'csv':
        print(out.to_csv(index=False))
    elif args.format == 'json':
        # Emit array of team objects as JSON (default output)

        print(json.dumps(out.to_dict(orient='records'), indent=2))
    else:
        show = out.copy()
        # If weak_sorted is missing but weak exists, build it for display
        if not show.empty and 'weak_sorted' not in show.columns and 'weak' in show.columns:
            show['weak_sorted'] = show['weak'].apply(lambda s: ' '.join(sorted(t.capitalize() for t in (s or []))))

        # Pretty expand tuples with safe joiners
        def _join_names(t):
            if isinstance(t, (list, tuple)):
                return ', '.join(str(n).capitalize() for n in t)
            return ''

        def _join_types(t):
            if isinstance(t, (list, tuple)):
                return ', '.join(str(x) for x in t)
            return ''

        def _join_moves(m):
            if isinstance(m, (list, tuple)):
                return ' | '.join(str(x) for x in m)
            return ''

        show['Team'] = show['team'].apply(_join_names) if 'team' in show.columns else ''
        show['Types'] = show['types'].apply(_join_types) if 'types' in show.columns else ''
        # Prefer detailed movesets (with type/class); fall back to raw
        # if 'moves_detailed' in show.columns:
        #     show['Moves'] = show['moves_detailed'].apply(lambda m: ' | '.join(m))
        # else:
        #     show['Moves'] = show['moves'].apply(lambda m: ' | '.join(m))
        show['Moves'] = show['moves'].apply(_join_moves) if 'moves' in show.columns else ''

        # Build a two-line representation per team: first the normal row (Moves blank),
        # then a second row that prints just the Moves string.
        cols = ['Team', 'Types', 'cov_count', 'weak_count', 'weak_sorted', 'power_sum', 'bulk_sum', 'team_score']

        rows_out: list[dict] = []
        for _, r in show.iterrows():
            # First line: standard row without the moves text
            rows_out.append(
                {
                    'Team': r['Team'],
                    'Types': r['Types'],
                    'cov_count': r['cov_count'],
                    'weak_count': r['weak_count'],
                    # 'cov_sorted': r['cov_sorted'],
                    # 'weak_sorted': r['weak_sorted'],
                    'power_sum': r['power_sum'],
                    'bulk_sum': r['bulk_sum'],
                    'team_score': r['team_score'],
                }
            )
            # Second line: only moves
            rows_out.append(
                {
                    'Team': f'  -> {r["Moves"]}',
                    'Types': '',
                    'cov_count': '',
                    'weak_count': '',
                    # 'cov_sorted': '',
                    # 'weak_sorted': '',
                    'power_sum': '',
                    'bulk_sum': '',
                    'team_score': '',
                }
            )

        print(tabulate(rows_out, headers='keys', tablefmt='grid', showindex=False))
