"""Data for the language feature map (dist/feature-map.html).

Two steps:

  python3 tools/build_wals_map.py --fetch
      Downloads the feature values of WALS Online v2020.4 (CLDF, CC BY 4.0,
      https://github.com/cldf-datasets/wals) and writes the three small tables
      under source-data/wals-features/, which are committed. Run by hand only
      when moving to a new WALS release; it needs network access.

  python3 tools/build_wals_map.py
      Reads those tables, source-data/languages.csv (Glottolog) and
      source-data/wals.csv (WALS languages and their Glottocodes) and writes
      dist/data/features/ (not committed; built in CI):
        languages.json  one entry per Glottolog language with a point:
                        Glottocode, name, family, first WALS code (or "") and
                        the point in the map's SVG units (Web Mercator, as
                        dist/map/land.svg; see languoid_map.py)

It also checks that the map in dist/feature-map.html has the viewBox and
data-world that languoid_map.py computes for a whole-world map.
        features.json   every feature: id, name, area and its values with
                        their counts
        f/<ID>.json     one feature's values: a list with one number per
                        language in languages.json (0 = no data)

Points are Glottolog's representative coordinates, not the area where a
language is spoken.
"""
import csv
import hashlib
import io
import json
import sys
import urllib.request

from locations import ROOT
from languoid_map import min_width, project, world_box, world_view

SRC = ROOT / "source-data" / "wals-features"
OUT = ROOT / "dist" / "data" / "features"
VERSION = "v2020.4"
BASE = f"https://raw.githubusercontent.com/cldf-datasets/wals/{VERSION}/cldf/"

# Chapter areas of WALS Online (https://wals.info/chapter), by chapter number.
AREAS = [
    (1, 19, "Phonology"),
    (20, 29, "Morphology"),
    (30, 57, "Nominal categories"),
    (58, 64, "Nominal syntax"),
    (65, 80, "Verbal categories"),
    (81, 97, "Word order"),
    (98, 121, "Simple clauses"),
    (122, 128, "Complex sentences"),
    (129, 138, "Lexicon"),
    (139, 140, "Sign languages"),
    (141, 142, "Other"),
    (143, 144, "Word order"),
]


def area(chapter):
    for lo, hi, name in AREAS:
        if lo <= chapter <= hi:
            return name
    return "Other"


def fetch():
    SRC.mkdir(parents=True, exist_ok=True)
    tables = {
        "parameters.csv": ("ID", "Name", "Chapter_ID"),
        "codes.csv": ("ID", "Parameter_ID", "Name", "Number"),
        "values.csv": ("Language_ID", "Parameter_ID", "Value"),
    }
    for name, cols in tables.items():
        raw = urllib.request.urlopen(BASE + name, timeout=120).read()
        rows = csv.DictReader(io.StringIO(raw.decode("utf-8")))
        out = SRC / name
        with out.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(cols)
            for r in rows:
                w.writerow([r[c] for c in cols])
        print(f"Wrote {out.relative_to(ROOT)} from {VERSION} (source SHA-256 {hashlib.sha256(raw).hexdigest()[:16]})")


def build():
    """Points are every Glottolog language (level "language") with coordinates, so the
    map starts from all languages, not only those in WALS. Each WALS language is
    attached to its Glottolog language: a WALS lect mapped to a dialect counts for the
    dialect's language; one mapped to a family, or to nothing, is left out. When
    several WALS lects fall on one language, the first in WALS code order with a value
    for a feature gives that value."""
    glotto = list(csv.DictReader((ROOT / "source-data" / "languages.csv").open(encoding="utf-8")))
    by_id = {r["ID"]: r for r in glotto}
    langs = sorted((r for r in glotto if r["Level"] == "language" and r["Latitude"] and r["Longitude"]),
                   key=lambda r: r["ID"])
    index = {r["ID"]: i for i, r in enumerate(langs)}

    wals_to = {}   # WALS code -> index in langs
    wals_codes = {}  # index -> first WALS code
    for w in sorted(csv.DictReader((ROOT / "source-data" / "wals.csv").open(encoding="utf-8")), key=lambda r: r["ID"]):
        g = by_id.get(w["Glottocode"])
        if not g:
            continue
        if g["Level"] == "dialect":
            g = by_id.get(g["Language_ID"])
        i = index.get(g["ID"]) if g else None
        if i is None:
            continue
        wals_to[w["ID"]] = i
        wals_codes.setdefault(i, w["ID"])

    params = list(csv.DictReader((SRC / "parameters.csv").open(encoding="utf-8")))
    codes = {}
    for c in csv.DictReader((SRC / "codes.csv").open(encoding="utf-8")):
        codes.setdefault(c["Parameter_ID"], []).append({"n": int(c["Number"]), "name": c["Name"]})
    values = {}
    for v in sorted(csv.DictReader((SRC / "values.csv").open(encoding="utf-8")), key=lambda r: r["Language_ID"]):
        i = wals_to.get(v["Language_ID"])
        if i is not None:
            values.setdefault(v["Parameter_ID"], {}).setdefault(i, int(v["Value"]))

    OUT.joinpath("f").mkdir(parents=True, exist_ok=True)
    rows = []
    for i, r in enumerate(langs):
        x, y = project(float(r["Longitude"]), float(r["Latitude"]))
        fam = by_id.get(r["Family_ID"], {}).get("Name", "") if r["Family_ID"] else ""
        rows.append([r["ID"], r["Name"], fam, wals_codes.get(i, ""), round(x, 1), round(y, 1)])
    write(OUT / "languages.json", {"fields": ["glottocode", "name", "family", "wals", "x", "y"], "rows": rows})
    page = (ROOT / "dist" / "feature-map.html").read_text(encoding="utf-8")
    for attr in (f'viewBox="{world_view()}"', f'data-world="{world_box()}"', f'data-min="{min_width()}"'):
        if attr not in page:
            raise SystemExit(f"dist/feature-map.html: the map must have {attr} (see languoid_map.py)")

    features = []
    for p in params:
        pid = p["ID"]
        got = values.get(pid, {})
        if not got:
            continue
        counts = {}
        for n in got.values():
            counts[n] = counts.get(n, 0) + 1
        vals = sorted(codes.get(pid, []), key=lambda c: c["n"])
        for c in vals:
            c["count"] = counts.get(c["n"], 0)
        features.append({"id": pid, "name": p["Name"], "area": area(int(p["Chapter_ID"])),
                         "languages": len(got), "values": vals})
        write(OUT / "f" / f"{pid}.json", [got.get(i, 0) for i in range(len(langs))])
    write(OUT / "features.json", {"version": VERSION, "features": features})
    print(f"Wrote dist/data/features/: {len(langs)} Glottolog languages, {len(wals_codes)} with WALS data, {len(features)} features")


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    fetch() if "--fetch" in sys.argv[1:] else build()
