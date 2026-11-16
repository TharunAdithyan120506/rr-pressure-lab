/* RR Pressure Lab - static dashboard. Data comes from data.js (window.DATA). */
const D = window.DATA;
const app = document.getElementById("app");
document.getElementById("gen").textContent = D.generated;

// ---------- helpers ----------
const f0 = (x) => (x == null || isNaN(x) ? "–" : Math.round(x).toLocaleString("en-IN"));
const f1 = (x) => (x == null || isNaN(x) ? "–" : (+x).toFixed(1));
const f2 = (x) => (x == null || isNaN(x) ? "–" : (+x).toFixed(2));
const cr = (x) => (x == null ? "–" : "₹" + (+x).toFixed(x < 10 && x % 1 ? 2 : 1).replace(/\.0$/, "") + " cr");
const ord = (n) => { n = Math.round(n); const s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); };
const vClass = (v) => ({ "Retain": "v-retain", "Release": "v-release", "Release & rebuy": "v-rebuy", "Trade chip": "v-trade" }[v]);
const chip = (v) => `<span class="chip ${vClass(v)}">${v}</span>`;
const SIL = `<div class="sil"><svg width="150" height="180" viewBox="0 0 120 145" fill="currentColor" aria-label="No photo"><circle cx="60" cy="40" r="27"/><path d="M6 145c0-35 24-58 54-58s54 23 54 58z"/></svg></div>`;
const FLAG = { India: "\u{1F1EE}\u{1F1F3}", Australia: "\u{1F1E6}\u{1F1FA}", England: "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}", "South Africa": "\u{1F1FF}\u{1F1E6}", "New Zealand": "\u{1F1F3}\u{1F1FF}", "Sri Lanka": "\u{1F1F1}\u{1F1F0}", "West Indies": "\u{1F3CF}", Pakistan: "\u{1F1F5}\u{1F1F0}", Bangladesh: "\u{1F1E7}\u{1F1E9}", Afghanistan: "\u{1F1E6}\u{1F1EB}", Zimbabwe: "\u{1F1FF}\u{1F1FC}", Ireland: "\u{1F1EE}\u{1F1EA}" };
const flag = (c) => FLAG[c] || "\u{1F3CF}";
const photo = (p) => (p.photo ? `<img src="photos/${p.photo}" alt="${p.name}" loading="lazy">` : SIL);
const src = (id) => D.sources.find((s) => s.id === id);
const byPid = Object.fromEntries(D.squad.map((p) => [p.pid, p]));
const PURSE = D.purse.purse_total_cr;

const tip = document.getElementById("tip");
document.addEventListener("mousemove", (e) => {
  const t = e.target.closest("[data-tip]");
  if (!t) { tip.style.opacity = 0; return; }
  tip.innerHTML = t.dataset.tip;
  tip.style.opacity = 1;
  const w = tip.offsetWidth, x = Math.min(e.clientX + 14, innerWidth - w - 8);
  tip.style.left = x + "px"; tip.style.top = e.clientY + 16 + "px";
});

