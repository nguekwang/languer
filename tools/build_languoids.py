"""Convert the sources into Lang Log's own data shape and write it into dist/.

Lang Log keeps the sources as they were published (source-data/, listed in
source-data/sources.json) and deploys only its own data, in one shape for
every record whatever source it comes from (schema/languoid.schema.json):

- dist/<path>/languoid.json for every Glottolog record and every WALS
  language that Glottolog lacks, next to the record page at the same path
  (the path rules are those of tools/build_paths.py). A historical stage,
  whose page is a section <modern>/#<anchor>, has its file at
  <modern>/<anchor>/languoid.json.
- dist/features/index.json: Lang Log's feature catalogue
  (source-data/lang-log/features.json) with the number of records per value.
- dist/features/<feature id>.json: the feature and the value of every
  record that has one, as rows [Lang Log id, value id].
- dist/schema/: the JSON Schemas, so the data can be checked by anyone.

Sources read here, each converted by its own function:

- Glottolog 5.3 (languages.csv, classification.nex, dialects.md, names.csv,
  iso-map.json): records, classification, names, location, countries.
- WALS (wals.csv and source-data/wals/): WALS codes, WALS classification
  and feature values, mapped to Lang Log features by the catalogue.

Every file is checked against its schema; the build stops on the first
record that does not match, and when a WALS feature or value is missing from
the catalogue (run tools/feature_catalogue.py to add it).

Run after tools/build_paths.py, whose path rules it imports.
"""

from pathlib import Path
import collections
import csv
import itertools
import json
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source-data"
DIST = ROOT / "dist"
SCHEMA = ROOT / "schema"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_paths  # noqa: E402  (path rules: build_paths.path_of)

SOURCES = {
    s["id"]: s for s in json.loads((SRC / "sources.json").read_text(encoding="utf-8"))["sources"]
}
VERSION = {sid: s["version"] for sid, s in SOURCES.items()}
# Order in which the evidence of a feature value is preferred: the owner's
# own values first, then the catalogues.
PRIORITY = ["lang-log", "wals"]


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def blank(i, name, source):
    return {
        "schema_version": 1,
        "id": i,
        "name": name,
        "path": "",
        "codes": {"glottocode": None, "iso639_3": None, "wals": []},
        "names": [],
        "classification": {},
        "location": None,
        "macroarea": None,
        "countries": [],
        "isolate": False,
        "modality": "spoken",
        "constructed": False,
        "features": {},
        "sources": {source: VERSION[source]},
    }


def glottolog_parents():
    """Parent of every record, from the family trees and the dialect paths."""
    parents = {}

    def edge(child, parent):
        if parents.get(child, parent) != parent:
            raise ValueError(f"{child} has two parents: {parents[child]} and {parent}")
        parents[child] = parent

    def parse_tree(tokens):
        """Read one Newick tree of Glottocodes, recording every parent."""
        pos = 0

        def node():
            nonlocal pos
            children = []
            if tokens[pos] == "(":
                pos += 1
                while True:
                    children.append(node())
                    if tokens[pos] == ")":
                        pos += 1
                        break
                    pos += 1  # ","
            name = tokens[pos]
            pos += 1
            for c in children:
                edge(c, name)
            return name

        node()

    for line in open(SRC / "classification.nex", encoding="utf-8"):
        if " = [&R] " in line:
            parse_tree(re.findall(r"[a-z0-9]{4}[0-9]{4}|[(),;]", line.split(" = [&R] ")[1]))
    text = (SRC / "dialects.md").read_text(encoding="utf-8")
    for path in re.findall(r"\(tree/([^)]*)/md.ini\)", text):
        ids = path.split("/")
        for a, b in itertools.pairwise(ids):
            edge(b, a)
    return parents


