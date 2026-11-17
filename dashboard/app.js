/* Pressure Lab — static dashboard. All numbers come from data.js (window.DATA). */
const D = window.DATA;
const app = document.getElementById("app");
document.getElementById("gen").textContent = D.generated;

/* ---------------- helpers ---------------- */
const f0 = (x) => (x == null || isNaN(x) ? "–" : Math.round(x).toLocaleString("en-IN"));
const f1 = (x) => (x == null || isNaN(x) ? "–" : (+x).toFixed(1));
const f2 = (x) => (x == null || isNaN(x) ? "–" : (+x).toFixed(2));
const pc = (x) => (x == null ? "–" : Math.round(100 * x) + "%");
const cr = (x) => (x == null ? "–" : "₹" + (+x).toFixed(x < 10 && x % 1 ? 2 : 1).replace(/\.0$/, "") + " cr");
const ord = (n) => { n = Math.round(n); const s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); };
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const vClass = (v) => ({ "Retain": "v-retain", "Release": "v-release", "Release & rebuy": "v-rebuy", "Trade chip": "v-trade" }[v] || "v-trade");
const chip = (v) => `<span class="chip ${vClass(v)}">${esc(v)}</span>`;
const SIL = `<svg viewBox="0 0 120 150" fill="rgba(255,255,255,.16)" aria-hidden="true"><circle cx="60" cy="42" r="28"/><path d="M4 150c0-36 25-60 56-60s56 24 56 60z"/></svg>`;
const img = (p, cls = "") => (p ? `<img class="${cls}" src="photos/${p}" alt="" loading="lazy">` : `<span class="${cls}" style="display:grid;place-items:end center;height:100%">${SIL}</span>`);
const byPid = Object.fromEntries(D.squad.map((p) => [p.pid, p]));
const src = (id) => D.sources.find((s) => s.id === id);
const ARROW_L = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 5-7 7 7 7"/></svg>`;
const ARROW_R = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 5 7 7-7 7"/></svg>`;
/** macOS-style segmented control: a sliding knob behind the labels. */
function mac(opts, active, onPick) {
  const i = opts.findIndex((o) => o.v === active);
  const el = document.createElement("div");
  el.className = "mac";
  el.innerHTML = `<i></i>` + opts.map((o) => `<button data-v="${o.v}" class="${o.v === active ? "on" : ""}">${o.l}</button>`).join("");
  requestAnimationFrame(() => {
    const b = el.querySelectorAll("button")[i < 0 ? 0 : i];
    const k = el.querySelector("i");
    k.style.left = b.offsetLeft + "px";
    k.style.width = b.offsetWidth + "px";
  });
  el.querySelectorAll("button").forEach((b) => b.onclick = () => onPick(b.dataset.v));
  return el;
}
/** put a built node into the placeholder the template left behind */
const mount = (sel, node) => { const h = app.querySelector(sel); if (h) h.replaceWith(node); };

const tip = document.getElementById("tip");
addEventListener("mousemove", (e) => {
  const t = e.target.closest("[data-tip]");
  if (!t) { tip.style.opacity = 0; return; }
  tip.innerHTML = t.dataset.tip; tip.style.opacity = 1;
  tip.style.left = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 10) + "px";
  tip.style.top = Math.min(e.clientY + 16, innerHeight - tip.offsetHeight - 10) + "px";
});

const stat = (v, k, cls = "") => `<div class="stat ${cls}"><div class="v num">${v}</div><div class="k">${k}</div></div>`;
const tile = (v, k, d) => `<div class="card"><div class="k" style="font-family:var(--mono);font-size:10px;letter-spacing:.18em;text-transform:uppercase;color:var(--dim)">${k}</div>
  <div style="font-family:var(--disp);font-size:32px;font-weight:900;line-height:1.1;margin-top:6px">${v}</div><div class="note" style="margin-top:3px">${d || ""}</div></div>`;

function pairBars(rows) {
  const body = rows.filter((r) => r.p != null || r.o != null).map((r) => {
    const max = Math.max(r.p || 0, r.o || 0) * 1.12 || 1;
    const one = (v, col, nm, i) => v == null ? "" :
      `<div class="bar" data-tip="${r.label} · ${nm}: <b>${r.fmt(v)}</b>${r.n && r.n[i] ? "<br>" + r.n[i] : ""}"><i style="width:${(100 * v / max).toFixed(1)}%;background:var(--${col})"></i><span>${r.fmt(v)}</span></div>`;
    return `<div class="pb"><div class="lab">${r.label}<small>${r.hint || ""}</small></div><div class="bars">${one(r.p, "press", "Pressure", 0)}${one(r.o, "ord", "Ordinary", 1)}</div></div>`;
  }).join("");
  return `<div class="legend"><span><i style="background:var(--press)"></i>Pressure balls</span><span><i style="background:var(--ord)"></i>Ordinary balls</span></div>${body}`;
}
const batRows = (s) => {
  const p = s.pressure, o = s.ordinary; if (!p && !o) return [];
  const n = [p ? `${f0(p.balls)} balls` : "", o ? `${f0(o.balls)} balls` : ""];
  return [{ label: "Strike rate", hint: "runs per 100 balls", p: p?.sr, o: o?.sr, fmt: f0, n },
  { label: "Average", hint: "runs per dismissal", p: p?.outs ? p.avg : null, o: o?.outs ? o.avg : null, fmt: f1, n },
  { label: "Boundary %", hint: "balls hit for 4 or 6", p: p?.bnd_pct, o: o?.bnd_pct, fmt: f1, n },
  { label: "Dot ball %", hint: "lower is better", p: p?.dot_pct, o: o?.dot_pct, fmt: f1, n }];
};
const bowlRows = (s) => {
  const p = s.pressure, o = s.ordinary; if (!p && !o) return [];
  const n = [p ? `${f0(p.balls)} balls, ${f0(p.wkts)} wickets` : "", o ? `${f0(o.balls)} balls, ${f0(o.wkts)} wickets` : ""];
  return [{ label: "Economy", hint: "runs per over, lower is better", p: p?.econ, o: o?.econ, fmt: f2, n },
  { label: "Balls per wicket", hint: "lower is better", p: p?.wkts ? p.sr : null, o: o?.wkts ? o.sr : null, fmt: f1, n },
  { label: "Dot ball %", hint: "higher is better", p: p?.dot_pct, o: o?.dot_pct, fmt: f1, n },
  { label: "Boundary %", hint: "conceded, lower is better", p: p?.bnd_pct, o: o?.bnd_pct, fmt: f1, n }];
};
const meter = (label, v, detail) => v == null ? "" :
  `<div class="meter"><div class="top"><span>${label}</span><b>${ord(v)} pct</b></div>
   <div class="trk" data-tip="${label}: better than ${Math.round(v)}% of ranked players"><i style="left:${Math.max(2, Math.min(98, v))}%"></i></div><small>${detail || ""}</small></div>`;
