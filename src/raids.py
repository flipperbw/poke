import json
import typing as tp

import pandas as pd
from tabulate import tabulate


# -- Types
class DmgInner(tp.TypedDict):
    cnt: int
    typs: tp.List[str]


class DmgData(tp.TypedDict):
    quad: DmgInner
    double: DmgInner
    normal: DmgInner
    half: DmgInner
    quarter: DmgInner
    none: DmgInner
    weak: DmgInner
    strong: DmgInner


class DmgTo(tp.TypedDict):
    name: str
    data: DmgData


TypData = tp.TypedDict(
    'TypData', {
        'from': DmgData,
        'to_a': DmgTo,
        'to_b': tp.Optional[DmgTo]
    }
)

"""
tera_type, atk1, atk2, effective, ok, dont_use, weak_to 
Fighting, Normal, Ground,  x|y, z, w, w|x|y|z
Fighting, Normal, Psychic, y, w|z, x, w|x|y|z
"""

Ret = tp.List[tp.Tuple[str, str, str, tp.List[str], tp.List[str], tp.List[str], tp.List[str]]]


# TODO include recipes
# TODO tab with pokemon

def main() -> Ret:
    q: tp.Dict[str, TypData] = json.load(open('src/data/typs.json'))

    regular_types = {t: tv for t, tv in q.items() if '_' not in t}

    ret_data: Ret = []

    for tera_typ, v in regular_types.items():
        weak_to = v['from']['weak']['typs']

        ret_data.append((tera_typ.capitalize(), 'Unknown', '', [x.capitalize() for x in weak_to], [], [], [x.capitalize() for x in weak_to]))

        for atk1 in regular_types:
            for atk2 in regular_types:
                use: tp.List[str] = []
                dont_use: tp.List[str] = []
                ok_use: tp.List[str] = []

                for wtyp in weak_to:
                    s_from = q[wtyp]['from']

                    s_weak = s_from['weak']['typs']
                    s_none = s_from['none']['typs']
                    s_half = s_from['half']['typs']

                    # TODO show all bad
                    if atk1 in s_weak or atk2 in s_weak:
                        dont_use.append(wtyp)
                    elif atk1 in s_none or atk2 in s_none:
                        use.insert(0, wtyp)
                    elif atk1 in s_half or atk2 in s_half:
                        use.append(wtyp)
                    else:
                        ok_use.append(wtyp)

                ret_data.append(
                    (tera_typ.capitalize(), atk1.capitalize(), atk2.capitalize() if atk2 != atk1 else '', [x.capitalize() for x in use],
                    [x.capitalize() for x in ok_use], [x.capitalize() for x in dont_use], [x.capitalize() for x in weak_to])
                )

    return ret_data


if __name__ == '__main__':
    d = main()
    headers = ['Tera Type', 'Atk 1', 'Atk 2', 'GOOD', 'Ok', 'Bad', 'Weak To']

    sep = ', '
    transformed = [(row[0], row[1], row[2], sep.join(row[3]), sep.join(row[4]), sep.join(row[5]), sep.join(row[6])) for row in d]

    print(tabulate(transformed[:10], headers=headers))

    df = pd.DataFrame(transformed, columns=headers)
    df.to_csv('src/data/raids.csv', index=False)
