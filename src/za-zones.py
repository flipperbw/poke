import re
import csv
from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.serebii.net/legendsz-a/hyperspacewildzone/"

# All pages from your Hyperspace Lumiose list
TYPE_PAGES = {
    "Normal":   urljoin(BASE, "normal.shtml"),
    "Fighting": urljoin(BASE, "fighting.shtml"),
    "Flying":   urljoin(BASE, "flying.shtml"),
    "Poison":   urljoin(BASE, "poison.shtml"),
    "Ground":   urljoin(BASE, "ground.shtml"),
    "Rock":     urljoin(BASE, "rock.shtml"),
    "Bug":      urljoin(BASE, "bug.shtml"),
    "Ghost":    urljoin(BASE, "ghost.shtml"),
    "Steel":    urljoin(BASE, "steel.shtml"),
    "Fire":     urljoin(BASE, "fire.shtml"),
    "Water":    urljoin(BASE, "water.shtml"),
    "Grass":    urljoin(BASE, "grass.shtml"),
    "Electric": urljoin(BASE, "electric.shtml"),
    "Psychic":  urljoin(BASE, "psychic.shtml"),
    "Ice":      urljoin(BASE, "ice.shtml"),
    "Dragon":   urljoin(BASE, "dragon.shtml"),
    "Dark":     urljoin(BASE, "dark.shtml"),
    "Fairy":    urljoin(BASE, "fairy.shtml"),
    # "Legendary Pokémon Wild Zones" on Serebii is "special.shtml"
    "Legendary": urljoin(BASE, "special.shtml"),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
}

STAR_RE = re.compile(r"(?:^|\s)([1-5])\s*Star|★\s*([1-5])|([1-5])\s*★", re.I)
WILD_ZONE_RE = re.compile(r"\bWild Zone\b", re.I)


@dataclass(frozen=True)
class Appearance:
    type_name: str
    star: int
    zone_name: str
    zone_url: str
    # full wild list for the zone (names + image urls)
    zone_wild: tuple  # tuple[tuple[name, image_url], ...]


def absolutize_img(src: str, page_url: str) -> str:
    if not src:
        return ""
    return urljoin(page_url, src)


def infer_name(a_tag, img_tag) -> str:
    """
    Robust name extraction:
    1) img alt
    2) img title
    3) anchor text
    4) dex number from filename as fallback (e.g. '681')
    """
    for cand in [
        (img_tag.get("alt") if img_tag else None),
        (img_tag.get("title") if img_tag else None),
        (a_tag.get_text(" ", strip=True) if a_tag else None),
    ]:
        if cand:
            cand = cand.strip()
            if cand:
                return cand

    # fallback: pull digits from img src
    src = (img_tag.get("src") if img_tag else "") or ""
    m = re.search(r"/(\d+(?:-[a-z0-9]+)?)\.(?:png|gif|jpg|webp)$", src, re.I)
    if m:
        return m.group(1)

    return "Unknown"


def find_star_for_element(el) -> int:
    """
    Walk backwards in the document to find the nearest heading/label containing a star rating.
    This is resilient against Serebii layout changes.
    """
    cur = el
    while cur:
        # Check this node's text
        text = cur.get_text(" ", strip=True) if hasattr(cur, "get_text") else ""
        if text:
            m = STAR_RE.search(text)
            if m:
                for g in m.groups():
                    if g:
                        return int(g)

        # Move to previous sibling, else climb to parent
        prev = getattr(cur, "previous_sibling", None)
        if prev is None:
            cur = getattr(cur, "parent", None)
        else:
            cur = prev

    return 0  # unknown


def extract_zone_name(table) -> str:
    """
    Tries to find 'Wild Zone X' label inside the table.
    """
    text = table.get_text("\n", strip=True)
    # Try a concise first line approach
    for line in text.split("\n"):
        if "Wild Zone" in line:
            return line.strip()
    # fallback
    return "Unknown Zone"


