/* Biofuels desk front end: reads the published JSON in data/ and draws each tab. No model logic lives here. */
const $ = s => document.querySelector(s);
const J = {};
const C = {s1:'#8fd16a',s2:'#3a9cc0',s3:'#e0605a',s4:'#e8c84a',s5:'#b48ae0',s6:'#e8964a',grid:'#232840',dim:'#8a8d9e'};
window.onerror = (m, s, l) => { const e = $('#err'); e.hidden = false; e.textContent = `Script error: ${m} (line ${l})`; };
async function load(name, path) { try { const r = await fetch(path + '?t=' + Date.now()); J[name] = r.ok ? await r.json() : null; } catch { J[name] = null; } }
const f = (v, d = 2) => v == null || isNaN(v) ? '—' : Number(v).toLocaleString('en-US', {minimumFractionDigits: d, maximumFractionDigits: d});
const sgn = (v, d = 2) => v == null ? '—' : (v >= 0 ? '+' : '') + f(v, d);
const cls = v => v == null ? '' : v >= 0 ? 'up' : 'dn';
const sec = t => `<div class="sec"><div class="sec-title">${t}</div><div class="sec-line"></div></div>`;
const charts = [];
function chart(id, cfg) { const el = document.getElementById(id); if (!el) return; charts.push(new Chart(el, cfg)); }
function baseOpts(extra = {}) {
  return Object.assign({responsive: true, maintainAspectRatio: false, animation: false, interaction: {mode: 'index', intersect: false},
    plugins: {legend: {labels: {color: C.dim, boxWidth: 12, font: {size: 11}}}},
    scales: {x: {type: 'time', grid: {color: C.grid}, ticks: {color: C.dim, maxTicksLimit: 8}},
             y: {grid: {color: C.grid}, ticks: {color: C.dim}}}}, extra);
}
const pts = (arr, from) => (arr || []).filter(p => !from || p[0] >= from).map(p => ({x: p[0].length === 7 ? p[0] + '-01' : p[0], y: p[1]}));
const line = (label, data, color, extra = {}) => Object.assign({label, data, borderColor: color, backgroundColor: color, pointRadius: 0, borderWidth: 1.6, spanGaps: true}, extra);
function kpi(label, val, unit, sub, chg) {
  return `<div class="kpi"><div class="kpi-label">${label}</div><div class="kpi-val">${val}<span class="kpi-unit">${unit || ''}</span></div>
  <div class="kpi-sub">${chg != null ? `<span class="${cls(chg)}">${sgn(chg, Math.abs(chg) < 1 ? 3 : 2)}</span> · ` : ''}${sub || ''}</div></div>`;
}
const P = k => (J.latest && J.latest.prices && J.latest.prices[k]) || null;
function pk(k, label, unit, d = 2) { const p = P(k); if (!p) return kpi(label, '—', unit, 'no feed'); return kpi(label, f(p.close, d), unit, p.stale ? `stale · ${p.date}` : p.date, p.prev != null ? p.close - p.prev : null); }
function asofBar(keys, extra = '') {
  const a = J.asof || {}; const parts = keys.filter(k => a[k]).map(k => `${k.replace(/_/g, ' ')}: ${a[k]}`);
  return `<div class="source-bar">Data as of — ${parts.join(' · ') || 'pending first run'}${extra ? '<br>' + extra : ''}</div>`;
}

