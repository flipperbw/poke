import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.serebii.net"
START = "https://www.serebii.net/legendsz-a/hyperspacelumiose.shtml"

TYPE_LINK_RE = re.compile(r"/legendsz-a/hyperspacewildzone/[^/]+\.shtml$", re.I)
POKE_IMG_RE = re.compile(r"/legendsz-a/pokemon/(icons/)?\d+.*\.png$", re.I)

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    }
)

def fetch_soup(url: str) -> BeautifulSoup:
    r = session.get(url, timeout=60)
    r.raise_for_status()

    # Serebii sometimes trips decoders; force a sane single-byte decode.
    # (This also fixes some “unicode decoding” headaches.)
    r.encoding = r.encoding or "ISO-8859-1"
    return BeautifulSoup(r.text, "html.parser")

def abs_url(u: str) -> str:
    return urljoin(BASE, u)

def clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def pokemon_name_from_img(img) -> str:
    # Best sources first
    for attr in ("alt", "title"):
        if img.has_attr(attr):
            v = clean_ws(img.get(attr))
            if v:
                return v

    # Sometimes the image is wrapped in <a> with text
    a = img.find_parent("a")
    if a:
        t = clean_ws(a.get_text(" ", strip=True))
        if t:
            return t

    # Fallback: parse dex-ish part from filename
    m = re.search(r"/(\d+)[^/]*\.png$", img.get("src", ""))
    if m:
        return f"#{m.group(1)}"
    return ""

def find_zone_name(wild_table) -> str:
    """
    Zone name usually appears just before the wild pokemon table.
    We look backwards for a nearby text node containing 'Wild Zone'.
    """
    txt = wild_table.find_previous(string=re.compile(r"Wild Zone", re.I))
    if txt:
        # Try to use a compact parent chunk, not the entire page
        parent = txt.parent
        candidate = clean_ws(parent.get_text(" ", strip=True))
        # If that parent is too noisy, just use the matched text itself
        if 5 <= len(candidate) <= 120:
            return candidate
        return clean_ws(str(txt))
    return "Unknown Zone"

def iter_zone_wild_tables(type_page_soup: BeautifulSoup):
    """
    Find each zone’s 'Wild Pokémon' table.
    Serebii pages generally use multiple repeated blocks; we locate tables that
    contain a header cell with 'Wild Pokémon'.
    """
    for table in type_page_soup.find_all("table"):
        # a header cell containing 'Wild Pokémon'
        header = table.find(string=re.compile(r"^\s*Wild Pokémon\s*$", re.I))
        if header:
            yield table

def extract_zone_pokemon(wild_table):
    """
    Return:
      - list of pokemon image URLs (absolute) found in the Wild Pokémon table
      - dict img_url -> name
      - other pokemon names in this zone (unique, in appearance order)
    """
    seen = set()
    ordered_imgs = []
    img_to_name = {}

    # Only consider pokemon images in this table, ignore UI icons etc
    for img in wild_table.find_all("img"):
        src = img.get("src", "")
        if not src:
            continue
        if not POKE_IMG_RE.search(src):
            continue
        full = abs_url(src)
        if full in seen:
            continue
        seen.add(full)
        ordered_imgs.append(full)
        nm = pokemon_name_from_img(img)
        img_to_name[full] = nm

    other_names = []
    for u in ordered_imgs:
        nm = img_to_name.get(u, "")
        if nm and nm not in other_names:
            other_names.append(nm)

    return ordered_imgs, img_to_name, other_names

def get_type_links():
    soup = fetch_soup(START)

    # Grab the type list block by matching the href pattern
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if TYPE_LINK_RE.search(href):
            links.append(abs_url(href))

    # Deduplicate preserving order
    out = []
    seen = set()
    for u in links:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def type_name_from_url(url: str) -> str:
    # .../hyperspacewildzone/normal.shtml -> Normal
    m = re.search(r"/hyperspacewildzone/([^/]+)\.shtml$", url, re.I)
    if not m:
        return "Unknown"
    slug = m.group(1).lower()
    if slug == "special":
        return "Legendary"
    return slug.capitalize()

@dataclass
class Appearance:
    type_name: str
    zone_url: str
    zone_name: str
    other_pokemon_names: list

def main(out_csv_path="rare_pokemon_zones.csv", max_zones=3):
    type_links = get_type_links()

    # pokemon_img_url -> {"name": str, "apps": [Appearance, ...]}
    pokemon = defaultdict(lambda: {"name": "", "apps": []})

    # First pass: collect per-zone membership and store “other pokemon” list for each zone
    for type_url in type_links:
        tname = type_name_from_url(type_url)
        soup = fetch_soup(type_url)

        for wild_table in iter_zone_wild_tables(soup):
            zone_name = find_zone_name(wild_table)

            imgs, img_to_name, other_names = extract_zone_pokemon(wild_table)

            # zone_url: we usually only have the type page url; keep it stable
            zone_url = type_url

            for img_url in imgs:
                nm = img_to_name.get(img_url, "")
                if nm and not pokemon[img_url]["name"]:
                    pokemon[img_url]["name"] = nm

                pokemon[img_url]["apps"].append(
                    Appearance(
                        type_name=tname,
                        zone_url=zone_url,
                        zone_name=zone_name,
                        other_pokemon_names=other_names,  # names only, full wild list
                    )
                )

    # Second pass: filter and write rows
    rows = []
    for img_url, info in pokemon.items():
        total = len(info["apps"])
        if total <= max_zones:
            name = info["name"] or ""
            for app in info["apps"]:
                # other_pokemon_in_zone: names only, include everyone in the zone (including this pokemon)
                other_str = "; ".join(app.other_pokemon_names)

                rows.append(
                    {
                        "pokemon_image_url": img_url,
                        "pokemon_name": name,
                        "total_zones": total,
                        "type": app.type_name,
                        "other_pokemon_in_zone": other_str,
                        "zone_url": app.zone_url,
                        "zone_name": app.zone_name,  # at the end
                    }
                )

    # Deterministic output
    rows.sort(key=lambda r: (r["total_zones"], r["pokemon_name"], r["type"], r["zone_name"]))

    with open(out_csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "pokemon_image_url",
                "pokemon_name",
                "total_zones",
                "type",
                "other_pokemon_in_zone",
                "zone_url",
                "zone_name",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out_csv_path}")

if __name__ == "__main__":
    main()
