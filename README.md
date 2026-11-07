# Lang Log

An interactive atlas of language families, sign languages and writing systems, with source-linked classifications, alternative hypotheses and exportable data.

It will also hold corpora and data for low-resource languages (planned).

Live site: https://lang-log.github.io/

## Run locally

The scripts live in `tools/`; run them from the repository root. Run `python3 tools/prepare_static.py`, `python3 tools/build_home.py` and `python3 tools/build_paths.py`, then serve the static site with `python -m http.server 8000 --directory dist` and open http://localhost:8000.

## Code quality checks

Every pull request and every push to `main` runs Prettier (formatting, with `@prettier/plugin-xml` for XML and SVG), ESLint (JavaScript) and Ruff (Python lint and formatting) before the site is built (`.github/workflows/quality.yml`, called by `site.yml`). `pages.yml` runs the same checks on `main` before every deployment, so nothing is published while they fail. The site itself needs no packages; these tools are only for development.

Tools: Node.js 22 (`.nvmrc`) with npm, and Python 3.12 or later.

Install the exact versions once, from the repository root:

```sh
npm ci --ignore-scripts
python3 -m pip install --require-hashes -r requirements-dev.txt
```

Run every check:

```sh
npm run check
```

Or one at a time:

| Command                       | What it does                                     |
| ----------------------------- | ------------------------------------------------ |
| `npm run format:check`        | Prettier: lists files that are not formatted     |
| `npm run lint:js`             | ESLint on the JavaScript in `dist/` and `tools/` |
| `npm run lint:python`         | Ruff lint on the Python in `tools/`              |
| `npm run format:python:check` | Ruff: lists Python files that are not formatted  |
| `npm run format`              | Prettier: formats the files (writes them)        |
| `npm run format:python`       | Ruff: formats the Python files (writes them)     |

`tools/build_site.sh` adds asset versions to `dist/lang.js` and the hand-written pages in `dist/`, so run the checks before building, or restore those files first with `git checkout -- dist`.

Settings: `.prettierrc.json` and `.prettierignore` (Prettier), `eslint.config.mjs` (ESLint), `pyproject.toml` (Ruff). Pinned versions: `package-lock.json` and `requirements-dev.txt`.

Left out on purpose:

- `source-data/`: third-party datasets and saved pages kept as published, and hand-curated data the build reads as it is (Prettier, Ruff).
- Files written by scripts and committed: `dist/integrated.json`, `dist/provenance.json`, `dist/signs-and-scripts.json`, `dist/language-atlas.xml`, `dist/signs-and-scripts.xml`, `dist/hf-iso-map.js`, `dist/logo.svg` and `dist/map/` (Prettier). OPML and CSV files are not formatted by any of the tools.
- Everything in `.gitignore`, such as the pages and data that `tools/build_site.sh` writes into `dist/` (all tools).
- `dist/*.html`: `tools/security_policy.py --write` keeps their policy `<meta>` tags as one exact string after `<meta charset="utf-8">`, and `--check` compares that text (Prettier).
- For now, the files that open pull requests change, so that they do not conflict: `dist/home.js`, `dist/tree.js`, `dist/i18n.js`, `dist/i18n/`, `dist/style.css` (Prettier; the first two also ESLint) and `tools/build_paths.py`, `tools/build_wals_map.py`, `tools/build_home.py` (Ruff format). They are formatted in their own pull request once those are merged.

## Shareable URLs

Every screen state that can be shared is kept in the query string, so a copied address bar URL reopens the same view. Back and Forward step through selections, branches, filters and view changes; typing, panning and zooming update the current entry instead of adding new ones.

The top page (`./`, `dist/index.html`) shows the logo, a search box and a short introduction. It is written by `tools/build_home.py`. Under the search box, a Random row (Language, Sign language, Writing system) opens the page of a random record of that kind; the top page is the only page with Random. `dist/home.js` draws from `dist/random.json`, which `tools/build_home.py` writes (not committed). Without JavaScript the row stays hidden.

