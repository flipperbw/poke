import json
import math
import typing as tp

import pokebase as pb
from src.poke import find_is_final
from src.utils import EvoDict, Species


def boxes() -> None:
    print('Running boxes')
    dexes = [31, 32, 33]

    tot_ids: tp.Dict[str, tp.List[EvoDict]] = {}
    tot_alt: tp.Dict[str, tp.List[EvoDict]] = {}

    # TODO floette?
    # TODO certain varieties have wrong dex (use species.pokedex_numbers)...wont work
    # TODO check has_gender_differences when no variety

    with open('src/data/pokes-comb.json') as f:
        full: tp.Dict[str, tp.Dict[str, tp.Any]] = json.load(f)

    for dex in dexes:
        ids: tp.List[EvoDict] = []
        alt: tp.List[EvoDict] = []
        for name, data in full.items():
            if data['dex'] != dex: continue
            if name in ['palafin-hero']: continue  # crorant-gulping, missing phony form

            if not len(data['evolves_to'] or []):
                dd = EvoDict(dex_id=data['dex_id'], id=data['id'], name=data['name'])
                if data['is_default']:
                    ids.append(dd)
                else:
                    alt.append(dd)

                print(data['dex_id'], data['name'])

        tot_ids[str(dex)] = sorted(ids, key=lambda x: x['dex_id'])
        tot_alt[str(dex)] = sorted(alt, key=lambda x: x['dex_id'])

    print(tot_ids)
    print(tot_alt)

    try:
        with open('src/data/final_evos.json', 'w') as f:
            json.dump(tot_ids, f, indent=2)
    except Exception:
        with open('data/final_evos.json', 'w') as f:
            json.dump(tot_ids, f, indent=2)

    try:
        with open('src/data/final_evos-alt.json', 'w') as f:
            json.dump(tot_alt, f, indent=2)
    except Exception:
        with open('data/final_evos-alt.json', 'w') as f:
            json.dump(tot_alt, f, indent=2)


def better_boxes() -> None:
    print('Running better boxes')
    dexes = [31, 32, 33]

    tot_ids: tp.Dict[str, tp.List[EvoDict]] = {}
    # tot_alt: tp.Dict[str, tp.List[EvoDict]] = {}

    for dex in dexes:
        ids: tp.List[EvoDict] = []
        # alt: tp.List[EvoDict] = []

        dex_data = pb.pokedex(dex)
        for entry in dex_data.pokemon_entries:
            dex_id: int = entry.entry_number
            species: Species = entry.pokemon_species
            chain = species.evolution_chain.chain
            pid = species.id

            # TODO swap
            fe = find_is_final(chain, species)
            # fe = True

            # if fe is None:
            #     print('ERROR: could not find', dex_id, pid)
            # else:
            #     if fe:
            varieties = species.varieties
            for variety in varieties:
                pok = variety.pokemon
                if any(
                    # n in pok.name for n in ('-gmax', '-galar', '-mega', '-totem')
                    pok.name.endswith(n) for n in (
                        '-gmax', '-mega', '-mega-x', 'mega-y', '-totem', '-build', '-mode', '-eternamax', '-ash', '-busted',
                        '-totem-disguised')
                ): continue

                if variety.is_default:
                    for f in pok.forms:
                        if f.is_default:
                            ids.append({'dex_id': dex_id, 'id': f.id, 'name': f.name, 'final': fe is True, 'alt': False})
                        else:
                            if f.is_battle_only:
                                print('skipping battle only', pok.name)
                                continue
                            ids.append({'dex_id': dex_id, 'id': f.id, 'name': f.name, 'final': fe is True, 'alt': True})
                            # alt.append({'dex_id': dex_id, 'id': f.id, 'name': f.name})
                        print(f.name)
                else:
                    for f in pok.forms:
                        if f.is_battle_only:
                            print('skipping battle only', pok.name)
                            continue
                        ids.append({'dex_id': dex_id, 'id': f.id, 'name': f.name, 'final': fe is True, 'alt': True})
                        # alt.append({'dex_id': dex_id, 'id': f.id, 'name': f.name})
                        print(f.name)

        tot_ids[str(dex)] = ids
        # tot_alt[str(dex)] = alt

    # print(tot_ids)

    with open('src/data/all_for_boxes.json', 'w') as f:
        json.dump(tot_ids, f, indent=2)

    # try:
    #     with open('src/data/final_evos_b.json', 'w') as f:
    #         json.dump(tot_ids, f, indent=2)
    # except Exception:
    #     with open('data/final_evos_b.json', 'w') as f:
    #         json.dump(tot_ids, f, indent=2)
    #
    # try:
    #     with open('src/data/final_evos_b-alt.json', 'w') as f:
    #         json.dump(tot_alt, f, indent=2)
    # except Exception:
    #     with open('data/final_evos_b-alt.json', 'w') as f:
    #         json.dump(tot_alt, f, indent=2)


