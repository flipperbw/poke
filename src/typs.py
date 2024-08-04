import json
import typing as tp
from copy import deepcopy


# types = {}
#
# for i in range(1, 20):
#     t = pb.type_(i)
#     rels = t.damage_relations or {}
#     types[t.name] = {
#         'id': t.id,
#         'dmg': {
#             'from_double': [x.name for x in t.damage_relations.double_damage_from] if t.damage_relations else [],
#             'from_half': [x.name for x in t.damage_relations.half_damage_from] if t.damage_relations else [],
#             'from_none': [x.name for x in t.damage_relations.no_damage_from] if t.damage_relations else [],
#             'to_double': [x.name for x in t.damage_relations.double_damage_to] if t.damage_relations else [],
#             'to_half': [x.name for x in t.damage_relations.half_damage_to] if t.damage_relations else [],
#             'to_none': [x.name for x in t.damage_relations.no_damage_to] if t.damage_relations else [],
#         }
#     }


class DmgType(tp.TypedDict):
    from_double: tp.List[str]
    from_half: tp.List[str]
    from_none: tp.List[str]
    to_double: tp.List[str]
    to_half: tp.List[str]
    to_none: tp.List[str]


class Typ(tp.TypedDict):
    id: int
    dmg: DmgType


types: tp.Dict[str, Typ] = {
    'normal': {
        'id': 1,
        'dmg': {
            'from_double': ['fighting'],
            'from_half': [],
            'from_none': ['ghost'],
            'to_double': [],
            'to_half': ['rock', 'steel'],
            'to_none': ['ghost'],
        },
    },
    'fighting': {
        'id': 2,
        'dmg': {
            'from_double': ['flying', 'psychic', 'fairy'],
            'from_half': ['rock', 'bug', 'dark'],
            'from_none': [],
            'to_double': ['normal', 'rock', 'steel', 'ice', 'dark'],
            'to_half': ['flying', 'poison', 'bug', 'psychic', 'fairy'],
            'to_none': ['ghost'],
        },
    },
    'flying': {
        'id': 3,
        'dmg': {
            'from_double': ['rock', 'electric', 'ice'],
            'from_half': ['fighting', 'bug', 'grass'],
            'from_none': ['ground'],
            'to_double': ['fighting', 'bug', 'grass'],
            'to_half': ['rock', 'steel', 'electric'],
            'to_none': [],
        },
    },
    'poison': {
        'id': 4,
        'dmg': {
            'from_double': ['ground', 'psychic'],
            'from_half': ['fighting', 'poison', 'bug', 'grass', 'fairy'],
            'from_none': [],
            'to_double': ['grass', 'fairy'],
            'to_half': ['poison', 'ground', 'rock', 'ghost'],
            'to_none': ['steel'],
        },
    },
    'ground': {
        'id': 5,
        'dmg': {
            'from_double': ['water', 'grass', 'ice'],
            'from_half': ['poison', 'rock'],
            'from_none': ['electric'],
            'to_double': ['poison', 'rock', 'steel', 'fire', 'electric'],
            'to_half': ['bug', 'grass'],
            'to_none': ['flying'],
        },
    },
    'rock': {
        'id': 6,
        'dmg': {
            'from_double': ['fighting', 'ground', 'steel', 'water', 'grass'],
            'from_half': ['normal', 'flying', 'poison', 'fire'],
            'from_none': [],
            'to_double': ['flying', 'bug', 'fire', 'ice'],
            'to_half': ['fighting', 'ground', 'steel'],
            'to_none': [],
        },
    },
    'bug': {
        'id': 7,
        'dmg': {
            'from_double': ['flying', 'rock', 'fire'],
            'from_half': ['fighting', 'ground', 'grass'],
            'from_none': [],
            'to_double': ['grass', 'psychic', 'dark'],
            'to_half': [
                'fighting',
                'flying',
                'poison',
                'ghost',
                'steel',
                'fire',
                'fairy',
            ],
            'to_none': [],
        },
    },
    'ghost': {
        'id': 8,
        'dmg': {
            'from_double': ['ghost', 'dark'],
            'from_half': ['poison', 'bug'],
            'from_none': ['normal', 'fighting'],
            'to_double': ['ghost', 'psychic'],
            'to_half': ['dark'],
            'to_none': ['normal'],
        },
    },
    'steel': {
        'id': 9,
        'dmg': {
            'from_double': ['fighting', 'ground', 'fire'],
            'from_half': [
                'normal',
                'flying',
                'rock',
                'bug',
                'steel',
                'grass',
                'psychic',
                'ice',
                'dragon',
                'fairy',
            ],
            'from_none': ['poison'],
            'to_double': ['rock', 'ice', 'fairy'],
            'to_half': ['steel', 'fire', 'water', 'electric'],
            'to_none': [],
        },
    },
    'fire': {
        'id': 10,
        'dmg': {
            'from_double': ['ground', 'rock', 'water'],
            'from_half': ['bug', 'steel', 'fire', 'grass', 'ice', 'fairy'],
            'from_none': [],
            'to_double': ['bug', 'steel', 'grass', 'ice'],
            'to_half': ['rock', 'fire', 'water', 'dragon'],
            'to_none': [],
        },
    },
    'water': {
        'id': 11,
        'dmg': {
            'from_double': ['grass', 'electric'],
            'from_half': ['steel', 'fire', 'water', 'ice'],
            'from_none': [],
            'to_double': ['ground', 'rock', 'fire'],
            'to_half': ['water', 'grass', 'dragon'],
            'to_none': [],
        },
    },
    'grass': {
        'id': 12,
        'dmg': {
            'from_double': ['flying', 'poison', 'bug', 'fire', 'ice'],
            'from_half': ['ground', 'water', 'grass', 'electric'],
            'from_none': [],
            'to_double': ['ground', 'rock', 'water'],
            'to_half': ['flying', 'poison', 'bug', 'steel', 'fire', 'grass', 'dragon'],
            'to_none': [],
        },
    },
    'electric': {
        'id': 13,
        'dmg': {
            'from_double': ['ground'],
            'from_half': ['flying', 'steel', 'electric'],
            'from_none': [],
            'to_double': ['flying', 'water'],
            'to_half': ['grass', 'electric', 'dragon'],
            'to_none': ['ground'],
        },
    },
    'psychic': {
        'id': 14,
        'dmg': {
            'from_double': ['bug', 'ghost', 'dark'],
            'from_half': ['fighting', 'psychic'],
            'from_none': [],
            'to_double': ['fighting', 'poison'],
            'to_half': ['steel', 'psychic'],
            'to_none': ['dark'],
        },
    },
    'ice': {
        'id': 15,
        'dmg': {
            'from_double': ['fighting', 'rock', 'steel', 'fire'],
            'from_half': ['ice'],
            'from_none': [],
            'to_double': ['flying', 'ground', 'grass', 'dragon'],
            'to_half': ['steel', 'fire', 'water', 'ice'],
            'to_none': [],
        },
    },
    'dragon': {
        'id': 16,
        'dmg': {
            'from_double': ['ice', 'dragon', 'fairy'],
            'from_half': ['fire', 'water', 'grass', 'electric'],
            'from_none': [],
            'to_double': ['dragon'],
            'to_half': ['steel'],
            'to_none': ['fairy'],
        },
    },
    'dark': {
        'id': 17,
        'dmg': {
            'from_double': ['fighting', 'bug', 'fairy'],
            'from_half': ['ghost', 'dark'],
            'from_none': ['psychic'],
            'to_double': ['ghost', 'psychic'],
            'to_half': ['fighting', 'dark', 'fairy'],
            'to_none': [],
        },
    },
    'fairy': {
        'id': 18,
        'dmg': {
            'from_double': ['poison', 'steel'],
            'from_half': ['fighting', 'bug', 'dark'],
            'from_none': ['dragon'],
            'to_double': ['fighting', 'dragon', 'dark'],
            'to_half': ['poison', 'steel', 'fire'],
            'to_none': [],
        },
    },
}


