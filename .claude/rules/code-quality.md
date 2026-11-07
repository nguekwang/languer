# Code quality checks

Prettier, ESLint and Ruff check every pull request and every push to `main` (the owner's request, 2026-11-07). How to install and run them: "Code quality checks" in `README.md`.

## In CI

- `.github/workflows/quality.yml` has one job per tool (`prettier`, `eslint`, `ruff`), each installing only what it needs (`npm ci --ignore-scripts` or `pip install --require-hashes -r requirements-dev.txt`) and running the same commands as `npm run check`. It has no trigger of its own; callers that `needs: quality` wait for all three jobs. A new tool gets its own job here, not a new workflow file, so the gates in `site.yml` and `pages.yml` cover it without change.
- `site.yml` calls it first; its `build` job (`tools/build_site.sh` and the preview) runs only when it passes.
- `pages.yml` calls it on the default branch before `publish`, for every trigger, because every run of the shared Pages workflow deploys the default branch. Keep `needs: quality` on `publish`, and give any new deployment path the same gate.
- Never skip a check, loosen a rule or add a path to an ignore list to make CI pass; fix the code. A false positive gets a comment with the reason on that line (`// eslint-disable-next-line <rule> -- why`, `# noqa: <rule>` with a comment above).
- Fixes for lint findings must not change what the code does. When a finding is a real bug, fix it in its own pull request.

## Before pushing

- Run `npm run check`; run `npm run format` and `npm run format:python` on the files you changed. New files must pass from the start.
- `tools/build_site.sh` rewrites `dist/lang.js` and `dist/*.html` (asset versions); run the checks on an unbuilt tree (`git checkout -- dist`), as CI does.

## What the tools cover and why some files are left out

- Prettier: JavaScript, CSS, JSON, YAML and Markdown (`.prettierrc.json`: single quotes in JavaScript, double quotes in YAML and Markdown, quoted object keys kept as written, lines of 100), and XML and SVG with `@prettier/plugin-xml`: one attribute per line when an element has more than one (`singleAttributePerLine`, the owner's choice, 2026-11-07), and text kept exactly as written (`xmlWhitespaceSensitivity: preserve`). HTML is a supported type, but `dist/*.html` is left out: `tools/security_policy.py --write` puts the policy `<meta>` tags after `<meta charset="utf-8">` as one exact string, and `--check` compares the text.
- `.prettierignore` also leaves out `source-data/` (published datasets and saved pages, and hand-curated data the build reads as it is) and the committed files that scripts write (`dist/integrated.json`, `dist/provenance.json`, `dist/signs-and-scripts.json`, `dist/language-atlas.xml`, `dist/signs-and-scripts.xml`, `dist/hf-iso-map.js`, `dist/logo.svg`, `dist/map/`). Prettier also skips `.gitignore`. Add a file there only when a script writes it or it is source data, and say why in the comment.
- ESLint (`eslint.config.mjs`): the recommended rules only, no plugins. `dist/**/*.js` are classic browser scripts (`sourceType: script`, browser globals); `tools/**/*.js` are Node.js checks (CommonJS, Node globals).
- Ruff (`pyproject.toml`): rules E, W, F, B and PLE for Python 3.12 (the version CI uses); E501 is off because the formatter sets line length and leaves long strings as they are.
- Versions are exact: `package.json` with `package-lock.json`, `requirements-dev.txt` with hashes. `overrides` pins `minimatch` to a version without the advisory GHSA-g3hv-75wg-m249 until ESLint depends on one; remove it then.

## Waiting for open pull requests

- Left out until #49 is merged: `dist/home.js`, `dist/tree.js`, `dist/i18n.js`, `dist/i18n/`, `dist/style.css` (Prettier) and `dist/home.js`, `dist/tree.js` (ESLint), `tools/build_home.py` (Ruff format). Until #40 is merged: `tools/build_paths.py`, `tools/build_wals_map.py` (Ruff format). Then format or fix them in their own pull request and remove the entries.
- When `dist/style.css` is formatted, `tools/build_logo.py` must still find the `.logo` aspect ratio: its regular expression expects `.logo{...aspect-ratio:W/H` without spaces.
