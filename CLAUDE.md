# CLAUDE.md

@../research-aide/.claude/common.md

Lang Log (https://lang-log.github.io/): an atlas of language families, sign languages and writing systems, built from source data into static pages in `dist/` by the scripts in `tools/`, checked and deployed by GitHub Actions.

This file holds only the principles. The owner's shared rules come from the `research-aide` repository (imported above; clone it next to this repository). Rules only for this repository live in `.claude/rules/`.

If the shared rules are not in your context (the import above can be skipped, for example before external imports are approved or when `../research-aide` is missing), read `../research-aide/.claude/common.md` and every file it lists before doing anything else. If `../research-aide` does not exist, clone `nguekwang/research-aide` next to this repository first, or tell the owner.

## Principles

- **Show the sources.** Every classification says which source it follows; alternative hypotheses are shown side by side, not merged away.
- **Static pages for now.** The site is plain files on GitHub Pages, with no server or database (the owner's decision, 2026-11-07; it may change later).
- **Fix things once, at the source.** Page generators in `tools/`, shared style and scripts in `dist/`; never patch one generated page.

## Where the rules are

- `.claude/rules/titles.md`: the ` by yoshi` title and the profile link, as used here.
- `.claude/rules/security.md`: the Content-Security-Policy and referrer policy on every page, and the headers GitHub Pages cannot send.
- `.claude/rules/license.md`: all rights reserved for the owner's work; third-party data keeps its own license.
- `.claude/rules/logo.md`: the Lang Log logo is always the one SVG.
- `.claude/rules/readable-code.md`: where each shared value is defined, and the check that finds copies.
- `.claude/rules/code-quality.md`: Prettier, ESLint and Ruff on every pull request and before every deployment.
- `.claude/rules/interface-text.md` (`dist/**`, `tools/**`): interface text in English and Japanese, colours, header.
- `.claude/rules/previews.md` (`.github/**`, `tools/build_site.sh`): pull request previews here.
- Browsers: `.github/workflows/browsers.yml` runs the shared browser check (`web-browsers.md` in `research-aide`) on every pull request; add a page there when a new kind of page appears.