/** Paired bars: pressure v ordinary, one metric per row, each on its own scale. */
function pairBars(rows) {
  const body = rows.filter((r) => r.p != null || r.o != null).map((r) => {
    const max = Math.max(r.p || 0, r.o || 0) * 1.12 || 1;
    const one = (v, col, name) => v == null ? "" :
      `<div class="bar" data-tip="${r.label} · ${name}: <b>${r.fmt(v)}</b>${r.n ? "<br>" + r.n[name === "Pressure" ? 0 : 1] : ""}"><i style="width:${(100 * v / max).toFixed(1)}%;background:var(--${col})"></i><span>${r.fmt(v)}</span></div>`;
    return `<div class="pb"><div class="lab">${r.label}<small>${r.hint || ""}</small></div><div class="bars">${one(r.p, "pressure", "Pressure")}${one(r.o, "ordinary", "Ordinary")}</div></div>`;
  }).join("");
  return `<div class="legend"><span><i style="background:var(--pressure)"></i>Pressure balls</span><span><i style="background:var(--ordinary)"></i>Ordinary balls</span></div>${body}`;
}
const batRows = (s) => {
  const p = s.pressure, o = s.ordinary; if (!p && !o) return [];
  const n = [p ? `${f0(p.balls)} balls` : "", o ? `${f0(o.balls)} balls` : ""];
  return [
    { label: "Strike rate", hint: "runs per 100 balls", p: p?.sr, o: o?.sr, fmt: f0, n },
    { label: "Average", hint: "runs per dismissal", p: p?.outs ? p.avg : null, o: o?.outs ? o.avg : null, fmt: f1, n },
    { label: "Boundary %", hint: "balls hit for 4 or 6", p: p?.bnd_pct, o: o?.bnd_pct, fmt: f1, n },
    { label: "Dot ball %", hint: "lower is better", p: p?.dot_pct, o: o?.dot_pct, fmt: f1, n },
  ];
};
const bowlRows = (s) => {
  const p = s.pressure, o = s.ordinary; if (!p && !o) return [];
  const n = [p ? `${f0(p.balls)} balls, ${f0(p.wkts)} wickets` : "", o ? `${f0(o.balls)} balls, ${f0(o.wkts)} wickets` : ""];
  return [
    { label: "Economy", hint: "runs per over, lower is better", p: p?.econ, o: o?.econ, fmt: f2, n },
    { label: "Balls per wicket", hint: "lower is better", p: p?.wkts ? p.sr : null, o: o?.wkts ? o.sr : null, fmt: f1, n },
    { label: "Dot ball %", hint: "higher is better", p: p?.dot_pct, o: o?.dot_pct, fmt: f1, n },
    { label: "Boundary %", hint: "conceded, lower is better", p: p?.bnd_pct, o: o?.bnd_pct, fmt: f1, n },
  ];
};
function meter(label, pct, detail) {
  if (pct == null) return "";
  return `<div class="meter"><div class="top2"><span>${label}</span><span>${ord(pct)} percentile</span></div>
    <div class="trk" data-tip="${label}: better than ${Math.round(pct)}% of ranked players"><i style="left:${Math.max(2, Math.min(98, pct))}%"></i></div><small>${detail || ""}</small></div>`;
}
function seasonCols(byYear, key, sub, fmtSub) {
  const yrs = Object.keys(byYear).filter((y) => byYear[y]).sort();
  if (!yrs.length) return `<p class="note">No IPL deliveries in the data.</p>`;
  const max = Math.max(...yrs.map((y) => byYear[y][key] || 0), 1);
  return `<div class="cols">${yrs.map((y) => { const r = byYear[y]; return `<div class="c" data-tip="IPL ${y}: <b>${f0(r[key])}</b> ${key === "runs" ? "runs" : "wickets"} · ${sub === "sr" ? "strike rate" : "economy"} ${fmtSub(r[sub])} · ${f0(r.balls)} balls">
    <b>${f0(r[key])}</b><i style="height:${Math.max(2, 78 * (r[key] || 0) / max)}px"></i><span>${y}</span><small>${fmtSub(r[sub])}</small></div>`; }).join("")}</div>`;
}
function splitTable(s, role) {
  const rows = [];
  const add = (name, r) => { if (r && r.balls) rows.push([name, r]); };
  add("All matches", s.all); add("IPL", s.ipl); add("T20 internationals", s.t20i); add("IPL 2026", s.ipl_2026);
  ["powerplay", "middle", "death"].forEach((ph) => add(ph[0].toUpperCase() + ph.slice(1) + " overs", s.phase?.[ph]));
  if (role === "bat") { add("Against pace", s.vs_type?.Pace); add("Against spin", s.vs_type?.Spin); }
  add("Batting first", s.innings?.["1"]); add(role === "bat" ? "Chasing" : "Defending", s.innings?.["2"]);
  if (role === "bat") return `<div class="scroll"><table><tr><th>Split</th><th class="r">Balls</th><th class="r">Runs</th><th class="r">Strike rate</th><th class="r">Average</th><th class="r">Boundary %</th><th class="r">Dot %</th></tr>
    ${rows.map(([n, r]) => `<tr><td>${n}</td><td class="r num">${f0(r.balls)}</td><td class="r num">${f0(r.runs)}</td><td class="r num">${f0(r.sr)}</td><td class="r num">${r.outs ? f1(r.avg) : "–"}</td><td class="r num">${f1(r.bnd_pct)}</td><td class="r num">${f1(r.dot_pct)}</td></tr>`).join("")}</table></div>`;
  return `<div class="scroll"><table><tr><th>Split</th><th class="r">Balls</th><th class="r">Wickets</th><th class="r">Economy</th><th class="r">Balls / wicket</th><th class="r">Dot %</th><th class="r">Boundary %</th></tr>
    ${rows.map(([n, r]) => `<tr><td>${n}</td><td class="r num">${f0(r.balls)}</td><td class="r num">${f0(r.wkts)}</td><td class="r num">${f2(r.econ)}</td><td class="r num">${r.wkts ? f1(r.sr) : "–"}</td><td class="r num">${f1(r.dot_pct)}</td><td class="r num">${f1(r.bnd_pct)}</td></tr>`).join("")}</table></div>`;
}
function moments(list, role) {
  if (!list || !list.length) return `<p class="note">No pressure appearances in the data.</p>`;
  return `<div class="mom">${list.map((m) => `<span class="note num">${m.date}</span><span>${m.kind === "worst" ? "Toughest day: " : ""}v ${m.opp} <span class="note">· ${m.comp}</span><br>
    <span class="note">${role === "bat" ? `${m.runs} runs off ${m.balls} pressure balls${m.wk ? ", dismissed" : ""}` : `${m.wk} wkt${m.wk === 1 ? "" : "s"} for ${m.runs} off ${m.balls} pressure balls`}</span></span>
    <span class="w ${m.wpa_pct >= 0 ? "pos" : "neg"}" data-tip="Change in his team's win probability across those balls">${m.wpa_pct >= 0 ? "+" : ""}${f1(m.wpa_pct)}%</span>`).join("")}</div>`;
}
const modelNote = (m) => !m ? "" : (m.eligible
  ? `${f0(m.n_p)} pressure balls in ${f0(m.m_p)} matches: enough for a full ranking.`
  : `Only ${f0(m.n_p)} pressure balls (${f0(m.m_p)} matches): below the ranking threshold, so the estimate sits close to average.`);

