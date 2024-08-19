import json

import pandas as pd

import pokebase as pb


def make_data():
    d = {}
    maxi = -1
    q = pb.APIResourceList('move')
    i = 0
    for m in q:
        if maxi != -1 and i >= maxi:
            break
        i += 1
        print(f'{i}/{q.count}', end='\r', flush=True)
        td = {}
        d[m['name']] = td
        move = pb.move(m['name'])

        td['accuracy'] = move.accuracy
        td['class'] = move.damage_class.name
        td['effect_chance'] = move.effect_chance
        td['effect_short'] = move.effect_entries[0].short_effect if move.effect_entries else ''
        td['effect_long'] = move.effect_entries[0].effect if move.effect_entries else ''

        td['learned_by'] = len(move.learned_by_pokemon)
        td['has_tm'] = len([x for x in move.machines if x.version_group.id in (25, 26, 27)]) > 0

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

    with open('src/data/moves.json', 'w') as f:
        json.dump(d, f, indent=2)

    return d


def main():
    df = pd.read_json('src/data/moves.json', orient='index')

    df['is_atk'] = df['class'] != 'status'

    atks = df[df['is_atk'] == True]
    atks = atks[(atks['learned_by'] > 0) | (atks['has_tm'] == True)]

    atks['dead_turn'] = atks['effect_short'].str.contains(r'turn to charge before attacking|next turn to recharge')
    atks['avg_hits'] = ((atks['min_hits'] + atks['max_hits']) / 2).fillna(1)

    atks['tot'] = (atks['power'] * atks['avg_hits'] * (atks['accuracy'] / 100)) / (atks['dead_turn'].astype(int) + 1)

    # hurts/kills self

    atks = atks.sort_values('tot', ascending=False)
    good = atks[['effect_short', 'learned_by', 'has_tm', 'category', 'pp', 'target', 'type', 'avg_hits', 'tot']]

    return good


if __name__ == '__main__':
    x = main()