def net_boxes() -> None:
    paldea = [
        'sprigatito',
        'floragato',
        'meowscarada',
        'fuecoco',
        'crocalor',
        'skeledirge',
        'quaxly',
        'quaxwell',
        'quaquaval',
        'lechonk',
        'oinkologne-male',
        'oinkologne-female',
        'tarountula',
        'spidops',
        'nymble',
        'lokix',
        'hoppip',
        'skiploom',
        'jumpluff',
        'fletchling',
        'fletchinder',
        'talonflame',
        'pawmi',
        'pawmo',
        'pawmot',
        'houndour',
        'houndoom-male',
        'houndoom-female',
        'yungoos',
        'gumshoos',
        'skwovet',
        'greedent',
        'sunkern',
        'sunflora',
        'kricketot-male',
        'kricketot-female',
        'kricketune-male',
        'kricketune-female',
        'scatterbug',
        'spewpa',
        'vivillon-marine',
        'vivillon-river',
        'vivillon-elegant',
        'vivillon-archipelago',
        'vivillon-icy-snow',
        'vivillon-sandstorm',
        'vivillon-meadow',
        'vivillon-modern',
        'vivillon-savanna',
        'vivillon-sun',
        'vivillon-jungle',
        'vivillon-continental',
        'vivillon-polar',
        'vivillon-high-plains',
        'vivillon-monsoon',
        'vivillon-tundra',
        'vivillon-ocean',
        'vivillon-garden',
        'vivillon-fancy',
        'combee-male',
        'combee-female',
        'vespiquen',
        'rookidee',
        'corvisquire',
        'corviknight',
        'happiny',
        'chansey',
        'blissey',
        'azurill',
        'marill',
        'azumarill',
        'surskit',
        'masquerain',
        'buizel-male',
        'buizel-female',
        'floatzel-male',
        'floatzel-female',
        'wooper-paldea',
        'clodsire',
        'psyduck',
        'golduck',
        'chewtle',
        'drednaw',
        'igglybuff',
        'jigglypuff',
        'wigglytuff',
        'ralts',
        'kirlia',
        'gardevoir',
        'gallade',
        'drowzee',
        'hypno-male',
        'hypno-female',
        'gastly',
        'haunter',
        'gengar',
        'tandemaus',
        'maushold-family-of-three',
        'maushold-family-of-four',
        'pichu',
        'pikachu-male',
        'pikachu-female',
        'raichu-male',
        'raichu-female',
        'fidough',
        'dachsbun',
        'slakoth',
        'vigoroth',
        'slaking',
        'bounsweet',
        'steenee',
        'tsareena',
        'smoliv',
        'dolliv',
        'arboliva',
        'bonsly',
        'sudowoodo-male',
        'sudowoodo-female',
        'rockruff',
        'lycanroc-midday',
        'lycanroc-midnight',
        'lycanroc-dusk',
        'rolycoly',
        'carkol',
        'coalossal',
        'shinx-male',
        'shinx-female',
        'luxio-male',
        'luxio-female',
        'luxray-male',
        'luxray-female',
        'starly-male',
        'starly-female',
        'staravia-male',
        'staravia-female',
        'staraptor-male',
        'staraptor-female',
        'oricorio-baile',
        'oricorio-pom-pom',
        'oricorio-pau',
        'oricorio-sensu',
        'mareep',
        'flaaffy',
        'ampharos',
        'petilil',
        'lilligant',
        'shroomish',
        'breloom',
        'applin',
        'flapple',
        'appletun',
        'spoink',
        'grumpig',
        'squawkabilly-green-plumage',
        'squawkabilly-blue-plumage',
        'squawkabilly-yellow-plumage',
        'squawkabilly-white-plumage',
        'misdreavus',
        'mismagius',
        'makuhita',
        'hariyama',
        'crabrawler',
        'crabominable',
        'salandit',
        'salazzle',
        'phanpy',
        'donphan-male',
        'donphan-female',
        'cufant',
        'copperajah',
        'gible-male',
        'gible-female',
        'gabite-male',
        'gabite-female',
        'garchomp-male',
        'garchomp-female',
        'nacli',
        'naclstack',
        'garganacl',
        'wingull',
        'pelipper',
        'magikarp-male',
        'magikarp-female',
        'gyarados-male',
        'gyarados-female',
        'arrokuda',
        'barraskewda',
        'basculin-red-striped',
        'basculin-blue-striped',
        'gulpin-male',
        'gulpin-female',
        'swalot-male',
        'swalot-female',
        'meowth',
        'persian',
        'drifloon',
        'drifblim',
        'flabebe-red',
        'flabebe-white',
        'flabebe-orange',
        'flabebe-yellow',
        'flabebe-blue',
        'floette-red',
        'floette-white',
        'floette-orange',
        'floette-yellow',
        'floette-blue',
        'florges-red',
        'florges-white',
        'florges-orange',
        'florges-yellow',
        'florges-blue',
        'diglett',
        'dugtrio',
        'torkoal',
        'numel-male',
        'numel-female',
        'camerupt-male',
        'camerupt-female',
        'bronzor',
        'bronzong',
        'axew',
        'fraxure',
        'haxorus',
        'mankey',
        'primeape',
        'annihilape',
        'meditite-male',
        'meditite-female',
        'medicham-male',
        'medicham-female',
        'riolu',
        'lucario',
        'charcadet',
        'armarouge',
        'ceruledge',
        'barboach',
        'whiscash',
        'tadbulb',
        'bellibolt',
        'goomy',
        'sliggoo',
        'goodra',
        'croagunk-male',
        'croagunk-female',
        'toxicroak-male',
        'toxicroak-female',
        'wattrel',
        'kilowattrel',
        'eevee-male',
        'eevee-female',
        'vaporeon',
        'jolteon',
        'flareon',
        'espeon',
        'umbreon',
        'leafeon',
        'glaceon',
        'sylveon',
        'dunsparce',
        'dudunsparce-two-segment',
        'dudunsparce-three-segment',
        'deerling-spring',
        'deerling-summer',
        'deerling-autumn',
        'deerling-winter',
        'sawsbuck-spring',
        'sawsbuck-summer',
        'sawsbuck-autumn',
        'sawsbuck-winter',
        'girafarig-male',
        'girafarig-female',
        'farigiraf',
        'grimer',
        'muk',
        'maschiff',
        'mabosstiff',
        'toxel',
        'toxtricity-amped',
        'toxtricity-low-key',
        'dedenne',
        'pachirisu-male',
        'pachirisu-female',
        'shroodle',
        'grafaiai',
        'stantler',
        'foongus',
        'amoonguss',
        'voltorb',
        'electrode',
        'magnemite',
        'magneton',
        'magnezone',
        'ditto',
        'growlithe',
        'arcanine',
        'teddiursa',
        'ursaring-male',
        'ursaring-female',
        'zangoose',
        'seviper',
        'swablu',
        'altaria',
        'skiddo',
        'gogoat',
        'tauros-paldean-combat-breed',
        'tauros-paldean-blaze-breed',
        'tauros-paldean-aqua-breed',
        'litleo',
        'pyroar-male',
        'pyroar-female',
        'stunky',
        'skuntank',
        'zorua',
        'zoroark',
        'sneasel-male',
        'sneasel-female',
        'weavile-male',
        'weavile-female',
        'murkrow-male',
        'murkrow-female',
        'honchkrow',
        'gothita',
        'gothorita',
        'gothitelle',
        'sinistea-phony',
        'sinistea-antique',
        'polteageist-phony',
        'polteageist-antique',
        'mimikyu',
        'klefki',
        'indeedee-male',
        'indeedee-female',
        'bramblin',
        'brambleghast',
        'toedscool',
        'toedscruel',
        'tropius',
        'fomantis',
        'lurantis',
        'klawf',
        'capsakid',
        'scovillain',
        'cacnea',
        'cacturne-male',
        'cacturne-female',
        'rellor',
        'rabsca',
        'venonat',
        'venomoth',
        'pineco',
        'forretress',
        'scyther-male',
        'scyther-female',
        'scizor-male',
        'scizor-female',
        'heracross-male',
        'heracross-female',
        'flittle',
        'espathra',
        'hippopotas-male',
        'hippopotas-female',
        'hippowdon-male',
        'hippowdon-female',
        'sandile',
        'krokorok',
        'krookodile',
        'silicobra',
        'sandaconda',
        'mudbray',
        'mudsdale',
        'larvesta',
        'volcarona',
        'bagon',
        'shelgon',
        'salamence',
        'tinkatink',
        'tinkatuff',
        'tinkaton',
        'hatenna',
        'hattrem',
        'hatterene',
        'impidimp',
        'morgrem',
        'grimmsnarl',
        'wiglett',
        'wugtrio',
        'bombirdier',
        'finizen',
        'palafin',
        'varoom',
        'revavroom',
        'cyclizar',
        'orthworm',
        'sableye',
        'shuppet',
        'banette',
        'falinks',
        'hawlucha',
        'spiritomb',
        'noibat',
        'noivern',
        'dreepy',
        'drakloak',
        'dragapult',
        'glimmet',
        'glimmora',
        'rotom-normal',
        'rotom-heat',
        'rotom-wash',
        'rotom-mow',
        'rotom-frost',
        'rotom-fan',
        'greavard',
        'houndstone',
        'oranguru',
        'passimian',
        'komala',
        'larvitar',
        'pupitar',
        'tyranitar',
        'stonjourner',
        'eiscue',
        'pincurchin',
        'sandygast',
        'palossand',
        'slowpoke',
        'slowbro',
        'slowking',
        'shellos-west',
        'shellos-east',
        'gastrodon-west',
        'gastrodon-east',
        'shellder',
        'cloyster',
        'qwilfish',
        'luvdisc',
        'finneon-male',
        'finneon-female',
        'lumineon-male',
        'lumineon-female',
        'bruxish',
        'alomomola',
        'skrelp',
        'dragalge',
        'clauncher',
        'clawitzer',
        'tynamo',
        'eelektrik',
        'eelektross',
        'mareanie',
        'toxapex',
        'flamigo',
        'dratini',
        'dragonair',
        'dragonite',
        'snom',
        'frosmoth',
        'snover-male',
        'snover-female',
        'abomasnow-male',
        'abomasnow-female',
        'delibird',
        'cubchoo',
        'beartic',
        'snorunt',
        'glalie',
        'froslass',
        'cryogonal',
        'cetoddle',
        'cetitan',
        'bergmite',
        'avalugg',
        'rufflet',
        'braviary',
        'pawniard',
        'bisharp',
        'kingambit',
        'deino',
        'zweilous',
        'hydreigon',
        'veluza',
        'dondozo',
        'tatsugiri-curly',
        'tatsugiri-droopy',
        'tatsugiri-stretchy',
        'great-tusk',
        'scream-tail',
        'brute-bonnet',
        'flutter-mane',
        'slither-wing',
        'sandy-shocks',
        'iron-treads',
        'iron-bundle',
        'iron-hands',
        'iron-jugulis',
        'iron-moth',
        'iron-thorns',
        'frigibax',
        'arctibax',
        'baxcalibur',
        'gimmighoul',
        'gholdengo',
        'wo-chien',
        'chien-pao',
        'ting-lu',
        'chi-yu',
        'roaring-moon',
        'iron-valiant',
        'koraidon',
        'miraidon',
    ]
    kitakami = [
        'spinarak',
        'ariados',
        'yanma',
        'yanmega',
        'wooper-male',
        'wooper-female',
        'quagsire-male',
        'quagsire-female',
        'poochyena',
        'mightyena',
        'volbeat',
        'illumise',
        'corphish',
        'crawdaunt',
        'sewaddle',
        'swadloon',
        'leavanny',
        'cutiefly',
        'ribombee',
        'ekans',
        'arbok',
        'bellsprout',
        'weepinbell',
        'victreebel',
        'sentret',
        'furret',
        'dipplin',
        'vulpix',
        'ninetales',
        'poliwag',
        'poliwhirl',
        'poliwrath',
        'politoed-male',
        'politoed-female',
        'hoothoot',
        'noctowl',
        'aipom-male',
        'aipom-female',
        'ambipom-male',
        'ambipom-female',
        'swinub',
        'piloswine-male',
        'piloswine-female',
        'mamoswine-male',
        'mamoswine-female',
        'seedot',
        'nuzleaf-male',
        'nuzleaf-female',
        'shiftry-male',
        'shiftry-female',
        'phantump',
        'trevenant',
        'poltchageist-counterfeit',
        'poltchageist-artisan',
        'sinistcha-unremarkable',
        'sinistcha-masterpiece',
        'geodude',
        'graveler',
        'golem',
        'timburr',
        'gurdurr',
        'conkeldurr',
        'morpeko',
        'munchlax',
        'snorlax',
        'lotad',
        'lombre',
        'ludicolo-male',
        'ludicolo-female',
        'nosepass',
        'probopass',
        'grubbin',
        'charjabug',
        'vikavolt',
        'sandshrew',
        'sandslash',
        'gligar-male',
        'gligar-female',
        'gliscor',
        'vullaby',
        'mandibuzz',
        'jangmo-o',
        'hakamo-o',
        'kommo-o',
        'koffing',
        'weezing',
        'mienfoo',
        'mienshao',
        'duskull',
        'dusclops',
        'dusknoir',
        'chingling',
        'chimecho',
        'slugma',
        'magcargo',
        'litwick',
        'lampent',
        'chandelure',
        'cleffa',
        'clefairy',
        'clefable',
        'feebas',
        'milotic-male',
        'milotic-female',
        'carbink',
        'ducklett',
        'swanna',
        'cramorant',
        'basculin-white-striped',
        'basculegion-male',
        'basculegion-female',
        'ursaluna-bloodmoon',
        'okidogi',
        'munkidori',
        'fezandipiti',
        'ogerpon',
    ]
    blueberry = [
        'doduo-male',
        'doduo-female',
        'dodrio-male',
        'dodrio-female',
        'exeggcute',
        'exeggutor',
        'exeggutor-alola',
        'rhyhorn-male',
        'rhyhorn-female',
        'rhydon-male',
        'rhydon-female',
        'rhyperior-male',
        'rhyperior-female',
        'elekid',
        'electabuzz',
        'electivire',
        'magby',
        'magmar',
        'magmortar',
        'kleavor',
        'tauros',
        'blitzle',
        'zebstrika',
        'smeargle',
        'milcery',
        'alcremie-vanilla-cream-berry',
        'alcremie-ruby-cream-berry',
        'alcremie-caramel-swirl-berry',
        'alcremie-ruby-swirl-berry',
        'alcremie-matcha-cream-berry',
        'alcremie-salted-cream-berry',
        'alcremie-lemon-cream-berry',
        'alcremie-mint-cream-berry',
        'alcremie-rainbow-swirl-berry',
        'alcremie-vanilla-cream-flower',
        'alcremie-ruby-cream-flower',
        'alcremie-caramel-swirl-flower',
        'alcremie-ruby-swirl-flower',
        'alcremie-matcha-cream-flower',
        'alcremie-salted-cream-flower',
        'alcremie-lemon-cream-flower',
        'alcremie-mint-cream-flower',
        'alcremie-rainbow-swirl-flower',
        'alcremie-vanilla-cream-strawberry',
        'alcremie-ruby-cream-strawberry',
        'alcremie-caramel-swirl-strawberry',
        'alcremie-ruby-swirl-strawberry',
        'alcremie-matcha-cream-strawberry',
        'alcremie-salted-cream-strawberry',
        'alcremie-lemon-cream-strawberry',
        'alcremie-mint-cream-strawberry',
        'alcremie-rainbow-swirl-strawberry',
        'alcremie-vanilla-cream-heart',
        'alcremie-ruby-cream-heart',
        'alcremie-caramel-swirl-heart',
        'alcremie-ruby-swirl-heart',
        'alcremie-matcha-cream-heart',
        'alcremie-salted-cream-heart',
        'alcremie-lemon-cream-heart',
        'alcremie-mint-cream-heart',
        'alcremie-rainbow-swirl-heart',
        'alcremie-vanilla-cream-clover',
        'alcremie-ruby-cream-clover',
        'alcremie-caramel-swirl-clover',
        'alcremie-ruby-swirl-clover',
        'alcremie-matcha-cream-clover',
        'alcremie-salted-cream-clover',
        'alcremie-lemon-cream-clover',
        'alcremie-mint-cream-clover',
        'alcremie-rainbow-swirl-clover',
        'alcremie-vanilla-cream-ribbon',
        'alcremie-ruby-cream-ribbon',
        'alcremie-caramel-swirl-ribbon',
        'alcremie-ruby-swirl-ribbon',
        'alcremie-matcha-cream-ribbon',
        'alcremie-salted-cream-ribbon',
        'alcremie-lemon-cream-ribbon',
        'alcremie-mint-cream-ribbon',
        'alcremie-rainbow-swirl-ribbon',
        'alcremie-vanilla-cream-star',
        'alcremie-ruby-cream-star',
        'alcremie-caramel-swirl-star',
        'alcremie-ruby-swirl-star',
        'alcremie-matcha-cream-star',
        'alcremie-salted-cream-star',
        'alcremie-lemon-cream-star',
        'alcremie-mint-cream-star',
        'alcremie-rainbow-swirl-star',
        'trapinch',
        'vibrava',
        'flygon',
        'pikipek',
        'trumbeak',
        'toucannon',
        'tentacool',
        'tentacruel',
        'horsea',
        'seadra',
        'kingdra',
        'cottonee',
        'whimsicott',
        'comfey',
        'oddish',
        'gloom-male',
        'gloom-female',
        'vileplume-male',
        'vileplume-female',
        'bellossom',
        'diglett-alola',
        'dugtrio-alola',
        'grimer-alola',
        'muk-alola',
        'slowpoke-galar',
        'slowbro-galar',
        'slowking-galar',
        'chinchou',
        'lanturn',
        'inkay',
        'malamar',
        'dewpider',
        'araquanid',
        'tyrogue',
        'hitmonlee',
        'hitmonchan',
        'hitmontop',
        'geodude-alola',
        'graveler-alola',
        'golem-alola',
        'drilbur',
        'excadrill',
        'espurr',
        'meowstic-male',
        'meowstic-female',
        'minior-red',
        'minior-indigo',
        'minior-yellow',
        'minior-green',
        'minior-blue',
        'minior-orange',
        'minior-violet',
        'cranidos',
        'rampardos',
        'shieldon',
        'bastiodon',
        'minccino',
        'cinccino',
        'skarmory',
        'plusle',
        'minun',
        'scraggy',
        'scrafty',
        'golett',
        'golurk',
        'porygon',
        'porygon2',
        'porygon-z',
        'joltik',
        'galvantula',
        'beldum',
        'metang',
        'metagross',
        'seel',
        'dewgong',
        'lapras',
        'qwilfish-hisui',
        'overqwil',
        'solosis',
        'duosion',
        'reuniclus',
        'snubbull',
        'granbull',
        'sandshrew-alola',
        'sandslash-alola',
        'vulpix-alola',
        'ninetales-alola',
        'duraludon',
        'archaludon',
        'hydrapple',
        'bulbasaur',
        'ivysaur',
        'venusaur-male',
        'venusaur-female',
        'charmander',
        'charmeleon',
        'charizard',
        'squirtle',
        'wartortle',
        'blastoise',
        'chikorita',
        'bayleef',
        'meganium-male',
        'meganium-female',
        'cyndaquil',
        'quilava',
        'typhlosion',
        'totodile',
        'croconaw',
        'feraligatr',
        'treecko',
        'grovyle',
        'sceptile',
        'torchic-male',
        'torchic-female',
        'combusken-male',
        'combusken-female',
        'blaziken-male',
        'blaziken-female',
        'mudkip',
        'marshtomp',
        'swampert',
        'turtwig',
        'grotle',
        'torterra',
        'chimchar',
        'monferno',
        'infernape',
        'piplup',
        'prinplup',
        'empoleon',
        'snivy',
        'servine',
        'serperior',
        'tepig',
        'pignite',
        'emboar',
        'oshawott',
        'dewott',
        'samurott',
        'chespin',
        'quilladin',
        'chesnaught',
        'fennekin',
        'braixen',
        'delphox',
        'froakie',
        'frogadier',
        'greninja',
        'rowlet',
        'dartrix',
        'decidueye',
        'litten',
        'torracat',
        'incineroar',
        'popplio',
        'brionne',
        'primarina',
        'grookey',
        'thwackey',
        'rillaboom',
        'scorbunny',
        'raboot',
        'cinderace',
        'sobble',
        'drizzile',
        'inteleon',
        'gouging-fire',
        'raging-bolt',
        'iron-boulder',
        'iron-crown',
        'terapagos',
        'walking-wake',
        'iron-leaves',
        'pecharunt',
    ]

    with open('src/data/all_for_boxes.json') as f:
        full: tp.Dict[str, tp.List[tp.Dict[str, tp.Any]]] = json.load(f)

    f_l: tp.Dict[str, tp.List[dict]] = {'31': [], '32': [], '33': []}

    for d in ((paldea, '31'), (kitakami, '32'), (blueberry, '33')):
        l, n = d
        seen_names: tp.List[str] = []
        p: str
        for p in l:
            pok = next((x for x in full.get(n, []) if x['name'] == p), None)
            if not pok:
                # print('nofind', p)
                pcheck = p.split('-')[0]
                pok = next((x for x in full.get(n, []) if x['name'] == pcheck), None)
                if not pok:
                    # print('nofind2', pcheck)
                    pok = next((x for x in full.get(n, []) if x['name'].split('-')[0] == p), None)
                    if not pok:
                        pok = next((x for x in full.get(n, []) if x['name'] == '-'.join(p.split('-')[:-1])), None)
                        if not pok:
                            print('ERROR: could not find:', p)
                            continue

            new_pok = pok.copy()
            new_pok['name'] = p
            if pok['name'] in seen_names:
                new_pok['alt'] = True

            f_l[n].append(new_pok)
            seen_names.append(pok['name'])

    with open('src/data/for-pretty.json', 'w') as f:
        json.dump(f_l, f, indent=2)