def get_combo_name(a: str, b: str | None = None) -> str:
    if not b:
        return a
    return '_'.join(sorted([a, b]))


def calc_types(
    an: str, a: DmgType, bn: str | None = None, b: DmgType | None = None
) -> tp.Dict[str, dict]:
    base: tp.Dict[str, dict] = {
        'quad': {'cnt': 0, 'typs': []},
        'double': {'cnt': 0, 'typs': []},
        'normal': {'cnt': 0, 'typs': []},
        'half': {'cnt': 0, 'typs': []},
        'quarter': {'cnt': 0, 'typs': []},
        'none': {'cnt': 0, 'typs': []},
        'weak': {'cnt': 0, 'typs': []},
        'strong': {'cnt': 0, 'typs': []},
    }

    d: tp.Dict[str, dict] = {
        'from': deepcopy(base),
        'to_a': {'name': an, 'data': deepcopy(base)},
        'to_b': {'name': bn, 'data': deepcopy(base)} if bn else None,
    }

    # calc from - single type
    for bt in typenames:
        a_from_val = (
            2.0
            if bt in a['from_double']
            else (
                0.5 if bt in a['from_half'] else (0.0 if bt in a['from_none'] else 1.0)
            )
        )
        b_from_val = (
            1.0
            if not b
            else (
                2.0
                if bt in b['from_double']
                else (
                    0.5
                    if bt in b['from_half']
                    else 0.0 if bt in b['from_none'] else 1.0
                )
            )
        )

        comb_from_val = a_from_val * b_from_val

        if comb_from_val == 4.0:
            d['from']['quad']['cnt'] += 1
            d['from']['quad']['typs'].append(bt)
            d['from']['weak']['cnt'] += 1
            d['from']['weak']['typs'].append(bt)
        elif comb_from_val == 2.0:
            d['from']['double']['cnt'] += 1
            d['from']['double']['typs'].append(bt)
            d['from']['weak']['cnt'] += 1
            d['from']['weak']['typs'].append(bt)
        elif comb_from_val == 1.0:
            d['from']['normal']['cnt'] += 1
            d['from']['normal']['typs'].append(bt)
        elif comb_from_val == 0.5:
            d['from']['half']['cnt'] += 1
            d['from']['half']['typs'].append(bt)
            d['from']['strong']['cnt'] += 1
            d['from']['strong']['typs'].append(bt)
        elif comb_from_val == 0.25:
            d['from']['quarter']['cnt'] += 1
            d['from']['quarter']['typs'].append(bt)
            d['from']['strong']['cnt'] += 1
            d['from']['strong']['typs'].append(bt)
        elif comb_from_val == 0.0:
            d['from']['none']['cnt'] += 1
            d['from']['none']['typs'].append(bt)
            d['from']['strong']['cnt'] += 1
            d['from']['strong']['typs'].append(bt)

    # calc to - dual type for each base type
    for cbt_a, cbt_b in combo_typenames:
        a_to_1_val = (
            2.0
            if cbt_a in a['to_double']
            else 0.5 if cbt_a in a['to_half'] else 0.0 if cbt_a in a['to_none'] else 1.0
        )
        a_to_2_val = (
            2.0
            if cbt_b in a['to_double']
            else 0.5 if cbt_b in a['to_half'] else 0.0 if cbt_b in a['to_none'] else 1.0
        )
        a_to_comb = a_to_1_val * a_to_2_val

        comb_name = get_combo_name(cbt_a, cbt_b)

        if a_to_comb == 4.0:
            d['to_a']['data']['quad']['cnt'] += 1
            d['to_a']['data']['quad']['typs'].append(comb_name)
            d['to_a']['data']['strong']['cnt'] += 1
            d['to_a']['data']['strong']['typs'].append(comb_name)
        elif a_to_comb == 2.0:
            d['to_a']['data']['double']['cnt'] += 1
            d['to_a']['data']['double']['typs'].append(comb_name)
            d['to_a']['data']['strong']['cnt'] += 1
            d['to_a']['data']['strong']['typs'].append(comb_name)
        elif a_to_comb == 1.0:
            d['to_a']['data']['normal']['cnt'] += 1
            d['to_a']['data']['normal']['typs'].append(comb_name)
        elif a_to_comb == 0.5:
            d['to_a']['data']['half']['cnt'] += 1
            d['to_a']['data']['half']['typs'].append(comb_name)
            d['to_a']['data']['weak']['cnt'] += 1
            d['to_a']['data']['weak']['typs'].append(comb_name)
        elif a_to_comb == 0.25:
            d['to_a']['data']['quarter']['cnt'] += 1
            d['to_a']['data']['quarter']['typs'].append(comb_name)
            d['to_a']['data']['weak']['cnt'] += 1
            d['to_a']['data']['weak']['typs'].append(comb_name)
        elif a_to_comb == 0.0:
            d['to_a']['data']['none']['cnt'] += 1
            d['to_a']['data']['none']['typs'].append(comb_name)
            d['to_a']['data']['weak']['cnt'] += 1
            d['to_a']['data']['weak']['typs'].append(comb_name)

        if b:
            b_to_1_val = (
                2.0
                if cbt_a in b['to_double']
                else (
                    0.5
                    if cbt_a in b['to_half']
                    else 0.0 if cbt_a in b['to_none'] else 1.0
                )
            )
            b_to_2_val = (
                2.0
                if cbt_b in b['to_double']
                else (
                    0.5
                    if cbt_b in b['to_half']
                    else 0.0 if cbt_b in b['to_none'] else 1.0
                )
            )
            b_to_comb = b_to_1_val * b_to_2_val

            if b_to_comb == 4.0:
                d['to_b']['data']['quad']['cnt'] += 1
                d['to_b']['data']['quad']['typs'].append(comb_name)
                d['to_b']['data']['strong']['cnt'] += 1
                d['to_b']['data']['strong']['typs'].append(comb_name)
            elif b_to_comb == 2.0:
                d['to_b']['data']['double']['cnt'] += 1
                d['to_b']['data']['double']['typs'].append(comb_name)
                d['to_b']['data']['strong']['cnt'] += 1
                d['to_b']['data']['strong']['typs'].append(comb_name)
            elif b_to_comb == 1.0:
                d['to_b']['data']['normal']['cnt'] += 1
                d['to_b']['data']['normal']['typs'].append(comb_name)
            elif b_to_comb == 0.5:
                d['to_b']['data']['half']['cnt'] += 1
                d['to_b']['data']['half']['typs'].append(comb_name)
                d['to_b']['data']['weak']['cnt'] += 1
                d['to_b']['data']['weak']['typs'].append(comb_name)
            elif b_to_comb == 0.25:
                d['to_b']['data']['quarter']['cnt'] += 1
                d['to_b']['data']['quarter']['typs'].append(comb_name)
                d['to_b']['data']['weak']['cnt'] += 1
                d['to_b']['data']['weak']['typs'].append(comb_name)
            elif b_to_comb == 0.0:
                d['to_b']['data']['none']['cnt'] += 1
                d['to_b']['data']['none']['typs'].append(comb_name)
                d['to_b']['data']['weak']['cnt'] += 1
                d['to_b']['data']['weak']['typs'].append(comb_name)

    return d


