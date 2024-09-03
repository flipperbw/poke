import json
import typing as tp

from more_itertools import first_true

import pokebase as pb
from src.typs import get_combo_name


# logging.basicConfig()
# logging.getLogger().setLevel(logging.DEBUG)
# requests_log = logging.getLogger('requests.packages.urllib3')
# requests_log.setLevel(logging.DEBUG)
# requests_log.propagate = True

class EvolutionChain:
    chain: 'Chain'


class Species:
    id: int
    name: str
    evolution_chain: EvolutionChain


class Chain:
    species: Species
    evolves_to: tp.List['Chain']


EvoDict = tp.TypedDict('EvoDict', {'name': str, 'dex_id': int, 'id': int})

unavailable_sv = [
    "caterpie",
    "metapod",
    "butterfree",
    "weedle",
    "kakuna",
    "beedrill",
    "pidgey",
    "pidgeotto",
    "pidgeot",
    "rattata",
    "raticate",
    "spearow",
    "fearow",
    "nidoran-f",
    "nidorina",
    "nidoqueen",
    "nidoran-m",
    "nidorino",
    "nidoking",
    "zubat",
    "golbat",
    "paras",
    "parasect",
    "abra",
    "kadabra",
    "alakazam",
    "machop",
    "machoke",
    "machamp",
    "ponyta",
    "rapidash",
    "farfetchd",
    "onix",
    "krabby",
    "kingler",
    "cubone",
    "marowak",
    "lickitung",
    "tangela",
    "kangaskhan",
    "goldeen",
    "seaking",
    "staryu",
    "starmie",
    "mr-mime",
    "jynx",
    "pinsir",
    "omanyte",
    "omastar",
    "kabuto",
    "kabutops",
    "aerodactyl",
    "ledyba",
    "ledian",
    "crobat",
    "togepi",
    "togetic",
    "natu",
    "xatu",
    "unown",
    "wobbuffet",
    "steelix",
    "shuckle",
    "corsola",
    "remoraid",
    "octillery",
    "mantine",
    "smoochum",
    "miltank",
    "celebi",
    "zigzagoon",
    "linoone",
    "wurmple",
    "silcoon",
    "beautifly",
    "cascoon",
    "dustox",
    "taillow",
    "swellow",
    "nincada",
    "ninjask",
    "shedinja",
    "whismur",
    "loudred",
    "exploud",
    "skitty",
    "delcatty",
    "mawile",
    "aron",
    "lairon",
    "aggron",
    "electrike",
    "manectric",
    "roselia",
    "carvanha",
    "sharpedo",
    "wailmer",
    "wailord",
    "spinda",
    "lunatone",
    "solrock",
    "baltoy",
    "claydol",
    "lileep",
    "cradily",
    "anorith",
    "armaldo",
    "castform",
    "kecleon",
    "absol",
    "wynaut",
    "spheal",
    "sealeo",
    "walrein",
    "clamperl",
    "huntail",
    "gorebyss",
    "relicanth",
    "bidoof",
    "bibarel",
    "budew",
    "roserade",
    "burmy",
    "wormadam",
    "mothim",
    "cherubi",
    "cherrim",
    "buneary",
    "lopunny",
    "glameow",
    "purugly",
    "mime-jr",
    "chatot",
    "skorupi",
    "drapion",
    "carnivine",
    "mantyke",
    "lickilicky",
    "tangrowth",
    "togekiss",
    "victini",
    "patrat",
    "watchog",
    "lillipup",
    "herdier",
    "stoutland",
    "purrloin",
    "liepard",
    "pansage",
    "simisage",
    "pansear",
    "simisear",
    "panpour",
    "simipour",
    "munna",
    "musharna",
    "pidove",
    "tranquill",
    "unfezant",
    "roggenrola",
    "boldore",
    "gigalith",
    "woobat",
    "swoobat",
    "audino",
    "tympole",
    "palpitoad",
    "seismitoad",
    "throh",
    "sawk",
    "venipede",
    "whirlipede",
    "scolipede",
    "darumaka",
    "darmanitan",
    "maractus",
    "dwebble",
    "crustle",
    "sigilyph",
    "yamask",
    "cofagrigus",
    "tirtouga",
    "carracosta",
    "archen",
    "archeops",
    "trubbish",
    "garbodor",
    "vanillite",
    "vanillish",
    "vanilluxe",
    "emolga",
    "karrablast",
    "escavalier",
    "frillish",
    "jellicent",
    "ferroseed",
    "ferrothorn",
    "klink",
    "klang",
    "klinklang",
    "elgyem",
    "beheeyem",
    "shelmet",
    "accelgor",
    "stunfisk",
    "druddigon",
    "bouffalant",
    "heatmor",
    "durant",
    "genesect",
    "bunnelby",
    "diggersby",
    "pancham",
    "pangoro",
    "furfrou",
    "honedge",
    "doublade",
    "aegislash",
    "spritzee",
    "aromatisse",
    "swirlix",
    "slurpuff",
    "binacle",
    "barbaracle",
    "helioptile",
    "heliolisk",
    "tyrunt",
    "tyrantrum",
    "amaura",
    "aurorus",
    "pumpkaboo",
    "gourgeist",
    "xerneas",
    "yveltal",
    "zygarde",
    "wishiwashi",
    "morelull",
    "shiinotic",
    "stufful",
    "bewear",
    "wimpod",
    "golisopod",
    "pyukumuku",
    "type-null",
    "silvally",
    "turtonator",
    "togedemaru",
    "drampa",
    "dhelmise",
    "tapu-koko",
    "tapu-lele",
    "tapu-bulu",
    "tapu-fini",
    "nihilego",
    "buzzwole",
    "pheromosa",
    "xurkitree",
    "celesteela",
    "kartana",
    "guzzlord",
    "marshadow",
    "poipole",
    "naganadel",
    "stakataka",
    "blacephalon",
    "zeraora",
    "meltan",
    "melmetal",
    "blipbug",
    "dottler",
    "orbeetle",
    "nickit",
    "thievul",
    "gossifleur",
    "eldegoss",
    "wooloo",
    "dubwool",
    "yamper",
    "boltund",
    "sizzlipede",
    "centiskorch",
    "clobbopus",
    "grapploct",
    "obstagoon",
    "cursola",
    "sirfetchd",
    "mr-rime",
    "runerigus",
    "dracozolt",
    "arctozolt",
    "dracovish",
    "arctovish",
]


