"""The security policy of every page in dist/: one place for the <meta> tags.

GitHub Pages cannot send our own response headers, so the policies a browser
accepts from a <meta> element are written into the <head> of every page:

- Content-Security-Policy: only the site itself, plus https://huggingface.co
  for the model list on record pages (dist/hf-models.js). No inline scripts,
  inline styles allowed only for WebKit's <select> (see CSP), no plugins, no frames, no <base>.
- referrer: no-referrer, so no page address leaves the site.

Policies that only work as response headers (frame-ancestors,
X-Frame-Options, Strict-Transport-Security, X-Content-Type-Options,
Permissions-Policy, Cross-Origin-*-Policy) are listed in
.claude/rules/security.md; they wait for a host that can send headers.

The page generators (tools/build_home.py, tools/build_paths.py) write HEAD
from here. The hand-written pages in dist/ carry the same text; run
`python3 tools/security_policy.py --write` after changing the policy.
`--check` (run by tools/build_site.sh) fails if any page in dist/ lacks the
current HEAD, has a second policy, or has a style="..." attribute or an
inline script, which the policy would block.
"""

import re
import sys

from locations import DIST


# A new script, style, image or connection source changes this list, in the
# same pull request (research-aide .claude/rules/web-security.md).
CSP = "; ".join(
    [
        "default-src 'none'",
        "script-src 'self'",
        # 'unsafe-inline' only for styles (the owner's choice, 2026-11-07): WebKit
        # reports a blocked inline stylesheet for every <select> under a strict
        # style-src, from its own rendering of the menu, not from the site. Scripts
        # stay strict, and --check still refuses style="..." in the site's own pages.
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self'",
        "connect-src 'self' https://huggingface.co",
        "base-uri 'none'",
        "form-action 'self'",  # the search form on the top page goes to ./
        "object-src 'none'",
        # No upgrade-insecure-requests: no source above allows http:, so it would
        # add nothing on the live HTTPS site, and WebKit applies it to
        # http://127.0.0.1, which breaks the local browser check.
    ]
)

HEAD = (
    f'<meta http-equiv="Content-Security-Policy" content="{CSP}">'
    '<meta name="referrer" content="no-referrer">'
)

CHARSET = '<meta charset="utf-8">'
ANY_POLICY = re.compile(
    r'<meta http-equiv="Content-Security-Policy"[^>]*>(<meta name="referrer"[^>]*>)?'
)
INLINE_STYLE = re.compile(r"<[^>]*\sstyle=")
INLINE_SCRIPT = re.compile(r'<script(?![^>]*\ssrc=)(?![^>]*type="application/ld\+json")[^>]*>')
INLINE_HANDLER = re.compile(r"<[^>]*\son[a-z]+=", re.I)


def problems(text):
    out = []
    if text.count(HEAD) != 1 or len(ANY_POLICY.findall(text)) != 1:
        out.append("does not have the current policy exactly once")
    # A <meta> policy covers only what comes after it, so it goes right after the charset.
    elif not text.startswith('<!doctype html><html lang="en"><head>' + CHARSET + HEAD):
        out.append("does not start <head> with the charset and the policy")
    if INLINE_STYLE.search(text):
        out.append('has a style="..." attribute')
    if INLINE_SCRIPT.search(text):
        out.append("has an inline script")
    if INLINE_HANDLER.search(text):
        out.append("has an inline event handler")
    if "<base" in text:
        out.append("has a <base> element")
    return out


def write(page):
    text = page.read_text(encoding="utf-8")
    new = ANY_POLICY.sub("", text).replace(CHARSET, CHARSET + HEAD, 1)
    if new != text:
        page.write_text(new, encoding="utf-8")


def main(argv):
    if argv[1:] == ["--write"]:
        for page in sorted(DIST.glob("*.html")):
            write(page)
        return 0
    if argv[1:] != ["--check"]:
        print("usage: security_policy.py --check | --write", file=sys.stderr)
        return 2
    bad = 0
    count = 0
    for page in DIST.rglob("*.html"):
        count += 1
        for p in problems(page.read_text(encoding="utf-8")):
            bad += 1
            if bad <= 20:
                print(f"{page.relative_to(DIST)}: {p}")
    # The SVG files are pages too when opened directly.
    for svg in DIST.rglob("*.svg"):
        if re.search(r"<script|\son[a-z]+=", svg.read_text(encoding="utf-8"), re.I):
            bad += 1
            print(f"{svg.relative_to(DIST)}: has a script")
    if bad:
        print(f"{bad} problems in {count} pages")
        return 1
    print(f"security policy present in all {count} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