def pretty_boxes() -> None:
    print('Running pretty boxes')
    skip_dupes = True

    brows = 5
    bcols = 6
    bsize = brows * bcols

    spaces = 18
    c_size = 14
    fmt = f'^{spaces}'
    ln = (spaces * bcols) + bcols + 1

    # with open('src/data/final_evos.json') as f:
    #     full: tp.Dict[str, tp.List[EvoDict]] = json.load(f)
    # with open('src/data/final_evos-alt.json') as f:
    #     alt: tp.Dict[str, tp.List[EvoDict]] = json.load(f)

    with open('src/data/for-pretty.json') as f:
        full: tp.Dict[str, tp.List[EvoDict]] = json.load(f)
    # with open('src/data/final_evos_b-alt.json') as f:
    #     alt: tp.Dict[str, tp.List[EvoDict]] = json.load(f)

    seen_ids: tp.List[str] = []

    print('DEFAULT')
    for k, v in full.items():
        print('====')
        print(k)
        print('====')

        new_v: tp.List[EvoDict] = []
        for fi in v:
            if fi['name'] not in seen_ids:
                if fi['final'] and not fi['alt']:
                    seen_ids.append(fi['name'])
                    new_v.append(fi)
            else:
                if skip_dupes:
                    print('skipping', fi['name'])
                    pass

        list_v = new_v if skip_dupes else v

        start = 1
        for i in range(0, len(list_v), bsize):
            box = list_v[i:i + bsize]
            end = box[-1]['dex_id']
            print(f'{"-" * round((ln - c_size) / 2)}{f"{k}: {start}-{end}": ^{c_size}}{"-" * math.floor((ln - c_size) / 2)}')
            for z in range(0, len(box), bcols):
                zd = [''] * bcols
                for j, x in enumerate(box[z:z + bcols]):
                    zd[j] = x['name']
                print(f'|{zd[0]: {fmt}}|{zd[1]: {fmt}}|{zd[2]: {fmt}}|{zd[3]: {fmt}}|{zd[4]: {fmt}}|{zd[5]: {fmt}}|')
            print('-' * ln)
            start = end + 1

    seen_ids: tp.List[str] = []

    print('ALT')
    for k, v in full.items():
        print('====')
        print(k)
        print('====')

        spaces = 28
        c_size = 14
        fmt = f'^{spaces}'
        ln = (spaces * bcols) + bcols + 1

        new_v: tp.List[EvoDict] = []
        for fi in v:
            if fi['name'] not in seen_ids:
                if fi['final'] and fi['alt']:
                    seen_ids.append(fi['name'])
                    new_v.append(fi)
            else:
                if skip_dupes:
                    print('skipping', fi['name'])
                    pass

        list_v = new_v if skip_dupes else v

        start = 1
        for i in range(0, len(list_v), bsize):
            box = list_v[i:i + bsize]
            end = box[-1]['dex_id']
            print(f'{"-" * round((ln - c_size) / 2)}{f"{k}: {start}-{end}": ^{c_size}}{"-" * math.ceil((ln - c_size) / 2)}')
            for z in range(0, len(box), bcols):
                zd = [''] * bcols
                for j, x in enumerate(box[z:z + bcols]):
                    zd[j] = x['name']
                print(f'|{zd[0]: {fmt}}|{zd[1]: {fmt}}|{zd[2]: {fmt}}|{zd[3]: {fmt}}|{zd[4]: {fmt}}|{zd[5]: {fmt}}|')
            print('-' * ln)
            start = end + 1


if __name__ == '__main__':
    # boxes()
    # better_boxes()
    net_boxes()
    pretty_boxes()

    print('done')
