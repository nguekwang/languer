"""Write one static page and one JSON file per Glottolog record, at a URL
that follows the classification: dist/<family>/<subgroup>/.../<language>/
(served as https://lang-log.github.io/<family>/.../<language>/).

Run after prepare_static.py (it reads dist/data.json and dist/integrated.json).

- Each path segment is an ASCII slug of the record name. When two siblings
  share a slug, both get "-<glottocode>" appended, so a URL never depends on
  the order of the data.
- Historical stages listed in source-data/historical-stages.json (for
  example Old English) have no directory of their own. They are a section of
  the modern language's page, reached as <modern path>/#<anchor> (for
  example .../english/#old). Their children live under
  <modern path>/<anchor>/<child>/.
- Records that exist only in another source's tree (WALS genera and
  families, clades and unmatched samples of the study trees) get the same kind
  of page under that source: dist/<source>/<path in that tree>/, for example
  dist/wals/turkic/azerbaijani/. A study tree's root is the source's own page
  (dist/gray-et-al-2009/); dist/wals/ lists the WALS families. Glottolog
  records inside a source tree link to their Glottolog page.
  dist/source-paths.json maps each of these records to its path for the
  scripts.
- The top page (dist/index.html, tools/build_home.py) lists the top-level
  families and isolates; breadcrumbs start there ("Top").
- A top-level slug (family or source) must not equal another top-level slug
  or a name already used at the top of dist/ (RESERVED); the build stops if
  one does.
- The pages need no JavaScript (dist/map-zoom.js only adds zoom and pan to
  the map). dist/lineage-paths.js uses the same rules to
  link to Glottolog records. Each page also has two parts that need it: the
  tree of its branch (dist/tree.js, drawn when the visitor asks for it) and
  the Hugging Face models (dist/hf-models.js).
"""
from html import escape

from locations import DIST, ROOT
from security_policy import HEAD as SECURITY_HEAD
from site_brand import TITLE_SUFFIX, by_yoshi
import csv
import json
import re
import shutil
import sys
import unicodedata

from languoid_map import map_svg

OUT = DIST
# Top-level names in dist/ that a family or source slug must not take.
RESERVED = {"map", "data", "i18n", "stats", "sources", "updates"}
# Directories of earlier builds that no longer exist; removed on each run.
OLD_DIRS = {"families"}

data = json.loads((DIST / "data.json").read_text(encoding="utf-8"))
unified = json.loads((DIST / "integrated.json").read_text(encoding="utf-8"))
stages = json.loads((ROOT / "source-data" / "historical-stages.json").read_text(encoding="utf-8"))["stages"]
nodes = data["nodes"]
extra = unified["extraNodes"]
sources = unified["sources"]


