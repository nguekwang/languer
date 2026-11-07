# Titles

The shared rule is `titles.md` in the `research-aide` repository (every page title and the header logo end with ` by yoshi`). Here:

- The `ref` for links to the personal site is `langlog` (`profile-links.md` in `research-aide`).
- In the header, `yoshi` links to the personal site's page in the interface language: `https://nguekwang.github.io/en/?ref=langlog`, or `/ja/?ref=langlog` when the language menu is set to Japanese. The link is written once, by `by_yoshi()` in `tools/site_brand.py` (with the title suffix and the copyright line); `dist/lang.js` switches its language part (`profileLinks()`).
