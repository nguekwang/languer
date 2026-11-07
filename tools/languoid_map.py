"""Static distribution maps for the record pages under dist/<family>/.../<language>/.

Each map is a small inline SVG: the shared background dist/map/land.svg
(drawn by build_land.py) is referenced with <use>, so it is downloaded once
and cached, and each page adds only its own points. The map works without
JavaScript; dist/map-zoom.js adds zoom and pan, and draws the 1:10m tiles
(dist/map/tiles/) over this background for the part in view.

Projection: Web Mercator (the projection of most web maps), cut at
MAX_LAT north and south, so the whole world is a square WORLD_W wide.
The map repeats to the east and west: the background is drawn once more on
each side, so a view may cross the 180th meridian, and dist/map-zoom.js
lets a visitor drag around the world without end. x = SCALE * longitude in
radians; north is up (y grows downwards, as in SVG).

Points are Glottolog's representative coordinates (one per record). They are
not the area where a language is spoken.
"""

from html import escape
import math

SCALE = 310.0
MAX_LAT = math.degrees(math.atan(math.sinh(math.pi)))  # 85.0511..., the square Web Mercator world

# Extent of the whole map in SVG units: a square, from -WORLD_W / 2 to WORLD_W / 2 in x and y.
WORLD_W = 2 * math.pi * SCALE
WORLD_H = WORLD_W
# The part of the world the locator (and a whole-world view) shows: the map is twice as
# wide as it is high, and the band from INSET_Y down holds every inhabited latitude.
INSET_Y = -0.29 * WORLD_W

LAYERS = (
    ("sphere", "lmap-sphere"),
    ("land", "lmap-land"),
    ("borders", "lmap-border"),
    ("disputed", "lmap-disputed"),
)


def wrap(lon):
    """Longitude in degrees to the range [-180, 180)."""
    return (lon + 180.0) % 360.0 - 180.0


def project(lon, lat):
    """Longitude and latitude in degrees to SVG x, y (origin at 0 degrees, 0 degrees).

    The longitude is not wrapped: 190 lies one tenth of a world east of 170,
    on the copy of the map drawn east of the 180th meridian.
    """
    phi = math.radians(min(max(lat, -MAX_LAT), MAX_LAT))
    return math.radians(lon) * SCALE, -math.log(math.tan(math.pi / 4 + phi / 2)) * SCALE


def unwrap(lons):
    """Shift longitudes by whole turns so the points sit together.

    The points are cut at the widest empty stretch of longitude, so a group
    around the 180th meridian (for example Oceanic) stays in one piece. The
    result is centred on [-180, 180).
    """
    if not lons:
        return []
    s = sorted(wrap(x) for x in lons)
    gaps = [(s[(i + 1) % len(s)] - s[i]) % 360.0 for i in range(len(s))]
    i = max(range(len(s)), key=lambda k: gaps[k])
    cut = s[(i + 1) % len(s)]  # the most western point after the widest gap
    out = [wrap(x) + (360.0 if wrap(x) < cut else 0.0) for x in lons]
    mid = (min(out) + max(out)) / 2
    shift = -360.0 * round(mid / 360.0)
    return [x + shift for x in out]


ASPECT = 2.0  # width / height of every map
MIN_W = 240.0  # smallest starting view, in SVG units (about 45 degrees of longitude at the equator)
ZOOM_MIN_W = 30.0  # smallest view after zooming in (about 550 km across); written as data-min for dist/map-zoom.js
PAD = 0.12  # margin around the points, as a share of their extent


