import argparse
import typing as tp

import numpy as np
import pandas as pd
from tabulate import tabulate


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

    # Keep essential columns used later
    keep_cols = [
        'class', 'type', 'pp', 'target', 'mv_score', 'stat_changes', 'effect_short'
    ]
    return df[keep_cols]


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
) -> pd.DataFrame:
    # Load data
    pokes = pd.read_json(pokes_path, orient='index')
    moves = _load_moves(moves_path)

    # Precompute mapping move_name -> row for quick join
    mv = moves.copy()
    mv.index.name = 'move_name'

    # Explode Pokémon moves to rows and attach move metadata
    pk = pokes[['name', 'dex', 'type', 'atk_type', 'tot', 'tot_b', 'is_legendary', 'is_mythical', 'moves']].copy()
    # Ensure moves list
    pk['moves'] = pk['moves'].apply(lambda xs: xs if isinstance(xs, list) else [])
    # Filter out tutor moves (not available in ZA)
    pk['moves'] = pk['moves'].apply(lambda xs: [m for m in xs if isinstance(m, dict) and m.get('how') != 'tutor'])
    exploded = pk.explode('moves')
    # Extract move name from dicts
    exploded['move_name'] = exploded['moves'].apply(lambda m: m.get('name') if isinstance(m, dict) else None)
    exploded = exploded.drop(columns=['moves'])

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
    def choose_bias(row_atk_type: str) -> str:
        if bias_mode == 'atk':
            return 'physical'
        if bias_mode == 'spa':
            return 'special'
        if bias_mode == 'any':
            return 'any'
        return _attack_bias(row_atk_type)

    exploded['bias'] = exploded['atk_type'].apply(choose_bias)

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
    # Boosting move: status, targets user, and has positive stat_changes for atk or spa
    def is_boost_row(r: pd.Series) -> bool:
        if not allow_boost:
            return False
        if r.get('is_status') is not True:
            return False
        tgt = str(r.get('target', ''))
        if 'user' not in tgt:
            return False
        sc = r.get('stat_changes')
        try:
            # stat_changes is list of dicts: {'amt': int, 'type': 'attack'|'special-attack'|...}
            return any((d.get('amt', 0) or 0) > 0 and d.get('type') in ('attack', 'special-attack') for d in sc or [])
        except Exception:
            return False

    exploded['is_boost'] = exploded.apply(is_boost_row, axis=1)

    # For each Pokémon, select up to `moves_per` moves: prefer STAB attacks, add coverage of other types, optionally one boost.
    def select_moves(group: pd.DataFrame) -> pd.Series:
        g = group.copy()
        # Separate
        atk = g[g['is_status'] == False].copy()
        # Prefer bias-aligned first
        if prefer_stab:
            atk.sort_values(['is_stab', 'bias_ok', 'eff_score'], ascending=[False, False, False], inplace=True)
        else:
            atk.sort_values(['bias_ok', 'eff_score'], ascending=[False, False], inplace=True)

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
                boost_pick = pref.iloc[0]
            elif not boosts.empty:
                boost_pick = boosts.iloc[0]

        # 2) Pick STAB attacks
        stab_attacks = atk[atk['is_stab']]
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
        coverage_attacks = atk[~atk['is_stab']]
        cov_seen: set[str] = set()
        for _, row in coverage_attacks.iterrows():
            t = str(row.get('type_move'))
            if t in cov_seen:
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

        # Fill with best remaining attacks (excluding already chosen moves)
        needed = max(0, moves_per - len(chosen))
        if needed > 0:
            chosen_names = {c['move_name'] for c in chosen}
            rest = atk[~atk['move_name'].isin(chosen_names)]
            rest = rest.sort_values(['bias_ok', 'eff_score'], ascending=[False, False])
            for _, row in rest.head(needed).iterrows():
                chosen.append(row)

        # Truncate to moves_per
        chosen = chosen[:moves_per]

        # Compute attack sum score from selected attacking moves
        atk_sum = float(sum(c['eff_score'] for c in chosen if c.get('is_status') is not True))

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
                'stab_moves': ', '.join(str(c['move_name']) for c in chosen if c.get('is_status') is not True and c.get('is_stab') is True),
                'coverage_moves': ', '.join(str(c['move_name']) for c in chosen if c.get('is_status') is not True and c.get('is_stab') is False),
                'boost_moves': ', '.join(str(c['move_name']) for c in chosen if c.get('is_boost') is True),
                'attack_sum': atk_sum,
            }
        )

    best = exploded.groupby(level=0).apply(select_moves)

    # Merge back to Pokémon base
    out = pk.drop(columns=['moves']).join(best)

    # Tier and final score
    out['tier'] = out.apply(_tier, axis=1)
    # Composite: include Speed (tot) + sum of selected attacking move scores
    out['score'] = out['tot'] + out['attack_sum'].fillna(0)

    # Sort overall
    out = out.sort_values(['score', 'tot_b', 'best_move_score'], ascending=False)

    # Output selection
    cols = [
        'name', 'dex', 'type', 'tier', 'atk_type', 'tot', 'tot_b',
        'best_move', 'best_move_type', 'best_move_class', 'best_move_score',
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
    p.add_argument('--csv', help='Write results to CSV at this path')
    return p.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    df = score_pokemon(
        pokes_path=args.pokes,
        moves_path=args.moves,
        top_n=args.top,
        bias_mode=tp.cast(tp.Literal['auto', 'atk', 'spa', 'any'], args.bias),
        no_stab_bonus=args.no_stab_bonus,
        per_type=args.per_type,
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

            print(tabulate(show, headers='keys', tablefmt='github', showindex=False))