typenames = types.keys()

combo_typenames: tp.List[tp.Tuple[str, str | None]] = []
for x in typenames:
    for y in typenames:
        if x == y:
            tup = (x, None)
        else:
            sorted_typs = sorted([x, y])
            tup = (sorted_typs[0], sorted_typs[1])
        if tup not in combo_typenames:
            combo_typenames.append(tup)


def main() -> None:
    typecalc: tp.Dict[str, tp.Dict[str, dict]] = {}

    for t, v in types.items():
        for st, sv in types.items():
            if t == st:
                typecalc[t] = calc_types(t, v['dmg'])
            else:
                combo = get_combo_name(t, st)
                if combo in typecalc:
                    continue
                typecalc[combo] = calc_types(t, v['dmg'], st, sv['dmg'])

    # print(json.dumps(typecalc, indent=2))

    froms = {}
    tos = {}
    tot = {}
    for k, v in typecalc.items():
        fr = v['from']
        strong = fr['strong']['cnt']
        weak = fr['weak']['cnt']
        reg = strong - weak
        val = (
            fr['quad']['cnt'] * -4
            + fr['double']['cnt'] * -2
            + fr['half']['cnt'] * 2
            + fr['quarter']['cnt'] * 4
            + fr['none']['cnt'] * 8
        )
        froms[k] = {'cnt': reg, 'num': val, 'strong': strong, 'weak': weak}

        to_a = v['to_a']['data']
        strong_to_a = to_a['strong']['cnt']
        weak_to_a = to_a['weak']['cnt']
        reg_to_a = strong_to_a - weak_to_a
        val_to_a = (
            to_a['quad']['cnt'] * 4
            + to_a['double']['cnt'] * 2
            + to_a['half']['cnt'] * -2
            + to_a['quarter']['cnt'] * -4
            + to_a['none']['cnt'] * -8
        )

        if v['to_b']:
            to_b = v['to_b']['data']
            strong_to_b = to_b['strong']['cnt']
            weak_to_b = to_b['weak']['cnt']
            reg_to_b = strong_to_b - weak_to_b
            val_to_b = (
                to_b['quad']['cnt'] * 4
                + to_b['double']['cnt'] * 2
                + to_b['half']['cnt'] * -2
                + to_b['quarter']['cnt'] * -4
                + to_b['none']['cnt'] * -8
            )
        else:
            strong_to_b = 0
            weak_to_b = 0
            reg_to_b = 0
            val_to_b = 0

        tos[k] = {
            'cnt': reg_to_a + reg_to_b,
            'num': val_to_a + val_to_b,
            'strong': strong_to_a + strong_to_b,
            'weak': weak_to_a + weak_to_b,
        }

        tot[k] = {
            'cnt': (reg_to_a + reg_to_b) / 2 + reg,
            'num': (val_to_a + val_to_b) / 2 + val,
        }

    froms_by_cnt = sorted(
        froms.items(), key=lambda item: (item[1]['cnt'], item[1]['num']), reverse=True
    )
    froms_by_num = sorted(
        froms.items(), key=lambda item: (item[1]['num'], item[1]['cnt']), reverse=True
    )

    tos_by_cnt = sorted(
        tos.items(), key=lambda item: (item[1]['cnt'], item[1]['num']), reverse=True
    )
    tos_by_num = sorted(
        tos.items(), key=lambda item: (item[1]['num'], item[1]['cnt']), reverse=True
    )

    tot_by_cnt = sorted(
        tot.items(), key=lambda item: (item[1]['cnt'], item[1]['num']), reverse=True
    )
    tot_by_num = sorted(
        tot.items(), key=lambda item: (item[1]['num'], item[1]['cnt']), reverse=True
    )

    print('from by cnt', json.dumps(froms_by_cnt[:10], indent=2))
    print('from by num', json.dumps(froms_by_num[:10], indent=2))
    print('to by cnt', json.dumps(tos_by_cnt[:10], indent=2))
    print('to by num', json.dumps(tos_by_num[:10], indent=2))
    print('tot by cnt', json.dumps(tot_by_cnt[:10], indent=2))
    print('tot by num', json.dumps(tot_by_num[:10], indent=2))
    print()


if __name__ == '__main__':
    main()
