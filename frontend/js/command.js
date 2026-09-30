// Command Centre view: live data from /api/v1
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const MSG = ['Stable. Supplies look healthy.', 'Watch. Some items are trending down.', 'Low stock. Items are under 14 days.', 'Critical. Items are under 5 days.', 'Emergency. Critical stock and ICU pressure.'];
  let pos = [], facs = [];

  function stress(f, minDays, icuPct) {
    let s = 0;
    if (minDays != null) s = minDays < 5 ? 3 : minDays < 14 ? 2 : minDays < 30 ? 1 : 0;
    if (icuPct >= 90) s = Math.max(s, 3);
    if (minDays != null && minDays < 5 && icuPct >= 85) s = 4;
    if (f.connectivity_status && f.connectivity_status !== 'ONLINE') s = Math.max(s, 1);
    return s;
  }

  function drawMap(fs, preds, recs) {
    const minDays = {};
    preds.forEach((p) => { const d = p.days_of_stock; if (minDays[p.facility_id] == null || d < minDays[p.facility_id]) minDays[p.facility_id] = d; });
    const R = 34, W = Math.sqrt(3) * R, cols = 7, ns = '';
    facs = fs.map((f) => { const icu = f.icu_beds ? (100 * f.icu_occupied) / f.icu_beds : 0; return { f, s: stress(f, minDays[f.facility_id], icu), icu }; });
    pos = {};
    let h = '';
    const pts = (cx, cy) => [0, 1, 2, 3, 4, 5].map((i) => { const a = (Math.PI / 180) * (60 * i - 30); return (cx + R * Math.cos(a)).toFixed(1) + ',' + (cy + R * Math.sin(a)).toFixed(1); }).join(' ');
    facs.forEach((o, i) => {
      const r = Math.floor(i / cols), c = i % cols, cx = 50 + W * c + (r % 2 ? W / 2 : 0), cy = 50 + r * R * 1.68;
      pos[o.f.facility_id] = [cx, cy];
      h += '<polygon class="hex s' + o.s + '" data-i="' + i + '" tabindex="0" points="' + pts(cx, cy) + '"><title>' + esc(o.f.name) + '</title></polygon>';
    });
    const t = recs.find((r) => r.status === 'AWAITING_APPROVAL' && pos[r.source_facility_id] && pos[r.dest_facility_id]);
    if (t) { const a = pos[t.source_facility_id], b = pos[t.dest_facility_id]; h += '<path class="cc-arc" d="M' + a[0] + ',' + a[1] + ' Q' + ((a[0] + b[0]) / 2) + ',' + (Math.min(a[1], b[1]) - 40) + ' ' + b[0] + ',' + b[1] + '"/>'; }
    const em = facs.find((o) => o.s === 4);
    if (em) h += '<circle class="cc-pulse" cx="' + pos[em.f.facility_id][0] + '" cy="' + pos[em.f.facility_id][1] + '" r="28"/>';
    const rows = Math.ceil(fs.length / cols);
    const svg = $('ccMap');
    svg.setAttribute('viewBox', '0 0 ' + (W * cols + 110) + ' ' + (rows * R * 1.68 + 50));
    svg.innerHTML = h;
  }

  function show(el) {
    const o = facs[+el.getAttribute('data-i')];
    document.querySelectorAll('#ccMap .hex').forEach((x) => x.classList.remove('sel'));
    el.classList.add('sel');
    $('ccRead').textContent = o.f.name + ' (' + (o.f.district_name || '') + '): ' + MSG[o.s] + ' ICU ' + Math.round(o.icu) + '% full.';
  }

  function recCard(r) {
    const reasons = (r.reason_list_parsed || []).slice(0, 3).map((x) => '<span>' + esc(x) + '</span>').join('');
    const conf = Math.round((r.confidence || 0) * 100);
    return '<div class="cc-rec" data-id="' + esc(r.recommendation_id) + '"><p><b>Move ' + esc(r.quantity) + ' ' + esc(r.unit_of_measure || 'units') + ' of ' + esc(r.product_name) + '</b> from ' + esc(r.source_facility_name) + ' to ' + esc(r.dest_facility_name) + '</p>' +
      '<div class="cc-why"><span>Destination: ' + esc(r.current_dest_days_stock) + ' days of stock</span>' + reasons + '</div>' +
      '<div class="cc-conf" title="Confidence ' + conf + '%"><div style="width:' + conf + '%"></div></div>' +
      '<div class="cc-act"><button class="cc-btn" data-a="approve">Approve</button><button class="cc-btn ghost" data-a="reject">Reject</button></div></div>';
  }

  async function load() {
    const A = window.Api;
    try {
      const [m, recs, preds, fs] = await Promise.all([A.getNationalMetrics(), A.getRecommendations(), A.getStockoutPredictions(), A.getFacilities()]);
      const pending = recs.filter((r) => r.status === 'AWAITING_APPROVAL');
      const crit = preds.filter((p) => p.risk_tier === 'CRITICAL' || p.risk_tier === 'EMERGENCY');
      const facN = new Set(crit.map((p) => p.facility_id)).size;
      $('ccHead').innerHTML = crit.length ? facN + ' facilities will run short of <b>essential medicines</b> soon.' : 'Supplies look stable across the network.';
      const top = pending[0];
      $('ccSub').textContent = top ? 'Moving ' + top.quantity + ' units of ' + top.product_name + ' from ' + top.source_facility_name + ' to ' + top.dest_facility_name + ' closes the largest gap. It needs your approval.' : 'No actions are waiting for approval.';
      $('ccKpis').innerHTML =
        '<div class="cc-kpi"><small>Critical stock-outs</small><strong>' + m.critical_stockouts_count + '</strong><em>' + m.active_alerts_total + ' active alerts</em></div>' +
        '<div class="cc-kpi"><small>ICU occupancy</small><strong>' + m.icu_occupancy_rate + '%</strong><em>' + m.icu_occupied + ' of ' + m.icu_beds + ' beds</em></div>' +
        '<div class="cc-kpi"><small>Staff present</small><strong>' + m.workforce_coverage_pct + '%</strong><em class="ok">' + m.staff_present + ' of ' + m.staff_scheduled + '</em></div>' +
        '<div class="cc-kpi"><small>Batches near expiry</small><strong>' + m.batches_near_expiry + '</strong><em class="ok">' + m.facilities_reporting + ' of ' + m.facilities_total + ' facilities reporting</em></div>';
      $('ccRecs').innerHTML = pending.length ? pending.map(recCard).join('') : '<div class="cc-empty">No recommendations are waiting for approval.</div>';
      const byProd = {};
      preds.forEach((p) => { if (!byProd[p.generic_name] || p.days_of_stock < byProd[p.generic_name]) byProd[p.generic_name] = p.days_of_stock; });
      const rows = Object.entries(byProd).sort((a, b) => a[1] - b[1]).slice(0, 6);
      $('ccFc').innerHTML = rows.map(([n, d]) => { const c = d < 5 ? 'var(--s4)' : d < 14 ? 'var(--s2)' : 'var(--s1)'; return '<div class="cc-fc"><span>' + esc(n) + '</span><div class="cc-bar"><div style="width:' + Math.min(100, (d / 30) * 100) + '%;background:' + c + '"></div></div><b>' + d.toFixed(1) + ' d</b></div>'; }).join('');
      drawMap(fs, preds, recs);
    } catch (e) { $('ccHead').textContent = 'Could not load live data.'; $('ccSub').textContent = 'Check that the server is running and you are signed in.'; console.error(e); }
  }

  window.loadCommandCentre = load;

  document.addEventListener('DOMContentLoaded', () => {
    if (!$('view-command')) return;
    $('ccMap').addEventListener('click', (e) => { if (e.target.classList.contains('hex')) show(e.target); });
    $('ccMap').addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.classList.contains('hex')) show(e.target); });
    $('ccRecs').addEventListener('click', async (e) => {
      const b = e.target.closest('button[data-a]'); if (!b) return;
      const card = b.closest('.cc-rec'), id = card.getAttribute('data-id'), act = card.querySelector('.cc-act');
      let who = 'Command Centre user';
      try { const u = JSON.parse(localStorage.getItem('fnhrip_user_profile') || '{}'); who = u.display_name || u.role || who; } catch (x) {}
      act.textContent = 'Saving...';
      try {
        if (b.dataset.a === 'approve') await window.Api.approveRecommendation(id, 'Approved from Command Centre', who);
        else await window.Api.rejectRecommendation(id, 'Rejected from Command Centre', who);
        act.innerHTML = '<span class="cc-done">' + (b.dataset.a === 'approve' ? 'Approved. Logged in audit trail.' : 'Rejected.') + '</span>';
      } catch (err) { act.innerHTML = '<span class="cc-done" style="color:var(--s4)">Could not save. Try again.</span>'; }
    });
    setTimeout(load, 300);
  });
})();
