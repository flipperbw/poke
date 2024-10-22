import numpy as np
import pandas as pd


def main() -> None:
    damage = pd.read_json('src/data/typs.json').transpose()
    pokes = pd.read_json('src/data/pokes.json').transpose()
    cnts = pd.read_json('src/data/typ_cnts.json').transpose()

    pokes.sort_values('stats', key=lambda x: x.str['special-attack'])

    # try to make sure defense has every type covered, more points for lower

    merged = damage.merge(cnts, left_index=True, right_index=True)
    merged = merged[merged['Cnt'] > 0]

    types_uncovered = merged.index.tolist()

    merged['from_typs'] = merged['from'].str['strong'].str['typs']  # type: ignore
    merged['from_cnt'] = merged['from'].str['strong'].str['cnt'] - merged['from'].str['weak'].str['cnt']  # type: ignore

    # noinspection PyTypeChecker
    merged['to_typs'] = (
        merged['to_a'].str['data'].str['strong'].str['typs'].apply(list) + merged['to_b'].str['data'].str['strong'].str['typs'].fillna('').apply(
        list
    )).map(lambda x: list(set([y for y in x if y in types_uncovered])))
    merged['to_cnt'] = merged['to_typs'].apply(len)

    merged['to_sum'] = merged['to_typs'].map(lambda x: np.sum(cnts.loc[x]['Cnt']))

    # merged['comb'] = merged['from_cnt'] + np.ceil(merged['to_cnt'] / 18)
    merged['comb_2'] = merged['from_cnt'] + np.round(merged['to_sum'] / 45)

    merged['list_stats'] = merged['List'].map(lambda x: [pokes.loc[y].stats['tot'] for y in x])

    strongest = merged[merged['list_stats'].map(lambda x: any(y > 500 for y in x))]

    best = strongest.sort_values('comb_2', ascending=False)[['comb_2', 'to_sum', 'from_cnt', 'from_typs', 'to_typs', 'List', 'list_stats']]

    # gliscor?

    remaining = set(types_uncovered)
    filtered = best.copy()

    # filtered = best[best['to_typs'].map(lambda x: any(y in remaining for y in x))].drop(['from_typs', 'to_typs'], axis=1)

    best.drop(['from_typs', 'to_typs'], axis=1)

    choice = best.loc['fairy_steel']  # tink
    remaining = remaining - set(choice.to_typs)
    filtered['rem'] = filtered['to_typs'].map(lambda x: len(remaining.intersection(set(x))))
    display = filtered.drop(['from_typs', 'to_typs'], axis=1).sort_values(['rem', 'comb_2'], ascending=False)

    choice = best.loc['dark_rock']  # tyranitar
    remaining = remaining - set(choice.to_typs)
    filtered['rem'] = filtered['to_typs'].map(lambda x: len(remaining.intersection(set(x))))
    display = filtered.drop(['from_typs', 'to_typs'], axis=1).sort_values(['rem', 'comb_2'], ascending=False)

    choice = best.loc['dragon_ground']  # garchomp | false swipe
    remaining = remaining - set(choice.to_typs)
    filtered['rem'] = filtered['to_typs'].map(lambda x: len(remaining.intersection(set(x))))
    display = filtered.drop(['from_typs', 'to_typs'], axis=1).sort_values(['rem', 'comb_2'], ascending=False)

    choice = best.loc['fighting_ghost']  # annihilape
    remaining = remaining - set(choice.to_typs)
    filtered['rem'] = filtered['to_typs'].map(lambda x: len(remaining.intersection(set(x))))
    display = filtered.drop(['from_typs', 'to_typs'], axis=1).sort_values(['rem', 'comb_2'], ascending=False)

    choice = best.loc['bug_fire']  # volcarona
    remaining = remaining - set(choice.to_typs)
    filtered['rem'] = filtered['to_typs'].map(lambda x: len(remaining.intersection(set(x))))
    display = filtered.drop(['from_typs', 'to_typs'], axis=1).sort_values(['rem', 'comb_2'], ascending=False)

    x = display.explode(['List', 'list_stats']).sort_values(['rem', 'list_stats'], ascending=False)
    x[x['List'].str.contains('31')]

    # need grass, arboliva

    # --

    choice = best.loc['electric_steel']  # magnezone
    remaining = remaining - set(choice.to_typs)
    filtered['rem'] = filtered['to_typs'].map(lambda x: len(remaining.intersection(set(x))))
    display = filtered.drop(['from_typs', 'to_typs'], axis=1).sort_values(['rem', 'comb_2'], ascending=False)

    choice = best.loc['dragon_ground']  # garchomp
    remaining = remaining - set(choice.to_typs)
    filtered['rem'] = filtered['to_typs'].map(lambda x: len(remaining.intersection(set(x))))
    display = filtered.drop(['from_typs', 'to_typs'], axis=1).sort_values(['rem', 'comb_2'], ascending=False)

    choice = best.loc['flying_water']  # gyarados
    remaining = remaining - set(choice.to_typs)
    filtered['rem'] = filtered['to_typs'].map(lambda x: len(remaining.intersection(set(x))))
    display = filtered.drop(['from_typs', 'to_typs'], axis=1).sort_values(['rem', 'comb_2'], ascending=False)

    choice = best.loc['bug_fire']  # volcarona
    remaining = remaining - set(choice.to_typs)
    filtered['rem'] = filtered['to_typs'].map(lambda x: len(remaining.intersection(set(x))))
    display = filtered.drop(['from_typs', 'to_typs'], axis=1).sort_values(['rem', 'comb_2'], ascending=False)

    choice = best.loc['dark_rock']  # tyranitar
    remaining = remaining - set(choice.to_typs)
    filtered['rem'] = filtered['to_typs'].map(lambda x: len(remaining.intersection(set(x))))
    display = filtered.drop(['from_typs', 'to_typs'], axis=1).sort_values(['rem', 'comb_2'], ascending=False)

    # tink, chesnaught


