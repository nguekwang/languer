#!/usr/bin/env bash
# Build dist/ as it is published, and check it. Run from the repository root.
# Used by .github/workflows/site.yml (pull requests) and pages.yml (the live site).
set -euo pipefail

# Restores dist/data.json and dist/language-families.xml from
# source-data/packed/ and checks their SHA-256.
python3 tools/prepare_static.py
# Writes the top page dist/index.html (the list of top-level families,
# the whole tree), dist/random.json (the records its Random buttons draw
# from) and the pages linked under the Random row: dist/stats/,
# dist/sources/ and dist/updates/ (not committed; built here).
python3 tools/build_home.py
# Writes one page and one record.json per Glottolog record under
# dist/<family>/.../<language>/, and per source-only record under
# dist/<source>/.../ with dist/source-paths.json (not committed; built
# here).
python3 tools/build_paths.py
# Writes the small files the pages load (dist/data/, not committed):
# the atlas tree, the search text and the names split into SHARDS files
# (the number is set in dist/atlas-data.js).
python3 tools/split_data.py
# Writes the language feature map's data (dist/data/features/, not
# committed) from source-data/wals-features/, source-data/wals.csv and
# source-data/languages.csv.
python3 tools/build_wals_map.py
# The browser rebuilds the same objects as data.json and integrated.json.
node tools/check_atlas_data.js
# Every interface language has every string (.claude/rules/interface-text.md).
node tools/check_i18n.js

echo "Check that every page and data file is present"
for f in index.html signs-and-scripts.html record.html 404.html \
         favicon.svg apple-touch-icon.png logo.svg theme.js i18n.js lang.js i18n/es.js i18n/ar.js i18n/fa.js \
         data.json integrated.json language-families.xml \
         lineage-paths.js stages.json tree.js record-page.js source-paths.json \
         afro-asiatic/berber/index.html wals/index.html gray-et-al-2009/index.html \
         map/land.svg map/tiles.json map-zoom.js data/atlas.json \
         data/search.json data/names/0.json atlas-data.js \
         home.js random.json \
         feature-map.html feature-map.js feature-map.css data/features/languages.json \
         data/features/features.json data/features/f/81A.json \
         stats/index.html stats.js sources/index.html updates/index.html; do
  test -s "dist/$f" || { echo "missing dist/$f"; exit 1; }
done

# The asterisk and "LANG LOG" are always the one SVG, dist/logo.svg
# (.claude/rules/logo.md): every page draws it, and no page writes the
# word mark as text.
echo "Check that every page draws the SVG logo"
missing=$(find dist -name '*.html' -print0 | xargs -0 grep -L 'logo.svg#logo' || true)
[ -z "$missing" ] || { echo "pages without the SVG logo:"; echo "$missing" | head; exit 1; }
text=$(find dist -name '*.html' -print0 | xargs -0 grep -il '>[[:space:]]*\(✱\|\*\|★\)\?[[:space:]]*lang log[[:space:]]*<' || true)
[ -z "$text" ] || { echo "pages with a text logo:"; echo "$text" | head; exit 1; }

# Every record is a languoid (one tree, no split by kind), so no page shows a
# kind label or a kind legend ("family", "Family / subgroup · Language ·
# Dialect"); see .claude/rules/interface-text.md.
echo "Check that no page labels records by kind"
kinds=$( { find dist -name '*.html' -print0 | xargs -0 grep -lE 'class="legend"|Family / subgroup|class="muted">(family|isolate|language|dialect|clade|sample)<' || true; } | head)
[ -z "$kinds" ] || { echo "pages with kind labels:"; echo "$kinds"; exit 1; }
if grep -nE 'lv-(hit-)?(family|language|dialect)|hit-kind|v-kind|n\.isolate\?.isolate.:n\.level' dist/*.js dist/*.css; then
  echo "scripts or styles that label records by kind (above)"; exit 1
fi

# Adds ?v=<content hash> to every local CSS, JS and SVG link in the
# pages, so a browser never pairs new HTML with an old cached file
# (Pages caches files for ten minutes). Runs after every page is written.
python3 tools/version_assets.py
echo "Check that the asset links are versioned"
grep -q 'href="style.css?v=' dist/index.html

# Every page starts with the one security policy of tools/security_policy.py
# (Content-Security-Policy and referrer), and none has an inline script, an
# inline style attribute or event handler that the policy would block
# (.claude/rules/security.md).
python3 tools/security_policy.py --check

# The site name, the title suffix and the profile link come from
# tools/site_brand.py; the hand-written pages must match it.
python3 tools/site_brand.py --check
# Each shared value is written in one place (.claude/rules/readable-code.md):
# no copies of the values in tools/single-source.json, no colours outside the
# tokens in dist/style.css, no constant defined twice with the same value.
python3 tools/check_single_source.py