function seasonCols(byYear, key, sub, fmtSub) {
  const yrs = Object.keys(byYear).filter((y) => byYear[y]).sort();
  if (!yrs.length) return `<p class="note">No IPL deliveries in the data.</p>`;
  const max = Math.max(...yrs.map((y) => byYear[y][key] || 0), 1);
  return `<div class="cols">${yrs.map((y) => { const r = byYear[y]; return `<div class="c" data-tip="IPL ${y}: <b>${f0(r[key])}</b> ${key === "runs" ? "runs" : "wickets"} · ${fmtSub(r[sub])} · ${f0(r.balls)} balls">
    <b>${f0(r[key])}</b><i style="height:${Math.max(3, 82 * (r[key] || 0) / max)}px"></i><span>${y}</span><small>${fmtSub(r[sub])}</small></div>`; }).join("")}</div>`;
}
function moments(list, role) {
  if (!list?.length) return `<p class="note">No pressure appearances in the data.</p>`;
  return `<div class="mom">${list.map((m) => `<span class="note num">${m.date}</span><span>${m.kind === "worst" ? "Toughest day: " : ""}v ${esc(m.opp)}
    <br><span class="note">${role === "bat" ? `${m.runs} runs off ${m.balls} pressure balls${m.wk ? ", dismissed" : ""}` : `${m.wk} wkt${m.wk === 1 ? "" : "s"} for ${m.runs} off ${m.balls} pressure balls`} · ${esc(m.comp)}</span></span>
    <span class="w ${m.wpa_pct >= 0 ? "pos" : "neg"}" data-tip="Change in his team's win probability across those balls">${m.wpa_pct >= 0 ? "+" : ""}${f1(m.wpa_pct)}%</span>`).join("")}</div>`;
}
function splitTable(s, role) {
  const rows = [];
  const add = (n, r) => { if (r && r.balls) rows.push([n, r]); };
  add("All matches", s.all); add("IPL", s.ipl); add("T20 internationals", s.t20i); add("IPL 2026", s.ipl_2026);
  ["powerplay", "middle", "death"].forEach((ph) => add(ph[0].toUpperCase() + ph.slice(1) + " overs", s.phase?.[ph]));
  if (role === "bat") { add("Against pace", s.vs_type?.Pace); add("Against spin", s.vs_type?.Spin); }
  add("Batting first", s.innings?.["1"]); add(role === "bat" ? "Chasing" : "Defending", s.innings?.["2"]);
  const h = role === "bat" ? ["Balls", "Runs", "Strike rate", "Average", "Bnd %", "Dot %"] : ["Balls", "Wickets", "Economy", "Balls/wkt", "Dot %", "Bnd %"];
  const cell = (r) => role === "bat"
    ? [f0(r.balls), f0(r.runs), f0(r.sr), r.outs ? f1(r.avg) : "–", f1(r.bnd_pct), f1(r.dot_pct)]
    : [f0(r.balls), f0(r.wkts), f2(r.econ), r.wkts ? f1(r.sr) : "–", f1(r.dot_pct), f1(r.bnd_pct)];
  return `<div class="scroll"><table><tr><th>Split</th>${h.map((x) => `<th class="r">${x}</th>`).join("")}</tr>
    ${rows.map(([n, r]) => `<tr><td>${n}</td>${cell(r).map((v) => `<td class="r num">${v}</td>`).join("")}</tr>`).join("")}</table></div>`;
}

/* ---------- 01 · TOP 10 ---------- */
let lbRole = "batters", lbSel = 0;
const lbStep = (d) => { const n = Math.min(10, D[lbRole].length); lbSel = (lbSel + d + n) % n; viewTop10(); };