// ---------- squad ----------
const retained = new Set(D.squad.filter((p) => p.verdict === "Retain").map((p) => p.pid));
let squadFilter = { group: "all", verdict: "all" };
function purseStats(set) {
  const keep = D.squad.filter((p) => set.has(p.pid));
  const spent = keep.reduce((a, p) => a + p.salary, 0);
  return { n: keep.length, spent, left: PURSE - spent, slots: D.purse.squad_max - keep.length, os: keep.filter((p) => p.overseas).length };
}
function viewSquad() {
  const st = purseStats(new Set(D.squad.filter((p) => p.verdict === "Retain").map((p) => p.pid)));
  const counts = {}; D.squad.forEach((p) => counts[p.verdict] = (counts[p.verdict] || 0) + 1);
  const list = D.squad.filter((p) => (squadFilter.group === "all" || p.group === squadFilter.group) && (squadFilter.verdict === "all" || p.verdict === squadFilter.verdict));
  const fb = (k, v, label) => `<button class="${squadFilter[k] === v ? "on" : ""}" data-k="${k}" data-v="${v}">${label}</button>`;
  app.innerHTML = `
    <div class="eyebrow">IPL 2027 retention window · deadline 17 November 2026</div>
    <h1 class="page">Rajasthan Royals: who stays, who goes</h1>
    <p class="sub">Every player in the 2026 squad, judged on how he performs when the match is on the line compared with his everyday level, what he costs, and what a replacement would cost. Open a player for the full evidence.</p>
    <div class="grid g4 section">
      <div class="tile"><div class="k">Retain</div><div class="v num">${st.n} <span style="font-size:15px;color:var(--muted)">of ${D.squad.length}</span></div><div class="d">${counts["Release"] || 0} release · ${counts["Release & rebuy"] || 0} release and rebuy · ${counts["Trade chip"] || 0} trade</div></div>
      <div class="tile"><div class="k">Purse left for the auction</div><div class="v num">${cr(st.left)}</div><div class="d">of ${cr(PURSE)} (reported, not confirmed)</div></div>
      <div class="tile"><div class="k">Squad slots to fill</div><div class="v num">${st.slots}</div><div class="d">squad limit ${D.purse.squad_max}</div></div>
      <div class="tile"><div class="k">Overseas players kept</div><div class="v num">${st.os} <span style="font-size:15px;color:var(--muted)">of ${D.purse.overseas_max}</span></div><div class="d">${D.purse.overseas_max - st.os} overseas slots open</div></div>
    </div>
    <div class="grid g3 section">${D.needs.map((n, i) => `<div class="card"><h3>Auction need ${i + 1}</h3><b>${n.need}</b><p class="note" style="margin:8px 0 0">${n.evidence}</p></div>`).join("")}</div>
    <div class="filters">${fb("group", "all", "All")}${fb("group", "bat", "Batters")}${fb("group", "ar", "All-rounders")}${fb("group", "bowl", "Bowlers")}<span class="sep"></span>
      ${fb("verdict", "all", "Any verdict")}${fb("verdict", "Retain", "Retain")}${fb("verdict", "Release", "Release")}${fb("verdict", "Release & rebuy", "Release & rebuy")}${fb("verdict", "Trade chip", "Trade chip")}</div>
    <div class="squad">${list.map((p) => {
      const r = p.group === "bowl" ? p.rank_bowl : p.rank_bat || p.rank_bowl;
      return `<a class="pc" href="#/player/${p.pid}">
        <div class="tilebox"><span class="flag">${flag(p.country)}</span>${p.overseas ? '<span class="os">✈</span>' : ""}<span class="no">${p.jersey ?? ""}</span><span class="ph">${photo(p)}</span></div>
        <div class="meta"><h4>${p.name}</h4><div class="role">${p.role}</div>
        <div class="row"><span class="price num">${cr(p.salary)}</span>${chip(p.verdict)}</div>
        <div class="rk">${r ? `Pressure rank ${r.rank} of ${r.of}` : "Not enough pressure balls to rank"}</div></div></a>`; }).join("") || `<p class="note">No players match these filters.</p>`}</div>`;
  app.querySelectorAll(".filters button").forEach((b) => b.onclick = () => { squadFilter[b.dataset.k] = b.dataset.v; viewSquad(); });
}