def _view(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w = max((x1 - x0) * (1 + 2 * PAD), MIN_W)
    h = max((y1 - y0) * (1 + 2 * PAD), MIN_W / ASPECT)
    if w / h < ASPECT:
        w = h * ASPECT
    else:
        h = w / ASPECT
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if w >= WORLD_W:
        # The whole way round, from the inhabited band of latitudes.
        return cx - WORLD_W / 2, INSET_Y, WORLD_W, WORLD_W / ASPECT
    # East and west the map goes on; north and south it ends.
    cy = min(max(cy, -WORLD_H / 2 + h / 2), WORLD_H / 2 - h / 2)
    return cx - w / 2, cy - h / 2, w, h


def _num(v):
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


def background(href, vx, vw):
    """<use> elements for the background layers, once for each copy of the world in view.

    Copies lie WORLD_W apart; every layer of every copy comes before the next
    layer, so no copy's sea covers its neighbour's borders.
    """
    copies = [
        k
        for k in (-2, -1, 0, 1, 2)
        if k * WORLD_W - WORLD_W / 2 < vx + vw and k * WORLD_W + WORLD_W / 2 > vx
    ]
    out = []
    for layer, cls in LAYERS:
        for k in copies:
            shift = f' x="{_num(k * WORLD_W)}"' if k else ""
            out.append(f'<use class="{cls}" href="{href}#{layer}"{shift}/>')
    return "".join(out)


def inset_rects(vx, vy, vw, vh):
    """The two rectangles that mark the view on the locator (the second is used when the view crosses its edge)."""
    nx = vx - WORLD_W * math.floor(
        (vx + WORLD_W / 2) / WORLD_W
    )  # left edge in [-WORLD_W / 2, WORLD_W / 2)
    rect = '<rect x="{}" y="{}" width="{}" height="{}"/>'
    return rect.format(_num(nx), _num(vy), _num(vw), _num(vh)) + rect.format(
        _num(nx - WORLD_W), _num(vy), _num(vw), _num(vh)
    )


def map_svg(
    map_dir, main, context=(), self_point=None, label="", main_ids=(), context_ids=(), self_id=""
):
    """Return an inline <svg> map, or "" when there is nothing to place.

    map_dir: relative URL of the map/ directory from the page, ending in "/".
    main: (lon, lat) points of the record's own members, drawn strong.
    context: points of related records (for example sister languages), drawn faint.
    self_point: the record's own point, drawn largest.
    main_ids, context_ids, self_id: the Glottocodes of those points, written into each
    circle as data-g (space-separated when points that overlap are drawn as one), so
    dist/map-zoom.js can show the records of a tapped point with links to their pages.
    """
    focus_ll = list(main) + ([self_point] if self_point else [])
    if not focus_ll:
        return ""
    lons = unwrap([lon for lon, _ in focus_ll])
    mid = (min(lons) + max(lons)) / 2
    focus = [project(lon, lat) for lon, (_, lat) in zip(lons, focus_ll, strict=False)]
    main_xy = focus[: len(main)]
    own = focus[-1] if self_point else None
    # Sister points go on the copy of the world nearest the record's own points.
    context = [project(lon - 360.0 * round((lon - mid) / 360.0), lat) for lon, lat in context]
    vx, vy, vw, vh = _view(focus)
    r = vw / 200  # point radius scales with the view
    show_inset = vw < WORLD_W * 0.5

    def circles(pts, rad, ids=()):
        ids = list(ids) or [""] * len(pts)
        cells = {}
        for (x, y), gid in zip(pts, ids, strict=False):
            # Drop only points that would still overlap at the deepest zoom: points
            # keep their size on screen when the map is zoomed. The records of a
            # dropped point stay on the point drawn in its place.
            g = rad * ZOOM_MIN_W / vw
            key = (round(x / g), round(y / g))
            if key not in cells:
                cells[key] = [x, y, []]
            if gid:
                cells[key][2].append(gid)
        out = []
        for x, y, gids in cells.values():
            data = f' data-g="{escape(" ".join(gids))}"' if gids else ""
            out.append(f'<circle cx="{_num(x)}" cy="{_num(y)}" r="{_num(rad)}"{data}/>')
        return "".join(out)

    land = escape(map_dir + "land.svg")
    parts = [
        f'<svg class="lmap" viewBox="{_num(vx)} {_num(vy)} {_num(vw)} {_num(vh)}" role="img" aria-label="{escape(label)}" preserveAspectRatio="xMidYMid meet" '
        f'data-map="land" data-base="{escape(map_dir)}" data-min="{min_width()}" '
        f'data-world="{world_box()}">',
        f"<title>{escape(label)}</title>",
        f'<g class="lmap-bg">{background(land, vx, vw)}</g>',
    ]
    if context:
        parts.append(f'<g class="lmap-ctx">{circles(context, r * 0.8, context_ids)}</g>')
    if main_xy:
        parts.append(f'<g class="lmap-main">{circles(main_xy, r, main_ids)}</g>')
    if own:
        parts.append(
            f'<g class="lmap-self"><circle cx="{_num(own[0])}" cy="{_num(own[1])}" r="{_num(r * 2.4)}"'
            + (f' data-g="{escape(self_id)}"' if self_id else "")
            + "/></g>"
        )
    if show_inset:
        # Locator: the whole world in the corner, with the shown area marked.
        iw = vw * 0.22
        ih = iw / ASPECT
        ix, iy = vx + vw - iw - vw * 0.015, vy + vh - ih - vw * 0.015
        parts.append(
            f'<g class="lmap-inset"><svg x="{_num(ix)}" y="{_num(iy)}" width="{_num(iw)}" height="{_num(ih)}" '
            f'viewBox="{_num(-WORLD_W / 2)} {_num(INSET_Y)} {_num(WORLD_W)} {_num(WORLD_W / ASPECT)}">'
            f'<use class="lmap-sphere" href="{land}#sphere"/><use class="lmap-land" href="{land}#land"/>'
            f"{inset_rects(vx, vy, vw, vh)}</svg></g>"
        )
    parts.append("</svg>")
    return "".join(parts)


def world_view():
    """viewBox of a map that shows the whole world once (dist/feature-map.html)."""
    return f"{_num(-WORLD_W / 2)} {_num(INSET_Y)} {_num(WORLD_W)} {_num(WORLD_W / ASPECT)}"


def world_box():
    """data-world of every map: the square Web Mercator world."""
    return f"{_num(-WORLD_W / 2)} {_num(-WORLD_H / 2)} {_num(WORLD_W)} {_num(WORLD_H)}"


def min_width():
    """data-min of every map: the smallest view width after zooming in (ZOOM_MIN_W)."""
    return _num(ZOOM_MIN_W)
