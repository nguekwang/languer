"""The site name, the owner's profile link and the copyright line: one place for each.

Every page title ends with TITLE_SUFFIX, and "yoshi" in the header links to
PROFILE_URL (the owner's title rule: research-aide .claude/rules/titles.md and
.claude/rules/titles.md here). The page generators (tools/build_home.py,
tools/build_paths.py) write them from here. The hand-written pages in dist/
carry the same text: `--check` (run by tools/build_site.sh) fails if one of
them differs, and `--write` rewrites their "by yoshi" link from here.

dist/lang.js switches the profile link to the interface language by changing
the language part of the link's own address, so it keeps no copy of
PROFILE_URL; dist/record.js keeps the title suffix its page was built with.
"""

import re
import sys
from html import escape

from locations import DIST


SITE_NAME = "Lang Log"
OWNER = "MATSUURA Yoshihiro"
HOME_TITLE = f"{SITE_NAME} by yoshi"
TITLE_SUFFIX = f" · {HOME_TITLE}"
# The English page of the personal site, with the ref that tells it where the
# visit came from (research-aide .claude/rules/profile-links.md).
PROFILE_REF = "langlog"
PROFILE_URL = f"https://nguekwang.github.io/en/?ref={PROFILE_REF}"
COPYRIGHT = f"© 2026 {OWNER}. All rights reserved."

# Any "by yoshi" link in a page, whatever its attributes.
ANY_BY = re.compile(r'<(span|p) class="(by|home-by)">by <a [^>]*>yoshi</a></\1>')


def by_yoshi(tag="span", cls="by"):
    """The "by yoshi" line; "yoshi" links to the profile (class "profile", for dist/lang.js)."""
    link = f'<a class="profile" href="{escape(PROFILE_URL)}" title="{escape(OWNER)}">yoshi</a>'
    return f'<{tag} class="{cls}">by {link}</{tag}>'


def problems(text):
    out = []
    if text.count(by_yoshi()) != 1 or len(ANY_BY.findall(text)) != 1:
        out.append('does not have the current "by yoshi" link exactly once')
    title = re.search(r"<title>([^<]*)</title>", text)
    if not title or not title.group(1).endswith(TITLE_SUFFIX.strip()):
        out.append(f'has a title that does not end with "{TITLE_SUFFIX.strip()}"')
    return out


def main(argv):
    pages = sorted(DIST.glob("*.html"))
    if argv[1:] == ["--write"]:
        for page in pages:
            text = page.read_text(encoding="utf-8")
            new = ANY_BY.sub(lambda m: by_yoshi(m.group(1), m.group(2)), text)
            if new != text:
                page.write_text(new, encoding="utf-8")
        return 0
    if argv[1:] != ["--check"]:
        print("usage: site_brand.py --check | --write", file=sys.stderr)
        return 2
    bad = 0
    for page in pages:
        if page.name == "index.html":  # written by build_home.py from here
            continue
        for p in problems(page.read_text(encoding="utf-8")):
            bad += 1
            print(f"dist/{page.name}: {p}")
    if bad:
        print("run: python3 tools/site_brand.py --write")
        return 1
    print(f"site name and profile link as in tools/site_brand.py in {len(pages)} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
