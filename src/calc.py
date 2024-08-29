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


def best_per_type():
    pokes = pd.read_json('src/data/pokes.json').transpose()
    d = pokes.copy()
    d['xtype'] = d['type'].apply(lambda x: str(x).split('_'))
    dx = d.explode('xtype')
    comb = pd.concat([dx.drop(['stats'], axis=1), dx['stats'].apply(pd.Series)], axis=1)

    comb['tot_b'] = comb['tot'] - comb['speed']
    comb['atk_type'] = np.where(comb['attack'] < comb['special-attack'], 'SpA', 'Atk')
    comb['def_type'] = np.where(comb['defense'] < comb['special-defense'], 'SpD', 'Def')
    comb['is_legendary'] = comb['is_legendary'].astype(int)

    cols = ['xtype', 'name', 'dex', 'is_legendary', 'tot_b', 'max_atk', 'atk_type', 'def_type']
    grouped = comb.groupby('xtype', as_index=False)

    lim = 5
    tot = grouped.apply(lambda x: x.nlargest(lim, 'tot_b')).reset_index(drop=True)[cols]

    # atk = grouped.apply(lambda x: x.nlargest(3, 'attack')).reset_index(drop=True)[cols]
    # spe = grouped.apply(lambda x: x.nlargest(3, 'special-attack')).reset_index(drop=True)[cols]

    print(tot.to_csv(index=False))


if __name__ == '__main__':
    main()
