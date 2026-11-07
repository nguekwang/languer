'use strict';
(async () => {
  const $ = (id) => document.getElementById(id),
    esc = (v) =>
      String(v ?? '').replace(
        /[&<>"']/g,
        (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
      );
  const params = new URLSearchParams(location.search),
    domain = ['sign', 'scripts'].includes(params.get('domain')) ? params.get('domain') : 'language',
    id = params.get('id');
  // Language records: the list is the top page, and every record has its own page there.
  const listURL = domain === 'language' ? './' : 'signs-and-scripts.html?domain=' + domain;
  $('back').href = listURL;
  async function get(file) {
    const r = await fetch(file);
    if (!r.ok) throw Error('Could not load the record data.');
    return r.json();
  }
  try {
    let N,
      S,
      E,
      notes = [],
      usage = [],
      conflicts = [],
      debates = [],
      base,
      sourcePaths = {};
    if (domain === 'language') {
      const [{ d, u }, names, sp] = await Promise.all([
        window.AtlasData.load(),
        window.AtlasData.names(id || ''),
        fetch('source-paths.json')
          .then((r) => (r.ok ? r.json() : {}))
          .catch(() => ({})),
      ]);
      sourcePaths = sp;
      base = d.nodes;
      if (base[id]) base[id].names = names;
      N = { ...base, ...u.extraNodes };
      await window.LineagePaths.init(base, d.roots);
      S = u.sources;
      E = u.assertions;
      const path = new Set();
      let p = id;
      while (base[p] && !path.has(p)) {
        path.add(p);
        p = base[p].parent;
      }
      debates = (u.debates || []).filter((d) => d.appliesTo.some((i) => path.has(i)));
      conflicts = (u.conflictIndex[id] || []).map((i) => u.conflicts[i]);
    } else {
      const d = await get('signs-and-scripts.json');
      N = d.nodes;
      S = d.sources;
      E = d.assertions;
      notes = d.notes.filter((x) => x.nodes.includes(id));
      usage = d.usage.filter((x) => x.script === id);
    }
    const n = N[id];
    if (!n || (domain !== 'language' && n.domain !== domain)) {
      $('variant-content').innerHTML =
        '<h1>Record not found</h1><p>This URL does not identify a record in this section.</p><a href="' +
        listURL +
        '">Return to the variant list</a>';
      return;
    }
    // Keep the title suffix record.html was written with (tools/site_brand.py).
    document.title = n.name + document.title.slice(document.title.lastIndexOf(' · '));
    const url = (i) => 'record.html?domain=' + domain + '&id=' + encodeURIComponent(i),
      nl = (i) => (N[i] ? `<a href="${esc(url(i))}">${esc(N[i].name)}</a>` : esc(i)),
      sl = (s) =>
        S[s]
          ? `<a href="${esc(S[s].url)}" target="_blank" rel="noopener noreferrer">${esc(S[s].title)}</a>`
          : esc(s);
    const incoming = E.filter((e) => e.child === id && e.parent),
      outgoing = E.filter((e) => e.parent === id),
      aliases = n.names || n.aliases || [],
      native = n.nativeNames || [];
    const evidence = (e) =>
      `<div class="evidence-card"><strong>${nl(e.parent)}</strong><p>According to ${sl(e.source)}</p>${e.kind ? '<p>' + esc(e.kind) + '</p>' : ''}${e.status && e.status !== 'reported' ? '<p>Status: ' + esc(e.status) + '</p>' : ''}${e.hypothesis ? '<p>' + esc(e.hypothesis) + '</p>' : ''}${e.sample ? '<p>Source sample: ' + esc(e.sample) + '</p>' : ''}${e.run ? '<p>Run: ' + esc(e.run) + '</p>' : ''}${e.posterior != null ? '<p>Posterior: ' + esc(e.posterior) + '</p>' : ''}${e.reportedVia ? '<p>Reported and discussed in ' + sl(e.reportedVia) + '</p>' : ''}</div>`;
    const sourceIds = new Set([
      ...(n.sources || []),
      ...incoming.map((e) => e.source),
      ...outgoing.map((e) => e.source),
      ...notes.flatMap((t) => t.sources),
    ]);
    if (base?.[id]) sourceIds.add('glottolog');
    const comparisons = new Map();
    for (const c of conflicts) {
      const key = c.a + '|' + c.b;
      if (!comparisons.has(key)) comparisons.set(key, c);
    }
    let html = `<h1>${esc(n.name)}</h1><div class="meta"><span>${esc(id)}</span>${n.iso ? '<span>ISO 639-3: ' + esc(n.iso) + '</span>' : ''}${n.code ? '<span>Script code: ' + esc(n.code) + '</span>' : ''}${n.category ? '<span>' + esc(n.category) + '</span>' : ''}</div><div class="variant-actions">${domain === 'language' ? (base?.[id] || sourcePaths[id] ? `<a href="${esc(base?.[id] ? window.LineagePaths.url(id) : sourcePaths[id])}">Record page</a>` : '') : `<a href="${esc(listURL + '&id=' + encodeURIComponent(id))}">Show in tree</a>`}<button id="copy-link" type="button">Copy link</button><span id="copy-status" role="status"></span></div>`;
    // Classification path from the top of the family down to this record.
    const up = {};
    for (const e of incoming) up[e.source] ??= e.parent;
    let lineSource = base?.[id]
      ? 'glottolog'
      : domain === 'language'
        ? n.source || 'glottolog'
        : up.glottolog
          ? 'glottolog'
          : Object.keys(up)[0];
    const parentOf = (i) =>
      domain === 'language'
        ? base?.[i] && lineSource === 'glottolog'
          ? base[i].parent
          : N[i]?.parent
        : E.find((e) => e.child === i && e.parent && e.source === lineSource)?.parent;
    const lineIds = [];
    {
      const seen = new Set();
      let p = id;
      while (p && N[p] && !seen.has(p)) {
        seen.add(p);
        lineIds.unshift(p);
        p = parentOf(p);
      }
    }
    const lineHTML = !lineSource
      ? ''
      : `<nav class="lineage" aria-label="Classification according to ${esc(S[lineSource]?.title || lineSource)}"><span class="lineage-source">${sl(lineSource)}</span>${
          lineIds.length > 1
            ? `<ol class="lineage-path">${lineIds
                .slice(0, -1)
                .map(
                  (i) =>
                    `<li>${base?.[i] && lineSource === 'glottolog' ? `<a href="${esc(window.LineagePaths.url(i))}">${esc(N[i].name)}</a>` : nl(i)}</li>`,
                )
                .join('')}</ol>`
            : `<span class="lineage-top">${n.isolate ? 'Isolate' : 'Top-level'}: no higher family</span>`
        }</nav>`;
    html = lineHTML + html;
    html +=
      '<section><h2>Names</h2>' +
      (native.length
        ? native
            .map(
              (a) =>
                `<p dir="auto">${esc(a.text || a.name || a)}${a.source && S[a.source] ? ' · ' + sl(a.source) : ''}</p>`,
            )
            .join('')
        : '<p class="muted">No verified same-language name recorded.</p>');
    if (n.glyphSample)
      html += `<p class="v-glyphs" dir="auto">${esc(n.glyphSample)}</p><p class="muted">Unicode letter sample, not a native name. ${sl('ucd')}</p>`;
    html += `<details><summary>Aliases and spellings · ${aliases.length}</summary><ul class="name-list">${aliases.map((a) => `<li dir="auto">${esc(a.text || a.name || a)} <span class="muted">${esc(a.lang || '')} · ${esc(a.provider || a.source || '')}</span></li>`).join('')}</ul></details></section>`;
    if (n.area || n.region || n.silType)
      html += `<section><h2>Record information</h2>${n.area ? '<p>Macroarea: ' + esc(n.area) + '</p>' : ''}${n.region ? '<p>Region: ' + esc(n.region) + '</p>' : ''}${n.silType ? '<p>SIL-reported type: ' + esc(n.silType) + '<br>Direction: ' + esc(n.direction) + '<br>Status: ' + esc(n.silStatus) + '</p>' : ''}</section>`;
    html += `<section><h2>Classification and placements</h2>${incoming.length ? incoming.map(evidence).join('') : '<p>No incoming placement is recorded in the imported sources. This alone does not establish an independent origin.</p>'}</section>`;
    if (notes.length || debates.length || comparisons.size) {
      html += '<section><h2>Alternative accounts and research notes</h2>';
      for (const note of notes)
        html += `<article class="evidence-card"><h3>${esc(note.title)}</h3><p>${esc(note.text)}</p>${note.sources.map(sl).join('<br>')}</article>`;
      for (const d of debates)
        html += `<article><h3>${esc(d.title)}</h3><p>${esc(d.status)}</p>${d.positions.map((p) => `<div class="evidence-card"><strong>According to ${esc(p.author)}</strong><p>${esc(p.claim)}</p><a href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">${esc(p.publication)} ↗</a></div>`).join('')}<p>${esc(d.note)}</p></article>`;
      for (const c of comparisons.values()) {
        const [a, b, d] = c.witness;
        html += `<div class="evidence-card"><h3>${esc(S[c.a].title)} / ${esc(S[c.b].title)}</h3><p>According to ${sl(c.a)}: ${nl(a)} + ${nl(b)} group before ${nl(d)}.</p><p>According to ${sl(c.b)}: ${nl(b)} + ${nl(d)} group before ${nl(a)}.</p><p>${c.sharedTips} shared samples compared. This incompatibility does not determine which study is correct.</p><p>${nl(c.cladeA)} · ${nl(c.cladeB)}</p></div>`;
      }
      html += '</section>';
    }
    html += `<section><h2>Related child records · ${outgoing.length}</h2><div class="record-links">${outgoing.map((e) => `<div>${nl(e.child)}<small>${esc(e.kind || 'Classification')} · ${sl(e.source)}</small></div>`).join('') || '<p>No child records imported.</p>'}</div></section>`;
    if (usage.length)
      html += `<section><h2>Language usage · ${usage.length}</h2><p>CLDR language codes and primary/secondary designations; usage is not ancestry. ${sl('cldr')}</p><ul class="v-usage">${usage.map((u) => '<li>' + esc(u.language) + ' · ' + esc(u.status) + (u.territories.length ? ' · ' + esc(u.territories.join(', ')) : '') + '</li>').join('')}</ul></section>`;
    if (n.iso && ['language', 'dialect'].includes(n.level || n.kind))
      html += '<section id="variant-models"></section>';
    html += `<section><h2>Sources</h2>${[...sourceIds].map((s) => '<p>' + sl(s) + '</p>').join('')}${base?.[id] ? `<p><a href="https://glottolog.org/resource/languoid/id/${encodeURIComponent(id)}" target="_blank" rel="noopener noreferrer">Glottolog record & bibliography ↗</a></p>` : ''}<p class="muted">Coverage is limited to the imported sources. No displayed alternative does not imply consensus.</p></section>`;
    $('variant-content').innerHTML = html;
    if ($('variant-models') && window.LanguageModels)
      window.LanguageModels.mount(
        $('variant-models'),
        { ...n, level: n.level || n.kind },
        {
          task: params.get('task') || '',
          onTask: (t) => {
            const u = new URL(location.href);
            if (t) u.searchParams.set('task', t);
            else u.searchParams.delete('task');
            history.replaceState(null, '', u);
          },
        },
      );
    $('copy-link').onclick = async () => {
      try {
        await navigator.clipboard.writeText(location.href);
        $('copy-status').textContent = 'Link copied';
      } catch {
        $('copy-status').textContent = 'Copy this page’s URL from your address bar.';
      }
    };
  } catch (e) {
    $('variant-content').innerHTML =
      '<h1>Unable to load this record</h1><p>' +
      esc(e.message) +
      '</p><a href="' +
      listURL +
      '">Return to the variant list</a>';
  }
})();
