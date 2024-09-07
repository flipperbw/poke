import json
import typing as tp

import pandas as pd

pd.set_option('display.width', 200)
pd.set_option('display.min_rows', 20)
pd.set_option('display.max_colwidth', 50)
pd.set_option('display.max_columns', 18)
pd.set_option('display.max_columns', None)


# logging.basicConfig()
# logging.getLogger().setLevel(logging.DEBUG)
# requests_log = logging.getLogger('requests.packages.urllib3')
# requests_log.setLevel(logging.DEBUG)
# requests_log.propagate = True

def print_full(x):
    pd.set_option('display.max_rows', len(x))
    print(x)
    pd.reset_option('display.max_rows')


class EvolutionChain:
    chain: 'Chain'


class Chain:
    species: 'Species'
    evolves_to: tp.List['Chain']


class EggGroups:
    name: str


class EvolvesFrom:
    name: str


class Variety:
    is_default: bool
    pokemon: 'Pokemon'


class Type:
    name: str


class PokemonType:
    slot: int
    type: Type


class Stat:
    name: str


class PokemonStat:
    base_stat: int
    stat: Stat


class Language:
    name: str


class AbilityEffectEntry:
    effect: str
    short_effect: str
    language: Language


class Ability:
    name: str
    effect_entries: tp.List[AbilityEffectEntry]


class PokemonAbility:
    is_hidden: bool
    ability: Ability


class Pokemon:
    name: str
    id: int
    types: tp.List[PokemonType]
    stats: tp.List[PokemonStat]
    abilities: tp.List[PokemonAbility]


class Species:
    id: int
    name: str
    capture_rate: int
    is_baby: bool
    is_legendary: bool
    is_mythical: bool
    evolution_chain: EvolutionChain
    egg_groups: tp.List[EggGroups]
    evolves_from_species: EvolvesFrom
    varieties: tp.List[Variety]


EvoDict = tp.TypedDict('EvoDict', {'name': str, 'dex_id': int, 'id': int, 'final': bool, 'alt': bool})


def dump_to(fname: str, data: tp.Any) -> None:
    try:
        with open(f'src/data/{fname}.json', 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        with open(f'data/{fname}.json', 'w') as f:
            json.dump(data, f, indent=2)


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
