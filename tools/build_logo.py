"""Write the Lang Log logo, dist/logo.svg: the asterisk and the word mark
"LANG LOG" as one drawing, so the logo link is a single rectangle (one tap
highlight, one focus ring) on every page.

The letters are outlines of Liberation Sans Bold (SIL Open Font License),
which has the same metrics as Arial, the site's font, so the logo looks the
same on every device and needs no web font. Run this script only to change
the logo; it needs fontTools (`pip install fonttools`) and the font file.

The file holds one <symbol id="logo">. Pages draw it with
<svg class="logo" viewBox="..."><use href="logo.svg#logo"/></svg>. Colours
come from the page: the letters use currentColor and the asterisk uses the
--teal custom property, so a light or dark theme on the page applies here too.
"""

import math
import re

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from locations import DIST

FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
OUT = DIST / "logo.svg"
CSS = OUT.with_name("style.css")  # its .logo rule carries the same aspect ratio
TEXT = "LANG LOG"
SIZE = 100  # font size in logo units
TRACKING = 13  # extra space after each letter (about 2px at 13px)
MARK = 180  # side of the asterisk's square
GAP = 62  # space between the asterisk and the letters
STROKE = MARK * 7 / 64  # same weight as the favicon


def main():
    font = TTFont(FONT)
    upm = font["head"].unitsPerEm
    scale = SIZE / upm
    cap = font["OS/2"].sCapHeight * scale
    glyphs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
    pen = SVGPathPen(glyphs)
    height = MARK
    baseline = height / 2 + cap / 2  # letters centred on the asterisk
    x = MARK + GAP
    for ch in TEXT:
        name = cmap[ord(ch)]
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, baseline)))
        x += hmtx[name][0] * scale + TRACKING
    width = math.ceil(x - TRACKING)
    c, r = MARK / 2, MARK / 2 - STROKE / 2
    d = r / math.sqrt(2)
    mark = (
        f"M{c:.1f} {c - r:.1f}V{c + r:.1f}M{c - r:.1f} {c:.1f}H{c + r:.1f}"
        f"M{c - d:.1f} {c - d:.1f}L{c + d:.1f} {c + d:.1f}M{c + d:.1f} {c - d:.1f}L{c - d:.1f} {c + d:.1f}"
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg"><symbol id="logo" viewBox="0 0 {width} {height}">'
        f'<path d="{mark}" fill="none" style="stroke:var(--teal,#386e6d)" stroke-width="{STROKE:.1f}"/>'
        f'<path d="{pen.getCommands()}" fill="currentColor"/></symbol></svg>\n'
    )
    OUT.write_text(svg, encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    css = re.sub(r"(\.logo\{[^}]*aspect-ratio:)\d+/\d+", rf"\g<1>{width}/{height}", css)
    CSS.write_text(css, encoding="utf-8")
    print(f"viewBox 0 0 {width} {height}")


if __name__ == "__main__":
    main()