def flatten(l: tp.List['Chain']) -> tp.List['Chain']:
    result = []
    for el in l:
        result.append(el)
        if len(el.evolves_to):
            result.extend(flatten(el.evolves_to))
    return result


def find_is_final(d: Chain, s: Species):
    if s.name in ('stantler', 'ursaring', 'qwilfish'): return True

    if not len(d.evolves_to): return True

    evos = flatten(d.evolves_to)
    found = first_true(evos + [d], pred=lambda x: x.species.id == s.id)
    if not found:
        return None
    else:
        return not len(found.evolves_to)


def boxes() -> None:
    print('Running boxes')
    dexes = [31, 32, 33]

    tot_ids: tp.Dict[str, tp.List[EvoDict]] = {}

    for dex in dexes:
        ids: tp.List[EvoDict] = []
        tot_ids[str(dex)] = ids

        dex_data = pb.pokedex(dex)
        for entry in dex_data.pokemon_entries:
            dex_id: int = entry.entry_number
            species: Species = entry.pokemon_species
            chain = species.evolution_chain.chain
            pid = species.id

            fe = find_is_final(chain, species)
            if fe is None:
                print('could not find', dex_id, pid)
            else:
                if fe:
                    ids.append({'dex_id': dex_id, 'id': pid, 'name': species.name})

                print(species.name, fe)

    print(tot_ids)

    try:
        with open('src/data/final_evos.json', 'w') as f:
            json.dump(tot_ids, f, indent=2)
    except Exception:
        with open('data/final_evos.json', 'w') as f:
            json.dump(tot_ids, f, indent=2)


