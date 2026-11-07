"""Check that each shared value is written in one place only.

The rule (.claude/rules/readable-code.md, and readable-code.md in research-aide):
a value that two files need is written once, and the other file reads it. This
check fails when

- a value listed in tools/single-source.json appears outside its source file
  (and the files listed as checked copies),
- a colour (#rgb, #rrggbb, #rrggbbaa) is written outside dist/style.css and the
  files listed under "colours",
- two files define a constant with the same name and the same value (such as
  the number of name files in a script and again in a page script), which is a copy that will
  drift apart.

Run from the repository root: python3 tools/check_single_source.py
"""

import fnmatch
import json
import re
import subprocess
import sys

from locations import ROOT

CONFIG = json.loads((ROOT / "tools" / "single-source.json").read_text(encoding="utf-8"))
# Code written by hand. Generated files (listed in .prettierignore / written by
# scripts) and third-party data are left out.
CODE = [
    "dist/*.js",
    "dist/*.css",
    "dist/*.html",
    "dist/i18n/*.js",
    "tools/*.py",
    "tools/*.js",
    "tools/*.sh",
]
GENERATED = {"dist/hf-iso-map.js"}
COLOUR = re.compile(r"(?<![\w&/])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
EMPTY = {"{}", "[]", "''", "0", "null", "None"}
# NAME = value, in Python or JavaScript (var/const/let optional).
CONSTANT = re.compile(
    r"(?:^|[\s,;(])(?:(?:var|const|let)\s+)?([A-Z][A-Z0-9_]{2,})\s*=(?!=)\s*([^;\n]+)"
)


def files():
    out = subprocess.run(
        ["git", "ls-files", *CODE], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.split()
    return [f for f in out if f not in GENERATED and f != "tools/single-source.json"]


def matches(path, globs):
    return any(fnmatch.fnmatch(path, g) for g in globs)


def normal(value):
    """A constant's value without spaces, quote style or bracket style."""
    v = re.sub(r"\s+", "", value).rstrip(",;")
    return v.replace('"', "'").replace("(", "[").replace(")", "]")


def main():
    errors = []
    texts = {f: (ROOT / f).read_text(encoding="utf-8") for f in files()}

    for entry in CONFIG["values"]:
        pattern = re.compile(entry["pattern"])
        allowed = [entry["source"], *entry.get("also", [])]
        for f, text in texts.items():
            if matches(f, allowed):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    errors.append(
                        f"{f}:{n}: /{entry['pattern']}/ belongs in {entry['source']} ({entry['why']})"
                    )

    colours = CONFIG["colours"]
    allowed = [colours["source"], *colours["also"]]
    for f, text in texts.items():
        if matches(f, allowed) or f.endswith(".html"):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for m in COLOUR.finditer(line):
                errors.append(
                    f"{f}:{n}: colour {m.group(0)} belongs in {colours['source']} as a token"
                )

    seen = {}
    for f, text in texts.items():
        if f.endswith((".html", ".css")) or "/i18n" in f:
            continue
        for line in text.splitlines():
            for m in CONSTANT.finditer(line):
                key = (m.group(1), normal(m.group(2)))
                seen.setdefault(key, set()).add(f)
    for (name, value), where in sorted(seen.items()):
        # Empty values ({} filled in later, "" ...) say nothing about a shared value.
        if len(where) > 1 and value not in EMPTY:
            errors.append(
                f"{name} = {value[:60]} is defined in {', '.join(sorted(where))}: keep one and read it from there"
            )

    if errors:
        print("\n".join(errors))
        print(
            f"{len(errors)} values written in more than one place (see .claude/rules/readable-code.md)"
        )
        return 1
    print(
        f"single source: {len(CONFIG['values'])} shared values, colours and constants in {len(texts)} files"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
