// Language menu at the right end of the header, after the theme toggle, as on the owner's
// profile site (nguekwang.github.io). It switches the interface text (buttons, headings,
// help) between the same languages as the profile site, in the same order. Record names,
// source titles and other data stay as the sources give them.
// - The pages are written in English. This script translates the text on the page with
//   the dictionary of the chosen language (exact strings, then patterns), and keeps
//   translating what the atlas scripts add later (a MutationObserver), so the atlas code
//   needs no changes.
// - Dictionaries: Japanese is in i18n.js, loaded by every page; every other language is in
//   i18n/<code>.js, loaded only when that language is chosen. While it loads, the page is
//   hidden (at most LOAD_WAIT ms), so English does not flash before the translation.
// - Numbers and dates captured by a pattern are written in the language's own format
//   (Intl, Gregorian calendar, digits 0-9 except Persian ۰-۹), as on the profile site.
// - Arabic and Persian pages are right to left (dir="rtl" on <html>).
// - Without a saved choice the language follows the browser, otherwise English. A pick is
//   saved in localStorage ("lang") and applies to every page. Switching adds no history
//   entry and keeps the URL.
// - Without JavaScript the pages are in English and the menu is not shown.
// - Elements with class "notranslate" (and their children) are never translated.
(function () {
  var root = document.documentElement;
  var KEY = 'lang';
  // [code, name in the language itself, short label for narrow screens, direction]
  var LANGS = [
    ['en', 'English', 'EN'],
    ['ja', '日本語', 'JA'],
    ['es', 'Español', 'ES'],
    ['fr', 'Français', 'FR'],
    ['ru', 'Русский', 'RU'],
    ['zh-Hans', '简体中文', '简体'],
    ['zh-Hant', '繁體中文', '繁體'],
    ['ar', 'العربية', 'AR', 'rtl'],
    ['ko', '한국어', 'KO'],
    ['vi', 'Tiếng Việt', 'VI'],
    ['de', 'Deutsch', 'DE'],
    ['pt', 'Português', 'PT'],
    ['it', 'Italiano', 'IT'],
    ['nl', 'Nederlands', 'NL'],
    ['tr', 'Türkçe', 'TR'],
    ['id', 'Bahasa Indonesia', 'ID'],
    ['th', 'ไทย', 'TH'],
    ['hi', 'हिन्दी', 'HI'],
    ['fa', 'فارسی', 'FA', 'rtl'],
    ['pl', 'Polski', 'PL'],
    ['uk', 'Українська', 'UK'],
  ];
  // Digits other than 0-9 (Intl numbering system), as in the profile site's data/site.yaml.
  var DIGITS = { fa: 'arabext' };
  var ATTRS = ['placeholder', 'aria-label', 'title', 'alt'];
  var SKIP = 'script,style,code,.notranslate';
  var LOAD_WAIT = 3000;
  // Content hashes of i18n/<code>.js, filled in by tools/version_assets.py in CI so a
  // browser never uses an old cached dictionary.
  var VERSIONS = {};
  var script = document.currentScript;
  var BASE = script && script.src ? script.src.replace(/[^/]*$/, '') : '';

  function info(code) {
    for (var i = 0; i < LANGS.length; i++) if (LANGS[i][0] === code) return LANGS[i];
    return null;
  }
  function saved() {
    try {
      var v = localStorage.getItem(KEY);
      return info(v) ? v : null;
    } catch {
      return null;
    }
  }
  function browser() {
    var list = navigator.languages || [navigator.language || 'en'];
    for (var i = 0; i < list.length; i++) {
      var l = String(list[i]).toLowerCase();
      if (/^zh\b/.test(l)) return /hant|-tw|-hk|-mo/.test(l) ? 'zh-Hant' : 'zh-Hans';
      for (var j = 0; j < LANGS.length; j++) {
        var c = LANGS[j][0];
        if (c.indexOf('-') < 0 && (l === c || l.indexOf(c + '-') === 0)) return c;
      }
    }
    return 'en';
  }
  var lang = saved() || browser();

  // Originals of what was translated, so English can be put back without a reload.
  var textOrig = new WeakMap();
  var attrOrig = new WeakMap();
  var touched = [];

  var MONTHS = {
    Jan: 0,
    Feb: 1,
    Mar: 2,
    Apr: 3,
    May: 4,
    Jun: 5,
    Jul: 6,
    Aug: 7,
    Sep: 8,
    Oct: 9,
    Nov: 10,
    Dec: 11,
  };
  function intlLocale() {
    return lang + '-u-nu-' + (DIGITS[lang] || 'latn') + '-ca-gregory';
  }
  // A number ("27,123") or a date ("12 Oct 2026") captured by a pattern, in the
  // language's own format. Anything else is returned unchanged.
  function local(v) {
    if (v == null || lang === 'en' || !window.Intl) return v;
    try {
      if (/^\d{1,3}(,\d{3})*$|^\d+$/.test(v))
        return new Intl.NumberFormat(intlLocale()).format(Number(v.replace(/,/g, '')));
      var m = v.match(/^(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{4})$/);
      if (m)
        return new Intl.DateTimeFormat(intlLocale(), {
          year: 'numeric',
          month: 'long',
          day: 'numeric',
          timeZone: 'UTC',
        }).format(new Date(Date.UTC(+m[3], MONTHS[m[2]], +m[1])));
    } catch {
      /* old browser: keep the English form */
    }
    return v;
  }

  function dict() {
    return (window.LANGLOG_I18N || {})[lang] || null;
  }
  function tr(s) {
    var d = dict();
    if (!d) return null;
    var key = s.replace(/\s+/g, ' ').trim();
    // A bare number (a count the scripts write) only changes its digits, in Persian.
    if (/^\d[\d,]*$/.test(key) && DIGITS[lang] === 'arabext')
      return key
        .replace(/\d/g, function (c) {
          return '۰۱۲۳۴۵۶۷۸۹'[c];
        })
        .replace(/,/g, '٬');
    if (!key || !/[A-Za-z]/.test(key)) return null;
    var out = Object.prototype.hasOwnProperty.call(d.exact, key) ? d.exact[key] : null;
    if (out === null) {
      for (var i = 0; i < d.patterns.length; i++) {
        var m = key.match(d.patterns[i][0]);
        if (m) {
          var g = m.map(local);
          var rep = d.patterns[i][1];
          out =
            typeof rep === 'function'
              ? rep(g, tr)
              : rep.replace(/\$(\d)/g, function (_, n) {
                  return g[+n] != null ? g[+n] : '';
                });
          break;
        }
      }
    }
    if (out === null) {
      // Long text: translate sentence by sentence, but only when every sentence is known.
      var parts = key.split(/(?<=\.)\s+/);
      if (parts.length > 1) {
        var done = [];
        for (var k = 0; k < parts.length; k++) {
          var p = tr(parts[k]);
          if (p === null) {
            done = null;
            break;
          }
          done.push(p);
        }
        if (done) out = done.join(d.join != null ? d.join : ' ');
      }
    }
    if (out === null || out === key) return null;
    var lead = s.match(/^\s*/)[0],
      tail = s.match(/\s*$/)[0];
    return lead + out + tail;
  }
  function skip(el) {
    return !el || (el.closest && el.closest(SKIP));
  }
  function doText(n) {
    if (skip(n.parentElement)) return;
    var t = tr(n.nodeValue);
    if (t === null) return;
    if (!textOrig.has(n)) touched.push(n);
    textOrig.set(n, n.nodeValue);
    n.nodeValue = t;
  }
  function doAttrs(el) {
    if (skip(el)) return;
    for (var i = 0; i < ATTRS.length; i++) {
      var a = ATTRS[i];
      if (!el.hasAttribute(a)) continue;
      var t = tr(el.getAttribute(a));
      if (t === null) continue;
      var o = attrOrig.get(el);
      if (!o) {
        o = {};
        attrOrig.set(el, o);
        touched.push(el);
      }
      o[a] = el.getAttribute(a);
      el.setAttribute(a, t);
    }
  }
  function walk(node) {
    if (node.nodeType === 3) {
      doText(node);
      return;
    }
    if (node.nodeType !== 1 || skip(node)) return;
    doAttrs(node);
    var w = document.createTreeWalker(node, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    var n;
    while ((n = w.nextNode())) {
      if (n.nodeType === 3) doText(n);
      else doAttrs(n);
    }
  }

  var observer = null;
  function observe() {
    if (observer || !window.MutationObserver) return;
    observer = new MutationObserver(function (records) {
      observer.disconnect();
      for (var i = 0; i < records.length; i++) {
        var r = records[i];
        if (r.type === 'characterData') doText(r.target);
        else if (r.type === 'attributes') doAttrs(r.target);
        else for (var j = 0; j < r.addedNodes.length; j++) walk(r.addedNodes[j]);
      }
      observer.observe(document.documentElement, OPTS);
    });
    observer.observe(document.documentElement, OPTS);
  }
  var OPTS = {
    subtree: true,
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: ATTRS,
  };

  function restore() {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
    for (var i = 0; i < touched.length; i++) {
      var n = touched[i];
      if (n.nodeType === 3) {
        if (textOrig.has(n)) n.nodeValue = textOrig.get(n);
        textOrig.delete(n);
      } else {
        var o = attrOrig.get(n);
        if (o) for (var a in o) n.setAttribute(a, o[a]);
        attrOrig.delete(n);
      }
    }
    touched = [];
  }

  // "yoshi" in the header (a.profile, written from tools/site_brand.py) links to the profile
  // site's page in the interface language: only the language part of its address changes.
  function profileLinks() {
    Array.prototype.forEach.call(document.querySelectorAll('a.profile'), function (a) {
      a.href = a.href.replace(/^(https:\/\/[^/]+\/)[^/?#]+\//, '$1' + lang + '/');
    });
  }

  function menu() {
    var box = document.querySelector('body > header .tools');
    if (!box) return;
    var d = box.querySelector('.langmenu');
    if (!d) {
      d = document.createElement('details');
      d.className = 'langmenu notranslate';
      box.appendChild(d);
      d.addEventListener('click', function (e) {
        var b = e.target.closest('button[data-lang]');
        if (!b) return;
        d.open = false;
        set(b.getAttribute('data-lang'), true);
      });
      document.addEventListener('click', function (e) {
        if (d.open && !d.contains(e.target)) d.open = false;
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && d.open) {
          d.open = false;
          d.querySelector('summary').focus();
        }
      });
    }
    var cur = info(lang);
    var items = LANGS.map(function (l) {
      return l[0] === lang
        ? '<li><span lang="' + l[0] + '" aria-current="true">' + l[1] + '</span></li>'
        : '<li><button type="button" lang="' +
            l[0] +
            '" data-lang="' +
            l[0] +
            '">' +
            l[1] +
            '</button></li>';
    }).join('');
    d.innerHTML =
      '<summary aria-label="Language: ' +
      cur[1] +
      '" lang="' +
      lang +
      '"><span class="full">' +
      cur[1] +
      '</span><span class="short" aria-hidden="true">' +
      cur[2] +
      '</span></summary><div class="panel"><ul>' +
      items +
      '</ul></div>';
  }

  function setDir() {
    root.setAttribute('lang', lang);
    root.setAttribute('dir', info(lang)[3] || 'ltr');
  }

  // Run done() once the dictionary of code is there (English needs none). Japanese comes
  // with i18n.js; other languages load i18n/<code>.js. A failed load leaves English.
  function load(code, done) {
    if (code === 'en' || (window.LANGLOG_I18N || {})[code]) {
      done();
      return;
    }
    var finished = false;
    function finish() {
      if (!finished) {
        finished = true;
        root.classList.remove('i18n-wait');
        done();
      }
    }
    root.classList.add('i18n-wait');
    setTimeout(finish, LOAD_WAIT);
    var el = document.createElement('script');
    el.src = BASE + 'i18n/' + code + '.js' + (VERSIONS[code] ? '?v=' + VERSIONS[code] : '');
    el.onload = el.onerror = finish;
    (document.head || root).appendChild(el);
  }

  // The list count's label comes from CSS (#searchcount::before/::after in style.css):
  // split the translated "<n> roots in the list" around the number into two variables.
  function countLabel() {
    var out = lang === 'en' ? null : tr('7 roots in the list'),
      n = local('7'),
      i = out ? out.indexOf(n) : -1;
    if (i < 0) {
      root.style.removeProperty('--count-before');
      root.style.removeProperty('--count-after');
      return;
    }
    root.style.setProperty('--count-before', JSON.stringify(out.slice(0, i)));
    root.style.setProperty('--count-after', JSON.stringify(out.slice(i + n.length)));
  }
  function apply() {
    setDir();
    restore();
    countLabel();
    if (lang !== 'en') {
      walk(document.documentElement);
      observe();
    }
    profileLinks();
    menu();
  }

  function set(l, save) {
    if (l === lang || !info(l)) return;
    lang = l;
    if (save) {
      try {
        localStorage.setItem(KEY, l);
      } catch {
        /* private mode: this page only */
      }
    }
    load(l, function () {
      if (lang !== l) return;
      apply();
      document.dispatchEvent(new Event('langchange'));
    });
  }

  setDir();
  var first = lang;
  // Translate the head now (title) and the body as the parser builds it, so English
  // does not flash before the translation.
  load(first, function () {
    if (lang !== first || lang === 'en') return;
    countLabel();
    walk(document.documentElement);
    observe();
  });
  document.addEventListener('DOMContentLoaded', function () {
    if (lang !== 'en' && dict()) walk(document.body);
    profileLinks();
    menu();
    document.dispatchEvent(new Event('langchange'));
  });
  window.LANGLOG_LANG = function () {
    return lang;
  };
})();