def pretty_boxes() -> None:
    print('Running pretty boxes')
    skip_dupes = True

    brows = 5
    bcols = 6
    bsize = brows * bcols

    spaces = 14
    fmt = f'^{spaces}'
    ln = (spaces * bcols) + bcols + 1

    with open('src/data/final_evos.json') as f:
        full: tp.Dict[str, tp.List[EvoDict]] = json.load(f)

    seen_ids: tp.List[int] = []

    for k, v in full.items():
        print('====')
        print(k)
        print('====')

        new_v: tp.List[EvoDict] = []
        for fi in v:
            if fi['id'] not in seen_ids:
                seen_ids.append(fi['id'])
                new_v.append(fi)
            else:
                if skip_dupes: print('skipping', fi['name'])

        list_v = new_v if skip_dupes else v

        start = 1
        for i in range(0, len(list_v), bsize):
            box = list_v[i:i + bsize]
            end = box[-1]['dex_id']
            print(f'{"-" * round((ln - 12) / 2)}{f"{k}: {start}-{end}": ^12}{"-" * round((ln - 12) / 2)}')
            for z in range(0, len(box), bcols):
                zd = [''] * bcols
                for j, x in enumerate(box[z:z + bcols]):
                    zd[j] = x['name']
                print(f'|{zd[0]: {fmt}}|{zd[1]: {fmt}}|{zd[2]: {fmt}}|{zd[3]: {fmt}}|{zd[4]: {fmt}}|{zd[5]: {fmt}}|')
            print('-' * ln)
            start = end + 1


def main() -> None:
    print('Running main')
    # dexes = [31, 32, 33]
    dexes = [30, 33, 32, 31]
    # dexes = [1]

    data = {}

    for dex in dexes:
        dex_data = pb.pokedex(dex)

        for entry in dex_data.pokemon_entries:
            species = entry.pokemon_species

            # name = f'{species.name} ({dex})'
            pname = species.name

            if pname in unavailable_sv:
                print(f'{entry.entry_number} - {pname}: SKIPPED')
                continue

            print(f'{entry.entry_number} - {pname}')

            base_data = {
                'dex_id': entry.entry_number,
                'species_name': pname,
                'dex': dex,
                'capture_rate': species.capture_rate,
                'egg_groups': [x.name for x in species.egg_groups],
                'evolves_from': (
                    species.evolves_from_species.name
                    if species.evolves_from_species
                    else None
                ),
                'is_baby': species.is_baby,
                'is_legendary': species.is_legendary,
                'is_mythical': species.is_mythical,
                # 'varieties': [],
            }

            varieties = species.varieties
            for variety in varieties:
                base_v = base_data.copy()

                pok = variety.pokemon
                types = pok.types
                pstats = pok.stats
                typ = get_combo_name(
                    types[0].type.name,
                    types[1].type.name if len(types) > 1 else None,
                )
                stats = {s.stat.name: s.base_stat for s in pstats}
                more_stats = {
                    **stats,
                    'max_atk': max(stats['attack'], stats['special-attack']),
                    'max_def': max(stats['defense'], stats['special-defense']),
                    'sum_def': stats['defense'] + stats['special-defense'],
                    'tot': sum(stats.values()),
                    'tot_b': sum(stats.values()) - stats['speed'],
                    'atk_type': 'SpA' if stats['special-attack'] > stats['attack'] else 'Atk',
                    'def_type': 'SpD' if stats['special-defense'] > stats['defense'] else 'Def',
                }

                base_v['is_default'] = variety.is_default
                if not any(
                    # n in pok.name for n in ('-gmax', '-galar', '-mega', '-totem')
                    pok.name.endswith(n) for n in ('-gmax', '-mega', '-mega-x', 'mega-y', '-totem', '-build', '-mode', '-eternamax')
                ):
                    base_v['id'] = pok.id
                    base_v['type'] = typ
                    base_v['name'] = pok.name
                    base_v.update(more_stats)

                    data[pok.name] = base_v

                    # if pname in ('bulbasaur', 'zapdos'): print(pok.name, data[pok.name])

    filename = 'pokes-comb'
    try:
        with open(f'src/data/{filename}.json', 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        with open(f'data/{filename}.json', 'w') as f:
            json.dump(data, f, indent=2)
    # print(json.dumps(data, indent=2))


if __name__ == '__main__':
    main()
    # boxes()

    print('done')