def import_glottolog():
    rows = read_csv(SRC / "languages.csv")
    parents = glottolog_parents()
    out = {}
    for r in rows:
        n = blank(r["ID"], r["Name"], "glottolog")
        n["codes"]["glottocode"] = r["ID"]
        n["codes"]["iso639_3"] = r["ISO639P3code"] or None
        n["classification"]["glottolog"] = {"parent": parents.get(r["ID"]), "level": r["Level"]}
        if r["Latitude"] and r["Longitude"]:
            n["location"] = {
                "latitude": float(r["Latitude"]),
                "longitude": float(r["Longitude"]),
                "source": "glottolog",
            }
        n["macroarea"] = r["Macroarea"] or None
        n["countries"] = [c for c in r["Countries"].split(";") if c]
        n["isolate"] = r["Is_Isolate"] == "true"
        out[r["ID"]] = n
    missing = sorted(p for p in parents.values() if p not in out)
    if missing:
        raise ValueError(f"parents missing from languages.csv: {missing[:5]}")
    for i, n in out.items():
        root = i
        while out[root]["classification"]["glottolog"]["parent"]:
            root = out[root]["classification"]["glottolog"]["parent"]
        # Glottolog's other top-level groupings (Pidgin, Mixed Language,
        # Bookkeeping ...) are its own claims: they stay as the parents in
        # classification.glottolog, not as Lang Log labels.
        if out[root]["name"] == "Sign Language":
            n["modality"] = "signed"
        if out[root]["name"] == "Artificial Language":
            n["constructed"] = True
    iso_map = json.loads((SRC / "iso-map.json").read_text(encoding="utf-8"))
    placeholders = 0
    for r in read_csv(SRC / "names.csv"):
        n = out[r["Language_ID"]]
        if r["Name"].lower() == "not specified":  # a provider's placeholder, not a name
            placeholders += 1
            continue
        iso = n["codes"]["iso639_3"]
        n["names"].append(
            {
                "text": r["Name"],
                "lang": r["lang"],
                "provider": r["Provider"],
                "same_language": bool(
                    r["lang"] and iso and iso_map.get(r["lang"], r["lang"]) == iso
                ),
                "source": "glottolog",
            }
        )
    print(
        f"Glottolog: {len(out)} records, {sum(len(n['names']) for n in out.values())} names "
        f"({placeholders} 'not specified' placeholders left out)"
    )
    return out


def import_wals(records):
    """WALS codes, classification and feature values, added to the records."""
    rows = read_csv(SRC / "wals.csv")
    wals_id = {}  # WALS id -> Lang Log id
    for r in rows:
        wals_id[r["ID"]] = r["Glottocode"] if r["Glottocode"] in records else "wals:" + r["ID"]
    only_wals = 0
    languages = {}
    for r in rows:
        if r["ID"].startswith(("family-", "subfamily-", "genus-")):
            continue
        i = wals_id[r["ID"]]
        if i not in records:
            n = blank(i, r["Name"], "wals")
            n["codes"]["iso639_3"] = r["ISO639P3code"] or None
            if r["Latitude"] and r["Longitude"]:
                n["location"] = {
                    "latitude": float(r["Latitude"]),
                    "longitude": float(r["Longitude"]),
                    "source": "wals",
                }
            n["macroarea"] = r["Macroarea"] or None
            n["countries"] = [c for c in r["Country_ID"].split() if c]
            records[i] = n
            only_wals += 1
        n = records[i]
        n["codes"]["wals"].append(r["ID"])
        n["sources"]["wals"] = VERSION["wals"]
        parent = wals_id.get(r["Parent_ID"]) if r["Parent_ID"] else None
        if parent != i:
            n["classification"]["wals"] = {"parent": parent, "level": "language"}
        languages[r["ID"]] = i

    catalogue = json.loads((SRC / "lang-log" / "features.json").read_text(encoding="utf-8"))
    mapping = {}
    for f in catalogue["features"]:
        for m in f["mappings"]:
            if m["source"] == "wals":
                mapping[m["feature"]] = (f["id"], m["values"])
    codes = {c["ID"]: c["Name"] for c in read_csv(SRC / "wals" / "codes.csv")}
    count = 0
    for v in read_csv(SRC / "wals" / "values.csv"):
        if v["Parameter_ID"] not in mapping or v["Value"] not in mapping[v["Parameter_ID"]][1]:
            raise SystemExit(
                f"WALS {v['Parameter_ID']} value {v['Value']} is not in the feature catalogue; "
                "run python3 tools/feature_catalogue.py"
            )
        fid, values = mapping[v["Parameter_ID"]]
        e = {
            "source": "wals",
            "version": VERSION["wals"],
            "feature": v["Parameter_ID"],
            "value": values[v["Value"]],
            "raw": codes[v["Code_ID"]],
            "record": v["Language_ID"],
        }
        if v["Source"]:
            e["reference"] = v["Source"]
        if v["Comment"]:
            e["comment"] = v["Comment"]
        records[languages[v["Language_ID"]]]["features"].setdefault(
            fid, {"value": "", "evidence": []}
        )["evidence"].append(e)
        count += 1
    print(
        f"WALS: {len(languages)} languages ({only_wals} not in Glottolog), {count} feature values"
    )
    return catalogue