def extract_wild_pokemon_from_table(table, page_url: str):
    """
    The key fix you requested:
    - Only read from the "Wild Pokémon" section within the zone block.
    - Collect all Pokémon icons/links in that section.
    """
    # Find a tag whose text is exactly/contains "Wild Pokémon"
    wild_label = None
    for cand in table.find_all(string=re.compile(r"\bWild Pokémon\b", re.I)):
        wild_label = cand
        break

    if not wild_label:
        return []

    # Heuristic: the "Wild Pokémon" label is usually in a TD/TH,
    # and the actual list is in nearby following nodes within the same table.
    # We'll search forward within the table for <a><img> pairs until we hit another major label.
    container = wild_label.parent
    # Walk forward in document order, bounded to this table
    results = []
    for node in container.next_elements:
        if node == table:
            continue
        if hasattr(node, "find_all") and node.name in ("td", "th", "tr", "div"):
            # Stop if we encounter another section header (Rarity/Base Level/Alpha Chance etc.)
            t = node.get_text(" ", strip=True)
            if re.search(r"\b(Rarity|Base Level|Alpha Chance|Focus)\b", t, re.I):
                break

        if getattr(node, "name", None) == "a":
            img = node.find("img")
            if not img:
                continue
            src = absolutize_img(img.get("src", ""), page_url)
            if not src:
                continue
            name = infer_name(node, img)
            results.append((name, src))

    # Deduplicate by image url (important when the same mon is repeated in the table)
    seen = set()
    dedup = []
    for name, src in results:
        if src in seen:
            continue
        seen.add(src)
        dedup.append((name, src))
    return dedup


def extract_appearances(type_name: str, page_url: str):
    html = requests.get(page_url, headers=HEADERS, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")

    # Serebii uses lots of tables; we only want tables that contain "Wild Zone"
    tables = soup.find_all("table")
    appearances = []

    for tbl in tables:
        if not tbl.get_text(" ", strip=True):
            continue
        if not WILD_ZONE_RE.search(tbl.get_text(" ", strip=True)):
            continue

        # Must contain a "Wild Pokémon" section or it's not a real zone block
        if not re.search(r"\bWild Pokémon\b", tbl.get_text(" ", strip=True), re.I):
            continue

        star = find_star_for_element(tbl)
        zone_name = extract_zone_name(tbl)

        zone_wild = extract_wild_pokemon_from_table(tbl, page_url)
        if not zone_wild:
            continue

        appearances.append(
            Appearance(
                type_name=type_name,
                star=star,
                zone_name=zone_name,
                zone_url=page_url,
                zone_wild=tuple(zone_wild),
            )
        )

    return appearances


def main(out_csv="hyperspace_rare_pokemon.csv", max_zones=3):
    all_appearances = []
    for tname, url in TYPE_PAGES.items():
        print(f"Fetching {tname}: {url}")
        aps = extract_appearances(tname, url)
        print(f"  zones found: {len(aps)}")
        all_appearances.extend(aps)

    # Count how many zones each unique pokemon-image appears in
    zones_by_pokemon_img = defaultdict(set)  # img -> set of (type, star, zone_name)
    name_by_img = {}  # stable-ish name per img (first seen)
    for ap in all_appearances:
        zone_key = (ap.type_name, ap.star, ap.zone_name)
        for name, img in ap.zone_wild:
            zones_by_pokemon_img[img].add(zone_key)
            name_by_img.setdefault(img, name)

    # Filter to those appearing in <= max_zones
    rare_imgs = {img for img, zones in zones_by_pokemon_img.items() if len(zones) <= max_zones}
    print(f"Total unique pokemon-images: {len(zones_by_pokemon_img)}")
    print(f"Rare (<= {max_zones} zones): {len(rare_imgs)}")

    rows = []
    for ap in all_appearances:
        wild_imgs = [img for _, img in ap.zone_wild]
        wild_names = [nm for nm, _ in ap.zone_wild]
        for idx, (name, img) in enumerate(ap.zone_wild):
            if img not in rare_imgs:
                continue

            total = len(zones_by_pokemon_img[img])

            # Other Pokémon in this zone (names only, excludes the current img)
            others = []
            for (oname, oimg) in ap.zone_wild:
                if oimg == img:
                    continue
                others.append(oname)

            rows.append({
                "image_url": img,
                "pokemon_name": name_by_img.get(img, name) or name,
                "total_zone_count": total,
                "type": ap.type_name,
                "star": ap.star,
                "zone_url": ap.zone_url,
                "other_pokemon_in_zone": "; ".join(others),
                "zone_name": ap.zone_name,  # last column per your request
            })

    # Sort: rarest first, then type/star/zone/name
    rows.sort(key=lambda r: (r["total_zone_count"], r["type"], r["star"], r["zone_name"], r["pokemon_name"]))

    # Write CSV
    fieldnames = [
        "image_url",
        "pokemon_name",
        "total_zone_count",
        "type",
        "star",
        "zone_url",
        "other_pokemon_in_zone",
        "zone_name",
    ]

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"Wrote {len(rows)} rows to {out_csv}")


if __name__ == "__main__":
    main(out_csv="hyperspace_rare_pokemon.csv", max_zones=3)
