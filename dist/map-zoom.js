// Zoom and pan for the maps drawn by tools/languoid_map.py (svg.lmap on the record pages)
// and for the language feature map. Without JavaScript the map is a still picture; this
// script only adds movement.
//
// - The map goes round the world: dragging east or west never reaches an edge. The
//   background is drawn three times side by side (the world and one copy on each side),
//   the view's centre is kept on the middle copy, and every point is moved to the copy
//   nearest the centre of the view. North and south the map ends, as on other web maps.
// - Drag (mouse or one finger), pinch, Ctrl/Cmd + wheel or trackpad pinch, double click,
//   the + / - buttons (only with a mouse or trackpad), Reset, and the keyboard
//   (+ - arrows 0) move the view. Reset and the buttons glide to the new view instead of
//   jumping, unless the visitor asked for reduced motion.
// - Points keep their size on screen at every zoom (their r is rescaled), and border lines
//   keep their width (vector-effect in the map files), so nothing grows blurry or blobby.
// - Once the view is narrower than TILE_BELOW, the 1:10m tiles in map/tiles/<name>/ for the
//   part in view are drawn over the 1:50m world map (see tools/build_land.py).
//
// - Map view: the button in the corner opens the map over the whole window, with nothing
//   else on screen; the close button, Esc or the browser's Back button closes it. The page
//   cannot scroll meanwhile, so a plain wheel zooms too. The view keeps its scale on screen
//   when it opens and closes, and takes the shape of the window. The address gets
//   #map-view (one history entry), so a shared link opens the map view at once.
// - Points: a tap (or click) on a circle with data-g (Glottocodes, written by
//   languoid_map.py) shows a box with the names of its records, each a link to the
//   record's page. Names and addresses come from dist/atlas-data.js and
//   dist/lineage-paths.js, loaded on the first tap; records() is shared with the
//   feature map, whose own box shows more.
//
// Other pages can reuse it: window.LangLogMap.mount(svg) on an <svg> with the attributes
// languoid_map.py writes (viewBox, data-map, data-base, data-min, data-world). The svg receives an
// "lmap:view" event, detail {k, x, y, w, h}, after every change; k is the view width
// divided by the starting width, so a point of radius r0 should be drawn at r0 * k. A page
// that adds or replaces points after mounting calls refresh() on the object mount returns.
(function () {
  'use strict';
  var TILE_BELOW = 700; // view width (SVG units) below which tiles are drawn
  var STEP = 1.6; // zoom factor of one button press or key press
  var GLIDE_MS = 550; // length of the Reset animation
  var STEP_MS = 220; // length of the + / - animation
  var HASH = '#map-view'; // address of the map view
  var TAP_PX = 14; // how far from a point (screen pixels) a tap still hits it
  var manifest = null,
    manifestWait = [],
    atlas = null,
    opened = null;

  // [{id, name, url}] of Glottocodes; url is '' for a record without its own page. root is
  // the site root relative to the page ("../../").
  function records(ids, root) {
    var A = window.AtlasData,
      P = window.LineagePaths;
    if (!A || !P)
      return Promise.resolve(
        ids.map(function (id) {
          return { id: id, name: id, url: '' };
        }),
      );
    if (!atlas) {
      A.base = root + 'data/';
      atlas = A.load().then(function (r) {
        return P.init(r.d.nodes, r.d.roots, root).then(function () {
          return r.d.nodes;
        });
      });
      atlas.catch(function () {
        atlas = null;
      });
    }
    return atlas.then(function (nodes) {
      return ids.map(function (id) {
        var n = nodes[id];
        return { id: id, name: n ? n.name : id, url: n ? root + P.url(id) : '' };
      });
    });
  }

  function icon(d) {
    var s = el('svg', {
      viewBox: '0 0 16 16',
      width: '16',
      height: '16',
      'aria-hidden': 'true',
      focusable: 'false',
    });
    s.appendChild(
      el('path', {
        d: d,
        fill: 'none',
        stroke: 'currentColor',
        'stroke-width': '1.6',
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
      }),
    );
    return s;
  }
  var ICON_OPEN = 'M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4';
  var ICON_CLOSE = 'M3.5 3.5l9 9M12.5 3.5l-9 9';

  function loadManifest(base, done) {
    if (manifest) return done(manifest);
    manifestWait.push(done);
    if (manifestWait.length > 1) return;
    fetch(base + 'tiles.json')
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .catch(function () {
        return null;
      })
      .then(function (m) {
        manifest = m || { grid: [1, 1], bounds: [0, 0, 1, 1], tiles: {} };
        manifestWait.splice(0).forEach(function (f) {
          f(manifest);
        });
      });
  }

  function el(name, attrs) {
    var e = document.createElementNS('http://www.w3.org/2000/svg', name);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  function reducedMotion() {
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function ease(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  function mount(svg) {
    if (svg.__lmap) return svg.__lmap;
    var vb = svg.viewBox.baseVal;
    var home = { x: vb.x, y: vb.y, w: vb.width, h: vb.height };
    var homeAspect = home.w / home.h,
      aspect = homeAspect;
    // Map view: px is the width of the map on screen divided by its width in the page, so
    // points, tiles and zoom limits keep their size on screen.
    var full = false,
      px = 1,
      pageW = 0;
    // Sizes come only from the attributes languoid_map.py writes; a map without them is not mounted.
    var name = svg.getAttribute('data-map');
    var base = svg.getAttribute('data-base');
    var minW = parseFloat(svg.getAttribute('data-min'));
    var wb = (svg.getAttribute('data-world') || '').split(' ').map(parseFloat);
    if (!name || base === null || !(minW > 0) || wb.length !== 4 || wb.some(isNaN)) return null;
    var world = { x: wb[0], y: wb[1], w: wb[2], h: wb[3] };
    var W = world.w;
    // The starting view may lie east of the 180th meridian (languoid_map.py keeps a group of
    // points together); measure it on the middle copy of the world, as clamp() does.
    home.x -= W * Math.floor((home.x + home.w / 2 - world.x) / W);
    var view = { x: home.x, y: home.y, w: home.w, h: home.h };
    var raf = 0,
      glide = 0;

    // Background: every layer three times, one world apart.
    var bg = svg.querySelector('.lmap-bg');
    if (!bg) {
      bg = el('g', { 'class': 'lmap-bg' });
      svg.insertBefore(bg, svg.querySelector(':scope > use'));
    }
    // The layers, in the order the page draws them (LAYERS in languoid_map.py): each <use>
    // names its file, its layer (#sphere, #land, ...) and its class. Copies of a layer share a class.
    var layers = [],
      seen = {};
    Array.prototype.forEach.call(
      svg.querySelectorAll(':scope > use, .lmap-bg > use'),
      function (u) {
        var cls = u.getAttribute('class'),
          href = u.getAttribute('href').split('#');
        if (!seen[cls]) {
          seen[cls] = true;
          layers.push({ file: href[0], id: href[1], cls: cls });
        }
        u.parentNode.removeChild(u);
      },
    );
    // Tiles (tools/build_land.py) hold the same layers, with the sea of the tile in place of the sphere.
    var tileLayers = layers.map(function (p) {
      return { id: p.id === 'sphere' ? 'sea' : p.id, cls: p.cls };
    });
    layers.forEach(function (p) {
      [-1, 0, 1].forEach(function (k) {
        var u = el('use', { href: p.file + '#' + p.id, 'class': p.cls });
        if (k) u.setAttribute('x', k * W);
        bg.appendChild(u);
      });
    });
    var tiles = el('g', { 'class': 'lmap-tiles' });
    tileLayers.forEach(function () {
      tiles.appendChild(el('g', {}));
    });
    // Tiles cover the whole world map under them, borders included, and carry their own.
    bg.appendChild(tiles);
    var shown = {};

    // Points: the radius of the ones written in the page, and their own x.
    var scaled = Array.prototype.map.call(
      svg.querySelectorAll('.lmap-ctx circle, .lmap-main circle, .lmap-self circle'),
      function (c) {
        return [c, parseFloat(c.getAttribute('r'))];
      },
    );
    var points = null;
    function allPoints() {
      if (!points) {
        points = Array.prototype.slice.call(svg.querySelectorAll('circle'));
        points.forEach(function (c) {
          if (c.__x0 === undefined) {
            c.__x0 = parseFloat(c.getAttribute('cx'));
            c.__k = 0;
          }
        });
      }
      return points;
    }

    var inset = svg.querySelector('.lmap-inset > svg');
    var insetRects = inset ? Array.prototype.slice.call(inset.querySelectorAll('rect')) : [];
    if (inset && insetRects.length === 1) {
      insetRects.push(insetRects[0].cloneNode(false));
      inset.appendChild(insetRects[1]);
    }

    // Widest view: the whole world once, and never taller than the world.
    function lim(w) {
      return Math.min(Math.max(w, minW * px), W, world.h * aspect);
    }

    function fit(v) {
      v.w = lim(v.w);
      v.h = v.w / aspect;
      // East and west: keep the centre on the middle copy of the world.
      var c = v.x + v.w / 2;
      v.x -= W * Math.floor((c - world.x) / W);
      if (v.h >= world.h) v.y = world.y + (world.h - v.h) / 2;
      else v.y = Math.min(Math.max(v.y, world.y), world.y + world.h - v.h);
      return v;
    }
    function clamp() {
      fit(view);
    }
    // The starting view at the present size: its centre, at its scale on screen.
    function homeView() {
      var w = lim(home.w * px);
      return fit({ x: home.x + home.w / 2 - w / 2, y: home.y + home.h / 2 - w / aspect / 2, w: w });
    }

    function draw() {
      raf = 0;
      svg.setAttribute(
        'viewBox',
        [view.x, view.y, view.w, view.h]
          .map(function (v) {
            return +v.toFixed(2);
          })
          .join(' '),
      );
      var k = view.w / (home.w * px),
        e = view.w / px;
      for (var i = 0; i < scaled.length; i++)
        scaled[i][0].setAttribute('r', +(scaled[i][1] * k).toFixed(3));
      // Each point goes to the copy of the world nearest the centre of the view.
      var cx = view.x + view.w / 2,
        ps = allPoints();
      for (var j = 0; j < ps.length; j++) {
        var p = ps[j],
          n = Math.round((cx - p.__x0) / W);
        if (n !== p.__k) {
          p.__k = n;
          p.setAttribute('cx', +(p.__x0 + n * W).toFixed(2));
        }
      }
      if (inset) {
        var show = e < W * 0.5;
        inset.parentNode.style.display = show ? '' : 'none';
        if (show) {
          var iw = Math.min(view.w, view.h * 2) * 0.22,
            ih = iw / 2;
          inset.setAttribute('x', view.x + view.w - iw - view.w * 0.015);
          inset.setAttribute('y', view.y + view.h - ih - view.w * 0.015);
          inset.setAttribute('width', iw);
          inset.setAttribute('height', ih);
          var nx = view.x - W * Math.floor((view.x - world.x) / W);
          insetRects.forEach(function (r, i) {
            r.setAttribute('x', nx - i * W);
            r.setAttribute('y', view.y);
            r.setAttribute('width', view.w);
            r.setAttribute('height', view.h);
          });
        }
      }
      var hv = homeView();
      var moved =
        Math.abs(view.w - hv.w) > 0.01 ||
        Math.abs(view.x - hv.x) > 0.01 ||
        Math.abs(view.y - hv.y) > 0.01;
      svg.classList.toggle('lmap-moved', moved);
      svg.classList.toggle('lmap-in', e < home.w - 0.01);
      updateTiles(e);
      svg.dispatchEvent(
        new CustomEvent('lmap:view', {
          detail: { k: k, x: view.x, y: view.y, w: view.w, h: view.h },
        }),
      );
    }

    function schedule() {
      clamp();
      if (!raf) raf = requestAnimationFrame(draw);
    }

    function updateTiles(e) {
      if (e >= TILE_BELOW) {
        tiles.style.display = 'none';
        return;
      }
      tiles.style.display = '';
      loadManifest(base, function (m) {
        var have = m.tiles[name] || [];
        var gx = m.grid[0],
          gy = m.grid[1],
          b = m.bounds,
          tw = b[2] / gx,
          th = b[3] / gy;
        // Columns run on past the edge of the world; column c is tile c mod gx, one world over.
        var c0 = Math.floor((view.x - b[0]) / tw),
          c1 = Math.floor((view.x + view.w - b[0]) / tw);
        var r0 = Math.max(0, Math.floor((view.y - b[1]) / th)),
          r1 = Math.min(gy - 1, Math.floor((view.y + view.h - b[1]) / th));
        for (var c = c0; c <= c1; c++)
          for (var r = r0; r <= r1; r++) {
            var col = ((c % gx) + gx) % gx,
              shift = Math.floor(c / gx) * b[2];
            var id = col + '-' + r,
              key = id + '@' + Math.round(shift);
            if (shown[key] || have.indexOf(id) < 0) continue;
            shown[key] = true;
            var href = base + 'tiles/' + name + '/' + id + '.svg';
            // One group per layer, so no tile's sea covers the edge of its neighbour's land.
            tileLayers.forEach(function (p, i) {
              var u = el('use', { href: href + '#' + p.id, 'class': p.cls });
              if (shift) u.setAttribute('x', shift);
              tiles.childNodes[i].appendChild(u);
            });
          }
      });
    }

    function stop() {
      if (glide) {
        cancelAnimationFrame(glide);
        glide = 0;
      }
    }

    // Move smoothly to the view {x, y, w}: the centre slides along the shorter way round
    // the world while the width changes at an even rate of zoom.
    function glideTo(to, ms) {
      stop();
      to.w = lim(to.w);
      if (reducedMotion()) {
        view = { x: to.x, y: to.y, w: to.w, h: to.w / aspect };
        schedule();
        return;
      }
      var fw = view.w,
        tw = to.w;
      var fx = view.x + view.w / 2,
        tx = to.x + to.w / 2;
      fx -= W * Math.round((fx - tx) / W);
      var fy = view.y + view.h / 2,
        ty = to.y + to.w / aspect / 2;
      var t0 = performance.now();
      function frame(now) {
        var t = Math.min(1, (now - t0) / ms),
          e = ease(t);
        var w = Math.exp(Math.log(fw) + (Math.log(tw) - Math.log(fw)) * e);
        var cx = fx + (tx - fx) * e,
          cy = fy + (ty - fy) * e;
        view = { x: cx - w / 2, y: cy - w / aspect / 2, w: w, h: w / aspect };
        clamp();
        draw();
        glide = t < 1 ? requestAnimationFrame(frame) : 0;
      }
      glide = requestAnimationFrame(frame);
    }

    // The view after zooming by factor f (>1 zooms in) keeping the SVG point (px, py) where it is.
    function zoomed(f, px, py) {
      if (px === undefined) {
        px = view.x + view.w / 2;
        py = view.y + view.h / 2;
      }
      var w = lim(view.w / f);
      var s = w / view.w;
      return { x: px - (px - view.x) * s, y: py - (py - view.y) * s, w: w };
    }
    function zoom(f, px, py) {
      stop();
      var v = zoomed(f, px, py);
      view.x = v.x;
      view.y = v.y;
      view.w = v.w;
      schedule();
    }
    function zoomSmooth(f) {
      glideTo(zoomed(f), STEP_MS);
    }

    function toSvg(clientX, clientY) {
      var r = svg.getBoundingClientRect();
      // preserveAspectRatio meet: the view fills the box when the box has the same aspect.
      var scale = Math.max(view.w / r.width, view.h / r.height);
      var ox = (r.width - view.w / scale) / 2,
        oy = (r.height - view.h / scale) / 2;
      return [
        view.x + (clientX - r.left - ox) * scale,
        view.y + (clientY - r.top - oy) * scale,
        scale,
      ];
    }

    function reset() {
      glideTo(homeView(), GLIDE_MS);
    }

    // Pointers: one pans (a finger too, from the start: touch-action is none on the map,
    // so the page scrolls from outside the map), two pinch.
    var pts = {},
      start = null;
    function snapshot() {
      var ids = Object.keys(pts);
      if (!ids.length) {
        start = null;
        return;
      }
      var a = pts[ids[0]],
        b = pts[ids[1]] || a;
      start = {
        n: ids.length,
        view: { x: view.x, y: view.y, w: view.w },
        mid: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2],
        dist: Math.hypot(a[0] - b[0], a[1] - b[1]) || 1,
      };
      start.at = toSvg(start.mid[0], start.mid[1]);
    }
    svg.addEventListener('pointerdown', function (e) {
      if (e.button !== undefined && e.button !== 0) return;
      stop();
      pts[e.pointerId] = [e.clientX, e.clientY];
      try {
        svg.setPointerCapture(e.pointerId);
      } catch {
        /* the pointer is already gone */
      }
      svg.classList.add('lmap-drag');
      snapshot();
    });
    svg.addEventListener('pointermove', function (e) {
      if (!pts[e.pointerId] || !start) return;
      pts[e.pointerId] = [e.clientX, e.clientY];
      var ids = Object.keys(pts);
      if (start.n !== ids.length) snapshot();
      var a = pts[ids[0]],
        b = pts[ids[1]] || a;
      var mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
      var f = ids.length > 1 ? Math.hypot(a[0] - b[0], a[1] - b[1]) / start.dist : 1;
      var w = lim(start.view.w / f),
        s = w / start.view.w;
      var scale = start.at[2] * s;
      view.w = w;
      view.x = start.at[0] - (start.at[0] - start.view.x) * s - (mid[0] - start.mid[0]) * scale;
      view.y = start.at[1] - (start.at[1] - start.view.y) * s - (mid[1] - start.mid[1]) * scale;
      schedule();
      e.preventDefault();
    });
    function up(e) {
      delete pts[e.pointerId];
      if (!Object.keys(pts).length) svg.classList.remove('lmap-drag');
      snapshot();
    }
    svg.addEventListener('pointerup', up);
    svg.addEventListener('pointercancel', up);
    svg.addEventListener(
      'wheel',
      function (e) {
        // Plain wheel scrolls the page; Ctrl/Cmd + wheel (and trackpad pinch, which browsers
        // report as Ctrl + wheel) zooms the map.
        // In the map view there is no page to scroll, so every wheel zooms.
        if (!full && !e.ctrlKey && !e.metaKey) return;
        e.preventDefault();
        var p = toSvg(e.clientX, e.clientY);
        zoom(Math.exp(-e.deltaY * (e.deltaMode === 1 ? 0.05 : 0.0025)), p[0], p[1]);
      },
      { passive: false },
    );
    // Safari trackpad pinch.
    var g0 = null;
    svg.addEventListener('gesturestart', function (e) {
      e.preventDefault();
      stop();
      g0 = { w: view.w, at: toSvg(e.clientX, e.clientY) };
    });
    svg.addEventListener('gesturechange', function (e) {
      if (!g0) return;
      e.preventDefault();
      var w = lim(g0.w / e.scale);
      zoom(view.w / w, g0.at[0], g0.at[1]);
    });
    svg.addEventListener('gestureend', function () {
      g0 = null;
    });
    svg.addEventListener('dblclick', function (e) {
      var p = toSvg(e.clientX, e.clientY);
      glideTo(zoomed(e.shiftKey ? 1 / STEP : STEP, p[0], p[1]), STEP_MS);
    });
    svg.setAttribute('tabindex', '0');
    svg.addEventListener('keydown', function (e) {
      var d = view.w * 0.15,
        used = true;
      if (e.key === '+' || e.key === '=') zoomSmooth(STEP);
      else if (e.key === '-' || e.key === '_') zoomSmooth(1 / STEP);
      else if (e.key === '0') reset();
      else if (e.key === 'Escape' && full) closeView();
      else if (e.key === 'ArrowLeft') {
        stop();
        view.x -= d;
        schedule();
      } else if (e.key === 'ArrowRight') {
        stop();
        view.x += d;
        schedule();
      } else if (e.key === 'ArrowUp') {
        stop();
        view.y -= d;
        schedule();
      } else if (e.key === 'ArrowDown') {
        stop();
        view.y += d;
        schedule();
      } else used = false;
      if (used) e.preventDefault();
    });

    // Buttons, placed over the top right corner of the map.
    var bar = document.createElement('div');
    bar.className = 'lmap-tools';
    // + and - only where a mouse or trackpad exists; on phones and tablets people pinch.
    var fine = !window.matchMedia || window.matchMedia('(any-pointer: fine)').matches;
    (fine
      ? [
          [
            '+',
            'Zoom in',
            function () {
              zoomSmooth(STEP);
            },
          ],
          [
            '−',
            'Zoom out',
            function () {
              zoomSmooth(1 / STEP);
            },
          ],
        ]
      : []
    )
      .concat([['Reset', 'Reset view', reset]])
      .forEach(function (b) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = b[0];
        btn.setAttribute('aria-label', b[1]);
        btn.title = b[1];
        btn.addEventListener('click', b[2]);
        if (b[0] === 'Reset') btn.className = 'lmap-reset';
        bar.appendChild(btn);
      });
    var fullBtn = document.createElement('button');
    fullBtn.type = 'button';
    fullBtn.className = 'lmap-full-btn';
    bar.appendChild(fullBtn);
    function label(open) {
      var t = open ? 'Close map view' : 'Map view';
      fullBtn.textContent = '';
      fullBtn.appendChild(icon(open ? ICON_CLOSE : ICON_OPEN));
      fullBtn.setAttribute('aria-label', t);
      fullBtn.title = t;
      fullBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    label(false);
    var parent = svg.parentNode;
    var wrap = document.createElement('div');
    wrap.className = 'lmap-wrap';
    parent.insertBefore(wrap, svg);
    wrap.appendChild(svg);
    wrap.appendChild(bar);
    // The part of the page that fills the window in the map view: the map, or a larger
    // box marked lmap-host that holds the map and its own overlays (the feature map).
    var host = wrap.closest('.lmap-host') || wrap;

    // Map view. resize() keeps the centre and the scale on screen while the box changes.
    var pushed = false,
      boxW = 0;
    function resize(before) {
      var r = svg.getBoundingClientRect();
      if (!r.width || !r.height || !before) return;
      var cx = view.x + view.w / 2,
        cy = view.y + view.h / 2;
      aspect = full ? r.width / r.height : homeAspect;
      px = full ? r.width / pageW : 1;
      view.w = lim((view.w * r.width) / before);
      view.h = view.w / aspect;
      view.x = cx - view.w / 2;
      view.y = cy - view.h / 2;
      boxW = r.width;
      schedule();
    }
    function openView(push) {
      if (full) return;
      if (opened && opened !== api) opened.close(false);
      stop();
      var before = svg.getBoundingClientRect().width;
      pageW = before;
      full = true;
      opened = api;
      host.classList.add('lmap-full');
      document.documentElement.classList.add('lmap-full-open');
      label(true);
      resize(before);
      draw();
      if (push && location.hash !== HASH) {
        try {
          history.pushState({ lmap: 1 }, '', location.pathname + location.search + HASH);
          pushed = true;
        } catch {
          /* no history entry: Back leaves the page */
        }
      }
      try {
        svg.focus({ preventScroll: true });
      } catch {
        svg.focus();
      }
      window.addEventListener('resize', onResize);
    }
    function close(fromHistory) {
      if (!full) return;
      stop();
      hidePop();
      var before = svg.getBoundingClientRect().width;
      full = false;
      if (opened === api) opened = null;
      host.classList.remove('lmap-full');
      document.documentElement.classList.remove('lmap-full-open');
      label(false);
      window.removeEventListener('resize', onResize);
      resize(before);
      draw();
      if (!fromHistory && location.hash === HASH) {
        // Leave the entry the map view added, or drop the mark from an address that came with it.
        if (pushed) history.back();
        else
          try {
            history.replaceState(history.state, '', location.pathname + location.search);
          } catch {
            /* keep the address as it is */
          }
      }
      pushed = false;
      fullBtn.focus();
    }
    function closeView() {
      close(false);
    }
    function onResize() {
      resize(boxW);
    }
    fullBtn.addEventListener('click', function () {
      if (full) closeView();
      else openView(true);
    });

    // Points with records: a box with their names, each linked to the record's page.
    var root = base.replace(/map\/$/, '');
    var pop = null,
      downAt = null;
    function hidePop() {
      if (pop) pop.hidden = true;
    }
    function nearest(clientX, clientY) {
      var p = toSvg(clientX, clientY),
        best = null,
        bd = Infinity;
      var cs = svg.querySelectorAll('circle[data-g]');
      for (var i = 0; i < cs.length; i++) {
        var c = cs[i],
          dx = parseFloat(c.getAttribute('cx')) - p[0],
          dy = parseFloat(c.getAttribute('cy')) - p[1];
        var d = Math.sqrt(dx * dx + dy * dy) / p[2];
        var reach = Math.max(TAP_PX, parseFloat(c.getAttribute('r')) / p[2] + 4);
        if (d <= reach && d < bd) {
          bd = d;
          best = c;
        }
      }
      return best;
    }
    function showPop(c, clientX, clientY) {
      var ids = c.getAttribute('data-g').split(' ').filter(Boolean);
      if (!pop) {
        pop = document.createElement('div');
        pop.className = 'lmap-pop';
        pop.setAttribute('role', 'dialog');
        pop.setAttribute('aria-label', 'Records at this point');
        host.appendChild(pop);
      }
      pop.textContent = '';
      var list = document.createElement('ul');
      list.className = 'notranslate';
      ids.forEach(function (id) {
        var li = document.createElement('li');
        li.textContent = id;
        list.appendChild(li);
      });
      pop.appendChild(list);
      var x = document.createElement('button');
      x.type = 'button';
      x.className = 'lmap-pop-close';
      x.setAttribute('aria-label', 'Close');
      x.appendChild(icon(ICON_CLOSE));
      x.addEventListener('click', function () {
        hidePop();
        svg.focus();
      });
      pop.appendChild(x);
      pop.hidden = false;
      place(clientX, clientY);
      records(ids, root).then(
        function (rs) {
          if (pop.hidden || pop.firstChild !== list) return;
          rs.forEach(function (r, i) {
            var li = list.childNodes[i];
            li.textContent = '';
            var a = document.createElement(r.url ? 'a' : 'span');
            a.textContent = r.name;
            if (r.url) a.href = r.url;
            li.appendChild(a);
          });
          place(clientX, clientY);
        },
        function () {},
      );
    }
    function place(clientX, clientY) {
      var b = host.getBoundingClientRect();
      var x = Math.min(clientX - b.left + 10, b.width - pop.offsetWidth - 8);
      var y = Math.min(clientY - b.top + 10, b.height - pop.offsetHeight - 8);
      pop.style.left = Math.max(8, x) + 'px';
      pop.style.top = Math.max(8, y) + 'px';
    }
    svg.addEventListener('pointerdown', function (e) {
      downAt = [e.clientX, e.clientY];
    });
    svg.addEventListener('click', function (e) {
      // Ignore clicks that ended a drag.
      if (downAt && Math.abs(e.clientX - downAt[0]) + Math.abs(e.clientY - downAt[1]) > 4) return;
      var c = nearest(e.clientX, e.clientY);
      if (c) showPop(c, e.clientX, e.clientY);
      else hidePop();
    });
    svg.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !full) hidePop();
    });

    var api = {
      svg: svg,
      zoom: zoom,
      reset: reset,
      open: function () {
        openView(true);
      },
      close: close,
      isOpen: function () {
        return full;
      },
      refresh: function () {
        points = null;
        schedule();
      },
      view: function () {
        return { x: view.x, y: view.y, w: view.w, h: view.h };
      },
    };
    svg.__lmap = api;
    schedule();
    // An address with #map-view opens the first map in the map view.
    if (location.hash === HASH && !opened) openView(false);
    return api;
  }

  // Back and Forward move between the page and its map view.
  window.addEventListener('popstate', function () {
    if (location.hash === HASH) {
      if (!opened) {
        var s = document.querySelector('svg.lmap');
        if (s && s.__lmap) s.__lmap.open();
      }
    } else if (opened) opened.close(true);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && opened && !e.defaultPrevented) opened.close(false);
  });

  window.LangLogMap = { mount: mount, records: records };
  function all() {
    Array.prototype.forEach.call(document.querySelectorAll('svg.lmap[data-map]'), mount);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', all);
  else all();
})();
