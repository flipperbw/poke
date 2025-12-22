import argparse
import itertools
import json
import typing as tp

import numpy as np
import pandas as pd
from tabulate import tabulate

# We reuse the scoring and move selection from score_za
from score_za import _load_type_offense, score_pokemon


def _load_moves_map(path: str) -> dict:
    """Map move name -> metadata dict (class, type, etc.)."""
    with open(path, 'r') as f:
        data = json.load(f)
    return data


def _load_typs(path: str) -> dict:
    with open(path, 'r') as f:
        return json.load(f)


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


def build_squads(
    pokes_path: str,
    moves_path: str,
    typs_path: str,
    k_candidates: int = 60,
    top_teams: int = 5,
    allow_legends: bool = True,
    allow_megas: bool = True,
    prefer_non_overlap: bool = True,
    coverage_weight: float = 1.0,
    power_weight: float = 0.8,
    bulk_weight: float = 0.6,
    weakness_weight: float = 0.6,
    weakness_overlap_weight: float = 0.8,
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

    # Load helpers
    moves_map = _load_moves_map(moves_path)
    typs_json = _load_typs(typs_path)
    type_offense = _load_type_offense(typs_path)

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
        return n.endswith('-mega') or n.endswith('-mega-x') or n.endswith('-mega-y')

    def _base_name(name: str) -> str:
        n = str(name).lower()
        # Strip any mega suffix but keep other hyphenated forms (e.g., mr-mime)
        for suf in ('-mega-x', '-mega-y', '-mega'):
            if n.endswith(suf):
                return n[: -len(suf)]
        return n

    # Evaluate all 3-combinations
    records: list[dict] = []
    idx_list = list(candidates.index)
    for i, j, k in itertools.combinations(range(len(idx_list)), 3):
        a = candidates.iloc[i]
        b = candidates.iloc[j]
        c = candidates.iloc[k]

        # Ensure unique Pokémon within the team (by name)
        names_set = {str(a['name']), str(b['name']), str(c['name'])}
        if len(names_set) < 3:
            continue

        # Enforce typing diversity: require all three to have distinct primary types
        prim_a = str(a['type']).split('_')[0]
        prim_b = str(b['type']).split('_')[0]
        prim_c = str(c['type']).split('_')[0]
        if len({prim_a, prim_b, prim_c}) < 3:
            continue

        # Enforce only one Mega per team and treat Mega forms as the same as base
        team_names = (str(a['name']).lower(), str(b['name']).lower(), str(c['name']).lower())
        mega_count = sum(_is_mega(n) for n in team_names)
        if mega_count > 1:
            continue
        base_equiv = {_base_name(n) for n in team_names}
        if len(base_equiv) < 3:
            # Contains base and its mega (or two megas of same base) -> skip
            continue

        # Combined offensive coverage set
        cov = set().union(a['cover_types'], b['cover_types'], c['cover_types'])
        cov_count = len(cov)

        # Combined weaknesses
        weak = set().union(a['weak_types'], b['weak_types'], c['weak_types'])
        weak_count = len(weak)

        # Penalize overlapping weaknesses (e.g., two or more team members sharing the same weakness)
        # Build counts per weakness type
        all_weak_list = list(a['weak_types']) + list(b['weak_types']) + list(c['weak_types'])
        if all_weak_list:
            vals, counts = np.unique(all_weak_list, return_counts=True)
            # sum of (cnt-1)^2 for cnt >= 2 to emphasize triple overlap
            overlap_penalty = float(np.sum([(int(c) - 1) ** 2 for c in counts if int(c) >= 2]))
        else:
            overlap_penalty = 0.0

        # Optional penalty for redundant attack types across members
        redundancy_pen = 0.0
        if prefer_non_overlap:
            atk_types_union = set().union(a['atk_types'], b['atk_types'], c['atk_types'])
            total_atk_types = len(a['atk_types']) + len(b['atk_types']) + len(c['atk_types'])
            # fraction overlapped
            if total_atk_types > 0:
                redundancy = 1.0 - (len(atk_types_union) / total_atk_types)
                redundancy_pen = 0.3 * redundancy  # small penalty

        # Team power/bulk (sum of normalized)
        team_power = float(a['power_norm'] + b['power_norm'] + c['power_norm'])
        team_bulk = float(a['bulk_norm'] + b['bulk_norm'] + c['bulk_norm'])

        # Objective: maximize coverage + weighted power + bulk, penalize weaknesses and redundancy
        score = (
            coverage_weight * cov_count
            + power_weight * team_power
            + bulk_weight * team_bulk
            - weakness_weight * weak_count
            - redundancy_pen
            - weakness_overlap_weight * overlap_penalty
        )

        moves_tuple = (a['moves4'], b['moves4'], c['moves4'])
        moves_detailed = tuple(_format_moveset(m, moves_map) for m in moves_tuple)

        records.append(
            dict(
                team=(a['name'], b['name'], c['name']),
                types=(a['type'], b['type'], c['type']),
                tiers=(a['tier'], b['tier'], c['tier']),
                moves=moves_tuple,
                moves_detailed=moves_detailed,
                cov_count=cov_count,
                weak_count=weak_count,
                cov_sorted=' '.join(sorted(t.capitalize() for t in cov)),
                weak_sorted=' '.join(sorted(t.capitalize() for t in weak)),
                power_sum=float(a['attack_sum'] + b['attack_sum'] + c['attack_sum']),
                bulk_sum=int(a['tot_b']) + int(b['tot_b']) + int(c['tot_b']),
                team_score=float(score),
            )
        )

    df = pd.DataFrame.from_records(records)
    if df.empty:
        return df
    df.sort_values('team_score', ascending=False, inplace=True)

    # When multiple teams are requested, ensure no Pokémon (by base-equivalence) appears in more than one team
    if top_teams and top_teams > 1:
        selected_rows: list[tp.Hashable] = []
        used_bases: set[str] = set()
        for idx, row in df.iterrows():
            team = row['team']  # tuple of names
            bases = {_base_name(str(n)) for n in team}
            # If any base already used in previous teams, skip
            if bases & used_bases:
                continue
            selected_rows.append(idx)
            used_bases |= bases
            if len(selected_rows) >= top_teams:
                break
        if selected_rows:
            return df.loc[selected_rows]
        # Fallback if we somehow didn't select any (shouldn't happen)
        return df.head(top_teams)
    else:
        return df.head(top_teams)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Suggest a 3-Pokémon squad for Legends: Z-A battle royale.')
    p.add_argument('--pokes', default='src/data/pokes-all-za.json', help='Path to pokes-all-za.json')
    p.add_argument('--moves', default='src/data/moves-za.json', help='Path to moves-za.json')
    p.add_argument('--typs', default='src/data/typs.json', help='Path to typs.json')
    p.add_argument('--k', type=int, default=60, help='Candidate pool size (top K individuals)')
    p.add_argument('--teams', type=int, default=5, help='How many top team suggestions to show')
    p.add_argument('--no-legends', action='store_true', help='Exclude Legendary/Mythical Pokémon')
    p.add_argument('--no-mega', action='store_true', help='Exclude Mega forms (e.g., -mega, -mega-x, -mega-y)')
    p.add_argument('--format', choices=['json', 'table', 'csv'], default='json', help='Output format (default: json)')
    return p.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    out = build_squads(
        pokes_path=args.pokes,
        moves_path=args.moves,
        typs_path=args.typs,
        k_candidates=args.k,
        top_teams=args.teams,
        allow_legends=not args.no_legends,
        allow_megas=not args.no_mega,
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
        # show['Tiers'] = show['tiers'].apply(lambda t: ', '.join(x for x in t))
        # Prefer detailed movesets (with type/class); fall back to raw
        if 'moves_detailed' in show.columns:
            show['Moves'] = show['moves_detailed'].apply(lambda m: ' | '.join(m))
        else:
            show['Moves'] = show['moves'].apply(lambda m: ' | '.join(m))
        cols = ['Team', 'Types', 'Moves', 'cov_count', 'weak_count', 'cov_sorted', 'weak_sorted', 'power_sum', 'bulk_sum', 'team_score']
        print(tabulate(show[cols], headers='keys', tablefmt='github', showindex=False))