// ---------- player ----------
function heroTiles(p) {
  const b = p.card.bat, w = p.card.bowl, tiles = [];
  const delta = (pv, ov, lowerBetter) => { if (pv == null || ov == null) return ""; const d = pv - ov, good = lowerBetter ? d < 0 : d > 0; return `<span class="${good ? "up" : "down"}">${d > 0 ? "▲" : "▼"} ${Math.abs(d).toFixed(lowerBetter ? 2 : 0)}</span> v ordinary`; };
  const bat = () => { const s = b.splits; if (s.pressure) tiles.push({ k: "Pressure strike rate", v: f0(s.pressure.sr), d: delta(s.pressure.sr, s.ordinary?.sr, false) }); };
  const bowl = () => { const s = w.splits; if (s.pressure) tiles.push({ k: "Pressure economy", v: f2(s.pressure.econ), d: delta(s.pressure.econ, s.ordinary?.econ, true) }); };
  const useBat = b && b.splits.all && (p.group !== "bowl"), useBowl = w && w.splits.all && (p.group !== "bat");
  if (useBat) bat(); if (useBowl) bowl();
  if (p.group === "bat" && b?.splits.pressure) tiles.push({ k: "Pressure average", v: b.splits.pressure.outs ? f1(b.splits.pressure.avg) : "–", d: `${f0(b.splits.pressure.runs)} runs, ${f0(b.splits.pressure.outs)} dismissals` });
  if (p.group === "bowl" && w?.splits.pressure) tiles.push({ k: "Pressure wickets", v: f0(w.splits.pressure.wkts), d: `${f0(w.splits.pressure.balls)} balls · ${f1(w.splits.pressure.dot_pct)}% dots` });
  const m = (p.group === "bowl" ? w?.model : b?.model) || w?.model || b?.model;
  tiles.push(m ? { k: "Pressure percentile", v: ord(m.level_pct), d: m.eligible ? "among ranked players" : "low-evidence estimate" } : { k: "Pressure percentile", v: "–", d: "no deliveries in the data" });
  while (tiles.length < 3) tiles.unshift({ k: "Pressure record", v: "–", d: "no deliveries in the data" });
  return `<div class="heroTiles">${tiles.slice(0, 3).map((t) => `<div class="ht"><div class="k">${t.k}</div><div class="v num">${t.v}</div><div class="d">${t.d || ""}</div></div>`).join("")}</div>`;
}
function roleBlock(p, role) {
  const c = p.card[role]; if (!c || !c.splits.all) return "";
  const s = c.splits, m = c.model, isBat = role === "bat", rk = isBat ? p.rank_bat : p.rank_bowl;
  const title = isBat ? "Batting" : "Bowling";
  return `<h2 class="section" style="font-size:21px">${title}${rk ? ` <span class="note" style="font-weight:500">· pressure rank ${rk.rank} of ${rk.of}, rating ${f1(rk.rating)}</span>` : ""}</h2>
  <div class="grid g2" style="margin-top:12px">
    <div class="card"><h3>Pressure v ordinary balls</h3>${s.pressure ? pairBars(isBat ? batRows(s) : bowlRows(s)) : `<p class="note">No pressure balls in the data.</p>`}</div>
    <div class="card"><h3>Where he stands</h3>
      ${m ? meter("Under pressure", m.level_pct, `Estimated ${m.level >= 0 ? "+" : ""}${(100 * m.level).toFixed(1)} runs per 100 balls v an average player`) +
            meter("Everyday level", m.ordinary_pct, `Estimated ${m.ordinary >= 0 ? "+" : ""}${(100 * m.ordinary).toFixed(1)} runs per 100 balls`) +
            meter("Lift: rises or dips when it matters", m.lift_pct, `${m.lift >= 0 ? "+" : ""}${(100 * m.lift).toFixed(1)} runs per 100 balls v his own everyday level`) +
            `<p class="note" style="margin:0">${modelNote(m)}</p>` : `<p class="note">No model estimate.</p>`}</div>
    <div class="card"><h3>IPL by season: ${isBat ? "runs" : "wickets"}</h3>${seasonCols(s.ipl_by_year || {}, isBat ? "runs" : "wkts", isBat ? "sr" : "econ", isBat ? (x) => "SR " + f0(x) : (x) => "econ " + f1(x))}</div>
    <div class="card"><h3>Biggest pressure days</h3>${moments(c.moments, role)}</div>
  </div>
  <div class="card section"><h3>${title} splits</h3>${splitTable(s, role)}</div>`;
}
function formBlock(p) {
  const f = p.card.form || {}; if (!f.bat && !f.bowl) return "";
  const lg = { ipl: "IPL", t20i: "T20 internationals", sa20: "SA20", bbl: "Big Bash", psl: "PSL", cpl: "CPL", ilt20: "ILT20", blast: "T20 Blast", smat: "Syed Mushtaq Ali", lpl: "LPL", bpl: "BPL", mlc: "MLC", all: "All T20" };
  const tb = (o, bat) => `<table><tr><th>${bat ? "Batting" : "Bowling"} since 2025</th><th class="r">Innings</th><th class="r">Balls</th><th class="r">${bat ? "Runs" : "Wickets"}</th><th class="r">${bat ? "Strike rate" : "Economy"}</th></tr>
    ${Object.entries(o).sort((a, b) => (a[0] === "all") - (b[0] === "all") || b[1].balls - a[1].balls).map(([k, r]) => `<tr${k === "all" ? ' style="font-weight:700"' : ""}><td>${lg[k] || k}</td><td class="r num">${f0(r.inns)}</td><td class="r num">${f0(r.balls)}</td><td class="r num">${f0(bat ? r.runs : r.wkts)}</td><td class="r num">${bat ? f0(r.sr) : f2(r.econ)}</td></tr>`).join("")}</table>`;
  return `<div class="card section"><h3>Recent form across all T20 cricket (Cricsheet, since Jan 2025)</h3><div class="grid g2">${f.bat ? `<div class="scroll">${tb(f.bat, true)}</div>` : ""}${f.bowl ? `<div class="scroll">${tb(f.bowl, false)}</div>` : ""}</div>
    <p class="note" style="margin:10px 0 0">Context only: these matches are outside the supplied data and do not feed the ranking. Cricsheet carries no Afghanistan matches and thin Indian domestic coverage.</p></div>`;
}
function viewPlayer(pid) {
  const p = byPid[pid]; if (!p) return viewSquad();
  const b = p.card.bat?.splits?.ipl_2026, w = p.card.bowl?.splits?.ipl_2026, v = p.value;
  const season = [`<div><b class="num">${f0(p.card.ipl26_matches)}</b><span>matches</span></div>`];
  if (b && b.balls >= 10) season.push(`<div><b class="num">${f0(b.runs)}</b><span>runs · SR ${f0(b.sr)}</span></div>`);
  if (w && w.balls >= 10) season.push(`<div><b class="num">${f0(w.wkts)}</b><span>wkts · econ ${f1(w.econ)}</span></div>`);
  const idx = D.squad.indexOf(p), prev = D.squad[(idx + D.squad.length - 1) % D.squad.length], next = D.squad[(idx + 1) % D.squad.length];
  app.innerHTML = `
  <div class="hero">
    <div class="word">ROYALS</div>
    ${p.jersey != null ? `<div class="jersey"><small>#</small>${p.jersey}</div>` : ""}
    <div class="left">
      <a class="back" href="#/squad">← Squad</a>
      <h1>${p.name.replace(" ", "<br>")}</h1>
      <div class="team"><i>RR</i>Rajasthan Royals · ${p.role}</div>
      <div class="facts">
        <div><span>Age</span><b class="num">${p.age}</b></div><div><span>Salary</span><b class="num">${cr(p.salary)}</b></div>
        <div><span>Country</span><b>${p.country}${p.overseas ? " ✈" : ""}</b></div><div><span>Bats / bowls</span><b style="font-size:13px">${p.bats} · ${p.bowls}</b></div>
        <div style="grid-column:1/-1"><span>How acquired</span><b style="font-size:13px">${p.acquired}</b></div>
      </div>
    </div>
    <div class="mid">${photo(p)}</div>
    <div class="right">
      <div class="vcard"><div class="lab">Our call for 2027</div>${chip(p.verdict)} <span class="conf">${p.confidence} confidence</span><p>${p.headline}</p></div>
      <div class="vcard"><div class="lab">IPL 2026</div><div class="big">${season.join("")}</div></div>
      <div class="vcard"><div class="lab">Value v salary</div><div class="big"><div><b class="num">${cr(v.value_cr)}</b><span>output worth</span></div><div><b class="num" style="color:${v.surplus_cr >= 0 ? "var(--good)" : "var(--bad)"}">${v.surplus_cr >= 0 ? "+" : "−"}${cr(Math.abs(v.surplus_cr)).slice(1)}</b><span>${v.surplus_cr >= 0 ? "surplus" : "deficit"}</span></div></div>
        <div class="note" style="margin-top:6px" data-tip="Runs above a replacement-level player in IPL 2026, priced at what RR's own wage bill implies a run is worth. Fielding, keeping and captaincy are not valued.">${f0(v.runs_above_repl)} runs above replacement in 2026 ⓘ</div></div>
    </div>
  </div>
  ${heroTiles(p)}
  <div class="grid g2 section">
    <div class="card"><h3>Why: ${p.verdict.toLowerCase()}</h3><ul class="why">${p.reasons.map((r) => `<li>${r}</li>`).join("")}</ul>${p.watch && p.watch !== "None." ? `<div class="watch"><b>Watch:</b> ${p.watch}</div>` : ""}</div>
    <div class="card"><h3>Reporting we used</h3>${p.sources.length ? `<ul class="src" style="margin:0;padding-left:18px">${p.sources.map((id) => { const s = src(id); return `<li><em class="t-${s.tier}">${s.tier === "aggregator" ? "rumour / prediction" : s.tier}</em><a href="${s.url}" target="_blank" rel="noopener">${s.title}</a><div class="note">${s.note}</div></li>`; }).join("")}</ul>` : `<p class="note">No external reporting was needed: this call rests on the ball-by-ball data alone.</p>`}
      <p class="note" style="margin:10px 0 0">Reporting informs the verdict only. It never feeds the pressure ranking.</p></div>
  </div>
  ${p.group === "bowl" ? roleBlock(p, "bowl") + roleBlock(p, "bat") : roleBlock(p, "bat") + roleBlock(p, "bowl")}
  ${!p.card.bat && !p.card.bowl ? `<div class="card section"><h3>No deliveries in the data</h3><p class="note">This player has not batted or bowled in the supplied IPL and T20I matches, so there is nothing to measure. The verdict rests on cost, age and squad balance only.</p></div>` : ""}
  ${formBlock(p)}
  <div class="section" style="display:flex;justify-content:space-between"><a class="back" href="#/player/${prev.pid}" style="font-weight:600">← ${prev.name}</a><a class="back" href="#/player/${next.pid}" style="font-weight:600">${next.name} →</a></div>`;
}

// ---------- purse ----------
function viewPurse() {
  const st = purseStats(retained), max = Math.max(...D.squad.map((p) => Math.abs(p.value.surplus_cr)), 1);
  const order = ["Retain", "Release & rebuy", "Trade chip", "Release"];
  const rows = [...D.squad].sort((a, b) => order.indexOf(a.verdict) - order.indexOf(b.verdict) || b.salary - a.salary);
  const over = st.left < 0 || st.slots < 0 || st.os > D.purse.overseas_max;
  app.innerHTML = `
    <div class="eyebrow">Purse planner</div>
    <h1 class="page">What the retention list leaves for the auction</h1>
    <p class="sub">Switch any player in or out and the purse updates. ${D.purse.purse_note}</p>
    <div class="tabs"><button data-s="rec">Recommended</button><button data-s="safe">Safe: keep Jadeja and Bishnoi</button><button data-s="all">Keep everyone</button><button data-s="none">Clear</button></div>
    <div class="grid g4">
      <div class="tile"><div class="k">Purse left</div><div class="v num" style="color:${st.left < 0 ? "var(--bad)" : "var(--ink)"}">${cr(st.left)}</div><div class="d">${cr(st.spent)} committed of ${cr(PURSE)}</div></div>
      <div class="tile"><div class="k">Players retained</div><div class="v num">${st.n}</div><div class="d">${st.slots >= 0 ? st.slots + " slots to fill" : "over the limit of " + D.purse.squad_max}</div></div>
      <div class="tile"><div class="k">Overseas retained</div><div class="v num" style="color:${st.os > D.purse.overseas_max ? "var(--bad)" : "var(--ink)"}">${st.os} <span style="font-size:15px;color:var(--muted)">of ${D.purse.overseas_max}</span></div><div class="d">${Math.max(0, D.purse.overseas_max - st.os)} overseas slots open</div></div>
      <div class="tile"><div class="k">Average per open slot</div><div class="v num">${st.slots > 0 ? cr(st.left / st.slots) : "–"}</div><div class="d">if spread evenly</div></div>
    </div>
    ${over ? `<div class="watch section"><b>Not a legal squad:</b> ${st.left < 0 ? "salaries exceed the purse. " : ""}${st.slots < 0 ? "More than " + D.purse.squad_max + " players. " : ""}${st.os > D.purse.overseas_max ? "More than " + D.purse.overseas_max + " overseas players." : ""}</div>` : ""}
    <div class="card section"><h3>Purse use</h3><div class="pbar" data-tip="${cr(st.spent)} committed · ${cr(Math.max(st.left, 0))} free"><i style="width:${Math.min(100, 100 * st.spent / PURSE)}%;background:linear-gradient(90deg,#2A5BB8,#4D8DF6)"></i><i style="flex:1;background:linear-gradient(90deg,var(--pink),var(--pink-2))"></i></div>
      <div class="legend" style="margin:8px 0 0"><span><i style="background:#4D8DF6"></i>Committed to retained players</span><span><i style="background:var(--pink)"></i>Free for the auction</span></div></div>
    <div class="card section"><h3>Squad</h3><div class="scroll"><table>
      <tr><th>Keep</th><th>Player</th><th>Role</th><th class="r">Salary</th><th class="r">Output worth</th><th>Surplus / deficit</th><th>Our call</th></tr>
      ${rows.map((p) => { const s = p.value.surplus_cr, wd = (50 * Math.abs(s) / max).toFixed(1); return `<tr class="${retained.has(p.pid) ? "" : "out"}">
        <td><input class="sw" type="checkbox" data-pid="${p.pid}" ${retained.has(p.pid) ? "checked" : ""} aria-label="Retain ${p.name}"></td>
        <td><a href="#/player/${p.pid}" style="font-weight:600">${p.name}</a>${p.overseas ? ' <span class="note">✈</span>' : ""}</td><td class="note">${p.role}</td>
        <td class="r num">${cr(p.salary)}</td><td class="r num">${cr(p.value.value_cr)}</td>
        <td><div style="display:flex;align-items:center;gap:8px"><div class="dv" data-tip="${p.name}: output worth ${cr(p.value.value_cr)} v salary ${cr(p.salary)}"><i class="${s >= 0 ? "pos" : "neg"}" style="width:${wd}%"></i></div><span class="num" style="font-weight:600">${s >= 0 ? "+" : "−"}${Math.abs(s).toFixed(1)}</span></div></td>
        <td>${chip(p.verdict)}</td></tr>`; }).join("")}
    </table></div>
    <p class="note" style="margin:12px 0 0"><b>Output worth</b> = runs above a replacement-level player in IPL 2026 (batting and bowling, pressure balls weighted in), priced at what RR's own wage bill implies a run is worth. It is a within-squad comparison, not a market price: fielding, wicketkeeping, captaincy and players who did not play in 2026 are not valued.</p></div>
    <div class="section"><h2 style="font-size:21px;margin-bottom:14px">What other squads teach</h2><div class="grid g2">${D.lessons.map((l) => { const s = src(l.source); return `<div class="card"><h3>${l.title}</h3><p style="margin:0">${l.text}</p><p class="note src" style="margin:8px 0 0">Source: <a href="${s.url}" target="_blank" rel="noopener">${s.title}</a></p></div>`; }).join("")}</div></div>`;
  app.querySelectorAll(".sw").forEach((c) => c.onchange = () => { c.checked ? retained.add(c.dataset.pid) : retained.delete(c.dataset.pid); viewPurse(); });
  app.querySelectorAll(".tabs button").forEach((b) => b.onclick = () => {
    retained.clear();
    const s = b.dataset.s;
    D.squad.forEach((p) => { if (s === "all" || (s !== "none" && p.verdict === "Retain") || (s === "safe" && D.scenarios.safe.retain_extra.includes(p.pid))) retained.add(p.pid); });
    viewPurse();
  });
}

// ---------- top 10 ----------
let lbRole = "batters", lbOpen = null;
function viewTop() {
  const isBat = lbRole === "batters", list = D[lbRole], lo = 80, hi = 205, x = (v) => Math.max(0, Math.min(100, 100 * (v - lo) / (hi - lo)));
  const row = (r, i) => {
    const ev = isBat ? `SR ${f0(r.sr_p)} · avg ${f1(r.avg_p)} <span style="opacity:.7">(ordinary ${f0(r.sr_o)} · ${f1(r.avg_o)})</span>` : `econ ${f2(r.econ_p)} · ${f0(r.wkts_p)} wkts <span style="opacity:.7">(ordinary ${f2(r.econ_o)})</span>`;
    const c = D.top_cards[r.pid], rr = byPid[r.pid];
    const open = lbOpen === r.pid && c ? `<div class="lbx"><div class="grid g2"><div class="card"><h3>Pressure v ordinary balls</h3>${pairBars(isBat ? batRows(c.bat.splits) : bowlRows(c.bowl.splits))}</div>
      <div class="card"><h3>Biggest pressure days</h3>${moments((isBat ? c.bat : c.bowl).moments, isBat ? "bat" : "bowl")}
      <p class="note" style="margin:12px 0 0">${f0(r.n_p)} pressure balls in ${f0(r.m_p)} matches · ${Math.round(100 * r.ipl_share)}% of his balls in the IPL · pressure balls added ${r.wpa_p >= 0 ? "+" : ""}${f1(r.wpa_p)} wins of win probability in total.</p></div></div></div>` : "";
    return `<div class="lb" data-pid="${r.pid}"><span class="rk num">${r.rank}</span><span class="nm"><b>${r.name}${rr ? ' <span class="chip v-trade" style="font-size:9px;padding:1px 7px">RR</span>' : ""}</b><span>${r.team}</span></span>
      <span class="rt">${f1(r.rating)}</span>
      <span class="iv" data-tip="Rating ${f1(r.rating)} (conservative score).<br>90% of resampled seasons fall between ${f1(r.rating_lo)} and ${f1(r.rating_hi)}."><span class="m" style="left:${x(100)}%"></span><span class="w" style="left:${x(r.rating_lo)}%;width:${x(r.rating_hi) - x(r.rating_lo)}%"></span><span class="p" style="left:${x(r.rating)}%"></span></span>
      <span class="num" data-tip="Share of 1,000 match-resamples in which he ranks in the top 10">${Math.round(100 * r.p_top10)}%</span><span class="ev num">${ev}</span>${open}</div>`;
  };
  const v = D.validation[lbRole];
  const rrRanks = D.squad.map((p) => ({ p, r: isBat ? p.rank_bat : p.rank_bowl })).filter((o) => o.r).sort((a, b) => a.r.rank - b.r.rank);
  app.innerHTML = `
    <div class="eyebrow">Round 1 submission</div>
    <h1 class="page">The ten most reliable ${isBat ? "batters" : "bowlers"} under pressure</h1>
    <p class="sub">Ranked on IPL and T20I deliveries from 2022 to 2026. The rating combines how good a player is on high-leverage balls with whether he rises or dips against his own everyday level, shrunk for sample size. 100 is the average ranked player; 15 points is one standard deviation.</p>
    <div class="tabs"><button class="${isBat ? "on" : ""}" data-r="batters">Batters</button><button class="${isBat ? "" : "on"}" data-r="bowlers">Bowlers</button></div>
    <div class="card">
      <div class="lb head"><span>#</span><span>Player</span><span>Rating</span><span>90% range (line marks 100)</span><span data-tip="Share of 1,000 match-resamples in which he ranks in the top 10">Top-10 odds</span><span>Pressure record</span></div>
      ${list.slice(0, 10).map(row).join("")}
      <p class="note" style="margin:12px 6px 0">Click a player for his evidence. ${D.hp[isBat ? "bat" : "bowl"].eligible} ${isBat ? "batters" : "bowlers"} qualified: at least ${D.params.min_pressure_balls} pressure balls in ${D.params.min_pressure_matches}+ matches, and active since 2025.</p>
    </div>
    <div class="grid g2 section">
      <div class="card"><h3>Next in line: ranks 11 to 25</h3><div class="scroll"><table><tr><th>#</th><th>Player</th><th class="r">Rating</th><th class="r">Top-10 odds</th><th class="r">${isBat ? "Pressure SR" : "Pressure econ"}</th></tr>
        ${list.slice(10, 25).map((r) => `<tr><td class="num">${r.rank}</td><td>${r.name} <span class="note">· ${r.team}</span></td><td class="r num">${f1(r.rating)}</td><td class="r num">${Math.round(100 * r.p_top10)}%</td><td class="r num">${isBat ? f0(r.sr_p) : f2(r.econ_p)}</td></tr>`).join("")}</table></div></div>
      <div><div class="card"><h3>Where RR's ${isBat ? "batters" : "bowlers"} rank</h3><div class="scroll"><table><tr><th>#</th><th>Player</th><th class="r">Rating</th></tr>
        ${rrRanks.map((o) => `<tr><td class="num">${o.r.rank}</td><td><a href="#/player/${o.p.pid}" style="font-weight:600">${o.p.name}</a></td><td class="r num">${f1(o.r.rating)}</td></tr>`).join("")}</table></div><p class="note" style="margin:8px 0 0">Out of ${list.length ? D.hp[isBat ? "bat" : "bowl"].eligible : 0} ranked. Players with too few pressure balls are not ranked.</p></div>
      <div class="card section"><h3>How far to trust the order</h3><ul class="why">
        <li>Split the matches in two at random and the two halves agree at <b>${f2(v.split_half.composite.full_sample_reliability)}</b> reliability (raw pressure averages: ${f2(v.split_half.raw_level.full_sample_reliability)}).</li>
        <li>Estimated from half the matches, the rating predicts pressure results in the other half at <b>${f2(v.holdout_prediction["joint_shrunk_level (ours)"])}</b> correlation, against ${f2(v.holdout_prediction.raw_pressure_average)} for raw pressure averages.</li>
        <li>Top-10 odds below about 60% mean the player could plausibly sit a few places lower: positions 6 to 10 are close calls.</li></ul></div></div>
    </div>`;
  app.querySelectorAll(".tabs button").forEach((b) => b.onclick = () => { lbRole = b.dataset.r; lbOpen = null; viewTop(); });
  app.querySelectorAll(".lb[data-pid]").forEach((el) => el.onclick = (e) => { if (e.target.closest(".lbx")) return; lbOpen = lbOpen === el.dataset.pid ? null : el.dataset.pid; viewTop(); });
}

// ---------- method ----------
function viewMethod() {
  const pd = D.pressure_def, pv = pd.pressure_vs_ordinary, vb = D.validation.batters, vw = D.validation.bowlers, hb = D.hp.bat, hw = D.hp.bowl;
  const sensT = (rows) => `<div class="scroll"><table><tr><th>Change to the method</th><th class="r">Players</th><th class="r">Rank correlation</th><th class="r">Top 10 kept</th></tr>
    ${rows.map((r) => `<tr><td>${r.variant}</td><td class="r num">${r.players_compared}</td><td class="r num">${f2(r.spearman_vs_primary)}</td><td class="r num">${r.primary_top10_in_variant_top10} of 10</td></tr>`).join("")}</table></div>`;
  const groups = { official: "Official", major: "Established outlets and published research", aggregator: "Rumour and prediction sites (shown as rumour only)" };
  app.innerHTML = `
    <div class="eyebrow">Method</div>
    <h1 class="page">How pressure is defined and how players are rated</h1>
    <div class="grid g4 section">
      <div class="tile"><div class="k">Pressure balls</div><div class="v num">${f0(pv.pressure.balls)}</div><div class="d">the 20% of balls with the most at stake</div></div>
      <div class="tile"><div class="k">Share of all win-probability movement</div><div class="v num">${Math.round(100 * pd.pressure_share_of_total_abs_wpa)}%</div><div class="d">happens on those balls</div></div>
      <div class="tile"><div class="k">Team that wins the pressure balls</div><div class="v num">${Math.round(100 * pd.team_won_pressure_wpa_and_match)}%</div><div class="d">also wins the match</div></div>
      <div class="tile"><div class="k">Win-probability model</div><div class="v num">${f2(D.ctx.wp_v2_context.auc)}</div><div class="d">AUC on unseen 2024–26 matches</div></div>
    </div>
    <div class="grid g2 section">
      <div class="card prose"><h3>1 · What counts as pressure</h3>
        <p>A model trained on 9,606 T20 matches estimates the batting side's chance of winning before every ball, from the score, wickets, balls left, target, venue, season and the strength of the two teams. The last four overs of a chase use a separate, finer endgame model.</p>
        <p>The <b>Leverage Index</b> of a ball is how far that chance is expected to swing across the ball's possible outcomes (dot, single, two, four, six, wicket), divided by the average swing. 1.0 is an average ball. Knockout matches are multiplied by ${pd.knockout_mult}.</p>
        <p>A <b>pressure ball</b> is one in the top 20% by Leverage Index (${f2(pd.q80)} or higher). On those balls the average swing in win probability is ${f1(pv.pressure.mean_abs_wpa_pct)}%, against ${f1(pv.ordinary.mean_abs_wpa_pct)}% otherwise; strike rate falls from ${f0(pv.ordinary.strike_rate)} to ${f0(pv.pressure.strike_rate)} and dot balls rise from ${f1(pv.ordinary.dot_pct)}% to ${f1(pv.pressure.dot_pct)}%.</p></div>
      <div class="card"><h3>Where the pressure balls are</h3><div class="scroll"><table><tr><th>Innings</th><th>Phase</th><th class="r">Average leverage</th><th class="r">Balls that are pressure</th><th class="r">Share of all pressure balls</th></tr>
        ${D.composition.map((r) => `<tr><td>${r.innings === 1 ? "Batting first" : "Chase"}</td><td>${r.phase}</td><td class="r num">${f2(r.mean_li)}</td><td class="r num">${Math.round(100 * r.share_pressure)}%</td><td class="r num">${Math.round(100 * r.share_of_all_pressure)}%</td></tr>`).join("")}</table></div>
        <p class="note" style="margin:10px 0 0">Three in four pressure balls come in chases. Batting-first pressure is mostly early wickets in the powerplay.</p>
        <h3 style="margin-top:16px">Sanity check on known finishes</h3><div class="scroll"><table><tr><th>Chase</th><th class="r">Peak leverage</th><th>At</th></tr>
        ${D.validation.spot_checks.map((s) => `<tr><td>${s.match}</td><td class="r num">${f1(s.peak_li)}×</td><td>ball ${s.peak_at_ball}, needing ${s.peak_needed}</td></tr>`).join("")}</table></div></div>
    </div>
    <div class="grid g2 section">
      <div class="card prose"><h3>2 · Measuring performance</h3><ol>
        <li><b>Against expectation.</b> Every ball is compared with what an average player does in the same situation: expected runs and expected chance of a wicket, from models that never saw that match. A wicket is converted to runs using how many runs a wicket costs at that point of an innings (about ${f1(D.ctx.oof_on_supplied.wcost_mean)} on average).</li>
        <li><b>Against the opponent.</b> A ridge regression credits each ball for the batter and bowler involved and for the strength of the opposing team, so runs against strong attacks count for more.</li>
        <li><b>Two parts.</b> Run-scoring value is far more repeatable than dismissal value, so the two are tracked separately and each counts in proportion to the signal it carries.</li></ol></div>
      <div class="card prose"><h3>3 · Turning it into a rating</h3><ol>
        <li><b>Level</b>: the player's estimated true performance on pressure balls. <b>Lift</b>: how much better or worse that is than his own everyday level.</li>
        <li>Both come from one statistical model that treats pressure skill as everyday skill plus lift, and pulls small samples toward the average. Lift is real but small: its spread is about half the spread of everyday skill (best fit ${hb.kappa_mle} for batters, ${hw.kappa_mle} for bowlers; we fix 0.5).</li>
        <li>Rating = 70% Level + 30% Lift. Matches are resampled 1,000 times and the final score is the level a player reaches in three resamples out of four, so one or two freak games cannot carry anyone.</li>
        <li>To qualify: ${D.params.min_pressure_balls}+ pressure balls in ${D.params.min_pressure_matches}+ matches and active since 2025. ${hb.eligible} batters and ${hw.eligible} bowlers qualify.</li></ol></div>
    </div>
    <div class="grid g2 section">
      <div class="card"><h3>Does the order survive changes? Batters</h3>${sensT(D.sensitivity.batters)}</div>
      <div class="card"><h3>Does the order survive changes? Bowlers</h3>${sensT(D.sensitivity.bowlers)}</div>
    </div>
    <div class="card section prose"><h3>What the rating cannot tell you</h3><ul>
      <li><b>Being good under pressure is mostly being good.</b> True pressure skill and everyday skill correlate at about 0.9. Ranking on a player's pressure balls alone gives a list that does not repeat (reliability ${f2(vb.split_half.raw_level.full_sample_reliability)} for batters, ${f2(vw.split_half.raw_level.full_sample_reliability)} for bowlers), which is why the rating borrows from all his balls.</li>
      <li><b>It describes 2022–26, it is not a forecast.</b> Batters' pressure results in 2022–24 barely predict 2025–26 (correlation ${f2(vb.persistence.predict_later_pressure_level["joint_shrunk_level (ours)"])}); bowlers' carry over better (${f2(vw.persistence.predict_later_pressure_level["joint_shrunk_level (ours)"])}).</li>
      <li><b>Places 6 to 10 are close.</b> IPL-only and T20I-only versions keep 5 to 8 of each top 10.</li>
      <li>Fielding, wicketkeeping, captaincy, pitch on the day and the non-striker are not measured. Balls against associate nations rely on a team-strength adjustment.</li></ul></div>
    <div class="card section"><h3>Sources</h3>${Object.entries(groups).map(([t, label]) => `<p style="font-weight:700;margin:10px 0 6px">${label}</p><ul class="src" style="margin:0;padding-left:18px">${D.sources.filter((s) => s.tier === t).map((s) => `<li><a href="${s.url}" target="_blank" rel="noopener">${s.title}</a><div class="note">${s.note}</div></li>`).join("")}</ul>`).join("")}</div>`;
}

// ---------- router ----------
function route() {
  const [, r, id] = (location.hash || "#/squad").split("/");
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("on", a.dataset.r === r || (r === "player" && a.dataset.r === "squad")));
  ({ squad: viewSquad, player: () => viewPlayer(id), purse: viewPurse, top10: viewTop, method: viewMethod }[r] || viewSquad)();
  window.scrollTo(0, 0);
}
addEventListener("hashchange", route);
route();