function viewTop10() {
  const isBat = lbRole === "batters", list = D[lbRole], hero = list[lbSel] || list[0];
  const c = D.top_cards[hero.pid], card = c ? (isBat ? c.bat : c.bowl) : null;
  const pd = D.pressure_def, v = D.validation[lbRole];
  const nm = hero.name.split(" "), first = nm.shift(), last = nm.join(" ") || first;
  const heroStats = isBat
    ? [[f0(hero.sr_p), "Strike rate under pressure", "pink"], [f1(hero.avg_p), "Average under pressure", "gold"], [f0(hero.n_p), "Pressure balls faced", "blue"]]
    : [[f2(hero.econ_p), "Economy under pressure", "pink"], [f0(hero.wkts_p), "Wickets under pressure", "gold"], [f0(hero.n_p), "Pressure balls bowled", "blue"]];

  app.innerHTML = `
  <div class="head">
    <div class="ttl"><span class="eyebrow">Round 1 · most reliable under pressure</span>
      <h1>The top ten</h1></div>
    <span id="macslot"></span>
    <div class="stepper">
      <button id="prev" aria-label="Previous player">${ARROW_L}</button>
      <span class="pos num">${String(lbSel + 1).padStart(2, "0")} / 10</span>
      <button id="next" aria-label="Next player">${ARROW_R}</button>
    </div>
  </div>

  <section class="hero">
    <div class="rankword">${esc(first.toUpperCase())}</div>
    <div class="left">
      <div class="rankbadge"><i>RANK</i><b>${hero.rank}</b></div>
      <h1>${esc(first)}<span class="l2">${esc(last)}</span></h1>
      <div class="meta">
        <span class="pill">${esc(hero.team2027 || hero.team)}</span>
        <span class="pill">Rating <b>${f1(hero.rating)}</b></span>
        <span class="pill" data-tip="Share of 1,000 resamples of his matches in which he still ranks top 10">Top-10 odds <b>${pc(hero.p_top10)}</b></span>
      </div>
      <div class="stack">${heroStats.map(([v2, k, cl]) => stat(v2, k, cl)).join("")}</div>
    </div>
    <button class="arrow l" id="aprev" aria-label="Previous player">${ARROW_L}</button>
    <button class="arrow r" id="anext" aria-label="Next player">${ARROW_R}</button>
    <div class="cut">${img(hero.photo)}</div>
    <div class="right">
      ${hero.note ? `<div class="whycard"><div class="h">${esc(hero.note.head)}</div><p>${esc(hero.note.body)}</p></div>` : ""}
      ${hero.recent?.length ? `<div class="recent">${hero.recent.map((m) => `
        <div class="r" data-tip="${esc(m.comp)} · moved his side's win probability by ${m.wpa >= 0 ? "+" : ""}${f1(m.wpa)}%">
          <b>${esc(m.line)}</b><span class="o">v ${esc(m.opp)}</span><span class="w">${m.wpa >= 0 ? "+" : ""}${f0(m.wpa)}%</span>
        </div>`).join("")}</div>` : ""}
      <div class="card"><h3>Pressure v ordinary</h3>${card ? pairBars(isBat ? batRows(card.splits) : bowlRows(card.splits)) : `<p class="note">—</p>`}</div>
    </div>
  </section>

  <div class="rail10">${list.slice(0, 10).map((r, i) => `
    <div class="rc ${i === lbSel ? "on" : ""}" data-i="${i}">
      ${img(r.photo)}<span class="scrim"></span><span class="n num">${String(r.rank).padStart(2, "0")}</span>
      <h4>${esc(r.name)}</h4><div class="rt num">${f1(r.rating)}</div>
    </div>`).join("")}</div>

  <section class="sec-pad grid3">
    ${tile(pc(pd.pressure_share_of_total_abs_wpa), "Of a match's win probability", "moves on the 20% of balls we call pressure")}
    ${tile(pc(pd.team_won_pressure_wpa_and_match), "Of sides that win those balls", "go on to win the match")}
    ${tile(f2(D.ctx.wp_v2_context.auc), "Win-probability model AUC", "on 2024–26 matches it never saw")}
  </section>

  <section class="sec-pad grid2">
    <div class="card"><h3>Pressure balls really are different</h3>
      <div class="scroll"><table><tr><th></th><th class="r">Pressure</th><th class="r">Ordinary</th></tr>
      ${[["Balls", "balls", f0], ["Win probability moved per ball", "mean_abs_wpa_pct", (x) => f1(x) + "%"], ["Strike rate", "strike_rate", f0],
      ["Dot balls", "dot_pct", (x) => f1(x) + "%"], ["Boundaries", "boundary_pct", (x) => f1(x) + "%"], ["Wickets", "wicket_pct", (x) => f1(x) + "%"]]
      .map(([l, k, f]) => `<tr><td>${l}</td><td class="r num">${f(pd.pressure_vs_ordinary.pressure[k])}</td><td class="r num">${f(pd.pressure_vs_ordinary.ordinary[k])}</td></tr>`).join("")}
      </table></div>
      <p class="note" style="margin-top:10px"><a href="#/pressure" style="color:var(--pink-2);text-decoration:underline">How pressure is defined →</a></p></div>
    <div class="card"><h3>How far to trust the order</h3><ul class="why">
      <li>Split the matches in two at random and the halves agree at <b>${f2(v.split_half.composite.full_sample_reliability)}</b>, against ${f2(v.split_half.raw_level.full_sample_reliability)} for raw pressure averages.</li>
      <li>Estimated from half the matches, the rating predicts pressure results in the other half at <b>${f2(v.holdout_prediction["joint_shrunk_level (ours)"])}</b>, better than raw pressure averages (${f2(v.holdout_prediction.raw_pressure_average)}) or everyday balls alone (${f2(v.holdout_prediction.ordinary_ball_average)}).</li>
      <li>Top-10 odds below about 60% mean a player could plausibly sit a few places lower. Places 6–10 are close calls.</li>
      <li><a href="#/pressure" style="color:var(--pink-2);text-decoration:underline">All 17 verification checks pass →</a></li></ul></div>
  </section>

  <section class="sec-pad">
    <h2 class="sec">Ranks 11–25</h2>
    <div class="card" style="margin-top:14px"><div class="scroll"><table>
      <tr><th>#</th><th>Player</th><th>Team 2027</th><th class="r">Rating</th><th class="r">90% range</th><th class="r">Top-10 odds</th><th class="r">${isBat ? "Pressure SR" : "Pressure econ"}</th><th class="r">Pressure balls</th></tr>
      ${list.slice(10, 25).map((r) => `<tr><td class="num">${r.rank}</td><td style="font-weight:600">${esc(r.name)}</td><td class="note">${esc(r.team2027 || r.team)}</td>
        <td class="r num">${f1(r.rating)}</td><td class="r num dim">${f0(r.rating_lo)}–${f0(r.rating_hi)}</td><td class="r num">${pc(r.p_top10)}</td>
        <td class="r num">${isBat ? f0(r.sr_p) : f2(r.econ_p)}</td><td class="r num dim">${f0(r.n_p)}</td></tr>`).join("")}
    </table></div></div>
  </section>`;

  mount("#macslot", mac([{ v: "batters", l: "Batters" }, { v: "bowlers", l: "Bowlers" }], lbRole,
    (v) => { lbRole = v; lbSel = 0; viewTop10(); }));
  app.querySelector("#prev").onclick = app.querySelector("#aprev").onclick = () => lbStep(-1);
  app.querySelector("#next").onclick = app.querySelector("#anext").onclick = () => lbStep(1);
  app.querySelectorAll(".rc").forEach((el) => el.onclick = () => { lbSel = +el.dataset.i; viewTop10(); });
}

/* ---------------- 02 · ROYALS ---------------- */
let sqFilter = { group: "all" };
function viewRoyals() {
  const rank = (p) => (p.group === "bowl" ? (p.rank_bowl || p.rank_bat) : (p.rank_bat || p.rank_bowl));
  const list = D.squad.filter((p) => sqFilter.group === "all" || p.group === sqFilter.group)
    .slice().sort((x, y) => (rank(y)?.rating || 0) - (rank(x)?.rating || 0));
  const rated = D.squad.map(rank).filter(Boolean);
  const top = D.squad.slice().sort((x, y) => (rank(y)?.rating || 0) - (rank(x)?.rating || 0))[0];
  const fb = (v, l) => `<button class="${sqFilter.group === v ? "on" : ""}" data-v="${v}">${l}</button>`;
  app.innerHTML = `
    <div class="head"><div class="ttl"><span class="eyebrow">Rajasthan Royals · squad</span><h1>The Royals, rated</h1></div>
      <div class="filters">${fb("all", "All")}${fb("bat", "Batters")}${fb("ar", "All-rounders")}${fb("bowl", "Bowlers")}</div></div>
    <section>
      <p class="sub">Every player in the squad on the same pressure scale as the top ten. The rating is 100 for an
      average qualified player and 15 points to a standard deviation; a player with too few pressure balls to rank is
      shown without one. Click anyone for his full profile.</p>
    </section>

    <section class="sec-pad grid4">
      ${tile(f1(rank(top)?.rating), "Best in the squad", esc(top.name))}
      ${tile(`${rated.length}/${D.squad.length}`, "Players with a rating", "the rest have too few pressure balls")}
      ${tile(f0(D.squad.reduce((a2, p) => a2 + (p.value.matches_2026 || 0), 0)), "Appearances in IPL 2026", "across the squad")}
      ${tile(cr(D.squad.reduce((a2, p) => a2 + p.salary, 0)), "Squad wage bill", "2026 contracts")}
    </section>

    <section class="sec-pad">
      <h2 class="sec">Squad</h2>
      <div class="roster" style="margin-top:16px">${list.map((p) => {
        const r = rank(p), b = p.card.bat?.splits?.pressure, w = p.card.bowl?.splits?.pressure;
        const line = p.group === "bowl"
          ? (w ? `econ ${f2(w.econ)} on ${f0(w.balls)} pressure balls` : "no pressure balls bowled")
          : (b ? `SR ${f0(b.sr)} on ${f0(b.balls)} pressure balls` : "no pressure balls faced");
        return `<a class="rrow" href="#/royals/${p.pid}">
          <div class="ph">${img(p.photo)}</div>
          <div><b>${esc(p.name)}${p.overseas ? ' <span class="note">✈</span>' : ""}</b><div class="sub2">${esc(p.role)} · ${line}</div></div>
          <div class="pos">${r ? `${r.rank} of ${r.of}` : "unranked"}</div>
          <div class="sal">${cr(p.salary)}</div>
          <div class="rt">${r ? f1(r.rating) : "–"}<small>${r ? "RATING" : "NO RANK"}</small></div></a>`; }).join("")}</div>
      <p class="note" style="margin-top:14px">Ratings come from the same model as the top ten: value against what an
      average player does in the same situation, credited for the opponent faced, shrunk for sample size.</p>
    </section>`;
  app.querySelectorAll(".filters button").forEach((btn) => btn.onclick = () => { sqFilter.group = btn.dataset.v; viewRoyals(); });
}

