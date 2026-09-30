// Signature intelligence: Supply Weather Map, Cascade Simulator, Impact Ledger
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const fmt = (n) => Math.round(n).toLocaleString('en-IN');
  const TIER = { 'Warehouse': 0, 'Medical College': 1, 'District Hospital': 1, 'CHC': 2, 'PHC': 3 };
  const hav = (a, b) => { const r = Math.PI / 180, dl = (b.latitude - a.latitude) * r, dn = (b.longitude - a.longitude) * r; const x = Math.sin(dl / 2) ** 2 + Math.cos(a.latitude * r) * Math.cos(b.latitude * r) * Math.sin(dn / 2) ** 2; return 12742 * Math.asin(Math.sqrt(x)); };
  let D = null;

  async function getData() {
    const A = window.Api;
    const [fs, preds, recs] = await Promise.all([A.getFacilities(), A.getStockoutPredictions(), A.getRecommendations()]);
    const minDays = {}, items = {};
    preds.forEach((p) => { (items[p.facility_id] = items[p.facility_id] || []).push(p); if (minDays[p.facility_id] == null || p.days_of_stock < minDays[p.facility_id]) minDays[p.facility_id] = p.days_of_stock; });
    D = { fs, preds, recs, minDays, items, byId: Object.fromEntries(fs.map((f) => [f.facility_id, f])) };
    return D;
  }
  const fail = (id, e) => { const el = $(id); if (el) el.innerHTML = '<div class="ins-empty">Could not load live data. Check that the server is running and you are signed in.</div>'; console.error(e); };

  /* ---------- 1. SUPPLY WEATHER ---------- */
  const WX = [[.2, '#2f8f83', 'Clear'], [.45, '#e8a317', 'Watch'], [.7, '#e4572e', 'Warning'], [2, '#b3261e', 'Storm']];
  const wxCol = (i) => WX.find((w) => i < w[0]);
  const dayLbl = (t) => (t === 0 ? 'Today' : 'Day ' + t);
  function pAt(p, t) {
    if (p.days_of_stock <= t) return 1;
    const q = [[0, 0], [7, p.p_stockout_7d || 0], [14, p.p_stockout_14d || 0], [30, p.p_stockout_30d || 0]];
    for (let i = 1; i < q.length; i++) if (t <= q[i][0]) return q[i - 1][1] + (q[i][1] - q[i - 1][1]) * (t - q[i - 1][0]) / (q[i][0] - q[i - 1][0]);
    return q[3][1];
  }
  function intensity(fid, t) {
    const it = D.items[fid]; if (!it || !it.length) return 0;
    const ps = it.map((p) => pAt(p, t));
    return Math.min(1, 0.6 * Math.max(...ps) + 0.4 * ps.reduce((a, b) => a + b, 0) / ps.length);
  }
  function drawWx() {
    const t = +$('wxDay').value;
    $('wxDayLbl').textContent = dayLbl(t);
    const P = (f) => [20 + (f.longitude - 72.3) / 6.6 * 600, 15 + (30.9 - f.latitude) / 12.3 * 470];
    let blobs = '', dots = '', grid = '';
    for (let i = 1; i < 6; i++) grid += '<line x1="' + (i * 106) + '" y1="0" x2="' + (i * 106) + '" y2="500"/><line x1="0" y1="' + (i * 83) + '" x2="640" y2="' + (i * 83) + '"/>';
    const ranked = D.fs.map((f) => ({ f, i: intensity(f.facility_id, t) }));
    ranked.forEach(({ f, i }) => {
      const [x, y] = P(f), c = wxCol(i);
      if (i > 0.05) blobs += '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="' + (24 + i * 44).toFixed(0) + '" fill="' + c[1] + '" opacity="' + (0.3 + 0.55 * i).toFixed(2) + '"/>';
      dots += '<circle cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="3.2" fill="#fff"><title>' + esc(f.name) + ': ' + c[2] + ' (' + Math.round(i * 100) + '%)</title></circle>';
    });
    $('wxMap').innerHTML = '<defs><filter id="wxBlur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="13"/></filter></defs><g stroke="#ffffff14" stroke-width="1">' + grid + '</g><g filter="url(#wxBlur)">' + blobs + '</g>' + dots;
    const warn = ranked.filter((o) => o.i >= 0.45).sort((a, b) => b.i - a.i).slice(0, 6);
    $('wxWarn').innerHTML = warn.length ? warn.map((o) => {
      const w = D.items[o.f.facility_id].slice().sort((a, b) => a.days_of_stock - b.days_of_stock)[0], c = wxCol(o.i);
      const when = w.days_of_stock <= t ? 'out of stock' : 'out in ' + w.days_of_stock.toFixed(1) + ' d';
      return '<div class="ins-row"><span class="ins-dot" style="background:' + c[1] + '"></span><div><b>' + esc(o.f.name) + '</b><small>' + esc(w.generic_name) + ' · ' + when + '</small></div><em>' + c[2] + '</em></div>';
    }).join('') : '<div class="ins-empty">Clear skies. No facility is at warning level on this day.</div>';
  }
  function drawOutlook() {
    const days = [0, 7, 14, 21, 30], counts = days.map((d) => D.fs.filter((f) => intensity(f.facility_id, d) >= 0.45).length), mx = Math.max(1, ...counts);
    $('wxOutlook').innerHTML = '<div class="ins-outlook">' + days.map((d, k) => '<div><div class="ins-ob" style="height:' + Math.max(4, counts[k] / mx * 70) + 'px"></div><b>' + counts[k] + '</b><small>' + dayLbl(d) + '</small></div>').join('') + '</div><p class="ins-note">Facilities at Warning or Storm level. Blobs grow and darken as stock-out probability rises.</p>';
  }
  let wxTimer = null;
  async function loadWx() {
    try { await getData(); } catch (e) { return fail('wxWarn', e); }
    if (!$('wxDay').dataset.bound) {
      $('wxDay').dataset.bound = 1;
      $('wxDay').addEventListener('input', drawWx);
      $('wxPlay').addEventListener('click', () => {
        if (wxTimer) { clearInterval(wxTimer); wxTimer = null; $('wxPlay').textContent = 'Play forecast'; return; }
        $('wxPlay').textContent = 'Pause';
        if (+$('wxDay').value >= 30) $('wxDay').value = 0;
        wxTimer = setInterval(() => { const v = +$('wxDay').value + 1; $('wxDay').value = v; drawWx(); if (v >= 30) { clearInterval(wxTimer); wxTimer = null; $('wxPlay').textContent = 'Play forecast'; } }, 300);
      });
    }
    drawOutlook(); drawWx();
  }

  /* ---------- 2. CASCADE SIMULATOR ---------- */
  let G = null, failed = null, reroute = false;
  function buildGraph() {
    const nodes = D.fs.map((f) => ({ f, id: f.facility_id, tier: TIER[f.facility_type] != null ? TIER[f.facility_type] : 3, d: D.minDays[f.facility_id] != null ? D.minDays[f.facility_id] : 10, kids: [], parent: null }));
    nodes.forEach((n) => {
      if (n.tier === 0) return;
      const pools = [
        nodes.filter((m) => m.tier === n.tier - 1 && m.f.district_id === n.f.district_id),
        nodes.filter((m) => m.tier < n.tier && m.f.district_id === n.f.district_id),
        nodes.filter((m) => m.tier === n.tier - 1),
        nodes.filter((m) => m.tier < n.tier)];
      const pool = pools.find((p) => p.length); if (!pool) return;
      n.parent = pool.slice().sort((a, b) => hav(n.f, a.f) - hav(n.f, b.f))[0].id;
    });
    const by = Object.fromEntries(nodes.map((n) => [n.id, n]));
    nodes.forEach((n) => { if (n.parent) by[n.parent].kids.push(n); });
    let leaf = 0;
    const place = (n) => { if (!n.kids.length) n.x = leaf++; else { n.kids.forEach(place); n.x = (n.kids[0].x + n.kids[n.kids.length - 1].x) / 2; } };
    nodes.filter((n) => !n.parent).forEach(place);
    nodes.forEach((n) => { n.px = 40 + n.x * 44; n.py = 50 + n.tier * 92; });
    return { nodes, by, w: Math.max(640, leaf * 44 + 60) };
  }
  function descendants(id, parent) {
    const out = new Set(), q = [id];
    while (q.length) { const c = q.shift(); G.nodes.forEach((n) => { if (parent[n.id] === c && !out.has(n.id)) { out.add(n.id); q.push(n.id); } }); }
    return out;
  }
  function simulate(useReroute) {
    const parent = {}; G.nodes.forEach((n) => { parent[n.id] = n.parent; });
    let backup = null;
    if (useReroute) {
      const sub = descendants(failed, parent);
      G.nodes.filter((k) => parent[k.id] === failed).forEach((k) => {
        const c = G.nodes.filter((m) => m.id !== failed && !sub.has(m.id) && m.tier < k.tier).sort((a, b) => hav(k.f, a.f) - hav(k.f, b.f))[0];
        if (c) { parent[k.id] = c.id; backup = backup || c; }
      });
    }
    const t = { [failed]: 0 }, q = [failed];
    while (q.length) { const c = q.shift(); G.nodes.filter((n) => parent[n.id] === c).forEach((n) => { t[n.id] = t[c] + n.d; q.push(n.id); }); }
    return { t, parent, backup };
  }
  const people = (t, day) => G.nodes.filter((n) => t[n.id] != null && t[n.id] <= day && n.tier > 0).reduce((s, n) => s + (n.f.catchment_population || 0), 0);
  const cnt = (t, day) => G.nodes.filter((n) => t[n.id] != null && t[n.id] <= day).length;
  function drawCas() {
    const day = +$('casDay').value;
    $('casDayLbl').textContent = dayLbl(day);
    const base = simulate(false), cur = reroute ? simulate(true) : base, t = cur.t;
    let e = '', v = '';
    G.nodes.forEach((n) => { const p = cur.parent[n.id]; if (!p) return; const a = G.by[p], hit = t[n.id] != null && t[n.id] <= day; e += '<line x1="' + a.px + '" y1="' + a.py + '" x2="' + n.px + '" y2="' + n.py + '" stroke="' + (hit ? '#e4572e' : '#ffffff33') + '" stroke-width="' + (hit ? 2.4 : 1.4) + '"' + (cur.parent[n.id] !== n.parent ? ' stroke-dasharray="5 4" stroke="#8fe3c8"' : '') + '/>'; });
    G.nodes.forEach((n) => {
      const r = [16, 13, 10, 8][n.tier], tt = t[n.id];
      let col = '#2f8f83';
      if (n.id === failed) col = '#7f1d1d'; else if (tt != null && tt <= day) col = '#e4572e'; else if (tt != null && tt <= day + 7) col = '#e8a317';
      v += '<g class="ins-node" data-id="' + n.id + '"><circle cx="' + n.px + '" cy="' + n.py + '" r="' + r + '" fill="' + col + '" stroke="' + (n.id === failed ? '#fff' : '#0f2a2e') + '" stroke-width="2.5"><title>' + esc(n.f.name) + ' (' + esc(n.f.facility_type) + ')' + (tt != null ? ', dry in ' + tt.toFixed(1) + ' d' : '') + '</title></circle><text x="' + n.px + '" y="' + (n.py + r + 13) + '" text-anchor="middle">' + n.id.slice(-3) + '</text></g>';
    });
    const svg = $('casSvg'); svg.setAttribute('viewBox', '0 0 ' + G.w + ' 340'); svg.innerHTML = e + v;
    const f = G.by[failed].f;
    let h = '<div class="ins-big"><div><b>' + cnt(t, day) + '</b><small>facilities dry by ' + dayLbl(day).toLowerCase() + '</small></div><div><b>' + fmt(people(t, day)) + '</b><small>people losing access</small></div></div>';
    h += '<table class="ins-tbl"><tr><th>By</th><th>Facilities</th><th>People</th></tr>' + [7, 14, 30, 60].map((d) => '<tr><td>Day ' + d + '</td><td>' + cnt(t, d) + '</td><td>' + fmt(people(t, d)) + '</td></tr>').join('') + '</table>';
    const avoided = people(base.t, 60) - people(t, 60);
    if (reroute) h += '<p class="ins-good">Backup route protects ' + (cnt(base.t, 60) - cnt(t, 60)) + ' facilities and ' + fmt(avoided) + ' people within 60 days' + (cur.backup ? ', served from ' + esc(cur.backup.f.name) : '') + '.</p>';
    else h += '<p class="ins-note">Each level downstream runs dry only after the level above it, plus its own stock buffer.</p>';
    $('casInfo').innerHTML = '<h2>' + esc(f.name) + ' goes offline</h2>' + h;
    $('casBackup').textContent = reroute ? 'Remove backup route' : 'Apply backup route';
  }
  async function loadCas() {
    try { await getData(); } catch (e) { return fail('casInfo', e); }
    G = buildGraph();
    if (!failed || !G.by[failed]) { const cntKids = (n) => descendants(n.id, Object.fromEntries(G.nodes.map((m) => [m.id, m.parent]))).size; failed = G.nodes.filter((n) => n.tier === 0).sort((a, b) => cntKids(b) - cntKids(a))[0].id; }
    if (!$('casDay').dataset.bound) {
      $('casDay').dataset.bound = 1;
      $('casDay').addEventListener('input', drawCas);
      $('casSvg').addEventListener('click', (ev) => { const g = ev.target.closest('.ins-node'); if (g) { failed = g.getAttribute('data-id'); reroute = false; $('casDay').value = 0; drawCas(); } });
      $('casBackup').addEventListener('click', () => { reroute = !reroute; drawCas(); });
      let tm = null;
      $('casPlay').addEventListener('click', () => {
        if (tm) { clearInterval(tm); tm = null; return; }
        $('casDay').value = 0;
        tm = setInterval(() => { const v = +$('casDay').value + 1; $('casDay').value = v; drawCas(); if (v >= 60) { clearInterval(tm); tm = null; } }, 200);
      });
    }
    drawCas();
  }

  /* ---------- 3. IMPACT LEDGER ---------- */
  const H = 30;
  const outage = (days) => Math.max(0, H - (days || 0));
  function impact(r) { return Math.max(0, outage(r.current_dest_days_stock) - outage(r.expected_dest_days_stock)); }
  function countUp(el, to) { const t0 = performance.now(); (function s(now) { const k = Math.min(1, (now - t0) / 900); el.textContent = fmt(to * (1 - Math.pow(1 - k, 3))); if (k < 1) (window.requestAnimationFrame || setTimeout)(s); })(t0); }
  function ledRow(r, pending) {
    const a = outage(r.current_dest_days_stock), b = outage(r.expected_dest_days_stock), pop = (D.byId[r.dest_facility_id] || {}).catchment_population || 0;
    return '<div class="ins-led"><div><b>' + esc(r.quantity) + ' ' + esc(r.unit_of_measure || 'units') + ' of ' + esc(r.product_name) + '</b><small>' + esc(r.source_facility_name) + ' to ' + esc(r.dest_facility_name) + ' · serves ' + fmt(pop) + ' people</small>' +
      '<div class="ins-cmp"><span>Without</span><div class="ins-track"><i style="width:' + (a / H * 100) + '%;background:#e4572e"></i></div><span>' + a.toFixed(0) + ' d dry</span></div>' +
      '<div class="ins-cmp"><span>With</span><div class="ins-track"><i style="width:' + (b / H * 100) + '%;background:#2f8f83"></i></div><span>' + b.toFixed(0) + ' d dry</span></div></div>' +
      '<div class="ins-gain"><b>' + (pending ? '+' : '') + impact(r).toFixed(0) + '</b><small>' + (pending ? 'days if approved' : 'days prevented') + '</small></div></div>';
  }
  async function loadLed() {
    try { await getData(); } catch (e) { return fail('ledList', e); }
    const done = D.recs.filter((r) => r.status === 'APPROVED' || r.status === 'EXECUTED'), pend = D.recs.filter((r) => r.status === 'AWAITING_APPROVAL');
    const days = done.reduce((s, r) => s + impact(r), 0), units = done.reduce((s, r) => s + (r.quantity || 0), 0), ppl = done.reduce((s, r) => s + ((D.byId[r.dest_facility_id] || {}).catchment_population || 0), 0), atStake = pend.reduce((s, r) => s + impact(r), 0);
    $('ledKpis').innerHTML = '<div class="ins-k"><small>Stock-out days prevented</small><strong id="ledDays">0</strong></div><div class="ins-k"><small>Actions approved</small><strong>' + done.length + '</strong></div><div class="ins-k"><small>Units moved</small><strong>' + fmt(units) + '</strong></div><div class="ins-k"><small>People protected</small><strong>' + fmt(ppl) + '</strong></div>';
    countUp($('ledDays'), days);
    $('ledList').innerHTML = done.length ? done.map((r) => ledRow(r, false)).join('') : '<div class="ins-empty">No approved actions yet. Approve a recommendation to start the ledger.</div>';
    $('ledPend').innerHTML = pend.length ? '<p class="ins-warn">' + pend.length + ' pending action' + (pend.length > 1 ? 's' : '') + ' could prevent ' + atStake.toFixed(0) + ' more stock-out days.</p>' + pend.map((r) => ledRow(r, true)).join('') : '<div class="ins-empty">Nothing is waiting for approval.</div>';
  }

  window.TabHooks = Object.assign(window.TabHooks || {}, { weather: loadWx, cascade: loadCas, ledger: loadLed });
})();