The top page is also the top of the language-families tree. Below the introduction it lists all top-level families and isolates (each linked to its record page), draws the whole tree (`dist/tree.js`: list or zoomable tree, filters, dialects, SVG, XML and OPML downloads) and holds the Sources & scope text (`source-data/sources-and-scope.html`). There is no separate atlas page; every record has its own page (see Record pages).

Language families (the top page and every record page):

| Parameter     | Meaning                                                                                              |
| ------------- | ---------------------------------------------------------------------------------------------------- |
| `q`           | Search text (top page); the matches are listed under the search box                                  |
| `evidence`    | Evidence filter: `conflicts` or `studies` (top page)                                                 |
| `category`    | Record category filter, as in the category menu (for example `isolates`, `Sign Language`) (top page) |
| `dialects=0`  | Hide dialects in the tree                                                                            |
| `view=tree`   | Horizontal tree instead of the list                                                                  |
| `x`, `y`, `z` | Tree position (centre in tree coordinates) and zoom; present only after panning or zooming           |
| `task`        | Hugging Face model task on a record page (for example `translation`)                                 |

On a record page the tree is drawn when the visitor presses "Show the tree of this branch", or at once when the URL has `view`, `dialects` or `x`.

Signs and scripts (`signs-and-scripts.html`): `domain` (`sign` or `scripts`), `id`, `branch`, `q`, `view=tree`, `task` and `about=1`, with the same meanings.

Record pages (`record.html`): `domain`, `id` and `task`.

Not kept in the URL: rows expanded by hand in the list, the mobile search menu, scroll position and random draws (the drawn record is kept as `id`).

## Logo

The header logo (asterisk and "LANG LOG") is one SVG symbol, `dist/logo.svg`, drawn on every page with `<use href="logo.svg#logo">`, so the logo link is one rectangle. `tools/build_logo.py` writes it from Liberation Sans Bold outlines and updates the `.logo` aspect ratio in `dist/style.css`; it needs `fontTools` and is run only when the logo changes. Every place that shows the logo uses this SVG, including the not-found page `dist/404.html`; the logo is never written as text (see `.claude/rules/logo.md`; the `pages` workflow checks it).

## License

Lang Log is not open source. Its code, design, site text and the data compiled for it are copyright (C) 2026 MATSUURA Yoshihiro, all rights reserved; see `LICENSE`. No reuse, in whole or in part, commercial or non-commercial, without prior written permission. Versions published earlier under AGPL-3.0-only stay under that license for those who received them.

Third-party source datasets are not covered by this and keep their own licenses and attribution (for example Glottolog: CC BY 4.0; SIL Scripts Index: CC BY-SA 4.0; Power et al. 2020 CLDF dataset: GPL-3.0). See `dist/signs-and-scripts-licenses.txt`, the source registers in the site and the documentation below.

## GitHub Pages

The workflow `.github/workflows/pages.yml` runs `python3 tools/prepare_static.py`, `python3 tools/build_home.py`, `python3 tools/build_paths.py` and `python3 tools/split_data.py` and publishes `dist/` to https://lang-log.github.io/ on every push to `main`; pull requests only build. One-time setup: Settings > Pages > Build and deployment > Source: GitHub Actions. All paths in `dist/` are relative, so the site works at any prefix. No environment variables or secrets are required.

## Record pages

`tools/build_paths.py` writes one page and one `record.json` for each Glottolog record, at a URL that follows its classification, for example `indo-european/.../castilic/spanish/`. The breadcrumb starts at the top page, which lists all families and isolates. The pages need no JavaScript; `dist/lineage-paths.js` follows the same rules to link to them.

Each page shows the record's names and map, its placement in every source (Glottolog, WALS and the study trees, with paper links and the other direct members), the other sources' trees attached below it, incompatible study branches, curated debates, its members, the tree of its branch (`dist/tree.js`, on request) and Hugging Face models (`dist/hf-models.js`, loaded when the section scrolls into view; `dist/record-page.js`).

