import json

import pokebase as pb
from src.typs import get_combo_name


# logging.basicConfig()
# logging.getLogger().setLevel(logging.DEBUG)
# requests_log = logging.getLogger('requests.packages.urllib3')
# requests_log.setLevel(logging.DEBUG)
# requests_log.propagate = True


def main() -> None:
    dexes = [31, 32, 33]

    data = {}

    for dex in dexes:
        dex_data = pb.pokedex(dex)

        for entry in dex_data.pokemon_entries:
            species = entry.pokemon_species
            eggs = species.egg_groups
            name = f'{species.name} ({dex})'
            pname = species.name
            print(f'{entry.entry_number} - {name}')
            data[name] = {
                'dex_id': entry.entry_number,
                'name': pname,
                'dex': dex,
                'capture_rate': species.capture_rate,
                'egg_groups': [x.name for x in eggs],
                'evolves_from': (
                    species.evolves_from_species.name
                    if species.evolves_from_species
                    else None
                ),
                'is_baby': species.is_baby,
                'is_legendary': species.is_legendary,
                'is_mythical': species.is_mythical,
                'varieties': [],
            }

            varieties = species.varieties
            for variety in varieties:
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
                    'sum_def': stats['defense'] + stats['special-defense'],
                    'tot': sum(stats.values()),
                }
                if variety.is_default:
                    data[name]['id'] = pok.id
                    data[name]['type'] = typ
                    data[name]['stats'] = more_stats
                else:
                    if not any(
                        n in pok.name for n in ('-gmax', '-galar', '-mega', '-totem')
                    ):
                        data[name]['varieties'].append(
                            {
                                'id': pok.id,
                                'name': pok.name,
                                'type': typ,
                                'stats': more_stats,
                            }
                        )

            # print(name, data[name])

    with open('src/data/pokes.json', 'w') as f:
        json.dump(data, f, indent=2)
    # print(json.dumps(data, indent=2))


if __name__ == '__main__':
    main()
    print('done')
