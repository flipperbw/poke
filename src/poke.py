import argparse
import logging
import typing as tp

from more_itertools import first_true

import pokebase as pb
from pokebase.api import get_data
from pokebase.cache import SHELVE_CACHE, set_cache
from pokebase.common import cache_uri_build
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
    if s.name in ('stantler', 'ursaring', 'qwilfish', 'sawk'): return None
    if not len(d.evolves_to): return None

    evos = flatten(d.evolves_to)
    found = first_true(evos + [d], pred=lambda x: x.species.id == s.id)
    if not found:
        return None  # False
    else:
        return [f.species.name for f in found.evolves_to]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('-d', '--dex', action='append', help='Dex id or name (repeatable). If omitted, defaults to national dex (1).')
    p.add_argument('--cache-dir', help='Directory for pokebase cache. Use a fresh path to avoid stale data.')
    p.add_argument('--skip-unavailable-sv', action='store_true', help='Skip Scarlet/Violet-unavailable mons (legacy behavior). Off by default for ZA.')
    p.add_argument('--vg', action='append', help='Version-group name or id to include when gathering moves (repeatable). If omitted, all version-groups are considered.')
    p.add_argument('--no-tutor', action='store_true', help='Exclude tutor-learned moves from the gathered move lists.')
    return p.parse_args()


def _resolve_dexes(args: argparse.Namespace) -> tp.List[int | str]:
    if not args.dex:
        return [1]
    # Coerce numeric strings to ints to avoid name/id confusion
    ret: tp.List[int | str] = []
    for d in args.dex:
        if isinstance(d, str) and d.isdigit():
            try:
                ret.append(int(d))
                continue
            except ValueError:
                pass
        ret.append(d)
    return ret


def _get_pokedex_resource(dex: int | str):
    """Fetch a pokedex resource ensuring it has pokemon_entries.

    Handles stale cache by invalidating and forcing a fresh lookup when needed.
    """
    pdx = pb.pokedex(dex)
    try:
        # trigger lazy load
        _ = pdx.pokemon_entries
        return pdx
    except AttributeError:
        # Invalidate cached entry and force a fresh fetch
        try:
            uri = cache_uri_build('pokedex', dex, None)
            try:
                del SHELVE_CACHE[uri]
            except Exception:
                pass
            # Force remote fetch and save into cache
            _ = get_data('pokedex', dex, None, force_lookup=True)
        except Exception:
            pass
        # Retry
        pdx = pb.pokedex(dex)
        # If it still fails, let it raise to caller
        _ = pdx.pokemon_entries
        return pdx


def main() -> None:
    args = _parse_args()

    if args.cache_dir:
        set_cache(args.cache_dir)

    print('Running main')
    dexes: tp.List[int | str] = _resolve_dexes(args)

    data = {}

    diff_limit = 0.15

    # Resolve allowed version-groups (by name) if provided
    allowed_vg_names: set[str] | None = None
    allowed_vg_ids: set[int] | None = None
    if args.vg:
        allowed_vg_names = set()
        allowed_vg_ids = set()
        for vg in args.vg:
            try:
                # Allow numeric ids or names
                vgr = pb.version_group(int(vg)) if str(vg).isdigit() else pb.version_group(str(vg))
                allowed_vg_names.add(vgr.name)
                allowed_vg_ids.add(vgr.id)
            except Exception:
                # If resolution fails, keep the raw provided token as a name fallback
                allowed_vg_names.add(str(vg))

    print(f'Dexes: {dexes}')
    for dex in dexes:
        dex_data = _get_pokedex_resource(dex)

        for entry in dex_data.pokemon_entries:
            species: Species = entry.pokemon_species

            # name = f'{species.name} ({dex})'
            pname = species.name

            if args.skip_unavailable_sv and pname in unavailable_sv:
                print(f'{entry.entry_number} - {pname}: SKIPPED (SV unavailable)')
                continue

            print(f'{entry.entry_number} - {pname}')

            # Some evolution chains occasionally fail to materialize from cache/API for specific species.
            # Be resilient: warn and treat as having no evolutions when that happens.
            try:
                chain = species.evolution_chain.chain
                et = find_evolves_to(chain, species)
            except Exception as ex:
                logging.warning(
                    "Failed to read evolution chain for species '%s' (dex %s): %s. Treating as no evolutions.",
                    pname,
                    entry.entry_number,
                    ex,
                )
                et = None

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
                        # '-mega', '-mega-x', 'mega-y',
                        '-gmax', '-totem', '-build', '-mode', '-eternamax', '-ash', '-busted',
                        '-totem-disguised'
                    )
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

                    # Build move list with optional filters for version-group and tutor exclusion
                    moves: tp.List[tp.Dict[str, str]] = []
                    for pm in pok.moves:
                        mv_name = pm.move.name
                        # Consider all version-group details for this move
                        details = list(pm.version_group_details)
                        if not details:
                            continue
                        # # Optionally restrict to allowed version-groups
                        # if allowed_vg_names is not None:
                        #     original_details = details
                        #     if mv_name.lower() == 'earthquake':
                        #         for d in details:
                        #             print(d)
                        #             print(d.version_group)
                        #     details = [
                        #         d for d in details
                        #         if (d.version_group.name in allowed_vg_names)
                        #         or (allowed_vg_ids is not None and d.version_group.id in allowed_vg_ids)
                        #     ]
                        #     if not details:
                        #         # No match for provided version-groups: fallback to any available
                        #         # logging.debug(
                        #         #     "No version-group match for move %s on %s; falling back to latest available entry.",
                        #         #     mv_name,
                        #         #     pok.name,
                        #         # )
                        #         details = original_details
                        # Optionally exclude tutor learn method
                        if args.no_tutor:
                            details_no_tutor = [d for d in details if d.move_learn_method.name != 'tutor']
                            # If all entries are tutor, drop the move
                            details = details_no_tutor or []
                            if not details:
                                continue
                        # Choose the latest entry (highest version-group id) among remaining
                        try:
                            chosen = max(details, key=lambda d: d.version_group.id)
                        except Exception:
                            chosen = details[-1]
                        moves.append({'name': mv_name, 'how': chosen.move_learn_method.name})

                    base_v['is_default'] = variety.is_default
                    base_v['id'] = pok.id
                    base_v['type'] = typ
                    base_v['name'] = pok.name
                    base_v['abilities'] = abilities
                    base_v['moves'] = moves
                    base_v.update(more_stats)

                    data[pok.name] = base_v

                    # if pname in ('bulbasaur', 'zapdos', 'urshifu', 'iron-hands'): print(pok.name, data[pok.name])

    filename = 'pokes-all-za'
    dump_to(filename, data)
    # print(json.dumps(data, indent=2))

    SHELVE_CACHE.close()


if __name__ == '__main__':
    main()

    print('done')