Records that exist only in another source's tree (WALS genera and families, study clades and unmatched samples, 3,708 records) get the same kind of page under that source, for example `wals/altaic/turkic/azerbaijani/`. A study tree's root is the source's page (`gray-et-al-2009/`); `wals/` lists the WALS families. `dist/source-paths.json` maps these records to their paths for the scripts. Family and source slugs share the top level; the build stops if two are equal.

- Each segment is an ASCII slug of the name. Siblings with the same slug both get `-<glottocode>`.
- Historical stages listed in `source-data/historical-stages.json` are a section of the modern language's page, such as `.../english/#old` and `.../english/#middle`. Glottolog does not record which modern language a stage belongs to, so this list is curated by hand; edit it to add or remove stages.
- The record pages (one directory per top-level family or source under `dist/`), `dist/stages.json` and `dist/source-paths.json` are built by the Pages workflow and are not committed.
- Each page has a static map (inline SVG, no JavaScript; `tools/languoid_map.py`). A family shows the languages below it; a language shows its own point and its dialects; faint points are the other members of the parent group. Points are Glottolog's representative coordinates (`source-data/languages.csv`), one per record, not the area where a language is spoken. `record.json` carries the same `coordinates`.
- The land and country borders behind the points are `dist/map/land.svg`, drawn by `tools/build_land.py` from Natural Earth 1:50m land and boundary lines v5.1.2 (public domain) in the Web Mercator projection (cut at 85 degrees north and south, as on other web maps) and committed. The map goes round the world: each page draws it once more on each side, and a group of points around the 180th meridian (for example Oceanic) stays together; each page refers to them with `<use>`, so browsers download them once. Borders are thin solid lines; disputed, indefinite and unrecognised boundaries are dashed.
- `dist/map-zoom.js` adds zoom and pan: drag (one finger is enough on a phone; the page scrolls from outside the map), east and west without end, pinch, Ctrl/Cmd + wheel, double click, the + / − buttons (shown only when the device has a mouse or trackpad), Reset (which glides back to the starting view) and the keyboard. Points and border lines keep their size on screen at every zoom. Once the view is narrow enough (the starting view of most record pages already is), it draws the 1:10m tiles in `dist/map/tiles/land/` (listed in `dist/map/tiles.json`, also written by `tools/build_land.py`) for the part in view. Other pages can reuse it with `window.LangLogMap.mount(svg)`; see the comment at the top of the file.

## Interface language and theme

The right end of the header on every page has a light/dark theme toggle and a language menu with the same 21 languages as the profile site, which work like the ones on the owner's profile site.

- `dist/theme.js` adds the toggle and applies a saved theme before the page is drawn. Without a saved choice the page follows the system setting. Every colour is a variable at the top of `dist/style.css` (`--c-<light hex>`), with one light and one dark value; the canvas tree in `dist/tree.js` reads the same variables.
- `dist/lang.js` adds the language menu. The pages are written in English; in another language the script translates the interface text with that language's dictionary (`dist/i18n.js` for Japanese, `dist/i18n/<code>.js` for the others, loaded only when chosen) and keeps translating what the atlas scripts add later. Record names, source titles, citations and codes are data and stay as the sources give them. Without a saved choice the language follows the browser. Arabic and Persian are right-to-left; numbers and dates follow each language's conventions (0-9 except Persian ۰-۹).
- Both choices are kept in `localStorage` (`theme`, `lang`) for every page. Switching keeps the URL and adds no history entry. Without JavaScript the pages are English, follow the system theme, and show neither control.
- When you add interface text to a page or a script, add its translation to every dictionary; `node tools/check_i18n.js` lists what is missing.

## Search from the address bar

`https://lang-log.github.io/?q=<text>` opens the top page with `<text>` in the search box and its matches listed under it (the `q` parameter, see Shareable URLs). To add the site as a browser search engine by hand, use that address with `%s` in place of `<text>`.