function roleBlock(p, role) {
  const c = p.card[role]; if (!c?.splits?.all) return "";
  const s = c.splits, m = c.model, isBat = role === "bat", rk = isBat ? p.rank_bat : p.rank_bowl;
  return `<h2 class="sec sec-pad">${isBat ? "Batting" : "Bowling"}${rk ? ` <span class="note" style="font-weight:500;text-transform:none">· pressure rank ${rk.rank} of ${rk.of}, rating ${f1(rk.rating)}</span>` : ""}</h2>
  <div class="grid2" style="margin-top:14px">
    <div class="card"><h3>Pressure v ordinary balls</h3>${s.pressure ? pairBars(isBat ? batRows(s) : bowlRows(s)) : `<p class="note">No pressure balls.</p>`}</div>
    <div class="card"><h3>Where he stands</h3>${m ? meter("Under pressure", m.level_pct, `${m.level >= 0 ? "+" : ""}${f1(100 * m.level)} runs per 100 balls v an average player`)
    + meter("Everyday level", m.ordinary_pct, "") + meter("Lift when it matters", m.lift_pct, `${m.lift >= 0 ? "+" : ""}${f1(100 * m.lift)} v his own baseline`)
    + `<p class="note" style="margin:0">${m.eligible ? `${f0(m.n_p)} pressure balls in ${f0(m.m_p)} matches: enough for a full ranking.` : `Only ${f0(m.n_p)} pressure balls: below the ranking threshold, so this estimate sits close to average.`}</p>` : ""}</div>
    <div class="card"><h3>IPL by season: ${isBat ? "runs" : "wickets"}</h3>${seasonCols(s.ipl_by_year || {}, isBat ? "runs" : "wkts", isBat ? "sr" : "econ", isBat ? (x) => "SR " + f0(x) : (x) => "econ " + f1(x))}</div>
    <div class="card"><h3>Biggest pressure days</h3>${moments(c.moments, role)}</div>
  </div>
  <div class="card" style="margin-top:16px"><h3>${isBat ? "Batting" : "Bowling"} splits</h3>${splitTable(s, role)}</div>`;
}

function viewPlayer(pid) {
  const p = byPid[pid]; if (!p) return viewRoyals();
  const v = p.value, b = p.card.bat?.splits?.ipl_2026, w = p.card.bowl?.splits?.ipl_2026;
  const nm = p.name.split(" "), first = nm.shift(), last = nm.join(" ") || first;
  const season = [[f0(p.card.ipl26_matches), "Matches 2026", "pink"]];
  if (b && b.balls >= 10) season.push([f0(b.runs), `Runs · SR ${f0(b.sr)}`, "gold"]);
  if (w && w.balls >= 10) season.push([f0(w.wkts), `Wickets · econ ${f1(w.econ)}`, "blue"]);
  const i = D.squad.indexOf(p), prev = D.squad[(i + D.squad.length - 1) % D.squad.length], next = D.squad[(i + 1) % D.squad.length];
  const rk = p.group === "bowl" ? (p.rank_bowl || p.rank_bat) : (p.rank_bat || p.rank_bowl);
  const mdl = (p.card.bat?.model && p.group !== "bowl") ? p.card.bat.model : (p.card.bowl?.model || p.card.bat?.model);
  const pb = p.card.bat?.splits?.pressure, pw = p.card.bowl?.splits?.pressure;
  const heroLeft = p.group === "bowl"
    ? [[pw ? f2(pw.econ) : "–", "Economy under pressure", "pink"], [pw ? f0(pw.wkts) : "–", "Wickets under pressure", "gold"], [f0(mdl?.n_p || 0), "Pressure balls", "blue"]]
    : [[pb ? f0(pb.sr) : "–", "Strike rate under pressure", "pink"], [pb && pb.outs ? f1(pb.avg) : "–", "Average under pressure", "gold"], [f0(mdl?.n_p || 0), "Pressure balls", "blue"]];
  app.innerHTML = `
  <section class="hero">
    <i class="glow"></i><div class="rankword">ROYALS</div>
    <div class="left">
      <a class="note" href="#/royals" style="font-weight:600">← Squad</a>
      <h1 style="margin-top:14px">${esc(first)}<span class="l2">${esc(last)}</span></h1>
      <div class="meta"><span class="pill">${esc(p.role)}</span><span class="pill">Age <b>${p.age}</b></span>
        <span class="pill">${esc(p.country)}${p.overseas ? " ✈" : ""}</span><span class="pill">${esc(p.bats)} · ${esc(p.bowls)}</span></div>
      <div class="stack">${heroLeft.map(([a2, k, cl]) => stat(a2, k, cl)).join("")}</div>
    </div>
    <button class="arrow l" id="pprev" aria-label="Previous player">${ARROW_L}</button>
    <button class="arrow r" id="pnext" aria-label="Next player">${ARROW_R}</button>
    <div class="cut">${img(p.photo)}</div>
    <div class="right">
      <div class="card"><h3>Pressure rating</h3>
        <div style="display:flex;gap:22px;flex-wrap:wrap">
          ${stat(rk ? f1(rk.rating) : "–", rk ? `Rank ${rk.rank} of ${rk.of}` : "Too few pressure balls", "pink")}
          ${stat(mdl ? ord(mdl.level_pct) : "–", "Percentile under pressure", "gold")}
          ${stat(mdl ? ord(mdl.lift_pct) : "–", "Lift when it matters", "blue")}</div>
        <p class="note" style="margin:11px 0 0">${mdl && mdl.eligible ? `Enough evidence for a full ranking: ${f0(mdl.n_p)} pressure balls across ${f0(mdl.m_p)} matches.` : "Below the ranking threshold, so his estimate sits close to the average."}</p></div>
      <div class="card"><h3>IPL 2026</h3><div style="display:flex;gap:22px;flex-wrap:wrap">${season.map(([a2, k, cl]) => stat(a2, k, cl)).join("")}</div></div>
    </div>
  </section>
  ${p.group === "bowl" ? roleBlock(p, "bowl") + roleBlock(p, "bat") : roleBlock(p, "bat") + roleBlock(p, "bowl")}
  ${!p.card.bat && !p.card.bowl ? `<div class="card sec-pad"><h3>No deliveries in the data</h3><p class="note">This player has not batted or bowled in the supplied matches, so there is nothing to measure. The verdict rests on cost, age and squad balance only.</p></div>` : ""}
  <section class="sec-pad" style="display:flex;justify-content:space-between;gap:12px">
    <a class="note" href="#/royals/${prev.pid}" style="font-weight:600">← ${esc(prev.name)}</a>
    <a class="note" href="#/royals/${next.pid}" style="font-weight:600">${esc(next.name)} →</a></section>`;
  app.querySelector("#pprev").onclick = () => location.hash = `#/royals/${prev.pid}`;
  app.querySelector("#pnext").onclick = () => location.hash = `#/royals/${next.pid}`;
}

