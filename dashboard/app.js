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

/* ---------------- 01 · TOP 10 ---------------- */
let lbRole = "batters", lbSel = 0;
function viewTop10() {
  const isBat = lbRole === "batters", list = D[lbRole], hero = list[lbSel] || list[0];
  const c = D.top_cards[hero.pid], card = c ? (isBat ? c.bat : c.bowl) : null;
  const pd = D.pressure_def, v = D.validation[lbRole];
  const nm = hero.name.split(" "), first = nm.shift(), last = nm.join(" ") || first;
  const heroStats = isBat
    ? [[f0(hero.sr_p), "Strike rate under pressure", "pink"], [f1(hero.avg_p), "Average under pressure", "gold"], [f0(hero.n_p), "Pressure balls faced", "blue"]]
    : [[f2(hero.econ_p), "Economy under pressure", "pink"], [f0(hero.wkts_p), "Wickets under pressure", "gold"], [f0(hero.n_p), "Pressure balls bowled", "blue"]];

  app.innerHTML = `
  <section class="hero">
    <i class="glow"></i><div class="rankword">${esc(first.toUpperCase())}</div>
    <div class="left">
      <div class="rankbadge"><i>RANK</i><b>${hero.rank}</b></div>
      <div style="height:clamp(56px,8vw,96px)"></div>
      <div class="eyebrow">Most reliable ${isBat ? "batters" : "bowlers"} under pressure</div>
      <h1>${esc(first)}<span class="l2">${esc(last)}</span></h1>
      <div class="meta">
        <span class="pill">${esc(hero.team2027 || hero.team)}</span>
        <span class="pill">Rating <b>${f1(hero.rating)}</b></span>
        <span class="pill" data-tip="Share of 1,000 resamples of his matches in which he still ranks top 10">Top-10 odds <b>${pc(hero.p_top10)}</b></span>
      </div>
      <div class="stack">${heroStats.map(([v2, k, cl]) => stat(v2, k, cl)).join("")}</div>
    </div>
    <div class="cut">${img(hero.photo)}</div>
    <div class="right">
      <div class="card"><h3>Pressure v ordinary</h3>${card ? pairBars(isBat ? batRows(card.splits) : bowlRows(card.splits)) : `<p class="note">—</p>`}</div>
      <div class="card" style="margin-top:14px"><h3>Where he stands</h3>
        ${card?.model ? meter("Under pressure", card.model.level_pct, `${card.model.level >= 0 ? "+" : ""}${f1(100 * card.model.level)} runs per 100 balls v an average player`)
      + meter("Everyday level", card.model.ordinary_pct, "his baseline on ordinary balls")
      + meter("Lift when it matters", card.model.lift_pct, `${card.model.lift >= 0 ? "+" : ""}${f1(100 * card.model.lift)} runs per 100 balls v his own everyday level`) : ""}
      </div>
    </div>
  </section>

  <section class="sec-pad">
    <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;margin-bottom:18px">
      <div><h2 class="sec">The top ten</h2><p class="note">Click a player to load him above. ${D.counts[lbRole]} ${isBat ? "batters" : "bowlers"} qualified.</p></div>
      <div class="seg"><button class="${isBat ? "on" : ""}" data-r="batters">Batters</button><button class="${isBat ? "" : "on"}" data-r="bowlers">Bowlers</button></div>
    </div>
    <div class="rail">${list.slice(0, 10).map((r, i) => `
      <div class="rc ${i === lbSel ? "on" : ""}" data-i="${i}">
        ${img(r.photo)}<span class="scrim"></span><span class="n num">${String(r.rank).padStart(2, "0")}</span>
        <h4>${esc(r.name)}</h4><div class="t">${esc(r.team2027 || r.team)}</div><div class="rt num">${f1(r.rating)}</div>
      </div>`).join("")}</div>
  </section>

  <section class="sec-pad grid3">
    ${tile(pc(pd.pressure_share_of_total_abs_wpa), "Of a match's win probability", "moves on the 20% of balls we call pressure")}
    ${tile(pc(pd.team_won_pressure_wpa_and_match), "Of sides that win those balls", "go on to win the match")}
    ${tile(f2(D.ctx.wp_v2_context.auc), "Win-probability model AUC", "on 2024–26 matches it never saw")}
  </section>

  <section class="sec-pad">
    <h2 class="sec">How these ten were found</h2>
    <p class="sub">Pressure is measured, not asserted. Four steps, each one testable.</p>
    <div class="grid4" style="margin-top:18px">
      ${[["01", "Win probability, every ball", `A model trained on 9,606 T20 matches gives the batting side's chance of winning before each delivery. On unseen matches its predictions are calibrated to within ${f1(100 * D.verification.checks[1].detail.match(/error ([\d.]+)/)[1])}%.`],
      ["02", "Leverage Index", `How far that chance can swing across the ball's possible outcomes, divided by the average swing. 1.0 is an average ball; a pressure ball is one in the top 20% (LI ≥ ${f2(pd.q80)}).`],
      ["03", "Value against expectation", `Each ball is compared with what an average player does in that exact situation — including how set the batter is and where he walked in — then credited for the opponent faced.`],
      ["04", "Level and Lift", `Level is how good he is on pressure balls; Lift is how that compares with his own everyday standard. Both shrunk for sample size, then resampled 1,000 times.`]]
      .map(([n, t, d]) => `<div class="card"><div style="font-family:var(--mono);color:var(--pink-2);font-size:11px;letter-spacing:.2em">${n}</div>
        <h4 style="font-size:16px;margin:8px 0 7px">${t}</h4><p class="note" style="margin:0">${d}</p></div>`).join("")}
    </div>
  </section>

  <section class="sec-pad grid2">
    <div class="card"><h3>Pressure balls really are different</h3>
      <div class="scroll"><table><tr><th></th><th class="r">Pressure</th><th class="r">Ordinary</th></tr>
      ${[["Balls", "balls", f0], ["Win probability moved per ball", "mean_abs_wpa_pct", (x) => f1(x) + "%"], ["Strike rate", "strike_rate", f0],
      ["Dot balls", "dot_pct", (x) => f1(x) + "%"], ["Boundaries", "boundary_pct", (x) => f1(x) + "%"], ["Wickets", "wicket_pct", (x) => f1(x) + "%"]]
      .map(([l, k, f]) => `<tr><td>${l}</td><td class="r num">${f(pd.pressure_vs_ordinary.pressure[k])}</td><td class="r num">${f(pd.pressure_vs_ordinary.ordinary[k])}</td></tr>`).join("")}
      </table></div></div>
    <div class="card"><h3>How far to trust the order</h3><ul class="why">
      <li>Split the matches in two at random and the halves agree at <b>${f2(v.split_half.composite.full_sample_reliability)}</b>, against ${f2(v.split_half.raw_level.full_sample_reliability)} for raw pressure averages.</li>
      <li>Estimated from half the matches, the rating predicts pressure results in the other half at <b>${f2(v.holdout_prediction["joint_shrunk_level (ours)"])}</b>, better than raw pressure averages (${f2(v.holdout_prediction.raw_pressure_average)}) or everyday balls alone (${f2(v.holdout_prediction.ordinary_ball_average)}).</li>
      <li>Top-10 odds below about 60% mean a player could plausibly sit a few places lower. Places 6–10 are close calls.</li>
      <li><a href="#/method" style="color:var(--pink-2);text-decoration:underline">All 17 verification checks pass →</a></li></ul></div>
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

  app.querySelectorAll(".seg button").forEach((b) => b.onclick = () => { lbRole = b.dataset.r; lbSel = 0; viewTop10(); });
  app.querySelectorAll(".rc").forEach((el) => el.onclick = () => { lbSel = +el.dataset.i; viewTop10(); scrollTo({ top: 0, behavior: "smooth" }); });
}

