"""Split the atlas data into small files the browser can load quickly.

dist/data.json (21 MB) and dist/integrated.json (9 MB) stay as downloads,
but the pages no longer load them. Instead this script writes, under
dist/data/:

- atlas.json: everything the atlas needs to draw the tree and search by
  name, Glottocode and ISO code. Glottolog records are stored as columns,
  and values the browser can recompute are left out (each record's id,
  children, root and size, the Glottolog assertions and the placements
  index). dist/atlas-data.js rebuilds the original objects from it.
- names/<n>.json: the recorded names and spellings of each record, split
  into SHARDS files by a hash of the id (see shard()). A page loads one
  only when it shows a record's names.
- search.json: the text of all recorded names, for search. The atlas loads
  it after the tree is shown.

The WALS genus lists in data.json ("wals", "walsRoots" and each record's
"wals") are not used by any page and are left out.

Run after prepare_static.py. check() rebuilds the objects the same way
the browser does and fails if anything differs from the originals.
"""

import json
import re

from locations import DIST

OUT = DIST / "data"
# The number of name files is set once, in dist/atlas-data.js (the browser must know it
# before any data has loaded); read it from there so the two always agree.
SHARDS = int(
    re.search(
        r"\bconst SHARDS\s*=\s*(\d+)", (DIST / "atlas-data.js").read_text(encoding="utf-8")
    ).group(1)
)
# Glottolog record fields stored as columns, in the original key order.
# id, children, root, size, wals and names are left out (see above).
COLUMNS = ["name", "level", "area", "iso", "countries", "isolate", "parent", "category"]
CODED = {"level", "area", "category"}  # few distinct values: stored as indexes


def shard(record_id):
    """Same hash as shard() in dist/atlas-data.js."""
    h = 0
    for ch in record_id:
        h = (h * 31 + ord(ch)) % SHARDS
    return h


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build(data, unified):
    nodes = data["nodes"]
    ids = list(nodes)
    index = {k: i for i, k in enumerate(ids)}
    cols = {}
    codes = {}
    for field in COLUMNS:
        values = [nodes[k][field] for k in ids]
        if field == "parent":
            values = [-1 if v is None else index[v] for v in values]
        elif field == "isolate":
            values = [1 if v else 0 for v in values]
        elif field in CODED:
            table = list(dict.fromkeys(values))
            codes[field] = table
            pos = {v: i for i, v in enumerate(table)}
            values = [pos[v] for v in values]
        cols[field] = values
    # Children keep their Glottolog order: rank = position among siblings.
    rank = [0] * len(ids)
    for k in ids:
        for i, c in enumerate(nodes[k]["children"]):
            rank[index[c]] = i
    cols["rank"] = rank
    native = {str(index[k]): nodes[k]["nativeNames"] for k in ids if nodes[k]["nativeNames"]}

    assertions = unified["assertions"]
    glottolog = len(ids)
    rest = assertions[glottolog:]
    lite = {k: v for k, v in unified.items() if k not in ("assertions", "placements")}
    lite["otherAssertions"] = rest
    atlas = {
        "format": 1,
        "ids": ids,
        "columns": cols,
        "codes": codes,
        "nativeNames": native,
        "roots": data["roots"],
        "stats": data["stats"],
        "retrieved": data["retrieved"],
        "glottologVersion": data["glottologVersion"],
        "unified": lite,
    }
    shards = [{} for _ in range(SHARDS)]
    search = {}
    for k in ids:
        names = nodes[k]["names"]
        if names:
            shards[shard(k)][k] = names
            search[k] = " ".join(dict.fromkeys(r["text"] for r in names)).lower()
    return atlas, shards, search


def rebuild(atlas):
    """Python twin of AtlasData.load() in dist/atlas-data.js, for check()."""
    ids, cols, codes = atlas["ids"], atlas["columns"], atlas["codes"]
    nodes = {}
    for i, k in enumerate(ids):
        n = {"id": k}
        for field in COLUMNS:
            v = cols[field][i]
            if field == "parent":
                v = None if v < 0 else ids[v]
            elif field == "isolate":
                v = bool(v)
            elif field in CODED:
                v = codes[field][v]
            n[field] = v
        n["children"] = []
        nodes[k] = n
    kids = {}
    for i, k in enumerate(ids):
        p = nodes[k]["parent"]
        if p is not None:
            kids.setdefault(p, []).append((cols["rank"][i], k))
    for p, lst in kids.items():
        nodes[p]["children"] = [k for _, k in sorted(lst)]

    def root(k):
        while nodes[k]["parent"] is not None:
            k = nodes[k]["parent"]
        return k

    size = {}

    def count(k):
        if k not in size:
            size[k] = 1 + sum(count(c) for c in nodes[k]["children"])
        return size[k]

    for k in ids:
        nodes[k]["root"] = root(k)
        nodes[k]["size"] = count(k)
        nodes[k]["nativeNames"] = []
    for i, v in atlas["nativeNames"].items():
        nodes[ids[int(i)]]["nativeNames"] = v
    u = dict(atlas["unified"])
    other = u.pop("otherAssertions")
    assertions = [
        {"parent": nodes[k]["parent"], "child": k, "source": "glottolog"} for k in ids
    ] + other
    placements = {}
    for a in assertions:
        if a["parent"] is not None:
            placements.setdefault(a["child"], []).append(a)
    u["assertions"] = assertions
    u["placements"] = placements
    return nodes, u


def check(data, unified, atlas, shards):
    import sys

    sys.setrecursionlimit(100000)
    nodes, u = rebuild(atlas)
    for k, n in data["nodes"].items():
        want = {f: v for f, v in n.items() if f not in ("wals", "names")}
        got = dict(nodes[k])
        if got != want:
            raise ValueError("Record differs after rebuilding: " + k)
        if shards[shard(k)].get(k, []) != n["names"]:
            raise ValueError("Names differ after rebuilding: " + k)
    for key, value in unified.items():
        if u[key] != value:
            raise ValueError("integrated.json differs after rebuilding: " + key)


def main():
    import sys

    sys.setrecursionlimit(100000)
    data = json.loads((DIST / "data.json").read_text(encoding="utf-8"))
    unified = json.loads((DIST / "integrated.json").read_text(encoding="utf-8"))
    if any(a["source"] != "glottolog" for a in unified["assertions"][: len(data["nodes"])]):
        raise ValueError("integrated.json no longer starts with the Glottolog assertions")
    atlas, shards, search = build(data, unified)
    check(data, unified, atlas, shards)
    dump(OUT / "atlas.json", atlas)
    for i, s in enumerate(shards):
        dump(OUT / "names" / f"{i}.json", s)
    dump(OUT / "search.json", search)
    print("Wrote dist/data/atlas.json, search.json and", SHARDS, "name files")


if __name__ == "__main__":
    main()
