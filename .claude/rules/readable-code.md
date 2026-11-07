# Readable code

The shared rule is `readable-code.md` in the `research-aide` repository (each value is written once; names say what a value means). Here:

## Where each shared value lives

- Site name, title suffix (` · Lang Log by yoshi`), the profile link and the copyright line: `tools/site_brand.py`. The generators import it; the hand-written pages in `dist/*.html` are kept equal by `python3 tools/site_brand.py --check` (`--write` rewrites them). `dist/lang.js` and `dist/record.js` read what the page already has.
- Repository folders (`ROOT`, `DIST`): `tools/locations.py`. Never work them out again from `__file__`.
- Colours: the tokens at the top of `dist/style.css`. Other CSS uses `var(--...)`; scripts read a token with `getComputedStyle`. Exceptions (files opened on their own, where the stylesheet does not apply) are listed in `tools/single-source.json`.
- A length the CSS and a script both need (such as `--stats-duration`): a custom property in `dist/style.css`, read by the script.
- Map sizes (`ZOOM_MIN_W`, the world box, the layers): `tools/languoid_map.py`, written into each map's attributes and `<use>` elements; `dist/map-zoom.js` reads them and keeps no defaults of its own.
- The number of name files (`SHARDS`): `dist/atlas-data.js`; `tools/split_data.py` reads it.
- Interface languages: `LANGS` in `dist/lang.js`; `tools/check_i18n.js` reads it.

## Checks

- `tools/check_single_source.py` (run by `tools/build_site.sh`) fails on a copy of a value listed in `tools/single-source.json`, on a colour outside `dist/style.css` and the listed files, and on a constant with the same name and value in two files. A new shared value gets an entry there in the same pull request.
- Prettier, ESLint and Ruff (`.claude/rules/code-quality.md`) handle layout and common mistakes.

## Known gaps (fix when the file is next worked on)

- `Glottolog 5.3` is written in about 20 places (pages, scripts, dictionaries); it should come from `glottologVersion` in the data, with a placeholder in the dictionaries.
- The colour tokens are named after their light-theme value (`--c-386e6d`), so the name says nothing and the dark theme gives `--c-ffffff` a dark colour. Rename them by role (`--surface`, `--accent`), after PR #49.
- The phone width `700px` is repeated in every `@media` rule (CSS cannot use a variable there) and again in `dist/tree.js`; the script should read a custom property instead.
- `dist/*.js`, `dist/*.css` and many `tools/*.py` are written as long single lines; the formatter breaks them up (the files #53 left out are formatted in its follow-up).
