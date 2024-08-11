import pandas as pd

from src.typs import combo_typenames, get_combo_name


# pd.set_option('display.width', 200)
# pd.set_option('display.min_rows', 20)
# pd.set_option('display.max_colwidth', 50)
# pd.set_option('display.max_columns', 18)


def print_full(x):
    pd.set_option('display.max_rows', len(x))
    print(x)
    pd.reset_option('display.max_rows')


df = pd.read_json('src/data/pokes.json')
df = df.transpose()

df_by_tot = df.sort_values('stats', key=lambda k: k.str['tot'], ascending=False)

typ_cnts = (
    df.reset_index()
    .groupby('type')[['type', 'index']]
    .agg(Cnt=('type', 'count'), List=('index', list))
)

t = pd.DataFrame([get_combo_name(*x) for x in combo_typenames])

merged_types = t.merge(typ_cnts, how='left', left_on=0, right_index=True).set_index(0)
merged_types = merged_types.fillna({'Cnt': 0})
for row in merged_types.loc[merged_types.List.isna(), 'List'].index:
    merged_types.at[row, 'List'] = []

merged_types = merged_types.sort_values('Cnt', ascending=False)

merged_types.to_json('src/data/typ_cnts.json', indent=2, orient='index')