/* ---------- Overview ---------- */
function overview() {
  const m = J.margins || {}, i = m.inputs || {}, b = J.balance || {};
  const y26 = (b.years || {})['2026'] || {};
  let h = sec('Market');
  h += `<div class="kpis">${pk('ZL', 'Soybean oil', '¢/lb')}${pk('HO', 'NY Harbor ULSD', '$/gal', 4)}
    ${kpi('BOHO spread', f(i.boho, 3), '$/gal', 'ZL×7.5 lb − HO')}
    ${pk('RN4', 'D4 RIN', '$/RIN', 4)}${pk('RN6', 'D6 RIN', '$/RIN', 4)}${pk('RN3', 'D3 RIN', '$/RIN', 4)}
    ${kpi('D4 − D6', f(i.d4_minus_d6, 4), '$/RIN', 'nesting spread')}
    ${kpi('LCFS credit', f(i.lcfs, 0), '$/t', i.lcfs_src || '')}
    ${kpi('Palm (Bursa)', f(i.feeds && i.feeds.palm && i.feeds.palm.c_lb, 1), '¢/lb', 'FCPO in US¢/lb')}
    ${pk('RS', 'ICE canola', 'CAD/t', 1)}${pk('ECO', 'Euronext rapeseed', '€/t', 2)}${pk('FUCO', 'Bursa UCO', '$/t', 1)}</div>`;
  if (m.read && m.read.length) h += sec('Desk read') + `<div class="insight"><div class="ins-head">What the numbers say · ${m.asof || ''}</div><ul>${m.read.map(x => `<li>${x}</li>`).join('')}</ul></div>`;
  h += sec('Producer margins at screen prices') + marginTable(m.pathways || [], true);
  h += `<div class="g2" style="margin-top:16px"><div class="card"><div class="chart-title">BOHO vs D4 RIN value per biodiesel gallon</div><div class="chart-sub">$/gal · D4 × 1.5 covers the BOHO when it sits above it</div><div class="chart-wrap"><canvas id="c_boho"></canvas></div></div>
    <div class="card"><div class="chart-title">Soybean oil biodiesel screen margin</div><div class="chart-sub">$/gal · HO + D4×1.5 + glycerin − soybean oil − opex · no 45Z, no LCFS</div><div class="chart-wrap"><canvas id="c_bdm"></canvas></div></div></div>`;
  if (y26.rvo_bbd) h += sec('2026 mandate check') + `<div class="kpis">${kpi('BBD RVO 2026', f(y26.rvo_bbd, 2), 'bn RINs', 'incl. SRE reallocation')}
    ${kpi('D4 generated YTD', f(y26.D4_ytd_bn, 2), 'bn', `through ${y26.D4_last || '—'}`)}
    ${kpi('Full-year pace vs RVO', sgn(y26.D4_pace_vs_rvo_bn, 2), 'bn', 'D4 only; surplus fills advanced')}
    ${kpi('Needed per month', f(y26.D4_needed_per_month_rest_bn, 3), 'bn', `vs ${f(y26.D4_avg_month_ytd_bn, 3)} avg so far`)}</div>`;
  h += asofBar(['prices', 'model_economics', 'epa_emts', 'ams_cash', 'lcfs_ca_monthly']);
  $('#page').innerHTML = h;
  const H = m.history || {}, from = '2022-01-01';
  chart('c_boho', {type: 'line', data: {datasets: [line('BOHO', pts(H.boho, from), C.s3), line('D4 × 1.5', pts(H.rin_bd, from), C.s1)]}, options: baseOpts()});
  chart('c_bdm', {type: 'line', data: {datasets: [line('Soy BD margin', pts(H.soy_bd_margin, from), C.s4, {fill: {target: {value: 0}, above: 'rgba(143,209,106,.12)', below: 'rgba(232,90,90,.15)'}})]}, options: baseOpts()});
}
function marginTable(rows, compact) {
  if (!rows.length) return '<div class="card note">Margins appear after the first data run.</div>';
  const hd = compact ? ['Pathway', 'Feedstock ¢/lb', 'Feed $/gal', 'ULSD/jet', 'RINs', '45Z', 'Margin ex-CA', 'LCFS', 'Margin CA', 'Breakeven D4']
    : ['Pathway', 'Feedstock ¢/lb', 'Feed $/gal', 'Opex', 'ULSD/jet', 'EV', 'RINs $/gal', '45Z', 'Co-prod.', 'Margin ex-CA', 'LCFS', 'Margin CA', 'Breakeven D4', 'CI CARB', 'CI 45Z'];
  const tr = r => compact
    ? [r.label, f(r.feed_c_lb, 1), f(r.feed_per_gal, 2), f(r.fuel_px, 2), f(r.rin_per_gal, 2), f(r.z45_per_gal, 2), `<span class="${cls(r.margin_ex_ca)}">${f(r.margin_ex_ca, 2)}</span>`, f(r.lcfs_per_gal, 2), `<span class="${cls(r.margin_ca)}">${f(r.margin_ca, 2)}</span>`, f(r.breakeven_d4_ex_ca, 2)]
    : [r.label, f(r.feed_c_lb, 1), f(r.feed_per_gal, 2), f(r.opex, 2), f(r.fuel_px, 2), f(r.ev, 1), f(r.rin_per_gal, 2), f(r.z45_per_gal, 2), f(r.coproduct, 2), `<span class="${cls(r.margin_ex_ca)}">${f(r.margin_ex_ca, 2)}</span>`, f(r.lcfs_per_gal, 2), `<span class="${cls(r.margin_ca)}">${f(r.margin_ca, 2)}</span>`, f(r.breakeven_d4_ex_ca, 2), r.ci_carb, r.ci_45z];
  return `<div class="tcard"><table><thead><tr>${hd.map((x, j) => `<th class="${j ? 'r' : ''}">${x}</th>`).join('')}</tr></thead><tbody>
    ${rows.map(r => `<tr class="${r.id === 'soy_bd' ? 'hl' : ''}">${tr(r).map((x, j) => `<td class="${j ? 'r' : ''}">${x}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
    <div class="note">$/gal of fuel at screen prices. "Ex-CA" = sold outside California (no LCFS); "CA" adds the LCFS credit. Breakeven D4 = RIN price at which the ex-CA margin is zero. Imported UCO gets no 45Z from 2026 (North American feedstock rule).</div>`;
}

/* ---------- Input / output ---------- */
let yrSel = '2026';
function margins() {
  const m = J.margins || {}, i = m.inputs || {};
  const rows = yrSel === '2026' ? (m.pathways || []) : (m.pathways_2027 || []);
  let h = sec('Feedstock → fuel → credits: per-gallon stack');
  h += `<div class="toggle"><button data-y="2026" class="${yrSel === '2026' ? 'on' : ''}">2026 rules (RD EV 1.7)</button><button data-y="2027" class="${yrSel === '2027' ? 'on' : ''}">2027 rules (RD/SAF EV 1.5)</button></div>`;
  h += marginTable(rows, false);
  h += `<div class="g2" style="margin-top:16px"><div class="card"><div class="chart-title">Revenue vs cost stack by pathway</div><div class="chart-sub">$/gal · ex-California</div><div class="chart-wrap" style="height:360px"><canvas id="c_stack"></canvas></div></div>
   <div class="card"><div class="chart-title">Breakeven D4 RIN by pathway</div><div class="chart-sub">$/RIN · ex-California; the marginal (highest) breakeven is the floor the D4 market has to pay to keep that capacity running</div><div class="chart-wrap" style="height:360px"><canvas id="c_be"></canvas></div></div></div>`;
  const fd = i.feeds || {};
  h += sec('Inputs used') + `<div class="tcard"><table><thead><tr><th>Input</th><th class="r">Value</th><th>Source</th></tr></thead><tbody>
    ${[['NY Harbor ULSD', f(i.ulsd, 4) + ' $/gal', 'NYMEX HO front'], ['Gulf jet', f(i.jet, 4) + ' $/gal', 'EIA US Gulf Coast jet spot'], ['D4 RIN', f(i.d4, 4) + ' $/RIN', 'NYMEX D4 RIN (OPIS) futures'],
       ['LCFS credit', f(i.lcfs, 0) + ' $/t', i.lcfs_src || '']].concat(Object.entries(fd).map(([k, v]) => [k.replace('_', ' ') + ' oil/fat', f(v.c_lb, 2) + ' ¢/lb', v.src]))
      .map(r => `<tr><td>${r[0]}</td><td class="r">${r[1]}</td><td>${r[2]}</td></tr>`).join('')}</tbody></table></div>
    <div class="note">Variables in the stack: ${(m.variables || []).join(' · ')}. Formulas are explained in the margin primer.</div>`;
  h += asofBar(['prices', 'model_economics', 'ams_cash', 'eia_spot', 'lcfs_ca_monthly']);
  $('#page').innerHTML = h;
  document.querySelectorAll('.toggle button').forEach(b => b.onclick = () => { yrSel = b.dataset.y; render(); });
  const lab = rows.map(r => r.label.replace(' renewable diesel', ' RD').replace(' biodiesel', ' BD'));
  chart('c_stack', {type: 'bar', data: {labels: lab, datasets: [
    {label: 'ULSD/jet', data: rows.map(r => r.fuel_px), backgroundColor: C.s2, stack: 'rev'},
    {label: 'RINs', data: rows.map(r => r.rin_per_gal), backgroundColor: C.s1, stack: 'rev'},
    {label: '45Z', data: rows.map(r => r.z45_per_gal), backgroundColor: C.s4, stack: 'rev'},
    {label: 'Co-products', data: rows.map(r => r.coproduct), backgroundColor: C.s5, stack: 'rev'},
    {label: 'Feedstock', data: rows.map(r => r.feed_per_gal), backgroundColor: C.s3, stack: 'cost'},
    {label: 'Opex', data: rows.map(r => r.opex), backgroundColor: C.s6, stack: 'cost'}]},
    options: {responsive: true, maintainAspectRatio: false, animation: false, plugins: {legend: {labels: {color: C.dim, boxWidth: 12}}},
      scales: {x: {stacked: true, ticks: {color: C.dim, font: {size: 10}}, grid: {color: C.grid}}, y: {stacked: true, ticks: {color: C.dim}, grid: {color: C.grid}}}}});
  chart('c_be', {type: 'bar', data: {labels: lab, datasets: [{label: 'Breakeven D4', data: rows.map(r => r.breakeven_d4_ex_ca), backgroundColor: C.s4},
      {label: 'D4 now', data: rows.map(() => i.d4), type: 'line', borderColor: C.s1, pointRadius: 0, borderWidth: 2}]},
    options: {responsive: true, maintainAspectRatio: false, animation: false, plugins: {legend: {labels: {color: C.dim}}}, scales: {x: {ticks: {color: C.dim, font: {size: 10}}, grid: {color: C.grid}}, y: {ticks: {color: C.dim}, grid: {color: C.grid}}}}});
}

/* ---------- RINs & mandate ---------- */
function rins() {
  const b = J.balance || {}, S = J.series || {}, e = J.emts || {};
  let h = sec('RIN prices') + `<div class="kpis">${pk('RN4', 'D4 RIN', '$/RIN', 4)}${pk('RN6', 'D6 RIN', '$/RIN', 4)}${pk('RN3', 'D3 RIN', '$/RIN', 4)}
     ${kpi('D5 RIN', '≈ D4/D6 band', '', 'no free D5 quote; nests between D6 and D4')}</div>`;
  h += `<div class="card" style="margin-top:14px"><div class="chart-title">D4, D6 and D3 RIN futures (OPIS)</div><div class="chart-sub">$/RIN · front contract</div><div class="chart-wrap"><canvas id="c_rins"></canvas></div></div>`;
  h += sec('RVO vs RIN generation');
  const yrs = b.years || {};
  h += `<div class="tcard"><table><thead><tr><th>Year</th><th class="r">BBD RVO</th><th class="r">Advanced</th><th class="r">Total</th><th class="r">D4 YTD</th><th class="r">Months</th><th class="r">D4 pace (12m)</th><th class="r">Pace vs BBD</th><th class="r">D5 YTD</th><th class="r">D6 YTD</th><th class="r">Needed / month</th></tr></thead><tbody>
    ${Object.entries(yrs).map(([y, v]) => `<tr><td>${y}</td><td class="r">${f(v.rvo_bbd)}</td><td class="r">${f(v.rvo_adv)}</td><td class="r">${f(v.rvo_total)}</td><td class="r">${f(v.D4_ytd_bn, 3)}</td><td class="r">${v.D4_months || '—'}</td><td class="r">${f(v.D4_pace_full_year_bn, 2)}</td><td class="r ${cls(v.D4_pace_vs_rvo_bn)}">${sgn(v.D4_pace_vs_rvo_bn)}</td><td class="r">${f(v.D5_ytd_bn, 3)}</td><td class="r">${f(v.D6_ytd_bn, 2)}</td><td class="r">${f(v.D4_needed_per_month_rest_bn, 3)}</td></tr>`).join('')}
    </tbody></table></div><div class="note">Billion RINs. RVOs are the Set 2 final rule (incl. SRE reallocation). D4 above the BBD line counts toward advanced (nesting), which is why D4 generation can run ahead of the BBD RVO.</div>`;
  h += `<div class="g2" style="margin-top:16px"><div class="card"><div class="chart-title">Monthly RIN generation</div><div class="chart-sub">million RINs · EPA EMTS</div><div class="chart-wrap"><canvas id="c_gen"></canvas></div></div>
     <div class="card"><div class="chart-title">D4 generation by fuel (latest year)</div><div class="chart-sub">million RINs · EPA EMTS by fuel category</div><div class="chart-wrap"><canvas id="c_fuel"></canvas></div></div></div>`;
  const og = e.origin || {};
  if (Object.keys(og).length) h += sec('Where D4 RINs come from') + `<div class="tcard"><table><thead><tr><th>Year</th><th class="r">Domestic</th><th class="r">Importer</th><th class="r">Foreign producer</th><th class="r">Total</th><th class="r">Import share</th></tr></thead><tbody>
     ${Object.entries(og).filter(([, v]) => v.D4).map(([y, v]) => { const d = v.D4; return `<tr><td>${y}</td><td class="r">${f(d.domestic / 1e6, 0)}</td><td class="r">${f(d.importer / 1e6, 0)}</td><td class="r">${f(d.foreign / 1e6, 0)}</td><td class="r">${f(d.total / 1e6, 0)}</td><td class="r">${f((d.importer + d.foreign) / d.total * 100, 1)}%</td></tr>`; }).join('')}</tbody></table></div><div class="note">Million D4 RINs. Fuel imports matter for the half-RIN debate (expected for 2028).</div>`;
  h += asofBar(['prices', 'epa_emts', 'model_balance']);
  $('#page').innerHTML = h;
  chart('c_rins', {type: 'line', data: {datasets: [line('D4', pts(S.RN4, '2022-01-01'), C.s1), line('D6', pts(S.RN6, '2022-01-01'), C.s2), line('D3', pts(S.RN3, '2022-01-01'), C.s5)]}, options: baseOpts()});
  const g = k => (b[k] || []).map(p => ({x: p[0] + '-01', y: p[1] / 1e6}));
  chart('c_gen', {type: 'bar', data: {datasets: [{label: 'D4', data: g('d4_monthly'), backgroundColor: C.s1}, {label: 'D5', data: g('d5_monthly'), backgroundColor: C.s4}, {label: 'D6', data: g('d6_monthly'), backgroundColor: C.s2}]},
    options: baseOpts({scales: {x: {type: 'time', time: {unit: 'quarter'}, grid: {color: C.grid}, ticks: {color: C.dim}}, y: {grid: {color: C.grid}, ticks: {color: C.dim}}}})});
  const bf = e.by_fuel || {}, ly = Object.keys(bf).sort().pop();
  if (ly) { const r = bf[ly].filter(x => x.d === 'D4' && x.rins > 0);
    chart('c_fuel', {type: 'bar', data: {labels: r.map(x => x.fuel), datasets: [{label: ly, data: r.map(x => x.rins / 1e6), backgroundColor: C.s1}]},
      options: {indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: false, plugins: {legend: {display: false}}, scales: {x: {ticks: {color: C.dim}, grid: {color: C.grid}}, y: {ticks: {color: C.dim, font: {size: 10}}, grid: {color: C.grid}}}}}); }
}

/* ---------- Feedstocks ---------- */
function feedstocks() {
  const m = J.margins || {}, i = m.inputs || {}, b = J.balance || {}, S = J.series || {}, fs = (J.feed || {}).series || {};
  let h = sec('Feedstock prices') + `<div class="kpis">${Object.entries(i.feeds || {}).map(([k, v]) => kpi(k.replace('_', ' '), f(v.c_lb, 1), '¢/lb', v.src)).join('')}</div>`;
  h += `<div class="g2" style="margin-top:16px"><div class="card"><div class="chart-title">Soybean oil vs palm oil</div><div class="chart-sub">US¢/lb · CBOT front vs Bursa FCPO converted</div><div class="chart-wrap"><canvas id="c_sp"></canvas></div></div>
    <div class="card"><div class="chart-title">Soybean oil share of US biofuel feedstock</div><div class="chart-sub">EIA, share of the main fats and oils used</div><div class="chart-wrap"><canvas id="c_share"></canvas></div></div></div>`;
  h += `<div class="card" style="margin-top:16px"><div class="chart-title">US biofuel feedstock use by type</div><div class="chart-sub">million lb per month · EIA</div><div class="chart-wrap" style="height:340px"><canvas id="c_mix"></canvas></div></div>`;
  const w = b.wasde;
  if (w) h += sec('WASDE soybean oil') + `<div class="tcard"><table><thead><tr><th>Line</th>${(w.columns || []).map(c => `<th class="r">${c}</th>`).join('')}</tr></thead><tbody>
      <tr class="hl"><td>Biofuel use (mil lb)</td>${(w.biofuel || []).map(v => `<td class="r">${f(v, 0)}</td>`).join('')}</tr>
      <tr><td>Ending stocks (mil lb)</td>${(w.ending_stocks || []).map(v => `<td class="r">${f(v, 0)}</td>`).join('')}</tr>
      <tr><td>Avg. price (¢/lb)</td>${(w.price || []).map(v => `<td class="r">${f(v, 2)}</td>`).join('')}</tr></tbody></table></div>
      <div class="note">${w.report} WASDE. EIA soybean oil use into biofuels, last 12 months: <b>${f(b.eia_soy_12m_bn_lb, 2)} bn lb</b> (through ${b.eia_soy_last || '—'}).</div>`;
  h += asofBar(['prices', 'ams_cash', 'eia_feedstocks', 'wasde', 'psd']);
  $('#page').innerHTML = h;
  chart('c_sp', {type: 'line', data: {datasets: [line('Soybean oil', pts(S.ZL, '2021-01-01'), C.s1), line('Palm oil', pts(S.PALM_c_lb, '2021-01-01'), C.s6)]}, options: baseOpts()});
  chart('c_share', {type: 'line', data: {datasets: [line('Soybean oil share', (b.feed_share_soy || []).map(p => ({x: p[0] + '-01', y: p[1] * 100})), C.s1)]}, options: baseOpts()});
  const cols = [C.s1, C.s4, C.s2, C.s3, C.s6, C.s5, '#6b7280', '#94a3b8', '#475569'];
  const keys = ['Soybean oil', 'Corn oil (DCO)', 'Canola oil', 'Tallow', 'Yellow grease (incl. UCO)', 'White grease', 'Poultry fat', 'Other vegetable oils', 'Other waste oils/fats'];
  chart('c_mix', {type: 'bar', data: {datasets: keys.filter(k => fs[k]).map((k, j) => ({label: k, data: pts(fs[k], '2021-01'), backgroundColor: cols[j], stack: 'a'}))},
    options: baseOpts({scales: {x: {type: 'time', stacked: true, grid: {color: C.grid}, ticks: {color: C.dim}}, y: {stacked: true, grid: {color: C.grid}, ticks: {color: C.dim}}}})});
}

/* ---------- LCFS & 45Z ---------- */
function credits() {
  const l = J.lcfs || {}, m = J.margins || {};
  let h = sec('Clean-fuel credit prices') + `<div class="kpis">${pk('LCS', 'CA LCFS futures', '$/t', 2)}
    ${kpi('CA LCFS (CARB monthly)', l.ca_monthly ? f(l.ca_monthly.at(-1)[1], 0) : '—', '$/t', l.ca_monthly ? l.ca_monthly.at(-1)[0] : '')}
    ${kpi('CA LCFS (CARB weekly)', l.ca_weekly ? f(l.ca_weekly.avg_price, 2) : '—', '$/t', l.ca_weekly ? (l.ca_weekly.week || l.ca_weekly.checked) : '')}
    ${kpi('Oregon CFP', l.or_monthly ? f(l.or_monthly.at(-1)[1], 0) : '—', '$/t', l.or_monthly ? l.or_monthly.at(-1)[0] : '')}
    ${kpi('Washington CFS', l.wa_monthly ? f(l.wa_monthly.at(-1)[1], 0) : '—', '$/t', l.wa_monthly ? l.wa_monthly.at(-1)[0] : '')}</div>`;
  h += `<div class="card" style="margin-top:16px"><div class="chart-title">Credit prices</div><div class="chart-sub">$/t CO2e · monthly averages</div><div class="chart-wrap"><canvas id="c_lcfs"></canvas></div></div>`;
  const rows = m.pathways || [];
  h += sec('Credit value per gallon by pathway') + `<div class="tcard"><table><thead><tr><th>Pathway</th><th class="r">CARB CI</th><th class="r">LCFS $/gal</th><th class="r">45Z CI (kg/mmBtu)</th><th class="r">45Z $/gal</th><th class="r">RINs $/gal</th><th class="r">Credits total (CA)</th></tr></thead><tbody>
    ${rows.map(r => `<tr><td>${r.label}</td><td class="r">${r.ci_carb}</td><td class="r">${f(r.lcfs_per_gal)}</td><td class="r">${r.ci_45z}</td><td class="r">${f(r.z45_per_gal)}</td><td class="r">${f(r.rin_per_gal)}</td><td class="r">${f(r.lcfs_per_gal + r.z45_per_gal + r.rin_per_gal)}</td></tr>`).join('')}</tbody></table></div>
    <div class="note">LCFS $/gal = credit price × (2026 diesel CI standard − pathway CI) × energy density ÷ 1,000,000. 45Z $/gal = $1.00 × inflation factor × (50 − CI) ÷ 50, North American feedstock only from 2026. CI values are typical pathway levels; plant-specific scores differ.</div>`;
  h += asofBar(['lcfs_ca_monthly', 'lcfs_ca_weekly', 'lcfs_oregon', 'lcfs_washington', 'prices']);
  $('#page').innerHTML = h;
  const mm = a => (a || []).map(p => ({x: p[0] + '-01', y: p[1]}));
  chart('c_lcfs', {type: 'line', data: {datasets: [line('California', mm(l.ca_monthly), C.s1, {pointRadius: 2}), line('Oregon', mm(l.or_monthly), C.s2, {pointRadius: 2}), line('Washington', mm(l.wa_monthly), C.s4, {pointRadius: 2})]}, options: baseOpts()});
}

/* ---------- Policy ---------- */
function policy() {
  const P2 = J.policy || {}, fr = (J.fedreg || {}).groups || {}, wt = J.watch || {};
  let h = sec('Renewable volume obligations') + table(P2.rvo, ['year', 'category', 'base_bn_rins', 'sre_realloc_bn_rins', 'total_bn_rins', 'status', 'note'], ['Year', 'Category', 'Base', 'SRE realloc.', 'Total (bn RINs)', 'Status', 'Note']);
  h += sec('Small refinery exemptions') + table(P2.sre, ['decision_date', 'compliance_years', 'petitions', 'granted_full', 'granted_partial', 'denied', 'rins_exempted_bn', 'status'], ['Decision', 'Years', 'Petitions', 'Full', 'Partial', 'Denied', 'RINs (bn)', 'Status']);
  h += sec('Policy timeline') + table(P2.timeline, ['date', 'area', 'event', 'status', 'market_read'], ['Date', 'Area', 'Event', 'Status', 'Market read']);
  h += sec('Federal Register (latest documents)');
  h += Object.entries(fr).map(([g, docs]) => `<div class="tcard" style="margin-bottom:12px"><div class="tcard-head">${g}</div><table><tbody>${docs.slice(0, 8).map(d => `<tr><td class="r">${d.date}</td><td>${d.type || ''}</td><td><a href="${d.url}" target="_blank" rel="noopener">${d.title}</a></td></tr>`).join('') || '<tr><td>none</td></tr>'}</tbody></table></div>`).join('');
  const ch = Object.entries(wt).filter(([, v]) => v.changed);
  h += sec('Watched policy pages') + `<div class="tcard"><table><thead><tr><th>Page</th><th>Last change seen</th><th>Checked</th></tr></thead><tbody>${Object.entries(wt).map(([k, v]) => `<tr class="${v.changed ? 'hl' : ''}"><td><a href="${v.url}" target="_blank" rel="noopener">${k}</a></td><td>${v.changed || '—'}</td><td>${v.checked || '—'}</td></tr>`).join('')}</tbody></table></div>`;
  h += asofBar(['policy_fedreg', 'policy_watch']);
  $('#page').innerHTML = h;
}
function table(rows, keys, heads) {
  if (!rows || !rows.length) return '<div class="card note">—</div>';
  return `<div class="tcard"><table><thead><tr>${heads.map(x => `<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${keys.map(k => `<td>${k === 'status' ? `<span class="pill ${String(r[k]).split(/[ ;]/)[0]}">${r[k]}</span>` : (r[k] ?? '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

/* ---------- News ---------- */
function news() {
  const n = (J.news || {}).items || [];
  $('#page').innerHTML = sec('Price- and production-relevant headlines') + `<div class="card"><ul class="news">${n.map(x => `<li><span class="d">${x.date}</span><a href="${x.url}" target="_blank" rel="noopener">${x.title}</a> <span class="pill">${x.source}</span></li>`).join('') || '<li>Headlines appear after the first run.</li>'}</ul></div>` + asofBar(['news']);
}

/* ---------- Primers ---------- */
function primers() {
  const p = J.primers || [];
  $('#page').innerHTML = sec('Primers: how every variable works') + `<div class="primer-nav">${p.map(x => `<a href="#primers/${x.id}">${x.title}</a>`).join('')}</div>` +
    p.map(x => `<div class="primer" id="p-${x.id}"><h3>${x.title}</h3>${x.html}</div>`).join('');
  const t = location.hash.split('/')[1]; if (t) { const el = document.getElementById('p-' + t); if (el) el.scrollIntoView(); }
}

const TABS = {overview, margins, rins, feedstocks, credits, policy, news, primers};
function render() {
  charts.splice(0).forEach(c => c.destroy());
  const t = (location.hash.slice(1).split('/')[0]) || 'overview';
  document.querySelectorAll('.nav-btn').forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#' + t));
  (TABS[t] || overview)();
}
function csv(txt) { const [h, ...r] = txt.trim().split('\n'); const k = h.split(','); return r.map(l => { const v = l.match(/("[^"]*"|[^,]*)(,|$)/g).map(s => s.replace(/,$/, '').replace(/^"|"$/g, '')); return Object.fromEntries(k.map((x, i) => [x, v[i]])); }); }
(async () => {
  await Promise.all([load('latest', 'data/prices/latest.json'), load('margins', 'data/model/margins.json'), load('balance', 'data/model/balance.json'),
    load('series', 'data/model/series.json'), load('emts', 'data/rfs/emts.json'), load('feed', 'data/eia/feedstocks.json'), load('lcfs', 'data/credits/lcfs.json'),
    load('fedreg', 'data/policy/fedreg.json'), load('watch', 'data/policy/watch.json'), load('news', 'data/news/news.json'), load('primers', 'data/primers.json'), load('asof', 'data/asof.json')]);
  J.policy = {};
  for (const [k, f2] of [['rvo', 'rvo.csv'], ['sre', 'sre.csv'], ['timeline', 'policy_timeline.csv']]) {
    try { const r = await fetch('data/manual/' + f2); if (r.ok) J.policy[k] = csv(await r.text()); } catch {}
  }
  if (J.policy.timeline) J.policy.timeline.sort((a, b) => b.date.localeCompare(a.date));
  $('#asof').textContent = J.margins && J.margins.asof ? `Prices as of ${J.margins.asof}` : 'awaiting first data run';
  window.onhashchange = render; render();
})();