`dist/opensearch.xml` describes the same search for browsers, and every page links to it with `<link rel="search">`. Firefox then offers "Add Lang Log" in the search menu; Chrome lists it under Settings > Search engine > Manage search engines and site search > Inactive shortcuts after the site has been visited.

---

# Data integration

## Rebuild

Run `python tools/build_data.py`, `python tools/enrich.py`, `python tools/unify.py`, then `python tools/finish_unified.py`. Serve `dist/` as static files.

## Integration model

All 27,177 Glottolog 5.3 records are retained. WALS and the 30 Phlorest data repositories discovered on 2026-10-12 contribute source-conditioned assertions. The software and .github repositories are not data sources. All 30 summary trees are imported; posterior tree samples are not. The D-PLACE catalog was used for discovery only; phylogeny data came directly from each original Phlorest repository.

Exact Glottocodes share one canonical record. Unmatched study samples and internal clades retain source-specific identities. Repeated samples preserve original labels on their edges. No anonymous study clade is claimed to be an accepted named family. Same-language labels remain as documented in provenance.

The default details/summary outline embeds alternative study branches into Glottolog navigation. Those attachments are display context, not genetic ancestry assertions. Each source branch expands only that source's edges. Source switching is not required. The diagram uses dashed navigation attachments and source-tagged occurrences of shared identities.

Automatic conflicts are crossing, non-nested rooted clades after restricting two summary trees to shared exact, non-repeated, non-ancestor tip IDs. Sampling differences, missing taxa and polytomies alone are not conflicts. These are computational comparisons of imported summary topologies, not a review of statistical uncertainty or scientific validity. The Transeurasian paper-level debate is separately curated with proposal, critique and response.

## Exports

XML schema v3 uses canonical nodes, named sources, source-conditioned placement assertions, conflict witnesses and paper debates. OPML repeats shared references to provide a hierarchical outline; node-id and source preserve their identity. SVG is a view export, not the authoritative graph model.

## Verification and scope

All assertion endpoints, original node IDs, XML node/edge counts and 2,247 conflict witnesses were checked. The interaction harness exercises conditional placements, both paper links, native-name search, inherited debates, branch expansion, horizontal layout and export. Browser visual QA is unavailable in this authoring environment.

This is not every publication worldwide. See Sources & scope and provenance.json for exact coverage, per-source licenses, hashes and remaining gaps. No unreviewed node is labeled consensus solely because no alternative has been imported.

## Hugging Face model discovery

`dist/hf-models.js` queries the public Hub API when a language detail is opened, with no account, token, inference call, or model download. `dist/hf-iso-map.js` contains the existing 184 exact ISO 639-1/639-3 equivalences from `source-data/iso-map.json`. Only the selected record's own language/dialect ISO code is used; a family or dialect does not inherit support from its relatives.

The client fetches up to 20 records per equivalent code and selected task, requires an exact `cardData.language` match, deduplicates model IDs, and displays up to 8 models sorted by downloads. Each entry links to its model card and shows task, matched codes, multilingual metadata, license when present, and download count. Results are publisher metadata, not independent quality evaluations or guarantees of coverage. A 30-minute in-memory cache and in-flight deduplication avoid repeated requests; failed calls are retryable, and Hub search links remain available. A stale response cannot overwrite a newer task or language selection. There is no inferred support for Chinese macrolanguage vs Mandarin, or other macrolanguage/member pairs.

The Sources panel documents this integration. XML and OPML remain classification exports and do not embed the live model results. API reference: https://huggingface.co/docs/hub/api ; model card language reference: https://huggingface.co/docs/huggingface_hub/package_reference/cards .

## Signs and scripts extension (17 October 2026)

`signs-and-scripts.html?domain=sign` and `signs-and-scripts.html?domain=scripts` extend the same public atlas. Domain navigation is added to the existing page without replacing its language data or controls.

Rebuild with `python tools/build_visual.py`; validate with `python tools/validate_visual.py` and `node --check dist/signs-and-scripts.js`.