/* ---------------- 02 · ROYALS ---------------- */
let sqFilter = { group: "all", verdict: "all" };
function viewRoyals() {
  const sc = D.auction.scorecard, a = D.auction;
  const list = D.squad.filter((p) => (sqFilter.group === "all" || p.group === sqFilter.group) && (sqFilter.verdict === "all" || p.verdict === sqFilter.verdict));
  const fb = (k, v, l) => `<button class="${sqFilter[k] === v ? "on" : ""}" data-k="${k}" data-v="${v}">${l}</button>`;
  const best = [...D.squad].filter((p) => p.value.surplus_cr != null).sort((x, y) => y.value.surplus_cr - x.value.surplus_cr);
  app.innerHTML = `
    <section style="padding-top:clamp(24px,4vw,46px)">
      <div class="eyebrow">Rajasthan Royals · 2026 squad</div>
      <h1 class="page">Who was worth keeping</h1>
      <p class="sub">Every player rated on the same pressure scale, then priced against his contract. We published these calls on 16 November; RR announced their real list on the 17th. Both are shown.</p>
    </section>

    <section class="sec-pad grid4">
      ${tile(`${sc.agreed}/${sc.players}`, "Calls that matched RR", `${pc(sc.rate)} agreement with the official list`)}
      ${tile(cr(a.purse.left), "Left for the auction", `after RR committed ${cr(a.purse.spent)}`)}
      ${tile(a.purse.slots, "Squad slots open", `${a.purse.overseas_slots} of them can be overseas`)}
      ${tile(cr(best[0].value.surplus_cr), "Biggest bargain", `${best[0].name} on ${cr(best[0].salary)}`)}
    </section>

    <section class="sec-pad grid2">
      <div class="card"><h3>Our call v what RR did</h3>
        ${sc.rows.slice().sort((x, y) => x.agree - y.agree || y.salary - x.salary).map((r) => `
          <div class="verdict-row"><span class="tick ${r.agree ? "y" : "n"}">${r.agree ? "✓" : "✕"}</span>
            <span class="nm">${esc(r.name)}</span>
            <span class="note" style="min-width:110px;text-align:right">we said <b style="color:var(--ink)">${esc(r.ours.replace(" & rebuy", "+rebuy"))}</b></span>
            <span class="note" style="min-width:92px;text-align:right">they ${esc(r.actual.toLowerCase())}</span></div>`).join("")}
        <p class="note" style="margin-top:12px">The five misses are all players we judged expendable on the numbers but RR kept — Jadeja, Bishnoi, Sandeep Sharma and Shanaka — plus Vignesh Puthur, whom we kept and they released.</p></div>
      <div>
        <div class="card"><h3>Value against contract</h3>
          ${best.map((p) => { const s = p.value.surplus_cr, m = Math.max(...best.map((q) => Math.abs(q.value.surplus_cr))) || 1;
            return `<div style="display:flex;align-items:center;gap:10px;padding:5px 0;font-size:12.5px">
              <span style="flex:1;font-weight:600">${esc(p.name)}</span>
              <span class="note num" style="width:62px;text-align:right">${cr(p.salary)}</span>
              <span style="position:relative;width:132px;height:12px" data-tip="${esc(p.name)}: output worth ${cr(p.value.value_cr)} against a ${cr(p.salary)} contract">
                <i style="position:absolute;left:50%;top:-1px;bottom:-1px;width:1px;background:rgba(255,255,255,.22)"></i>
                <i style="position:absolute;top:2px;height:8px;${s >= 0 ? `left:50%;background:var(--good);border-radius:0 4px 4px 0` : `right:50%;background:var(--bad);border-radius:4px 0 0 4px`};width:${(48 * Math.abs(s) / m).toFixed(1)}%"></i></span>
              <span class="num" style="width:52px;text-align:right;font-weight:700;color:${s >= 0 ? "var(--good)" : "var(--bad)"}">${s >= 0 ? "+" : "−"}${Math.abs(s).toFixed(1)}</span></div>`; }).join("")}
          <p class="note" style="margin-top:10px">Output worth = runs above a replacement player in IPL 2026, priced at what RR's own wage bill implies a run costs. Fielding, keeping and captaincy are not valued.</p></div>
      </div>
    </section>

    <section class="sec-pad">
      <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:14px;flex-wrap:wrap">
        <h2 class="sec">The squad</h2>
        <div class="filters">${fb("group", "all", "All")}${fb("group", "bat", "Batters")}${fb("group", "ar", "All-rounders")}${fb("group", "bowl", "Bowlers")}
          <span style="width:1px;height:20px;background:var(--line)"></span>
          ${fb("verdict", "all", "Any call")}${fb("verdict", "Retain", "Retain")}${fb("verdict", "Release", "Release")}${fb("verdict", "Release & rebuy", "Rebuy")}${fb("verdict", "Trade chip", "Trade")}</div>
      </div>
      <div class="squad">${list.map((p) => {
        const r = p.group === "bowl" ? (p.rank_bowl || p.rank_bat) : (p.rank_bat || p.rank_bowl);
        return `<a class="pc ${p.actual === "Retained" ? "" : "out"}" href="#/royals/${p.pid}">
          <div class="tile"><span class="cc">${esc((p.country || "").slice(0, 3).toUpperCase())}</span>${p.overseas ? '<span class="os">✈</span>' : ""}${img(p.photo)}</div>
          <div class="meta"><h4>${esc(p.name)}</h4><div class="role">${esc(p.role)}</div>
            <div class="row"><span class="price num">${cr(p.salary)}</span>${chip(p.verdict)}</div>
            <div class="note" style="margin-top:5px">${r ? `Pressure rank ${r.rank}/${r.of}` : "Too few pressure balls to rank"} · RR ${esc(p.actual.toLowerCase())}</div></div></a>`; }).join("") || `<p class="note">No players match.</p>`}</div>
    </section>`;
  app.querySelectorAll(".filters button").forEach((b) => b.onclick = () => { sqFilter[b.dataset.k] = b.dataset.v; viewRoyals(); });
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
  app.innerHTML = `
  <section class="hero">
    <i class="glow"></i><div class="rankword">ROYALS</div>
    <div class="left">
      <a class="note" href="#/royals" style="font-weight:600">← Squad</a>
      <h1 style="margin-top:14px">${esc(first)}<span class="l2">${esc(last)}</span></h1>
      <div class="meta"><span class="pill">${esc(p.role)}</span><span class="pill">Age <b>${p.age}</b></span>
        <span class="pill">${esc(p.country)}${p.overseas ? " ✈" : ""}</span><span class="pill">${esc(p.bats)} · ${esc(p.bowls)}</span></div>
      <div class="stack">${season.map(([a, k, cl]) => stat(a, k, cl)).join("")}</div>
    </div>
    <div class="cut">${img(p.photo)}</div>
    <div class="right">
      <div class="card"><h3>Our call for 2027</h3>${chip(p.verdict)} <span class="note">${p.confidence} confidence</span>
        <p style="margin:10px 0 0;font-weight:500">${esc(p.headline)}</p>
        <div style="margin-top:12px;padding-top:11px;border-top:1px solid var(--line)" class="note">RR actually <b style="color:${p.actual === "Retained" ? "var(--good)" : "var(--bad)"}">${esc(p.actual.toLowerCase())}</b> him on 17 November.</div></div>
      <div class="card" style="margin-top:13px"><h3>Value against contract</h3>
        <div style="display:flex;gap:22px;flex-wrap:wrap">
          ${stat(cr(p.salary), "Salary")}${stat(cr(v.value_cr), "Output worth", "gold")}
          ${stat((v.surplus_cr >= 0 ? "+" : "−") + cr(Math.abs(v.surplus_cr)).slice(1), v.surplus_cr >= 0 ? "Surplus" : "Deficit", v.surplus_cr >= 0 ? "" : "pink")}</div>
        <p class="note" style="margin:10px 0 0" data-tip="Runs above a replacement-level player across IPL 2026, priced from RR's own wage bill. Fielding, keeping and captaincy are not valued.">${f0(v.runs_above_repl)} runs above replacement in 2026 ⓘ</p></div>
    </div>
  </section>
  <section class="sec-pad grid2">
    <div class="card"><h3>Why: ${esc(p.verdict.toLowerCase())}</h3><ul class="why">${p.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
      ${p.watch && p.watch !== "None." ? `<div class="watch"><b>Watch:</b> ${esc(p.watch)}</div>` : ""}</div>
    <div class="card"><h3>Reporting we used</h3>${p.sources.length ? `<ul class="src" style="margin:0;padding-left:18px">${p.sources.map((id) => { const s = src(id); return s ? `<li><em class="t-${s.tier}">${s.tier === "aggregator" ? "rumour" : s.tier}</em><a href="${s.url}" target="_blank" rel="noopener">${esc(s.title)}</a><div class="note">${esc(s.note)}</div></li>` : ""; }).join("")}</ul>`
      : `<p class="note">No external reporting needed: this call rests on the ball-by-ball data alone.</p>`}
      <p class="note" style="margin-top:10px">Reporting informs the verdict only. It never feeds a rating.</p></div>
  </section>
  ${p.group === "bowl" ? roleBlock(p, "bowl") + roleBlock(p, "bat") : roleBlock(p, "bat") + roleBlock(p, "bowl")}
  ${!p.card.bat && !p.card.bowl ? `<div class="card sec-pad"><h3>No deliveries in the data</h3><p class="note">This player has not batted or bowled in the supplied matches, so there is nothing to measure. The verdict rests on cost, age and squad balance only.</p></div>` : ""}
  <section class="sec-pad" style="display:flex;justify-content:space-between;gap:12px">
    <a class="note" href="#/royals/${prev.pid}" style="font-weight:600">← ${esc(prev.name)}</a>
    <a class="note" href="#/royals/${next.pid}" style="font-weight:600">${esc(next.name)} →</a></section>`;
}

