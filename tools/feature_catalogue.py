"""Add the WALS features and values that Lang Log's feature catalogue lacks.

The catalogue, source-data/lang-log/features.json, is Lang Log's own list of
features (schema/features.schema.json). Each feature has its own id and value
ids; its "mappings" say which feature and value of each source give them.
The catalogue started as the 192 WALS features, one Lang Log feature each.
It is committed and may be edited by hand (names in other languages, a
feature merged with a Grambank feature, and so on).

This script never changes an entry that is already there. It only appends
WALS features that have no mapping yet, and WALS values missing from an
existing mapping, so that a new WALS release can be taken in. Run it when
tools/build_languoids.py stops with "not in the feature catalogue".

    python3 tools/feature_catalogue.py
"""

from pathlib import Path
import csv
import json
import re
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
WALS = ROOT / "source-data" / "wals"
CATALOGUE = ROOT / "source-data" / "lang-log" / "features.json"


def slug(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def read(name):
    with open(WALS / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    if CATALOGUE.exists():
        catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    else:
        catalogue = {"schema_version": 1, "features": []}
    features = catalogue["features"]
    by_wals = {m["feature"]: f for f in features for m in f["mappings"] if m["source"] == "wals"}
    taken = {f["id"] for f in features}
    areas = {a["ID"]: a["Name"] for a in read("areas.csv")}
    chapters = {c["ID"]: c for c in read("chapters.csv")}
    codes = {}
    for c in read("codes.csv"):
        codes.setdefault(c["Parameter_ID"], []).append(c)
    added_features = added_values = 0
    for p in read("parameters.csv"):
        feature = by_wals.get(p["ID"])
        if feature is None:
            fid = slug(p["Name"])
            if fid in taken:
                fid = fid + "-" + p["ID"].lower()
            taken.add(fid)
            feature = {
                "id": fid,
                "name": {"en": p["Name"]},
                "area": areas.get(chapters.get(p["Chapter_ID"], {}).get("Area_ID", ""), ""),
                "values": [],
                "mappings": [
                    {
                        "source": "wals",
                        "feature": p["ID"],
                        "url": "https://wals.info/feature/" + p["ID"],
                        "values": {},
                    }
                ],
            }
            features.append(feature)
            added_features += 1
        mapping = next(
            m for m in feature["mappings"] if m["source"] == "wals" and m["feature"] == p["ID"]
        )
        value_ids = {v["id"] for v in feature["values"]}
        rows = sorted(codes.get(p["ID"], []), key=lambda c: int(c["Number"]))
        base = [slug(c["Name"]) or c["Number"] for c in rows]
        for c, vid in zip(rows, base, strict=True):
            if c["Number"] in mapping["values"]:
                continue
            # Some WALS value names differ only in spacing or punctuation
            # (143B "NegV-Neg" and "Neg-V-Neg"); those get the WALS number.
            if base.count(vid) > 1 or vid in value_ids:
                vid = vid + "-" + c["Number"]
            feature["values"].append({"id": vid, "name": {"en": c["Name"]}})
            value_ids.add(vid)
            mapping["values"][c["Number"]] = vid
            added_values += 1
    CATALOGUE.parent.mkdir(parents=True, exist_ok=True)
    CATALOGUE.write_text(
        json.dumps(catalogue, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"{len(features)} features; added {added_features} features and {added_values} values")


if __name__ == "__main__":
    main()
