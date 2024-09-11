import logging
import typing as tp

from more_itertools import first_true

import pokebase as pb
from pokebase.cache import SHELVE_CACHE
from src.typs import get_combo_name
from src.utils import Chain, Species, dump_to, unavailable_sv

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger('requests.packages.urllib3')
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True


def flatten(l: tp.List['Chain']) -> tp.List['Chain']:
    result = []
    for el in l:
        result.append(el)
        if len(el.evolves_to):
            result.extend(flatten(el.evolves_to))
    return result


def find_is_final(d: Chain, s: Species) -> bool | None:
    if s.name in ('stantler', 'ursaring', 'qwilfish'): return True
    if not len(d.evolves_to): return True

    evos = flatten(d.evolves_to)
    found = first_true(evos + [d], pred=lambda x: x.species.id == s.id)
    if not found:
        return None
    else:
        return not len(found.evolves_to)


def find_evolves_to(d: Chain, s: Species) -> tp.List[str] | None:
    if s.name in ('stantler', 'ursaring', 'qwilfish'): return None
    if not len(d.evolves_to): return None

    evos = flatten(d.evolves_to)
    found = first_true(evos + [d], pred=lambda x: x.species.id == s.id)
    if not found:
        return None  # False
    else:
        return [f.species.name for f in found.evolves_to]


def main() -> None:
    print('Running main')
    dexes = [1]
    # dexes = [30, 33, 32, 31]
    # dexes = [31, 32, 33]

    data = {}

    diff_limit = 0.15

    for dex in dexes:
        dex_data = pb.pokedex(dex)

        for entry in dex_data.pokemon_entries:
            species: Species = entry.pokemon_species

            # name = f'{species.name} ({dex})'
            pname = species.name

            if pname in unavailable_sv:
                print(f'{entry.entry_number} - {pname}: SKIPPED')
                continue

            print(f'{entry.entry_number} - {pname}')

            chain = species.evolution_chain.chain
            et = find_evolves_to(chain, species)

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
                'evolves_to': et,
                'is_baby': species.is_baby,
                'is_legendary': species.is_legendary,
                'is_mythical': species.is_mythical,
            }

            varieties = species.varieties
            for variety in varieties:
                pok = variety.pokemon
                if not any(
                    # n in pok.name for n in ('-gmax', '-galar', '-mega', '-totem')
                    pok.name.endswith(n) for n in (
                        '-gmax', '-mega', '-mega-x', 'mega-y', '-totem', '-build', '-mode', '-eternamax', '-ash', '-busted',
                        '-totem-disguised')
                ):
                    if pok.name != pname:
                        print(f'    {pok.name}')

                    base_v = base_data.copy()

                    types = pok.types
                    pstats = pok.stats
                    typ = get_combo_name(
                        types[0].type.name,
                        types[1].type.name if len(types) > 1 else None,
                    )
                    abilities = [{
                        'hidden': a.is_hidden,
                        'name': a.ability.name,
                        'desc': next((ax.short_effect for ax in a.ability.effect_entries if ax.language.name == 'en'), None),
                        'flavor': next(
                            (ft.flavor_text for ft in a.ability.flavor_text_entries if ft.language.name == 'en' and ft.version_group.name == 'x-y'),
                            None
                        ) or next(
                            (ft.flavor_text for ft in a.ability.flavor_text_entries if ft.language.name == 'en'),
                            None
                        )
                    } for a in pok.abilities]

                    stats = {s.stat.name: s.base_stat for s in pstats}

                    atk_diff = (stats['attack'] - stats['special-attack']) / stats['attack']
                    def_diff = (stats['defense'] - stats['special-defense']) / stats['defense']

                    if atk_diff < -diff_limit:
                        atk_type = 'SpA'
                    elif atk_diff > diff_limit:
                        atk_type = 'Atk'
                    else:
                        atk_type = 'Any'

                    if def_diff < -diff_limit:
                        def_type = 'SpD'
                    elif def_diff > diff_limit:
                        def_type = 'Def'
                    else:
                        def_type = 'Any'

                    more_stats = {
                        **stats,
                        'max_atk': max(stats['attack'], stats['special-attack']),
                        'max_def': max(stats['defense'], stats['special-defense']),
                        'sum_def': stats['defense'] + stats['special-defense'],
                        'tot': sum(stats.values()),
                        'tot_b': sum(stats.values()) - stats['speed'],
                        'atk_type': atk_type,
                        'def_type': def_type,
                    }

                    base_v['is_default'] = variety.is_default
                    base_v['id'] = pok.id
                    base_v['type'] = typ
                    base_v['name'] = pok.name
                    base_v['abilities'] = abilities
                    base_v.update(more_stats)

                    data[pok.name] = base_v

                    if pname in ('bulbasaur', 'zapdos', 'urshifu', 'iron-hands'): print(pok.name, data[pok.name])

    filename = 'pokes-all-2'
    dump_to(filename, data)
    # print(json.dumps(data, indent=2))

    SHELVE_CACHE.close()


if __name__ == '__main__':
    main()

    print('done')