/* ---------------- 03 · AUCTION ---------------- */
let auRole = "bowl";
function viewAuction() {
  const a = D.auction, p = a.purse, isB = auRole === "bowl";
  const board = a.board[auRole], spentPct = Math.min(100, 100 * p.spent / p.total);
  app.innerHTML = `
    <div class="head"><div class="ttl"><span class="eyebrow">Mini-auction · ${a.auction.date} · ${esc(a.auction.venue)}</span><h1>What Rajasthan should do</h1></div></div>
    <section>
      <p class="sub">RR go to Goa with ${cr(p.left)} and ${p.slots} slots. These are the gaps the data says they still have, and the released players who best fill them.</p>
    </section>

    <section class="sec-pad grid4">
      ${tile(cr(p.left), "Purse remaining", `${cr(p.spent)} of ${cr(p.total)} committed`)}
      ${tile(`${p.kept}`, "Players retained", `${p.slots} slots to fill, max ${D.purse.squad_max}`)}
      ${tile(`${p.overseas_kept}/${D.purse.overseas_max}`, "Overseas kept", `${p.overseas_slots} overseas places open`)}
      ${tile(cr(p.slots ? p.left / p.slots : 0), "Average per slot", "if spread evenly")}
    </section>

    <section class="sec-pad card">
      <h3>Purse</h3>
      <div class="pbar" data-tip="${cr(p.spent)} committed to retentions · ${cr(p.left)} free"><i style="width:${spentPct}%;background:linear-gradient(90deg,#1B4DC8,var(--blue-2))"></i><i style="flex:1;background:linear-gradient(90deg,var(--pink),var(--pink-2))"></i></div>
      <div class="legend" style="margin:10px 0 0"><span><i style="background:var(--blue-2)"></i>Committed to the 19 retained</span><span><i style="background:var(--pink)"></i>Free for the auction</span></div>
      <p class="note" style="margin:10px 0 0">${esc(D.purse.purse_note)}</p>
    </section>

    <section class="sec-pad">
      <h2 class="sec">The three gaps</h2>
      <div class="grid3" style="margin-top:16px">${a.needs.map((n, i) => `<div class="card">
        <div style="font-family:var(--mono);color:var(--pink-2);font-size:11px;letter-spacing:.2em">GAP 0${i + 1}</div>
        <h4 style="font-size:16px;margin:9px 0 8px">${esc(n.need)}</h4><p class="note" style="margin:0">${esc(n.evidence)}</p></div>`).join("")}</div>
    </section>

    <section class="sec-pad">
      <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:16px">
        <div><h2 class="sec">The target board</h2>
          <p class="note">${a.pool_size} players were released league-wide; ${a.pool_rated} have enough pressure balls for us to rate. Ranked by how they perform when it matters.</p></div>
        <span id="macslot"></span>
      </div>
      <div class="card">${board.map((t) => `
        <div class="target">
          <div class="ph">${img(t.photo)}</div>
          <div><b>${esc(t.name)}</b><div class="sub2">released by ${esc(t.released_by)} · ${f0(t.n_p)} pressure balls
            · ${isB ? `econ ${f2(t.econ_p)} under pressure v ${f2(t.econ_o)} otherwise` : `SR ${f0(t.sr_p)} under pressure v ${f0(t.sr_o)} otherwise`}</div></div>
          <div class="mt"><b class="num">${ord(t.pct)}</b><span>percentile</span></div>
        </div>`).join("")}
        <p class="note" style="margin-top:12px">Percentile is among all ranked ${isB ? "bowlers" : "batters"} on pressure balls. Players with fewer than 100 pressure balls are left out: there is not enough evidence to judge them.</p>
      </div>
    </section>

    <section class="sec-pad grid2">
      <div class="card"><h3>The plan</h3><ul class="why">
        <li><b>Spend the bulk on one death bowler.</b> RR kept Archer and Shami but neither is cheap under pressure, and the gap costs them most in the last four overs. ${esc(board[0]?.name || "")} is the best-rated bowler on the board.</li>
        <li><b>Take the middle-order hitter second.</b> Jurel and Parag both drop sharply when the game tightens; a batter who holds his strike rate under pressure is the single biggest upgrade to the XI.</li>
        <li><b>Keep one overseas slot back.</b> With ${p.overseas_slots} open and only ${p.overseas_kept} overseas players retained, RR have room to take a punt late rather than bid early.</li>
        <li><b>Do not re-buy at the old price.</b> Hetmyer rates ${ord(a.board.bat.find((x) => x.name === "Shimron Hetmyer")?.pct || 74)} percentile under pressure and is worth a bid — but nothing like the ₹11 crore RR were paying.</li>
      </ul></div>
      <div class="card"><h3>What other squads teach</h3>
        ${D.lessons.map((l) => { const s = src(l.source); return `<div style="padding:9px 0;border-bottom:1px solid rgba(255,255,255,.055)">
          <b style="font-size:13.5px">${esc(l.title)}</b><p class="note" style="margin:5px 0 0">${esc(l.text)}</p>
          ${s ? `<a class="note" href="${s.url}" target="_blank" rel="noopener" style="color:var(--pink-2);text-decoration:underline">source</a>` : ""}</div>`; }).join("")}</div>
    </section>`;
  mount("#macslot", mac([{ v: "bowl", l: "Bowlers" }, { v: "bat", l: "Batters" }], auRole, (v) => { auRole = v; viewAuction(); }));
}

/* ---------------- 04 · METHOD ---------------- */
let chaseSel = 0;

