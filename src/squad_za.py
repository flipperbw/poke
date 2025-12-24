import argparse
import itertools
import json
import typing as tp

import numpy as np
import pandas as pd
from tabulate import tabulate
from line_profiler import profile

# We reuse the scoring and move selection from score_za
from score_za import _load_type_offense, score_pokemon

# In-code defaults you can edit
BLOCKED_POKEMON: set[str] = set()
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
    return ', '.join(pretty)


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
    # Pre-convert to plain Python records to avoid expensive per-element pandas iloc in the hot loop
    # Accessing dicts is substantially faster than constructing Series repeatedly
    recs: list[dict] = candidates.to_dict('records')
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

    for comb in itertools.combinations(range(len(idx_list)), team_size_int):
        # Use pre-materialized records instead of pandas iloc to cut overhead
        members = [recs[x] for x in comb]

        # Ensure unique Pokémon within the team (by name)
        names_set = {str(m['name']) for m in members}
        if len(names_set) < team_size_int:
            continue

        # Enforce typing diversity: require all three to have distinct primary types
        primaries = {str(m['type']).split('_')[0] for m in members}
        if len(primaries) < team_size_int:
            continue

        # Enforce only one Mega per team and treat Mega forms as the same as base
        team_names = tuple(str(m['name']).lower() for m in members)
        mega_count = sum(_is_mega(n) for n in team_names)
        if max_megas_per_team >= 0 and mega_count > max_megas_per_team:
            continue
        base_equiv = {_base_name(n) for n in team_names}
        if len(base_equiv) < team_size_int:
            # Contains base and its mega (or two megas of same base) -> skip
            continue

        # Enforce must-include constraint: all required base names must be in this team
        if must_bases and not must_bases.issubset(base_equiv):
            continue

        # Optionally enforce a screen-setter: at least one member must know BOTH Light Screen and Reflect
        if require_screen_setter:
            def knows_both_screens(mon_name: str) -> bool:
                # Check both the exact form and its base form for moves; exclude tutor-learned moves
                def _has_moves(row_obj: dict) -> bool:
                    mv_list = row_obj.get('moves') if isinstance(row_obj, dict) else None
                    if not isinstance(mv_list, list):
                        return False
                    names = {m.get('name') for m in mv_list if isinstance(m, dict) and m.get('how') != 'tutor'}
                    return 'light-screen' in names and 'reflect' in names

                nm = str(mon_name).lower()
                base_nm = _base_name(nm)
                row_exact = pokes_map.get(nm)
                row_base = pokes_map.get(base_nm)
                return (_has_moves(row_exact) or _has_moves(row_base))

            if not any(knows_both_screens(m['name']) for m in members):
                continue

        # Enforce counter constraints: for each target, at least one member must counter it
        # Accept any mapping-like row (either pandas Series or plain dict from pre-materialized records)
        def member_counters_target(member_row: tp.Mapping[str, tp.Any], target: dict) -> bool:
            # Offensive: member's coverage hits a target weakness
            if not (member_row.get('cover_types', set()) & target['weak']):
                return False
            # Defensive: choose appropriate defense stat threshold
            if target['prefers_physical']:
                mem_def = float(member_row.get('defense', np.nan))
                if not (mem_def == mem_def and mem_def >= def_threshold):  # NaN check via mem_def == mem_def
                    return False
            else:
                mem_spd = float(member_row.get('special-defense', np.nan))
                if not (mem_spd == mem_spd and mem_spd >= spd_threshold):
                    return False
            # Resist STAB: resist at least one STAB and not weak to any STAB
            m_type = str(member_row.get('type'))
            weak_set, resist_set, immune_set = _defensive_profile(typs_json, m_type)
            stab = target['stab']
            if any(t in weak_set for t in stab):
                return False
            if not (stab & (resist_set | immune_set)):
                return False
            return True

        if counter_targets:
            ok_for_all = True
            for targ in counter_targets:
                if not any(member_counters_target(m, targ) for m in members):
                    ok_for_all = False
                    break
            if not ok_for_all:
                continue

        # Combined offensive coverage set
        cov = set().union(*(m['cover_types'] for m in members)) if members else set()
        cov_count = len(cov)

        # Combined weaknesses
        weak = set().union(*(m['weak_types'] for m in members)) if members else set()
        weak_count = len(weak)

        # Penalize overlapping weaknesses (e.g., two or more team members sharing the same weakness)
        # Build counts per weakness type
        all_weak_list = []
        for m in members:
            all_weak_list += list(m['weak_types'])
        if all_weak_list:
            vals, counts = np.unique(all_weak_list, return_counts=True)
            # sum of (cnt-1)^2 for cnt >= 2 to emphasize triple overlap
            overlap_penalty = float(np.sum([(int(c) - 1) ** 2 for c in counts if int(c) >= 2]))
        else:
            overlap_penalty = 0.0

        # Optional penalty for redundant attack types across members
        redundancy_pen = 0.0
        if prefer_non_overlap:
            atk_types_union = set().union(*(m['atk_types'] for m in members)) if members else set()
            total_atk_types = sum(len(m['atk_types']) for m in members)
            # fraction overlapped
            if total_atk_types > 0:
                redundancy = 1.0 - (len(atk_types_union) / total_atk_types)
                redundancy_pen = 0.3 * redundancy  # small penalty

        # Team power/bulk (sum of normalized)
        team_power = float(sum(m['power_norm'] for m in members))
        team_bulk = float(sum(m['bulk_norm'] for m in members))

        # Objective: maximize coverage + weighted power + bulk, penalize weaknesses and redundancy
        score = (
            coverage_weight * cov_count
            + power_weight * team_power
            + bulk_weight * team_bulk
            - weakness_weight * weak_count
            - redundancy_pen
            - weakness_overlap_weight * overlap_penalty
        )

        moves_tuple = tuple(m['moves4'] for m in members)
        moves_detailed = tuple(_format_moveset(mv, moves_map) for mv in moves_tuple)

        records.append(
            dict(
                team=tuple(m['name'] for m in members),
                types=tuple(m['type'] for m in members),
                tiers=tuple(m['tier'] for m in members),
                moves=moves_tuple,
                moves_detailed=moves_detailed,
                cov_count=cov_count,
                weak_count=weak_count,
                cov_sorted=' '.join(sorted(t.capitalize() for t in cov)),
                weak_sorted=' '.join(sorted(t.capitalize() for t in weak)),
                power_sum=float(sum(m['attack_sum'] for m in members)),
                bulk_sum=int(sum(int(m['tot_b']) for m in members)),
                team_score=float(score),
            )
        )

    df = pd.DataFrame.from_records(records)
    if df.empty:
        return df
    df.sort_values('team_score', ascending=False, inplace=True)

    # When multiple teams are requested, optionally ensure no Pokémon (by base-equivalence) appears in more than one team
    if unique_across_teams and top_teams and top_teams > 1:
        selected_rows: list[tp.Hashable] = []
        used_bases: set[str] = set()
        for idx, row in df.iterrows():
            team = row['team']  # tuple of names
            bases = {_base_name(str(n)) for n in team}
            # Exempt must-include base names from cross-team uniqueness
            if must_bases:
                bases_for_uniqueness = bases - must_bases
            else:
                bases_for_uniqueness = bases
            # If any base already used in previous teams, skip
            if bases_for_uniqueness & used_bases:
                continue
            selected_rows.append(idx)
            used_bases |= bases_for_uniqueness
            if len(selected_rows) >= top_teams:
                break
        if selected_rows:
            return df.loc[selected_rows]
        # Fallback if we somehow didn't select any (shouldn't happen)
        return df.head(top_teams)
    else:
        return df.head(top_teams)


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
        import json as _json

        print(_json.dumps(out.to_dict(orient='records'), indent=2))
    else:
        show = out.copy()
        # Pretty expand tuples
        show['Team'] = show['team'].apply(lambda t: ', '.join(n.capitalize() for n in t))
        show['Types'] = show['types'].apply(lambda t: ', '.join(x for x in t))
        # Prefer detailed movesets (with type/class); fall back to raw
        # if 'moves_detailed' in show.columns:
        #     show['Moves'] = show['moves_detailed'].apply(lambda m: ' | '.join(m))
        # else:
        #     show['Moves'] = show['moves'].apply(lambda m: ' | '.join(m))
        show['Moves'] = show['moves'].apply(lambda m: ' | '.join(m))

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
