"""Add a content version to every local CSS, JS and SVG link in dist/*.html.

GitHub Pages serves every file with a ten-minute browser cache
(max-age=600). After a deploy, a browser could pair the new HTML with the
style.css or script it cached from the previous deploy, and the page looked
broken until the cache ran out. This script rewrites, for example,
href="style.css" to href="style.css?v=<hash>", where the hash comes from the
file's content, so a changed file always has a new address and an unchanged
one keeps its cache.

Run it last in the build, after every page has been written. It runs only in
CI; the HTML files committed in dist/ keep plain links.
"""

import hashlib
import re

from locations import DIST


# href="..." or src="..." pointing at a relative .css, .js or .svg file,
# with an optional #fragment (logo.svg#logo). Absolute URLs, data: URIs and
# links that already carry a query are left alone.
LINK = re.compile(r'\b(href|src)="((?:\.\./)*[A-Za-z0-9_./-]+\.(?:css|js|svg))(#[^"?]*)?"')

_versions = {}


def version(path):
    if path not in _versions:
        _versions[path] = (
            hashlib.sha256(path.read_bytes()).hexdigest()[:10] if path.is_file() else None
        )
    return _versions[path]


def rewrite(page):
    text = page.read_text(encoding="utf-8")

    def sub(m):
        attr, url, frag = m.group(1), m.group(2), m.group(3) or ""
        # "/style.css" (dist/404.html, served at any depth) is relative to dist/.
        v = version((DIST / url[1:] if url.startswith("/") else page.parent / url).resolve())
        if v is None:
            return m.group(0)
        return f'{attr}="{url}?v={v}{frag}"'

    new = LINK.sub(sub, text)
    if new != text:
        page.write_text(new, encoding="utf-8")
        return True
    return False


# lang.js loads the dictionary of the chosen language, i18n/<code>.js, itself. Its
# placeholder `var VERSIONS = {};` gets the content hash of every dictionary, so a changed
# dictionary also gets a new address. This runs before the pages are versioned, because
# it changes lang.js and so its hash.
LANG_JS = DIST / "lang.js"
VERSIONS = "var VERSIONS = {};"


def version_dictionaries():
    files = sorted((DIST / "i18n").glob("*.js"))
    table = ", ".join(f"'{f.stem}': '{version(f.resolve())}'" for f in files)
    text = LANG_JS.read_text(encoding="utf-8")
    if VERSIONS not in text:
        raise SystemExit(
            "tools/version_assets.py: placeholder 'var VERSIONS = {};' not found in dist/lang.js"
        )
    LANG_JS.write_text(text.replace(VERSIONS, "var VERSIONS = {" + table + "};"), encoding="utf-8")
    print(f"versioned {len(files)} dictionaries in lang.js")


def main():
    version_dictionaries()
    changed = sum(rewrite(p) for p in DIST.rglob("*.html"))
    print(f"versioned asset links in {changed} pages")


if __name__ == "__main__":
    main()