def slug(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def segments_for(ids):
    """Slug for each id among its siblings, with collisions disambiguated."""
    base = {i: slug(nodes[i]["name"]) or i for i in ids}
    count = {}
    for s in base.values():
        count[s] = count.get(s, 0) + 1
    return {i: (s if count[s] == 1 else s + "-" + i) for i, s in base.items()}


# Children per parent, with stages moved under their modern language.
stage_of = {s: v for s, v in stages.items() if s in nodes and v["modern"] in nodes}
segment = {}
segment.update(segments_for(data["roots"]))
for n in nodes.values():
    kids = [c for c in n["children"] if c not in stage_of]
    segment.update(segments_for(kids))

path_cache = {}


def source_slug(sid):
    """URL name of a source: gray_et_al2009 -> gray-et-al-2009, wals -> wals."""
    return re.sub(r"([a-z])(\d{4})$", r"\1-\2", slug(sid.replace("_", " ")))


SOURCE_SLUG = {sid: source_slug(sid) for sid in sources if sid != "glottolog"}

# Members of each record in each source tree: (source, parent) -> assertions.
by_source = {}
for e in unified["assertions"]:
    if e.get("parent"):
        by_source.setdefault((e["source"], e["parent"]), []).append(e)

# A study tree's root record is the source page itself.
study_root = {i for i, n in extra.items() if not n.get("parent") and n["source"] != "wals"}


def extra_segments(ids):
    base = {i: slug(extra[i]["name"]) or slug(i.split(":")[-1]) for i in ids}
    count = {}
    for s in base.values():
        count[s] = count.get(s, 0) + 1
    return {i: (s if count[s] == 1 else s + "-" + slug(i.split(":")[-1])) for i, s in base.items()}


extra_segment = {}
extra_segment.update(extra_segments([i for i, n in extra.items() if n["source"] == "wals" and not n.get("parent")]))
_extra_kids = {}
for i, n in extra.items():
    if n.get("parent"):
        _extra_kids.setdefault(n["parent"], []).append(i)
for kids in _extra_kids.values():
    extra_segment.update(extra_segments(kids))


def rec(i):
    """A record of any source: a Glottolog record or a source-only record."""
    return nodes.get(i) or extra.get(i) or {"id": i, "name": i, "level": "", "children": []}

# Glottolog's representative point of each record, as (longitude, latitude).
coords = {}
with open(ROOT / "source-data" / "languages.csv", encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        if row["Latitude"] and row["Longitude"] and row["ID"] in nodes:
            coords[row["ID"]] = (float(row["Longitude"]), float(row["Latitude"]))


def _points_under():
    """For a family: the languages below it; for a language: its dialects."""
    langs, dials = {}, {}

    def walk(i):
        la, di = [], []
        for c in nodes[i]["children"]:
            if c not in nodes:
                continue
            cl, cd = walk(c)
            la += cl
            di += cd
            lvl = nodes[c]["level"]
            if c in coords and lvl == "language":
                la.append(c)
            elif c in coords and lvl == "dialect":
                di.append(c)
        langs[i], dials[i] = la, di
        return la, di

    for r in data["roots"]:
        walk(r)
    for i in nodes:  # records not reached from a root
        if i not in langs:
            walk(i)
    return {i: (dials[i] if nodes[i]["level"] != "family" else langs[i]) for i in nodes}


points_under = _points_under()


def path_of(i):
    """URL path below the atlas root, without leading or trailing slash; stages end in #anchor."""
    if i in path_cache:
        return path_cache[i]
    if i in extra:
        n = extra[i]
        if i in study_root:
            p = SOURCE_SLUG[n["source"]]
        elif n.get("parent"):
            p = path_of(n["parent"]) + "/" + extra_segment[i]
        else:  # a WALS family
            p = SOURCE_SLUG[n["source"]] + "/" + extra_segment[i]
    elif i in stage_of:
        p = path_of(stage_of[i]["modern"]) + "/#" + stage_of[i]["anchor"]
    else:
        parent = nodes[i].get("parent")
        if parent in stage_of:
            # Child of a stage: <modern>/<anchor>/<child>
            st = stage_of[parent]
            p = path_of(st["modern"]) + "/" + st["anchor"] + "/" + segment[i]
        else:
            p = (path_of(parent) + "/" if parent else "") + segment[i]
    path_cache[i] = p
    return p


def lineage(i):
    out = []
    seen = set()
    while i and i in nodes and i not in seen:
        seen.add(i)
        out.insert(0, i)
        i = nodes[i].get("parent")
    return out


def href(from_dir_depth, target_id):
    """Relative link from a page at depth from_dir_depth below the atlas root to a record."""
    p = path_of(target_id)
    if "/#" in p:
        d, a = p.split("/#")
        return "../" * from_dir_depth + d + "/#" + a
    return "../" * from_dir_depth + p + "/"


def href_source(depth, sid):
    """Relative link to a source's own page (Glottolog's page is the top page)."""
    return "../" * depth + (SOURCE_SLUG[sid] + "/" if sid in SOURCE_SLUG else "")


def source_link(sid):
    s = sources.get(sid)
    if not s:
        return escape(sid)
    return f'<a href="{escape(s["url"])}" target="_blank" rel="noopener noreferrer">{escape(s["title"])}</a>'


def names_html(n):
    own = sorted({r["text"] for r in n.get("nativeNames", [])})
    seen = {}
    for r in n.get("names", []):
        if r.get("placeholder"):
            continue
        seen.setdefault((r["text"], r.get("lang", "")), set()).add(r.get("provider", ""))
    out = "<h3>Name in this language</h3>"
    out += (f'<p dir="auto">{" / ".join(escape(x) for x in own)}</p>' if own
            else '<p class="muted">Not recorded in the imported sources. No name inferred.</p>')
    if not seen:  # an empty toggle opens onto nothing, so say so in plain text
        return out + '<p class="muted">No other names or spellings recorded.</p>'
    out += f"<details><summary>Recorded names and spellings · {len(seen)}</summary><ul class=\"name-list\">"
    out += "".join(f'<li dir="auto">{escape(t)} <span class="muted">{escape(tag or "tag unspecified")} · {escape(" · ".join(sorted(p)))}</span></li>'
                   for (t, tag), p in sorted(seen.items()))
    return out + "</ul></details>"


def ext_link(sid):
    """Link to a source's paper or catalog, as on the old atlas cards."""
    src = sources.get(sid)
    if not src:
        return ""
    label = "Catalog" if src.get("kind") == "catalog" else "Paper"
    return f'<a href="{escape(src["url"])}" target="_blank" rel="noopener noreferrer">{label} ↗</a>'


def source_name_link(depth, sid):
    """A source's title, linked to its tree in Lang Log (Glottolog: the top page)."""
    return f'<a href="{escape(href_source(depth, sid))}">{escape(sources.get(sid, {}).get("title", sid))}</a>'


def record_link(depth, i):
    # A study tree's root is shown as the study itself (its page is the source's page).
    name = sources[extra[i]["source"]]["title"] if i in study_root else rec(i)["name"]
    return f'<a href="{escape(href(depth, i))}">{escape(name)}</a>'


def classification_html(depth, i):
    """Every source's placement of a record, with its other direct members, and
    the other sources' trees attached below it (the old atlas evidence cards)."""
    n = rec(i)
    cards = []
    if i in nodes and not nodes[i].get("parent"):
        kind = "isolate" if nodes[i].get("isolate") else "entry"
        cards.append(f'<div class="evidence-card"><strong>According to {source_name_link(depth, "glottolog")}</strong>'
                     f'<p>Independent top-level {kind}; no higher family asserted here.</p>{ext_link("glottolog")}</div>')
    seen = set()
    unique = []
    for e in unified["placements"].get(i, []):
        key = (e["source"], e["parent"], e.get("sample", ""))
        if key not in seen:
            seen.add(key)
            unique.append(e)
    if i in extra and not unique and n.get("parent"):
        unique.append({"source": n["source"], "parent": n["parent"]})
    for e in unique:
        peers = []
        for x in by_source.get((e["source"], e["parent"]), []):
            if x["child"] != i and x["child"] not in peers:
                peers.append(x["child"])
        more = f' <span class="muted">and {len(peers) - 5} more</span>' if len(peers) > 5 else ""
        card = (f'<div class="evidence-card"><strong>According to {source_name_link(depth, e["source"])}</strong>'
                f'<p>Placement: {record_link(depth, e["parent"])}</p>')
        if e.get("sample"):
            card += f'<p class="small-disclaimer">Source sample / record: {escape(e["sample"])}</p>'
        if peers:
            card += ('<p class="small-disclaimer">Other direct members: '
                     + ", ".join(record_link(depth, x) for x in peers[:5]) + more + "</p>")
        cards.append(card + ext_link(e["source"]) + "</div>")
    out = '<section class="classification"><h2>Classification by source</h2>' + "".join(cards)
    if len(unique) <= 1:
        out += ('<p class="small-disclaimer">No additional direct placement recorded here. This is not a consensus '
                'certificate; unimported studies may propose other relationships.</p>')
    attached = unified["anchors"].get(i, []) if i in nodes else []
    if attached:
        out += ('<h3>Other sources\' trees below this record</h3><ul class="record-links">'
                + "".join(f'<li><a href="{escape(href(depth, a["root"]))}">If following {escape(sources[a["source"]]["title"])}</a>'
                          f' <span class="muted">{"catalog grouping" if a["type"] == "catalog" else "sampled study tree"}</span></li>'
                          for a in attached)
                + '</ul><p class="small-disclaimer">Alternative source-conditioned branches. They are attached here for '
                  'navigation, not as additional ancestors.</p>')
    return out + "</section>"


def debates_html(i):
    ids = set(lineage(i)) if i in nodes else {i}
    out = ""
    for d in unified.get("debates", []):
        if not ids & set(d["appliesTo"]):
            continue
        out += f'<section class="debate"><h2>{escape(d["title"])}</h2><p class="small-disclaimer">{escape(d["status"])}</p>'
        for p in d["positions"]:
            cls = " conflict-card" if p.get("stance") == "critique" else ""
            out += (f'<div class="evidence-card{cls}"><strong>According to {escape(p["author"])}</strong><p>{escape(p["claim"])}</p>'
                    f'<span class="evidence-tag">{escape(p["publication"])}</span><br>'
                    f'<a href="{escape(p["url"])}" target="_blank" rel="noopener noreferrer">Paper ↗</a></div>')
        out += f'<p class="small-disclaimer">{escape(d["note"])}</p></section>'
    return out


def conflicts_html(depth, i):
    refs = unified["conflictIndex"].get(i, [])
    if not refs:
        return ""
    pairs = {}
    for k in refs:
        c = unified["conflicts"][k]
        pairs.setdefault((c["a"], c["b"]), [c, 0])[1] += 1
    def title(sid):
        return escape(sources[sid]["title"])
    out = (f'<section class="conflicts"><h2>Incompatible study branches · {len(pairs)} source pairs</h2>'
           '<p class="small-disclaimer">These summary clades cannot both hold on the shared sampled tips. This does not '
           'determine which study is correct. Examples below may involve a wider group containing this record.</p>')
    for c, count in pairs.values():
        a, b, d = (escape(rec(x)["name"]) for x in c["witness"])
        out += (f'<div class="evidence-card conflict-card"><strong>{title(c["a"])} vs {title(c["b"])}</strong>'
                f'<div class="conflict-witness">{title(c["a"])}: [{a} + {b}] before {d}.<br>{title(c["b"])}: [{b} + {d}] before {a}.</div>'
                f'<p class="small-disclaimer">Same {c["sharedTips"]} sampled IDs compared · {count} incompatible clade pair(s) involving this record.</p>'
                f'{ext_link(c["a"])} {ext_link(c["b"])}<br>'
                f'<a href="{escape(href(depth, c["cladeA"]))}">Clade in {title(c["a"])}</a> · '
                f'<a href="{escape(href(depth, c["cladeB"]))}">Clade in {title(c["b"])}</a></div>')
    return out + "</section>"


def tree_html(depth, i, sid):
    """The branch below a record, drawn by dist/tree.js when the visitor asks for it.
    Hidden without JavaScript; the Members list gives the same records."""
    return ('<section class="tree-section" id="tree-section" hidden><h2>Tree</h2>'
            '<p><button type="button" id="show-tree" class="show-tree">Show the tree of this branch</button></p>'
            + atlas_html("../" * depth, root=i, src=sid) + "</section>")


def atlas_html(base, root=None, src=None, downloads=""):
    """The outline and zoomable tree that dist/tree.js fills (shared with the top page)."""
    attrs = f' data-base="{escape(base)}"' + (f' data-root="{escape(root)}" data-src="{escape(src)}"' if root else "")
    filters = "" if root else (
        '<select id="evidence" aria-label="Evidence filter"><option value="all">All evidence</option>'
        '<option value="conflicts">With conflicting study clades</option><option value="studies">With research trees</option></select>'
        '<select id="category" aria-label="Record category"><option value="all">All categories</option>'
        '<option value="Spoken genealogy">Spoken genealogy</option><option value="isolates">Isolates</option>'
        + "".join(f"<option>{c}</option>" for c in ["Sign Language", "Unclassifiable", "Pidgin", "Mixed Language", "Unattested",
                                                   "Artificial Language", "Speech Register", "Bookkeeping"])
        + "</select>")
    return (f'<div id="atlas" class="workspace atlas-embed"{attrs} hidden>'
            '<div class="toolbar"><div class="seg" role="group" aria-label="View"><button id="listview" class="active" type="button">List</button>'
            '<button id="chartview" type="button">Tree</button></div>'
            f'{filters}<button id="collapse" type="button">Collapse all</button>'
            '<label><input type="checkbox" id="dialects" checked> Dialects</label>'
            f'<details class="menu downloads"><summary>Download</summary><div class="menu-panel"><button id="export" type="button">SVG (current view)</button>{downloads}</div></details></div>'
            '<div id="outline" aria-label="Expandable classification outline"></div>'
            '<div id="viewport" hidden><canvas id="tree" aria-label="Interactive language classification tree. Click a node to open its page."></canvas>'
            '<div class="canvas-title"><span class="eyebrow">INTEGRATED · SOURCE-CONDITIONED</span><h2 id="view-title">Language families</h2>'
            '<p id="view-count">Loading records…</p></div><div id="tooltip" hidden></div>'
            '<div class="zoom"><button id="minus" type="button" aria-label="Zoom out">−</button><button id="fit" type="button">Fit</button>'
            '<button id="plus" type="button" aria-label="Zoom in">+</button></div>'
            '<div class="canvas-note">Drag to pan · Scroll / pinch to zoom · Click a node to open its page</div></div>'
            '<div class="how-to-read"><p>Branches are conditional on their source. Different placements appear together; no source switch is needed.</p>'
            '<p>Open a row to see its members. Each name opens its own page, with every source\'s placement and paper links.</p>'
            '<p>Independent families and isolates are parallel roots. Dashed: navigation attachment, not ancestry. Distances are not time.</p></div>'
            '</div>')


def hf_html(n):
    """Hugging Face models, loaded from the Hub when the section scrolls into view (dist/record-page.js)."""
    return (f'<section class="hf-models" id="hf-models" hidden data-name="{escape(n["name"])}" '
            f'data-level="{escape(n.get("level", ""))}" data-iso="{escape(n.get("iso", ""))}" aria-label="Hugging Face models"></section>')


def breadcrumb(depth, ids, sid="glottolog"):
    """Classification path from the top page down to (not including) this record."""
    title = escape(sources.get(sid, {}).get("title", sid).split(" ")[0] if sid == "glottolog" else sources.get(sid, {}).get("title", sid))
    items = f'<li><a href="{"../" * depth}">Top</a></li>'
    if sid != "glottolog":
        items += f'<li><a href="{escape(href_source(depth, sid))}">{escape(sources[sid]["title"])}</a></li>'
    items += "".join(f'<li><a href="{escape(href(depth, a))}">{escape(rec(a)["name"])}</a></li>' for a in ids if a not in study_root)
    return f'<nav class="lineage" aria-label="Classification according to {title}"><span class="lineage-source">{title}</span><ol class="lineage-path">{items}</ol></nav>'


def children_html(depth, i):
    if i in nodes:
        kids = [(c, "") for c in nodes[i]["children"] if c not in stage_of]
    else:  # members in the record's own source tree, with the source's sample label
        kids, seen = [], set()
        for e in by_source.get((extra[i]["source"], i), []):
            if e["child"] not in seen:
                seen.add(e["child"])
                kids.append((e["child"], e.get("sample", "")))
    if not kids:
        return ""
    kids.sort(key=lambda c: rec(c[0])["name"].lower())
    rows = "".join(f'<li><a href="{escape(href(depth, c))}">{escape(rec(c)["name"])}</a>'
                   + (f' <small class="muted">sample: {escape(sm)}</small>' if sm and sm != rec(c)["name"] else "") + "</li>" for c, sm in kids)
    # A section gets the rule and spacing that set it apart from the names above.
    return f'<section class="members"><h2>Members · {len(kids)}</h2><ul class="record-links">{rows}</ul></section>'


def meta_html(n):
    parts = [n["id"]]  # no kind label (family, language, dialect): every record is a languoid
    if n["id"] in extra:
        parts.append("According to " + sources[n["source"]]["title"])
    if n.get("iso"):
        parts.append("ISO 639-3: " + n["iso"])
    if n.get("area"):
        parts.append(n["area"])
    return '<div class="meta">' + "".join(f"<span>{escape(p)}</span>" for p in parts) + "</div>"


def record_body(depth, i, heading="h1"):
    n = rec(i)
    body = f'<{heading}>{escape(n["name"])}</{heading}>{meta_html(n)}'
    if i in extra:
        body += '<p class="small-disclaimer">Source-specific grouping or sample; not a new accepted language family.</p>'
        links = [ext_link(n["source"])]
    else:
        links = [f'<a href="https://glottolog.org/resource/languoid/id/{escape(i)}" target="_blank" rel="noopener noreferrer">Glottolog record ↗</a>']
    links.append(f'<a href="{"../" * depth}record.html?domain=language&amp;id={escape(i)}">Full source detail</a>')
    body += "<p>" + " · ".join(links) + "</p>"
    if heading == "h1" and i in nodes:
        body += map_html(depth, i)
    if i in nodes or n.get("names") or n.get("nativeNames"):
        body += names_html(n)
    return body + classification_html(depth, i) + conflicts_html(depth, i) + debates_html(i)


def map_html(depth, i):
    n = nodes[i]
    family = n["level"] == "family"
    own = None if family else coords.get(i)
    # Many dialects carry their language's own point; those add nothing to show.
    main_ids = [c for c in points_under[i] if coords[c] != own]
    main = [coords[c] for c in main_ids]
    parent = n.get("parent")
    context_ids = []
    if parent in nodes:
        mine = set(points_under[i]) | {i}
        context_ids = [c for c in points_under[parent] if c not in mine]
    context = [coords[c] for c in context_ids]
    kind = "languages" if family else ("dialects" if n["level"] == "language" else "")
    if family:
        label = f"Map: {len(main)} languages of {n['name']}"
    else:
        label = f"Map: location of {n['name']}" + (f" and its {len(main)} {kind}" if main else "")
    svg = map_svg("../" * depth + "map/", main, context, own, label,
                  main_ids=main_ids, context_ids=context_ids, self_id=i if own else "")
    if not svg:
        return ""
    notes = []
    if family:
        total = sum(1 for c in languages_under_all(i))
        missing = total - len(main)
        notes.append(f"{len(main)} languages shown" + (f"; {missing} have no coordinates in Glottolog" if missing else "") + ".")
    if context:
        notes.append("Faint points: other members of " + escape(nodes[parent]["name"]) + ".")
    legend = " ".join(notes)
    return (f'<figure class="lmap-figure">{svg}<figcaption>{legend} '
            "Each point is the one representative location Glottolog gives for a record, not the area where it is spoken. "
            'Points: Glottolog 5.3 (CC BY 4.0). Land and borders: <a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener noreferrer">Natural Earth</a> (public domain). '
            "Dashed borders are disputed or not settled. "
            "Projection: Web Mercator.</figcaption></figure>")


def languages_under_all(i):
    """Every language below a family, with or without coordinates."""
    out = []
    stack = list(nodes[i]["children"])
    while stack:
        c = stack.pop()
        if c not in nodes:
            continue
        if nodes[c]["level"] == "language":
            out.append(c)
        stack.extend(nodes[c]["children"])
    return out


# Credit for the Glottolog data, which CC BY 4.0 requires on every page that uses it.
FOOTER = ('<footer class="credit"><p>Classification and names from '
          '<a href="https://glottolog.org/" target="_blank" rel="noopener noreferrer">Glottolog 5.3</a> '
          '(Hammarström, Forkel, Haspelmath &amp; Bank 2026, '
          '<a href="https://doi.org/10.5281/zenodo.18840935" target="_blank" rel="noopener noreferrer">doi:10.5281/zenodo.18840935</a>), '
          'used under <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>.</p></footer>')


# Links to the three atlases. No generated page shows them any more (owner, 2026-11-07:
# Lang Log is one tree, not three domains); kept so the UI can be reused.
def domain_nav(up, current="language"):
    items = [("language", up, "Language families"), ("sign", f"{up}signs-and-scripts.html?domain=sign", "Sign languages"),
             ("scripts", f"{up}signs-and-scripts.html?domain=scripts", "Writing systems")]
    return ('<nav class="domain-nav" aria-label="Atlas domains">'
            + "".join(f'<a href="{escape(h)}"' + (' aria-current="page"' if k == current else "") + f">{t}</a>" for k, h, t in items)
            + "</nav>")


# Scripts at the end of every record page: the branch tree (on request) and the Hugging Face models.
def page_scripts(up):
    return "".join(f'<script src="{up}{f}"></script>' for f in
                   ["atlas-data.js", "lineage-paths.js", "hf-iso-map.js", "hf-models.js", "tree.js", "record-page.js"])


def page(depth, title, body):
    up = "../" * depth
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"{SECURITY_HEAD}"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{escape(title)}{TITLE_SUFFIX}</title>"
            f"<link rel=\"icon\" href=\"{up}favicon.svg\" type=\"image/svg+xml\"><link rel=\"apple-touch-icon\" href=\"{up}apple-touch-icon.png\">"
            f"<link rel=\"stylesheet\" href=\"{up}style.css\"><link rel=\"stylesheet\" href=\"{up}signs-and-scripts.css\"><link rel=\"stylesheet\" href=\"{up}record.css\"><script src=\"{up}theme.js\"></script><script src=\"{up}i18n.js\"></script><script src=\"{up}lang.js\"></script><script src=\"{up}map-zoom.js\" defer></script></head>"
            f"<body class=\"variant-page\"><header><div class=\"brand\"><a class=\"home\" href=\"{up}\"><svg class=\"logo\" role=\"img\" aria-label=\"LANG LOG\"><use href=\"{up}logo.svg#logo\"/></svg></a> {by_yoshi()}</div></header>"
            f"<main>{body}</main>{FOOTER}{page_scripts(up)}</body></html>")


def record_json(i):
    if i in extra:
        n = extra[i]
        return {
            "id": i, "name": n["name"], "level": n["level"], "iso": n.get("iso", ""), "category": n.get("category", ""),
            "path": path_of(i), "source": sources[n["source"]]["title"],
            "lineage": [{"id": a, "name": extra[a]["name"], "path": path_of(a)} for a in extra_lineage(i)[:-1]],
            "children": [{"id": e["child"], "name": rec(e["child"])["name"], "level": rec(e["child"])["level"],
                          "path": path_of(e["child"]), "sample": e.get("sample", "")}
                         for e in by_source.get((n["source"], i), [])],
            "placements": [e for e in unified["placements"].get(i, [])],
        }
    n = nodes[i]
    return {
        "id": i, "name": n["name"], "level": n["level"], "iso": n.get("iso", ""),
        "coordinates": ({"latitude": coords[i][1], "longitude": coords[i][0]} if i in coords else None),
        "area": n.get("area", ""), "countries": n.get("countries", ""), "isolate": n.get("isolate", False),
        "path": path_of(i),
        "lineage": [{"id": a, "name": nodes[a]["name"], "path": path_of(a)} for a in lineage(i)[:-1]],
        "children": [{"id": c, "name": nodes[c]["name"], "level": nodes[c]["level"], "path": path_of(c)} for c in n["children"]],
        "stages": [{"id": s, "name": nodes[s]["name"], "anchor": v["anchor"]} for s, v in stage_of.items() if v["modern"] == i],
        "names": n.get("names", []), "nativeNames": n.get("nativeNames", []),
        "placements": [e for e in unified["placements"].get(i, [])],
        "source": "Glottolog 5.3 (CC BY 4.0)",
    }


def extra_lineage(i):
    out = []
    while i in extra:
        out.insert(0, i)
        i = extra[i].get("parent")
    return out


def source_page_body(sid):
    """Top of a source's tree: what the source is, and its top-level records."""
    src = sources[sid]
    body = (f'<nav class="lineage" aria-label="Classification according to {escape(src["title"])}"><span class="lineage-source">{escape(src["title"])}</span>'
            '<ol class="lineage-path"><li><a href="../">Top</a></li></ol></nav>'
            f'<h1>{escape(src["title"])}</h1><div class="meta"><span>{"catalog" if src.get("kind") == "catalog" else "study tree"}</span>'
            + (f'<span>{escape(src["family"])}</span>' if src.get("family") else "")
            + f'<span>{escape(src.get("license", ""))}</span></div>')
    if src.get("citation"):
        body += f'<p>{escape(src["citation"])}</p>'
    links = [ext_link(sid)]
    if src.get("dataset"):
        links.append(f'<a href="{escape(src["dataset"])}" target="_blank" rel="noopener noreferrer">Source tree &amp; data ↗</a>')
    body += "<p>" + " · ".join(links) + "</p>"
    if src.get("interpretationNote"):
        body += f'<p class="small-disclaimer">{escape(src["interpretationNote"])}</p>'
    attached = sorted({g for g, lst in unified["anchors"].items() if g in nodes for a in lst if a["source"] == sid},
                      key=lambda g: nodes[g]["name"].lower())
    if attached:
        body += ('<section class="attached"><h2>Where Lang Log attaches this tree</h2><ul class="record-links">'
                 + "".join(f'<li>{record_link(1, g)} <span class="muted">Glottolog</span></li>' for g in attached) + "</ul></section>")
    return body


def write_page(i, body, title):
    target = OUT / path_of(i)
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text(page(path_of(i).count("/") + 1, title, body), encoding="utf-8")
    (target / "record.json").write_text(json.dumps(record_json(i), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def write_source_pages():
    """One page per source-only record, under its source; returns the number written."""
    written = 0
    for i, n in extra.items():
        sid = n["source"]
        depth = path_of(i).count("/") + 1
        if i in study_root:
            body = source_page_body(sid) + children_html(depth, i)
        else:
            body = breadcrumb(depth, extra_lineage(i)[:-1], sid) + record_body(depth, i) + children_html(depth, i)
        body += tree_html(depth, i, sid) + hf_html(n)
        body += '<p class="muted"><a href="record.json">This record as JSON</a></p>'
        write_page(i, body, sources[sid]["title"] if i in study_root else n["name"])
        written += 1
    # dist/wals/: the WALS catalog and its families.
    fams = sorted((i for i, n in extra.items() if n["source"] == "wals" and not n.get("parent")), key=lambda i: extra[i]["name"].lower())
    target = OUT / SOURCE_SLUG["wals"]
    target.mkdir(parents=True, exist_ok=True)
    rows = "".join(f'<li>{record_link(1, f)}</li>' for f in fams)
    body = source_page_body("wals") + f'<section class="members"><h2>Families · {len(fams)}</h2><ul class="record-links">{rows}</ul></section>'
    (target / "index.html").write_text(page(1, sources["wals"]["title"], body), encoding="utf-8")
    return written


def main():
    top = {segment[r] for r in data["roots"]}
    src_top = set(SOURCE_SLUG.values())
    clash = sorted((top | src_top) & RESERVED) + sorted(top & src_top)
    if clash or len(src_top) != len(SOURCE_SLUG):
        sys.exit(f"Top-level slug(s) {clash} clash with each other or with names reserved in dist/; add a rule for them.")
    # Remove pages from an earlier run: each family and source directory, and directories no longer built.
    for name in top | src_top | OLD_DIRS:
        if (OUT / name).is_dir():
            shutil.rmtree(OUT / name)
    written = 0
    stages_by_modern = {}
    for s, v in stage_of.items():
        stages_by_modern.setdefault(v["modern"], []).append(s)
    for i in nodes:
        if i in stage_of:
            continue
        p = path_of(i)
        depth = p.count("/") + 1
        target = OUT / p
        target.mkdir(parents=True, exist_ok=True)
        anc = lineage(i)[:-1]
        body = breadcrumb(depth, anc) + record_body(depth, i)
        for s in sorted(stages_by_modern.get(i, []), key=lambda s: nodes[s]["name"]):
            st = stage_of[s]
            body += f'<section id="{escape(st["anchor"])}" class="stage"><p class="eyebrow">Historical stage · #{escape(st["anchor"])}</p>'
            body += record_body(depth, s, "h2")
            body += breadcrumb(depth, lineage(s)[:-1]).replace("aria-label=\"Classification according to Glottolog\"", "aria-label=\"Position in Glottolog\"")
            body += '<p class="muted">Position of this stage in the Glottolog tree. Glottolog does not record which modern language it is a stage of; that link is curated in this atlas.</p>'
            kids = sorted(nodes[s]["children"], key=lambda c: nodes[c]["name"].lower())
            if kids:
                body += "<ul class=\"record-links\">" + "".join(f'<li><a href="{escape(href(depth, c))}">{escape(nodes[c]["name"])}</a></li>' for c in kids) + "</ul>"
            body += "</section>"
        body += children_html(depth, i) + tree_html(depth, i, "glottolog") + hf_html(nodes[i])
        body += '<p class="muted"><a href="record.json">This record as JSON</a></p>'
        (target / "index.html").write_text(page(depth, nodes[i]["name"], body), encoding="utf-8")
        (target / "record.json").write_text(json.dumps(record_json(i), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        written += 1
    # A stage's anchor directory (e.g. .../korean/middle/) points back to the section.
    for s, v in stage_of.items():
        if nodes[s]["children"]:
            d = OUT / path_of(v["modern"]) / v["anchor"]
            d.mkdir(parents=True, exist_ok=True)
            if not (d / "index.html").exists():
                depth = path_of(v["modern"]).count("/") + 2
                (d / "index.html").write_text(page(depth, nodes[s]["name"], f'<h1>{escape(nodes[s]["name"])}</h1><p><a href="../#{escape(v["anchor"])}">See {escape(nodes[s]["name"])} on the {escape(nodes[v["modern"]]["name"])} page</a></p>'), encoding="utf-8")
    written_sources = write_source_pages()
    (OUT / "source-paths.json").write_text(json.dumps({i: path_of(i) + "/" for i in extra}, separators=(",", ":")), encoding="utf-8")
    (OUT / "stages.json").write_text(json.dumps({k: {"modern": v["modern"], "anchor": v["anchor"]} for k, v in stage_of.items()}), encoding="utf-8")
    if "--paths" in sys.argv:  # for checking dist/lineage-paths.js against these rules
        (OUT / "paths.json").write_text(json.dumps({i: (path_of(i) if "/#" in path_of(i) else path_of(i) + "/") for i in nodes}), encoding="utf-8")
    print(f"Wrote {written} Glottolog record pages and {written_sources} source-only record pages under dist/")


if __name__ == "__main__":
    main()