def choose_values(records):
    """Pick each feature's value from its evidence by source priority, then by majority."""
    disagreements = 0
    for n in records.values():
        for f in n["features"].values():
            best = min(PRIORITY.index(e["source"]) for e in f["evidence"])
            top = [e["value"] for e in f["evidence"] if PRIORITY.index(e["source"]) == best]
            f["value"] = collections.Counter(top).most_common(1)[0][0]
            if len({e["value"] for e in f["evidence"]}) > 1:
                f["disagreement"] = True
                disagreements += 1
    print(f"{disagreements} feature values where the evidence disagrees (all kept as evidence)")


def check(value, schema, where, root=None):
    """Check value against the subset of JSON Schema used in schema/."""
    root = root or schema
    types = schema.get("type")
    if types:
        names = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}
        ok = any(
            (isinstance(value, (int, float)) and not isinstance(value, bool))
            if t == "number"
            else (isinstance(value, int) and not isinstance(value, bool))
            if t == "integer"
            else isinstance(value, names[t])
            for t in ([types] if isinstance(types, str) else types)
        )
        if not ok:
            raise SystemExit(f"{where}: {value!r} is not {types}")
    if "enum" in schema and value not in schema["enum"]:
        raise SystemExit(f"{where}: {value!r} is not one of {schema['enum']}")
    if "pattern" in schema and isinstance(value, str) and not re.search(schema["pattern"], value):
        raise SystemExit(f"{where}: {value!r} does not match {schema['pattern']}")
    if isinstance(value, dict):
        for k in schema.get("required", []):
            if k not in value:
                raise SystemExit(f"{where}: missing {k}")
        props = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for k, v in value.items():
            if k in props:
                check(v, props[k], f"{where}.{k}", root)
            elif extra is False:
                raise SystemExit(f"{where}: unexpected key {k}")
            elif isinstance(extra, dict):
                check(v, extra, f"{where}.{k}", root)
    if isinstance(value, list) and "items" in schema:
        for k, v in enumerate(value):
            check(v, schema["items"], f"{where}[{k}]", root)


def main():
    records = import_glottolog()
    # The same records and parents as the atlas data the pages are built from.
    for i, n in build_paths.nodes.items():
        if (
            records[i]["classification"]["glottolog"]["parent"] != n["parent"]
            or records[i]["name"] != n["name"]
        ):
            raise SystemExit(f"{i}: Glottolog import differs from dist/data.json")
    if set(records) != set(build_paths.nodes):
        raise SystemExit("Glottolog import has other records than dist/data.json")
    catalogue = import_wals(records)
    choose_values(records)

    languoid_schema = json.loads((SCHEMA / "languoid.schema.json").read_text(encoding="utf-8"))
    features_schema = json.loads((SCHEMA / "features.schema.json").read_text(encoding="utf-8"))
    check(catalogue, features_schema, "source-data/lang-log/features.json")

    by_feature = collections.defaultdict(list)
    for i, n in records.items():
        n["path"] = build_paths.path_of(i)
        check(n, languoid_schema, i)
        target = DIST / n["path"].replace("/#", "/")
        target.mkdir(parents=True, exist_ok=True)
        (target / "languoid.json").write_text(
            json.dumps(n, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        for fid, f in n["features"].items():
            by_feature[fid].append([i, f["value"]])

    out = DIST / "features"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir()
    index = {
        "schema_version": 1,
        "sources": {k: SOURCES[k] for k in ("lang-log", "wals")},
        "features": [],
    }
    for f in catalogue["features"]:
        rows = sorted(by_feature.get(f["id"], []))
        counts = collections.Counter(v for _, v in rows)
        entry = dict(f, counts={v["id"]: counts.get(v["id"], 0) for v in f["values"]})
        index["features"].append(entry)
        (out / (f["id"] + ".json")).write_text(
            json.dumps(dict(entry, languoids=rows), ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
    (out / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    shutil.rmtree(DIST / "schema", ignore_errors=True)
    shutil.copytree(SCHEMA, DIST / "schema")
    print(
        f"Wrote {len(records)} languoid.json files and {len(catalogue['features'])} feature files"
    )


if __name__ == "__main__":
    main()