/** Animated win-probability line for one real chase, with the pressure balls shaded. */
function chaseChart(c) {
  const W = 1000, H = 230, PAD = 26;
  const n = c.balls.length;
  const x = (i) => PAD + (W - 2 * PAD) * (i / Math.max(n - 1, 1));
  const y = (wp) => PAD + (H - 2 * PAD) * (1 - wp);
  const pts = c.balls.map((d, i) => `${x(i).toFixed(1)},${y(d.wp).toFixed(1)}`);
  const line = "M" + pts.join("L");
  const area = line + `L${x(n - 1).toFixed(1)},${y(0)}L${x(0).toFixed(1)},${y(0)}Z`;
  // shade the stretches where the ball was a pressure ball
  const thr = D.pressure_def.q80;
  const bands = [];
  let st = null;
  c.balls.forEach((d, i) => {
    if (d.li >= thr && st === null) st = i;
    if ((d.li < thr || i === n - 1) && st !== null) { bands.push([st, i]); st = null; }
  });
  const pi = c.balls.findIndex((d) => d.b === c.peak.b);
  const px = x(pi < 0 ? n - 1 : pi), py = y(c.balls[pi < 0 ? n - 1 : pi].wp);
  const flip = px > W * 0.62;
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img"
      aria-label="Win probability through ${esc(c.label)}">
    <defs><linearGradient id="wpg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#FF1E7A" stop-opacity=".34"/><stop offset="100%" stop-color="#FF1E7A" stop-opacity="0"/>
    </linearGradient></defs>
    ${bands.map(([i, j]) => `<rect class="hi" x="${x(i).toFixed(1)}" y="${PAD}" width="${Math.max(2, x(j) - x(i)).toFixed(1)}" height="${H - 2 * PAD}"/>`).join("")}
    <line class="mid" x1="${PAD}" y1="${y(0.5)}" x2="${W - PAD}" y2="${y(0.5)}"/>
    <text class="lbl" x="${PAD}" y="${y(1) - 7}">CERTAIN WIN</text>
    <text class="lbl" x="${PAD}" y="${y(0) + 14}">CERTAIN LOSS</text>
    <path class="area" d="${area}"/>
    <path class="ln" d="${line}" style="--len:${Math.round(n * 12)}"/>
    <g class="pk" style="transform-origin:${px.toFixed(1)}px ${py.toFixed(1)}px">
      <circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="6" fill="#fff"/>
      <circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="12" fill="none" stroke="#FF1E7A" stroke-width="2"/>
      <text class="note" x="${(flip ? px - 16 : px + 16).toFixed(1)}" y="${(py - 16).toFixed(1)}" text-anchor="${flip ? "end" : "start"}">
        ${c.peak.need} needed off ${c.peak.left}</text>
      <text class="lbl" x="${(flip ? px - 16 : px + 16).toFixed(1)}" y="${(py - 3).toFixed(1)}" text-anchor="${flip ? "end" : "start"}">
        LEVERAGE ${c.peak.li}x</text>
    </g>
  </svg></div>`;
}

function viewPressure() {
  const pd = D.pressure_def, vb = D.validation.batters, vw = D.validation.bowlers, hb = D.hp.bat, hw = D.hp.bowl;
  const ver = D.verification, w = D.weights, c = D.chases[chaseSel] || D.chases[0];
  const P = pd.pressure_vs_ordinary.pressure, O = pd.pressure_vs_ordinary.ordinary;
  const sensT = (rows) => `<div class="scroll"><table><tr><th>Change to the method</th><th class="r">Players</th><th class="r">Rank corr.</th><th class="r">Top 10 kept</th></tr>
    ${rows.map((r) => `<tr><td>${esc(r.variant)}</td><td class="r num">${r.players_compared}</td><td class="r num">${f2(r.spearman_vs_primary)}</td><td class="r num">${r.primary_top10_in_variant_top10}/10</td></tr>`).join("")}</table></div>`;
  // the leverage dial: a few real situations, scaled by how much rides on the ball
  const dial = [["0.2x", "Over 3, batting first, 24 for 0", 0.2], ["0.6x", "Over 11, cruising at 95 for 2", 0.6],
  ["1.0x", "An average ball", 1.0], ["2.4x", "Chasing, 46 needed off 30", 2.4],
  ["5x", "Chasing, 12 needed off 6", 5], ["14x", "4 needed off the last ball", 14]];
  const dmax = 14;

  app.innerHTML = `
    <div class="head"><div class="ttl"><span class="eyebrow">The idea, in plain language</span><h1>What is pressure</h1></div></div>

    <section class="grid2" style="align-items:center;gap:26px">
      <div>
        <p class="lede">Every ball in a T20 counts the same on the scorecard. <em>Almost none of them count the same to the result.</em></p>
        <p class="sub" style="margin-top:14px">A single off the third ball of an innings barely moves anything. The same
        single with 4 needed off 2 decides the match. So before we can ask who performs under pressure, we have to measure
        how much is actually riding on each delivery — and we can, because we can estimate who is winning before and after it.</p>
      </div>
      <div class="vs">
        <div class="side"><div class="k">Ball 15 of the innings</div>
          <div class="sit">32 for 1, batting first, nothing decided yet.</div>
          <div class="big num">0.4x</div><div class="k">Leverage</div>
          <div class="swing"><i style="width:4%;animation-delay:.1s"></i></div>
          <div class="note" style="margin-top:7px">A dot here changes the odds by well under a percent.</div></div>
        <div class="mid">VS</div>
        <div class="side hot"><div class="k">Last over of a chase</div>
          <div class="sit">9 needed off 4, two wickets left.</div>
          <div class="big num">6.1x</div><div class="k">Leverage</div>
          <div class="swing"><i style="width:62%;animation-delay:.25s"></i></div>
          <div class="note" style="margin-top:7px">A dot here can swing the match by twenty points or more.</div></div>
      </div>
    </section>

    <section class="sec-pad">
      <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:12px">
        <div><h2 class="sec">Watch it happen in a real chase</h2>
          <p class="note">The line is the batting side's chance of winning, ball by ball. The pink bands are the balls we call pressure.</p></div>
      </div>
      <div class="chase-pick">${D.chases.map((ch, i) => `<button class="${i === chaseSel ? "on" : ""}" data-i="${i}">${esc(ch.label)}</button>`).join("")}</div>
      <div class="card">${chaseChart(c)}
        <p class="note" style="margin-top:10px">Flat stretches are balls that barely matter. The steep parts, and the
        moment ringed above — the single ball with the most riding on it, ${c.peak.li}x an ordinary delivery — is where the match
        was actually decided. That is exactly what the Leverage Index picks out.</p></div>
    </section>

    <section class="sec-pad grid2" style="gap:22px">
      <div class="card"><h3>What one "leverage" number means</h3>
        <p class="note" style="margin:0 0 6px">1.0 is an ordinary ball. Higher means more of the result rides on it.</p>
        <div class="dial">${dial.map(([lab, sit, v], i) => `<div class="b ${v >= 1.5 ? "hot" : ""}" data-tip="${esc(sit)}">
          <span>${lab}</span><i style="height:${Math.max(6, 100 * Math.sqrt(v / dmax)).toFixed(0)}%;animation-delay:${0.08 * i}s"></i></div>`).join("")}</div>
        <p class="note" style="margin-top:10px">We draw the line at the busiest 20% of balls — anything at
        <b>${f2(pd.q80)}x or above</b>. That is ${f0(P.balls)} deliveries out of the ${f0(P.balls + O.balls)} in the data.</p></div>
      <div class="card"><h3>Those balls really are harder</h3>
        ${pairBars([
    { label: "Strike rate", hint: "runs per 100 balls", p: P.strike_rate, o: O.strike_rate, fmt: f0 },
    { label: "Dot balls", hint: "% of deliveries", p: P.dot_pct, o: O.dot_pct, fmt: f1 },
    { label: "Boundaries", hint: "% of deliveries", p: P.boundary_pct, o: O.boundary_pct, fmt: f1 },
    { label: "Win % moved", hint: "per ball", p: P.mean_abs_wpa_pct, o: O.mean_abs_wpa_pct, fmt: f1 },
  ])}
        <p class="note" style="margin-top:4px">Scoring falls and dots rise, while each ball moves the result about three
        times as much. Batters are not simply swinging harder — it genuinely gets tougher.</p></div>
    </section>

    <section class="sec-pad">
      <h2 class="sec">So how do we rate a player?</h2>
      <div class="grid2" style="margin-top:16px;gap:22px">
        <div class="card">
          ${[["1", "Find the pressure balls", "Score every delivery for how much the result can swing on it. Keep the busiest fifth."],
      ["2", "Compare him with the average", "On each of those balls, what would a typical player have done here — same score, same overs left, same wickets down, even how set the batter is? The difference is his credit."],
      ["3", "Credit the opponent", "Runs off Bumrah count for more than runs off a part-timer, so each ball is adjusted for who he faced."],
      ["4", "Be honest about luck", "A good night is not a skill. Every player is pulled toward the average by how little we have seen of him, then his matches are reshuffled a thousand times to check he stays there."]]
      .map(([n, t, d]) => `<div class="step"><div class="no">${n}</div><div><h4>${t}</h4><p class="note" style="margin:0">${d}</p></div></div>`).join("")}
        </div>
        <div>
          <div class="card"><h3>Two things come out</h3>
            <p style="margin:0 0 10px"><b style="color:var(--pink-2)">Level</b> — how good he is when it matters.
            <b style="color:var(--blue-2);margin-left:8px">Lift</b> — whether that is better or worse than his own everyday standard.</p>
            <p class="note" style="margin:0">A player can rate highly two ways: by being brilliant everywhere and not
            flinching, or by being ordinary most of the time and finding something extra. Both show up, and we report them separately.</p></div>
          <div class="card" style="margin-top:14px"><h3>The honest headline</h3>
            <p style="margin:0">Being good under pressure is mostly just being good.</p>
            <p class="note" style="margin:9px 0 0">Rank players only on their pressure balls and the list falls apart the
            moment you split the data in half (reliability ${f2(vb.split_half.raw_level.full_sample_reliability)} for batters).
            There is a real pressure effect, but it is small next to plain ability — so our top tens are led by excellent
            players who do not shrink, not by modest players with a couple of famous nights.</p></div>
        </div>
      </div>
    </section>

    <section class="sec-pad">
      <h2 class="sec">Where pressure actually turns up</h2>
      <p class="note">Most people picture the death overs. The data says three in four pressure balls come in a chase —
      and the single biggest cluster is the powerplay of a chase, where early wickets quietly settle games nobody remembers as tense.</p>
      <div class="card" style="margin-top:14px"><div class="scroll"><table>
        <tr><th>Innings</th><th>Phase</th><th class="r">Average leverage</th><th class="r">Balls that are pressure</th><th class="r">Share of all pressure</th></tr>
        ${D.composition.map((r) => `<tr><td>${r.innings === 1 ? "Batting first" : "Chasing"}</td><td>${r.phase}</td>
          <td class="r num">${f2(r.mean_li)}</td><td class="r num">${pc(r.share_pressure)}</td><td class="r num">${pc(r.share_of_all_pressure)}</td></tr>`).join("")}
      </table></div></div>
    </section>

    <hr style="border:0;border-top:1px solid var(--line);margin:clamp(40px,6vw,70px) 0 0">
    <section class="sec-pad">
      <div class="eyebrow">For the sceptical reader</div>
      <h2 class="sec" style="margin-top:6px">The maths, and the tests</h2>
      <p class="sub">Everything above rests on models that can be wrong, so each one has a check that can fail.</p>
    </section>

    <section class="card">
      <h3>Verification: ${ver.passed} of ${ver.total} checks pass</h3>
      <div class="scroll"><table><tr><th>Check</th><th>Result</th></tr>
      ${ver.checks.map((ck) => `<tr><td style="white-space:nowrap"><span class="${ck.pass ? "pass" : "fail"}">${ck.pass ? "PASS" : "FAIL"}</span> &nbsp;${esc(ck.check)}</td><td class="note">${esc(ck.detail)}</td></tr>`).join("")}
      </table></div>
      <p class="note" style="margin-top:12px">Checks 8 and 9 invent players whose true ability is known by construction,
      simulate their deliveries, and ask whether the rating recovers it. That is the part most ratings never test.</p>
    </section>

    <section class="sec-pad grid2">
      <div class="card prose"><h3>The win-probability model</h3>
        <p>Gradient boosting over the match state, era, venue and both teams' Elo, trained on 9,606 T20 matches. The last
        four overs of a chase blend into a separate endgame model forced to respect common sense: fewer runs needed, more
        balls or more wickets can never hurt. Raw output was over-confident, so a monotone calibration map is fitted on
        Cricsheet matches that are <em>not</em> twins of the supplied ones.</p>
        <p class="note">AUC ${f2(D.ctx.wp_v2_context.auc)}, Brier ${f2(D.ctx.wp_v2_context.brier)} on 2024–26 matches never seen in
        training; calibration improved Brier from ${f2(D.ctx.calibration.brier_before)} to ${f2(D.ctx.calibration.brier_after)}.</p>
        <p>Leverage is then the expected absolute swing in that probability across the ball's six outcomes, divided by the
        average swing, so 1.0 is an average ball by construction.</p></div>
      <div class="card prose"><h3>Level, Lift and the weights</h3>
        <p>One hierarchical model shrinks both quantities for sample size, estimating the noise from match-to-match
        variation so balls in the same match are not counted as independent.</p>
        <p>The weights are not hand-picked. We sweep them and measure how well each mix predicts pressure performance in
        matches the estimate never saw. The curve is flat near its peak, so a band is indistinguishable from the optimum;
        within it we take the mix leaning most on Lift, because the brief asks for performance compared with usual levels.</p>
        <div class="scroll"><table><tr><th>Role</th><th class="r">Optimum</th><th class="r">Band</th><th class="r">Chosen</th></tr>
          ${["batters", "bowlers"].map((r) => { const x2 = w[r].weights, k = r === "batters" ? "bat" : "bowl";
    return `<tr><td>${r}</td><td class="r num">${f2(x2.best_w_level)}</td><td class="r num">${f2(Math.min(...x2.indistinguishable_from_best))}–${f2(Math.max(...x2.indistinguishable_from_best))}</td><td class="r num">${f2(D.params.weights[k].level)} / ${f2(D.params.weights[k].lift)}</td></tr>`; }).join("")}
        </table></div></div>
    </section>

    <section class="sec-pad grid2">
      <div class="card"><h3>Is "consistency" a real trait?</h3>
        <p class="note" style="margin-top:0">The brief asks for players who deliver <em>most consistently</em>, so we tested
        whether players genuinely differ in match-to-match volatility rather than assuming it.</p>
        <div class="scroll"><table><tr><th>Test</th><th class="r">Batters</th><th class="r">Bowlers</th></tr>
          <tr><td>Bartlett test for unequal volatility (p)</td><td class="r num">${f2(w.batters.consistency.p_value)}</td><td class="r num">${f2(w.bowlers.consistency.p_value)}</td></tr>
          <tr><td>Excess variance beyond noise</td><td class="r num">${f2(w.batters.consistency.excess_variance_tau2)}</td><td class="r num">${f2(w.bowlers.consistency.excess_variance_tau2)}</td></tr>
          <tr><td>Does volatility repeat? (split-half)</td><td class="r num">${f2(w.batters.consistency.split_half_persistence_of_volatility)}</td><td class="r num">${f2(w.bowlers.consistency.split_half_persistence_of_volatility)}</td></tr>
        </table></div>
        <p class="note" style="margin-top:10px">A weak, same-signed hint in both roles, but not significant at 5% and barely
        repeatable. So consistency is not rated as a separate skill; it enters through the match bootstrap instead.</p></div>
      <div class="card"><h3>Reliability</h3><div class="scroll"><table>
        <tr><th>Measure</th><th class="r">Batters</th><th class="r">Bowlers</th></tr>
        <tr><td>Split-half reliability of the rating</td><td class="r num">${f2(vb.split_half.composite.full_sample_reliability)}</td><td class="r num">${f2(vw.split_half.composite.full_sample_reliability)}</td></tr>
        <tr><td>…of raw pressure averages</td><td class="r num">${f2(vb.split_half.raw_level.full_sample_reliability)}</td><td class="r num">${f2(vw.split_half.raw_level.full_sample_reliability)}</td></tr>
        <tr><td>Predicts held-out pressure results (ours)</td><td class="r num">${f2(vb.holdout_prediction["joint_shrunk_level (ours)"])}</td><td class="r num">${f2(vw.holdout_prediction["joint_shrunk_level (ours)"])}</td></tr>
        <tr><td>…using raw pressure averages</td><td class="r num">${f2(vb.holdout_prediction.raw_pressure_average)}</td><td class="r num">${f2(vw.holdout_prediction.raw_pressure_average)}</td></tr>
        <tr><td>…using only his pressure balls</td><td class="r num">${f2(vb.holdout_prediction.pressure_only_shrunk)}</td><td class="r num">${f2(vw.holdout_prediction.pressure_only_shrunk)}</td></tr>
        <tr><td>2022–24 predicting 2025–26</td><td class="r num">${f2(vb.persistence.predict_later_pressure_level["joint_shrunk_level (ours)"])}</td><td class="r num">${f2(vw.persistence.predict_later_pressure_level["joint_shrunk_level (ours)"])}</td></tr>
      </table></div></div>
    </section>

    <section class="sec-pad grid2">
      <div class="card"><h3>Does the order survive a different method? Batters</h3>${sensT(D.sensitivity.batters)}</div>
      <div class="card"><h3>Bowlers</h3>${sensT(D.sensitivity.bowlers)}</div>
    </section>

    <section class="sec-pad card prose"><h3>What the rating cannot tell you</h3><ul>
      <li><b>It describes 2022–26; it is not a forecast.</b> Bowlers' pressure form carries into later seasons
        (${f2(vw.persistence.predict_later_pressure_level["joint_shrunk_level (ours)"])}); batters' barely does
        (${f2(vb.persistence.predict_later_pressure_level["joint_shrunk_level (ours)"])}).</li>
      <li><b>Extremes are slightly overstated.</b> The simulation shows the rating spreads a little wider than true talent
        at this pool size (slope 0.80–0.85 rather than 1.00).</li>
      <li><b>Places 6–10 are close calls</b> — the 90% ranges overlap heavily below the top three.</li>
      <li><b>Not measured:</b> fielding, wicketkeeping, captaincy, the pitch on the day, the partner at the other end, intent.</li></ul></section>

    <section class="sec-pad card"><h3>Sources</h3>
      ${[["official", "Official"], ["major", "Established outlets, data and published research"], ["aggregator", "Rumour and prediction sites — used only as flagged rumour"]].map(([t, l]) => {
    const items = D.sources.filter((x2) => x2.tier === t); if (!items.length) return "";
    return `<p style="font-weight:700;margin:12px 0 6px">${l}</p><ul class="src" style="margin:0;padding-left:18px">
        ${items.map((x2) => `<li><a href="${x2.url}" target="_blank" rel="noopener">${esc(x2.title)}</a><div class="note">${esc(x2.note)}</div></li>`).join("")}</ul>`; }).join("")}
    </section>`;

  app.querySelectorAll(".chase-pick button").forEach((btn) => btn.onclick = () => { chaseSel = +btn.dataset.i; viewPressure(); });
}

/* ---------------- router ---------------- */
function route() {
  const [, r, id] = (location.hash || "#/top10").split("/");
  document.querySelectorAll("#railnav a").forEach((a) => a.classList.toggle("on", a.dataset.r === r));
  try {
    ({ top10: viewTop10, royals: () => (id ? viewPlayer(id) : viewRoyals()), auction: viewAuction, pressure: viewPressure }[r] || viewTop10)();
  } catch (e) {
    app.innerHTML = `<section class="sec-pad card"><h3>Something broke rendering this page</h3><p class="note">${esc(e.message)}</p></section>`;
    console.error(e);
  }
  scrollTo(0, 0);
}
addEventListener("hashchange", route);
addEventListener("keydown", (e) => {
  if (!(location.hash || "#/top10").startsWith("#/top10")) return;
  if (e.target.closest("input,textarea")) return;
  if (e.key === "ArrowLeft") { e.preventDefault(); lbStep(-1); }
  if (e.key === "ArrowRight") { e.preventDefault(); lbStep(1); }
});
route();