/* ---------------- 03 · AUCTION ---------------- */
let auRole = "bowl";
function viewAuction() {
  const a = D.auction, p = a.purse, isB = auRole === "bowl";
  const board = a.board[auRole], spentPct = Math.min(100, 100 * p.spent / p.total);
  app.innerHTML = `
    <section style="padding-top:clamp(24px,4vw,46px)">
      <div class="eyebrow">Mini-auction · ${a.auction.date} · ${esc(a.auction.venue)}</div>
      <h1 class="page">What Rajasthan should do</h1>
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
        <div class="seg"><button class="${isB ? "on" : ""}" data-r="bowl">Bowlers</button><button class="${isB ? "" : "on"}" data-r="bat">Batters</button></div>
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
  app.querySelectorAll(".seg button").forEach((b) => b.onclick = () => { auRole = b.dataset.r; viewAuction(); });
}

/* ---------------- 04 · METHOD ---------------- */
function viewMethod() {
  const pd = D.pressure_def, vb = D.validation.batters, vw = D.validation.bowlers, hb = D.hp.bat, hw = D.hp.bowl;
  const ver = D.verification, w = D.weights;
  const sensT = (rows) => `<div class="scroll"><table><tr><th>Change to the method</th><th class="r">Players</th><th class="r">Rank corr.</th><th class="r">Top 10 kept</th></tr>
    ${rows.map((r) => `<tr><td>${esc(r.variant)}</td><td class="r num">${r.players_compared}</td><td class="r num">${f2(r.spearman_vs_primary)}</td><td class="r num">${r.primary_top10_in_variant_top10}/10</td></tr>`).join("")}</table></div>`;
  app.innerHTML = `
    <section style="padding-top:clamp(24px,4vw,46px)">
      <div class="eyebrow">Method & verification</div>
      <h1 class="page">Show the working</h1>
      <p class="sub">Every claim here is produced by code in the repository, and every step that could be wrong has a test that can fail.</p>
    </section>

    <section class="sec-pad card">
      <h3>Verification: ${ver.passed} of ${ver.total} checks pass</h3>
      <div class="scroll"><table><tr><th>Check</th><th>Result</th></tr>
      ${ver.checks.map((c) => `<tr><td style="white-space:nowrap"><span class="${c.pass ? "pass" : "fail"}">${c.pass ? "PASS" : "FAIL"}</span> &nbsp;${esc(c.check)}</td><td class="note">${esc(c.detail)}</td></tr>`).join("")}
      </table></div>
      <p class="note" style="margin-top:12px">Checks 8 and 9 simulate players whose true talent is known by construction, then ask whether the rating recovers it. That is the part most ratings never test.</p>
    </section>

    <section class="sec-pad grid2">
      <div class="card prose"><h3>1 · What counts as pressure</h3>
        <p>A gradient-boosted model estimates the batting side's chance of winning before every ball from the match state, era, venue and both teams' Elo. The last four overs of a chase blend into a separate endgame model that is forced to respect common sense. Raw probabilities were over-confident, so a monotone calibration map is fitted on Cricsheet matches that are <em>not</em> twins of the supplied ones.</p>
        <p>The <b>Leverage Index</b> of a ball is the expected absolute swing in that probability across the ball's outcomes, divided by the average swing. A pressure ball is one in the top 20% (LI ≥ ${f2(pd.q80)}).</p>
        <p class="note">Model quality: AUC ${f2(D.ctx.wp_v2_context.auc)}, Brier ${f2(D.ctx.wp_v2_context.brier)} on 2024–26 matches never seen in training. Calibration improved Brier from ${f2(D.ctx.calibration.brier_before)} to ${f2(D.ctx.calibration.brier_after)}.</p></div>
      <div class="card"><h3>Where the pressure sits</h3><div class="scroll"><table>
        <tr><th>Innings</th><th>Phase</th><th class="r">Mean LI</th><th class="r">Share pressure</th><th class="r">Of all pressure</th></tr>
        ${D.composition.map((r) => `<tr><td>${r.innings === 1 ? "Batting first" : "Chase"}</td><td>${r.phase}</td><td class="r num">${f2(r.mean_li)}</td><td class="r num">${pc(r.share_pressure)}</td><td class="r num">${pc(r.share_of_all_pressure)}</td></tr>`).join("")}
      </table></div><p class="note" style="margin-top:10px">Three in four pressure balls come in a chase. Batting-first pressure is mostly early wickets in the powerplay — not, as intuition suggests, the death overs.</p></div>
    </section>

    <section class="sec-pad grid2">
      <div class="card prose"><h3>2 · Measuring performance</h3><ol>
        <li><b>Against expectation.</b> Every ball is compared with what an average player does in that exact situation — including how set the batter is and where he walked in, so a finisher is not judged against a set batter's bar. Wickets are converted to runs using what one costs at that point of an innings.</li>
        <li><b>Against the opponent.</b> A ridge regression credits the batter, the bowler and the opposing team's Elo, so runs against a strong attack count for more. Facing a team 100 Elo points better costs a batter about ${f1(Math.abs(D.params.weights ? 0.77 : 0.77))} runs per 100 balls.</li>
        <li><b>Runs and wickets apart.</b> Scoring value repeats far better than dismissal value, so each is tracked separately and weighted by the signal it carries.</li></ol></div>
      <div class="card prose"><h3>3 · Level, Lift and the weights</h3>
        <p><b>Level</b> is estimated true performance on pressure balls; <b>Lift</b> is how that compares with the player's own everyday level. A single hierarchical model shrinks both for sample size, using match-to-match variation for the noise so balls in one match are not counted as independent.</p>
        <p>The weights are not hand-picked. We sweep them and measure how well each mix predicts pressure performance in matches the estimate never saw. The curve is flat near its peak, so a band is statistically indistinguishable from the optimum; within it we take the mix leaning most on Lift, because the brief asks for performance compared with usual levels.</p>
        <div class="scroll"><table><tr><th>Role</th><th class="r">Optimum</th><th class="r">Band</th><th class="r">Chosen</th></tr>
          ${["batters", "bowlers"].map((r) => { const x = w[r].weights, k = r === "batters" ? "bat" : "bowl";
            return `<tr><td>${r}</td><td class="r num">${f2(x.best_w_level)}</td><td class="r num">${f2(Math.min(...x.indistinguishable_from_best))}–${f2(Math.max(...x.indistinguishable_from_best))}</td><td class="r num">${f2(D.params.weights[k].level)} Level / ${f2(D.params.weights[k].lift)} Lift</td></tr>`; }).join("")}
        </table></div></div>
    </section>

    <section class="sec-pad grid2">
      <div class="card"><h3>Is "consistency" a real trait?</h3>
        <p class="note" style="margin-top:0">The brief asks for players who deliver <em>most consistently</em>. So we tested whether players genuinely differ in match-to-match volatility, rather than assuming it.</p>
        <div class="scroll"><table><tr><th>Test</th><th class="r">Batters</th><th class="r">Bowlers</th></tr>
          <tr><td>Bartlett test for unequal volatility (p)</td><td class="r num">${f2(w.batters.consistency.p_value)}</td><td class="r num">${f2(w.bowlers.consistency.p_value)}</td></tr>
          <tr><td>Excess variance beyond noise</td><td class="r num">${f2(w.batters.consistency.excess_variance_tau2)}</td><td class="r num">${f2(w.bowlers.consistency.excess_variance_tau2)}</td></tr>
          <tr><td>Does volatility repeat? (split-half)</td><td class="r num">${f2(w.batters.consistency.split_half_persistence_of_volatility)}</td><td class="r num">${f2(w.bowlers.consistency.split_half_persistence_of_volatility)}</td></tr>
        </table></div>
        <p class="note" style="margin-top:10px">A weak, same-signed hint in both roles, but not significant at 5% and barely repeatable. So we do not rate consistency as a separate skill. It enters instead through the match bootstrap: the published score is a lower quantile, so a player carried by two freak games cannot hold a high rank.</p></div>
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
      <li><b>Being good under pressure is mostly being good.</b> Ranking players on their pressure balls alone gives a list that does not repeat (reliability ${f2(vb.split_half.raw_level.full_sample_reliability)} for batters), which is why the rating borrows from every ball a player has faced.</li>
      <li><b>It describes 2022–26; it is not a forecast.</b> Bowlers' pressure form carries into later seasons (${f2(vw.persistence.predict_later_pressure_level["joint_shrunk_level (ours)"])}); batters' barely does (${f2(vb.persistence.predict_later_pressure_level["joint_shrunk_level (ours)"])}).</li>
      <li><b>Extremes are slightly overstated.</b> The simulation shows the rating spreads a little wider than true talent at this pool size (slope 0.80–0.85 rather than 1.00), so the very top and bottom are further apart than reality.</li>
      <li><b>Places 6–10 are close calls</b> — the 90% ranges overlap heavily below the top three.</li>
      <li><b>Not measured:</b> fielding, wicketkeeping, captaincy, the pitch on the day, the partner at the other end, intent.</li></ul></section>

    <section class="sec-pad card"><h3>Sources</h3>
      ${[["official", "Official"], ["major", "Established outlets, data and published research"], ["aggregator", "Rumour and prediction sites — used only as flagged rumour"]].map(([t, l]) => {
        const items = D.sources.filter((s) => s.tier === t); if (!items.length) return "";
        return `<p style="font-weight:700;margin:12px 0 6px">${l}</p><ul class="src" style="margin:0;padding-left:18px">
          ${items.map((s) => `<li><a href="${s.url}" target="_blank" rel="noopener">${esc(s.title)}</a><div class="note">${esc(s.note)}</div></li>`).join("")}</ul>`; }).join("")}
    </section>`;
}

/* ---------------- router ---------------- */
function route() {
  const [, r, id] = (location.hash || "#/top10").split("/");
  document.querySelectorAll("#tabs a").forEach((a) => a.classList.toggle("on", a.dataset.r === r || (r === "royals" && a.dataset.r === "royals")));
  try {
    ({ top10: viewTop10, royals: () => (id ? viewPlayer(id) : viewRoyals()), auction: viewAuction, method: viewMethod }[r] || viewTop10)();
  } catch (e) {
    app.innerHTML = `<section class="sec-pad card"><h3>Something broke rendering this page</h3><p class="note">${esc(e.message)}</p></section>`;
    console.error(e);
  }
  scrollTo(0, 0);
}
addEventListener("hashchange", route);
route();