abilityMap = {
    """
    
    """
}


def best_per_type():
    # pokes = pd.read_json('src/data/pokes.json').transpose()
    # pokes = pd.read_json('src/data/pokes-all.json').transpose()
    # pokes = pd.read_json('src/data/pokes-comb.json').transpose()
    pokes = pd.read_json('src/data/pokes-all-2.json').transpose()

    d = pokes.copy()
    d.rename(columns={'type': 'otype'}, inplace=True)
    d['type'] = d['otype'].apply(lambda x: str(x).split('_'))
    dx = d.explode('type')

    comb = dx.copy()

    comb['has_nasty'] = comb['moves'].apply(lambda x: True if any(i['name'] == 'nasty-plot' for i in x) else False)
    comb['has_swords'] = comb['moves'].apply(lambda x: True if any(i['name'] == 'swords-dance' for i in x) else False)
    comb['has_raise'] = ((comb['has_swords'] == True) & (comb['atk_type'] != 'SpA')) | ((comb['has_nasty'] == True) & (comb['atk_type'] != 'Atk'))

    # comb = pd.concat([dx.drop(['stats'], axis=1), dx['stats'].apply(pd.Series)], axis=1)

    # comb['tot_b'] = comb['tot'] - comb['speed']
    # comb['atk_type'] = np.where(comb['attack'] < comb['special-attack'], 'SpA', 'Atk')
    # comb['def_type'] = np.where(comb['defense'] < comb['special-defense'], 'SpD', 'Def')
    comb['tot_c'] = np.where(comb['attack'] < comb['special-attack'], comb['tot_b'] - comb['attack'], comb['tot_b'] - comb['special-attack'])

    comb['ability_1'] = comb['abilities'].apply(
        lambda x: (f'<{x[0]["name"]}> ' + (x[0]['desc'] or x[0]["flavor"] or '<unk>')).replace('\n', ' ') if x[0]['hidden'] is not True else '-'
    )
    comb['ability_2'] = comb['abilities'].apply(
        lambda x: (f'<{x[1]["name"]}> ' + (x[1]['desc'] or x[1]["flavor"] or '<unk>')).replace('\n', ' ') if len(x) > 1 and x[1][
            'hidden'] is not True else '-'
    )
    comb['ability_h'] = comb['abilities'].apply(
        lambda x: (
            h := next((y for y in x if y['hidden'] is True), None),
            (f'<{h["name"]}> ' + (h['desc'] or
                                  h["flavor"] or
                                  '<unk>')) if h else '-'
        )[-1].replace('\n', ' ')
    )
    comb['ability_h'] = np.where(comb['ability_h'] == comb['ability_1'], '-', comb['ability_h'])

    comb['leg'] = (comb['is_legendary'] | comb['is_mythical']).astype(int)
    comb['tot_b'] = comb['tot_b'].astype(int)
    comb['max_atk'] = comb['max_atk'].astype(int)
    comb['max_def'] = comb['max_def'].astype(int)

    # TAKE OUT
    comb = comb[comb['has_raise'] == True]

    comb = comb.sort_values('tot_c', ascending=False)

    cols = ['type', 'name', 'dex', 'leg', 'tot_c', 'max_atk', 'max_def', 'atk_type', 'def_type', 'ability_1', 'ability_2', 'ability_h']
    grouped = comb.groupby('type', as_index=False)

    lim = 25

    by_col = 'max_atk'  # 'tot_b'
    tot = grouped.apply(lambda x: x.nlargest(lim, by_col)).reset_index(drop=True)[cols]

    # atk = grouped.apply(lambda x: x.nlargest(3, 'attack')).reset_index(drop=True)[cols]
    # spe = grouped.apply(lambda x: x.nlargest(3, 'special-attack')).reset_index(drop=True)[cols]

    print(tot.to_csv(index=False))


if __name__ == '__main__':
    # main()
    best_per_type()
