'use strict';
// Loads the split atlas data written by split_data.py (dist/data/) and
// rebuilds the objects the pages used to read from data.json and
// integrated.json, so the rest of the code is unchanged:
//   load()     -> {d: {nodes, roots, stats, ...}, u: integrated data}
//   names(id)  -> recorded names of a Glottolog record (one small file)
//   search()   -> {id: lower-case text of all its names}, for search
// Glottolog records have no "names" until names(id) has loaded them.
window.AtlasData = (() => {
  // Number of name files; tools/split_data.py reads it from here.
  const SHARDS = 64,
    shardFiles = new Map();
  let nodes = null,
    searchFile = null;
  // Path of dist/data/ from the page; a page below the site root sets AtlasData.base first.
  const api = { base: 'data/' };
  const get = (file) =>
    fetch(api.base + file).then((r) => {
      if (!r.ok) throw Error('Could not load ' + file);
      return r.json();
    });
  // Same hash as shard() in split_data.py.
  const shard = (id) => {
    let h = 0;
    for (const ch of id) h = (h * 31 + ch.codePointAt(0)) % SHARDS;
    return h;
  };
  function rebuild(a) {
    const ids = a.ids,
      c = a.columns,
      codes = a.codes,
      list = new Array(ids.length),
      out = {};
    for (let i = 0; i < ids.length; i++) {
      const p = c.parent[i];
      list[i] = {
        id: ids[i],
        name: c.name[i],
        level: codes.level[c.level[i]],
        area: codes.area[c.area[i]],
        iso: c.iso[i],
        countries: c.countries[i],
        isolate: !!c.isolate[i],
        parent: p < 0 ? null : ids[p],
        children: [],
        root: null,
        category: codes.category[c.category[i]],
        size: 1,
        nativeNames: [],
      };
    }
    const kids = new Map();
    for (let i = 0; i < ids.length; i++) {
      const p = c.parent[i];
      if (p < 0) continue;
      if (!kids.has(p)) kids.set(p, []);
      kids.get(p).push(i);
    }
    for (const [p, ks] of kids) {
      ks.sort((x, y) => c.rank[x] - c.rank[y]);
      list[p].children = ks.map((i) => ids[i]);
    }
    // Root and size (the record plus all records below it), without recursion.
    const order = [];
    for (let i = 0; i < ids.length; i++) if (c.parent[i] < 0) order.push(i);
    for (let j = 0; j < order.length; j++) {
      const i = order[j],
        p = c.parent[i];
      list[i].root = p < 0 ? ids[i] : list[p].root;
      for (const k of kids.get(i) || []) order.push(k);
    }
    for (let j = order.length - 1; j >= 0; j--) {
      const i = order[j],
        p = c.parent[i];
      if (p >= 0) list[p].size += list[i].size;
    }
    for (const [i, v] of Object.entries(a.nativeNames)) list[i].nativeNames = v;
    for (const n of list) out[n.id] = n;
    const u = { ...a.unified },
      assertions = list
        .map((n) => ({ parent: n.parent, child: n.id, source: 'glottolog' }))
        .concat(u.otherAssertions),
      placements = {};
    delete u.otherAssertions;
    for (const e of assertions) {
      if (e.parent === null) continue;
      (placements[e.child] ??= []).push(e);
    }
    u.assertions = assertions;
    u.placements = placements;
    return {
      d: {
        nodes: out,
        roots: a.roots,
        stats: a.stats,
        retrieved: a.retrieved,
        glottologVersion: a.glottologVersion,
      },
      u,
    };
  }
  return Object.assign(api, {
    async load() {
      const r = rebuild(await get('atlas.json'));
      nodes = r.d.nodes;
      for (const f of shardFiles.values())
        f.then(
          (f) => {
            for (const [k, v] of Object.entries(f)) if (nodes[k]) nodes[k].names = v;
          },
          () => {},
        );
      return r;
    },
    names(id) {
      const s = shard(id);
      if (!shardFiles.has(s))
        shardFiles.set(
          s,
          get('names/' + s + '.json').then(
            (f) => {
              if (nodes) for (const [k, v] of Object.entries(f)) if (nodes[k]) nodes[k].names = v;
              return f;
            },
            (e) => {
              shardFiles.delete(s);
              throw e;
            },
          ),
        );
      return shardFiles.get(s).then((f) => {
        const v = f[id] || [];
        if (nodes?.[id]) nodes[id].names = v;
        return v;
      });
    },
    search() {
      return (searchFile ??= get('search.json').catch((e) => {
        searchFile = null;
        throw e;
      }));
    },
  });
})();