Coverage: all 344 Glottolog 5.3 Sign Language-category records (including categories, families and dialects), all 76 Power et al. CLDF manual-alphabet samples, three Abner et al. consensus trees spanning 19 distinct language samples, all 226 rows of the downloaded ISO 15924 table, and all 325 SIL Scripts Index rows. Exact script codes are merged; SIL-local IDs remain distinct. There are 334 script/notation records, 63 reviewed historical/influence assertions and 1,001 explicit CLDR language/script usage entries. These counts measure different units. They do not establish exhaustive coverage of world literature or all proposed genealogies.

The Abner European trees are independent replicates, not independent publications. Historical manual-alphabet samples retain separate identities and only link to Glottocodes when explicitly mapped in the dataset. A manual-alphabet grouping is not treated as a whole-language genealogy. Broad script ancestry retains the qualifier “intermediate stages omitted”. Ledyard’s proposed Phags-pa influence is linked to the thesis and explicitly accompanied by Lee’s criticism. Brahmi origin accounts appear together with separate citations.

JSON and XML preserve all fields, assertions, source metadata, notes, usage and input checksums. XML uses typed `field`/`item` elements and is tested by exact JSON round-trip. OPML repeats references under alternate parents and preserves assertion citations, but does not carry the full metadata or usage table. Glottolog alias provider/language tags remain intact. Unicode letter samples are not labeled as native names.

Validation passed for catalog coverage, mappings, acyclic relationships, complete OPML reachability and XML round-trip. A temporary LinkeDOM harness also exercised both domains: rendering, pagination, alias search, mobile-menu state, record details, lazy expansion, horizontal/list switching, collapse and source register. This is DOM logic validation, not real-browser rendering or device testing; the managed environment had no supported browser QA capability.

Source files and their original licenses remain attributed. See `source-data/signs-and-scripts/input-provenance.json` and `dist/signs-and-scripts-licenses.txt`. The base language atlas is unchanged apart from domain navigation.

## Variant details and simplified copy (18 October 2026 JST)

Removed decorative hero copy and fixed “Start exploring” suggestions. Persistent dice controls select canonical language/dialect records (not families or study samples); the scripts section samples writing-system records and excludes special/collection codes. The currently selected record is excluded from the next draw.

`record.html?domain=language&id=<record-id>` provides standalone details for base language records and imported source-specific nodes. `domain=sign` and `domain=scripts` use the signs/scripts graph. Tree-node names and sidebar links open the record page. Pages include aliases, native-label evidence, source-conditioned parents and children, competing research accounts, script usage where applicable, and language-tagged Hugging Face results. Shareable URLs, copy-link control, return-to-tree links and random selection are included. Unknown IDs render a not-found state. No new decorative explanatory copy was added.

Syntax and DOM checks cover both list views, random selection, detail routes for language/dialect/source-node/sign/script records, copying URLs, navigation and unknown-ID handling. Real-browser visual QA remains unverified in this managed environment.

## Page data

The atlas and the record detail page (`record.html`) do not load the 30 MB `data.json` and `integrated.json`; those stay as downloads. `tools/split_data.py` writes smaller files to `dist/data/` (built by the Pages workflow, not committed), and `dist/atlas-data.js` rebuilds the same objects from them in the browser:

- `data/atlas.json` (about 0.8 MB compressed): the tree, native names, sources, study trees and conflicts. Glottolog records are stored as columns, and values the browser can recompute (ids inside records, children, root, size, Glottolog assertions, placements) are left out.
- `data/names/<n>.json`: recorded names and spellings, split into `SHARDS` files (set in `dist/atlas-data.js`) by a hash of the record id. A page loads one when it shows a record's names.
- `data/search.json`: the text of all recorded names. The atlas loads it after the tree is shown, so searching by an alternative name (for example 日本語) works a moment later than searching by name, Glottocode or ISO code.

The WALS genus lists in `data.json` are not used by the pages and are not in these files. `tools/split_data.py` rebuilds the objects the same way and stops if anything differs from `data.json` and `integrated.json`.
