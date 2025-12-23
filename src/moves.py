import argparse
import json
import logging

import pandas as pd

import pokebase as pb
from pokebase.cache import set_cache
from tqdm import tqdm

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger('requests.packages.urllib3')
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True


def make_data(max_items: int = -1, tm_vg_names: list[str] | None = None, ignore_acc: bool = True) -> dict:
    d: dict = {}
    maxi = max_items
    # Force fresh lookup to avoid stale, truncated lists in cache
    q = pb.APIResourceList('move', force_lookup=True)
    # Resolve version-group names to IDs if provided
    tm_vg_ids: set[int] | None = None
    if tm_vg_names:
        tm_vg_ids = set(pb.version_group(int(name)).id for name in tm_vg_names)
    i = 0
    for m in tqdm(q, total=q.count, desc='Moves', unit='move'):
        if maxi != -1 and i >= maxi:
            break
        i += 1
        td = {}
        d[m['name']] = td
        move = pb.move(m['name'])

        td['accuracy'] = 100 if ignore_acc else move.accuracy
        td['class'] = move.damage_class.name
        td['effect_chance'] = move.effect_chance
        td['effect_short'] = move.effect_entries[0].short_effect if move.effect_entries else ''
        td['effect_long'] = move.effect_entries[0].effect if move.effect_entries else ''

        td['learned_by'] = len(move.learned_by_pokemon)
        if tm_vg_ids is not None:
            td['has_tm'] = any(x.version_group.id in tm_vg_ids for x in move.machines)
        else:
            # fallback: consider any machine in any version-group as TM availability
            td['has_tm'] = len(move.machines) > 0

        # if not move.meta:
        #     print(f'\nmissing meta {i}')

        td['category'] = move.meta.category.name if move.meta else None
        td['ailment'] = move.meta.ailment.name if move.meta else None
        td['crit_rate'] = move.meta.crit_rate if move.meta else None
        td['drain'] = move.meta.drain if move.meta else None
        td['flinch_chance'] = move.meta.flinch_chance if move.meta else None
        td['healing'] = move.meta.healing if move.meta else None
        td['max_hits'] = move.meta.max_hits if move.meta else None
        td['max_turns'] = move.meta.max_turns if move.meta else None
        td['min_hits'] = move.meta.min_hits if move.meta else None
        td['min_turns'] = move.meta.min_turns if move.meta else None
        td['stat_chance'] = move.meta.stat_chance if move.meta else None

        td['power'] = move.power
        td['pp'] = move.pp
        td['priority'] = move.priority
        td['stat_changes'] = [{'amt': s.change, 'type': s.stat.name} for s in move.stat_changes]
        td['target'] = move.target.name
        td['type'] = move.type.name

    with open('src/data/moves-za.json', 'w') as f:
        json.dump(d, f, indent=2)

    return d


def analyze(no_tm_filter: bool = False):
    df = pd.read_json('src/data/moves-za.json', orient='index')

    df['is_atk'] = df['class'] != 'status'

    atks = df[df['is_atk'] == True]
    if no_tm_filter:
        atks = atks[(atks['learned_by'] > 0)]
    else:
        atks = atks[(atks['learned_by'] > 0) | (atks['has_tm'] == True)]

    atks['dead_turn'] = atks['effect_short'].str.contains(r'turn to charge before attacking|next turn to recharge')
    atks['avg_hits'] = ((atks['min_hits'] + atks['max_hits']) / 2).fillna(1)

    atks['tot'] = (atks['power'] * atks['avg_hits'] * (atks['accuracy'] / 100)) / (atks['dead_turn'].astype(int) + 1)

    # hurts/kills self

    atks = atks.sort_values('tot', ascending=False)
    good = atks[['effect_short', 'learned_by', 'has_tm', 'category', 'pp', 'target', 'type', 'avg_hits', 'tot']]

    return good


def good_raise():
    q = pd.read_json('src/data/moves-za.json', ).transpose()
    q = q[q['learned_by'] > 0]

    q['inc_atk'] = q['stat_changes'].apply(lambda x: next((y for y in x if y['type'] == 'attack'), {}).get('amt'))
    q['inc_spa'] = q['stat_changes'].apply(lambda x: next((y for y in x if y['type'] == 'special-attack'), {}).get('amt'))

    q[~q['inc_atk'].isna() & q['target'].str.contains('user')].sort_values('inc_atk', ascending=False)
    q[~q['inc_spa'].isna() & q['target'].str.contains('user')].sort_values('inc_spa', ascending=False)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--cache-dir', help='Directory for pokebase cache')
    p.add_argument('--generate', action='store_true', help='Fetch moves from API and write src/data/moves-za.json')
    p.add_argument('--max', type=int, default=-1, help='Max number of moves to fetch when generating (-1 = all)')
    p.add_argument('--tm-vg', action='append', help='Version-group name to consider for TM availability (repeatable). If omitted, any machine counts.')
    p.add_argument('--no-tm-filter', action='store_true', help='When analyzing, ignore TM availability and rely on learned_by only')
    p.add_argument('--no-ignore-acc', action='store_true', help='Do not ignore accuracy when computing move power')
    return p.parse_args()


if __name__ == '__main__':
    args = _parse_args()
    if args.cache_dir:
        set_cache(args.cache_dir)
    if args.generate:
        make_data(max_items=args.max, tm_vg_names=args.tm_vg, ignore_acc=not args.no_ignore_acc)
    x = analyze(no_tm_filter=args.no_tm_filter)
    print(x)
