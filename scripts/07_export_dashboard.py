"""Bundle everything the dashboard needs into dashboard/data.js (window.DATA).

The dashboard is a static site: open dashboard/index.html directly, no server needed.
"""
from __future__ import annotations

import json
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from rr_pressure.paths import REPORTS, ROOT, TRAINED  # noqa: E402

DASH = ROOT / "dashboard"
TODAY = date(2026, 11, 18)
BAT_COLS = ["pid", "rank", "name", "team", "rating", "rating_lo", "rating_hi", "p_top10", "level", "ordinary", "lift",
            "n_p", "m_p", "ipl_share", "sr_p", "sr_o", "avg_p", "avg_o", "bnd_pct_p", "bnd_pct_o", "dot_pct_p",
            "dot_pct_o", "runs_p", "balls_p", "runs_vs_exp_p", "wpa_p"]
BOWL_COLS = ["pid", "rank", "name", "team", "rating", "rating_lo", "rating_hi", "p_top10", "level", "ordinary", "lift",
             "n_p", "m_p", "ipl_share", "econ_p", "econ_o", "wkts_p", "wkts_o", "sr_p", "sr_o", "dot_pct_p",
             "dot_pct_o", "bnd_pct_p", "bnd_pct_o", "balls_p", "runs_saved_p", "wpa_p"]


def pkey(n):
    n = unicodedata.normalize("NFKD", str(n)).encode("ascii", "ignore").decode().lower()
    return "".join(c for c in n if c.isalnum() or c == " ").strip()


ALIAS = {"varun chakravarthy": "varun chakaravarthy", "mitchell marsh": "mitch marsh",
         "mitchell santner": "mitch santner", "namboori tilak varma": "tilak varma",
         "mohammed shami": "mohammad shami", "digvesh rathi": "digvesh singh rathi",
         "yash raj punja": "yash punja", "aman rao perala": "aman rao",
         "yudhvir singh": "yudhvir singh charak", "thangarasu natarajan": "t natarajan",
         "lhuan dre pretorius": "lhuandre pretorius"}



def note_for(r: dict, role: str, card: dict | None) -> dict:
    """A short, factual case for why this player holds his place, built from his own numbers."""
    pct = None
    if card and card.get("model"):
        pct = card["model"]["level_pct"]
    lift_pct = card["model"]["lift_pct"] if card and card.get("model") else None
    bits = []
    if role == "bat":
        head = (f"{int(r['runs_p'])} runs off {int(r['balls_p'])} pressure balls at a strike rate of "
                f"{r['sr_p']:.0f}" + (f", averaging {r['avg_p']:.0f}." if r.get("avg_p") else "."))
        d = r["sr_p"] - r["sr_o"]
        if d > 8:
            bits.append(f"He goes up a gear when it tightens: {r['sr_p']:.0f} under pressure against {r['sr_o']:.0f} otherwise.")
        elif d < -8:
            bits.append(f"He scores slower under pressure ({r['sr_p']:.0f} v {r['sr_o']:.0f}) but gives his wicket away far less.")
        else:
            bits.append(f"He does not lift so much as never drop: {r['sr_p']:.0f} under pressure against {r['sr_o']:.0f} otherwise.")
        if r.get("avg_p") and r.get("avg_o") and r["avg_p"] > r["avg_o"] * 1.25:
            bits.append(f"His average actually climbs, from {r['avg_o']:.0f} to {r['avg_p']:.0f}.")
        if r["bnd_pct_p"] >= 22:
            bits.append(f"{r['bnd_pct_p']:.0f}% of his pressure balls go for four or six.")
    else:
        head = (f"{int(r['wkts_p'])} wickets and an economy of {r['econ_p']:.2f} across "
                f"{int(r['n_p'])} pressure balls.")
        d = r["econ_o"] - r["econ_p"]
        if d > 0.5:
            bits.append(f"He gets cheaper when it matters: {r['econ_p']:.2f} an over under pressure against {r['econ_o']:.2f} otherwise.")
        elif d < -0.5:
            bits.append(f"He costs a little more under pressure ({r['econ_p']:.2f} v {r['econ_o']:.2f}) but keeps taking wickets.")
        else:
            bits.append(f"Nothing changes when the game tightens: {r['econ_p']:.2f} an over under pressure against {r['econ_o']:.2f} otherwise.")
        if r["dot_pct_p"] >= 38:
            bits.append(f"{r['dot_pct_p']:.0f}% of his pressure balls are dots.")
    if pct is not None and pct >= 90:
        bits.append(f"That puts him in the top {max(1, round(100 - pct))}% of ranked players on pressure balls.")
    if lift_pct is not None and lift_pct >= 85:
        bits.append("His lift over his own everyday level is among the biggest in the pool.")
    if r["n_p"] < 150:
        bits.append(f"Only {int(r['n_p'])} pressure balls, so the estimate is pulled toward the average and the range is wide.")
    return {"head": head, "body": " ".join(bits[:3])}


def recent_for(card: dict | None, role: str) -> list:
    """His biggest pressure days, newest first — the matches behind the rating."""
    c = (card or {}).get("bat" if role == "bat" else "bowl") or {}
    out = []
    for m in (c.get("moments") or []):
        if m["kind"] != "best":
            continue
        line = (f"{m['runs']} off {m['balls']}" if role == "bat"
                else f"{m['wk']}/{m['runs']} in {m['balls']}")
        out.append({"date": m["date"], "opp": m["opp"], "comp": m["comp"], "line": line,
                    "wpa": m["wpa_pct"], "balls": m["balls"]})
    return sorted(out, key=lambda x: x["date"], reverse=True)[:3]


def main() -> None:
    DASH.mkdir(exist_ok=True)
    photos = json.loads((DASH / "photos" / "index.json").read_text(encoding="utf-8"))
    PH = {pkey(k): v for k, v in photos.items()}

    def photo(name):
        k = pkey(name)
        return PH.get(k) or PH.get(ALIAS.get(k, k))

    cfg = json.loads((ROOT / "configs" / "rr_squad.json").read_text(encoding="utf-8"))
    ver = json.loads((ROOT / "configs" / "rr_verdicts.json").read_text(encoding="utf-8"))
    ret = json.loads((ROOT / "configs" / "retentions_2027.json").read_text(encoding="utf-8"))
    cards = json.loads((REPORTS / "rr" / "cards.json").read_text(encoding="utf-8"))
    auction = json.loads((REPORTS / "rr" / "auction.json").read_text(encoding="utf-8"))
    metrics = pd.read_csv(REPORTS / "rr" / "squad_metrics.csv", dtype={"pid": str}).set_index("pid")
    val = json.loads((REPORTS / "validation" / "validation.json").read_text())
    verif = json.loads((REPORTS / "validation" / "verification.json").read_text())
    wc = json.loads((REPORTS / "validation" / "weights_consistency.json").read_text())
    params = json.loads((REPORTS / "rankings" / "rating_params.json").read_text())
    ctx = json.loads((TRAINED / "ctx" / "metrics_ctx.json").read_text())
    sources = json.loads((REPORTS / "research" / "sources.json").read_text())["sources"]
    team2027 = {pkey(k): v for k, v in ret["team_of_player_2027"].items()}

    def ranking(fname, cols):
        t = pd.read_csv(REPORTS / "rankings" / f"{fname}_full.csv", dtype={"pid": str})
        sd = t["score"].std()
        t["rating_lo"] = (100 + 15 * t["lo"] / sd).round(1)
        t["rating_hi"] = (100 + 15 * t["hi"] / sd).round(1)
        out = t[cols].round(3)
        rows = json.loads(out.head(40).to_json(orient="records"))
        role = "bat" if fname == "batters" else "bowl"
        for i, r in enumerate(rows):
            r["photo"] = photo(r["name"])
            r["team2027"] = team2027.get(pkey(r["name"]), r["team"])
            cd = cards.get(r["pid"])
            if i < 12:
                r["note"] = note_for(r, role, (cd or {}).get(role))
                r["recent"] = recent_for(cd, role)
        idx = {r["pid"]: {"rank": int(r["rank"]), "rating": r["rating"], "of": len(t),
                          "p_top10": r["p_top10"]} for r in json.loads(out.to_json(orient="records"))}
        return rows, idx, len(t)

    # ball-by-ball win probability for the famous chases, so the explainer can animate a real match
    sc = pd.read_csv(REPORTS / "validation" / "spot_check_matches.csv")
    chases = []
    for label, g in sc.groupby("label", sort=False):
        g = g.sort_values("balls_bowled")
        pk = g.loc[g["li"].idxmax()]
        chases.append({
            "label": label,
            "balls": [{"b": int(b), "wp": round(float(w), 4), "li": round(float(l), 2),
                       "r": int(rt), "wk": bool(k), "need": None if pd.isna(rr) else int(rr),
                       "left": int(bl)}
                      for b, w, l, rt, k, rr, bl in
                      zip(g["balls_bowled"], g["wp"], g["li"], g["runs_total"], g["is_wicket"],
                          g["runs_required"], g["balls_left"])],
            "peak": {"b": int(pk["balls_bowled"]), "li": round(float(pk["li"]), 1),
                     "need": int(pk["runs_required"]), "left": int(pk["balls_left"]),
                     "batter": pk["batter"], "bowler": pk["bowler"]},
        })

    bat, bat_idx, n_bat = ranking("batters", BAT_COLS)
    bowl, bowl_idx, n_bowl = ranking("bowlers", BOWL_COLS)

    actual = {pkey(r["name"]): r["actual"] for r in auction["scorecard"]["rows"]}
    squad = []
    for p in cfg["players"]:
        pid = str(p["pid"])
        dob = date.fromisoformat(p["dob"])
        age = TODAY.year - dob.year - ((TODAY.month, TODAY.day) < (dob.month, dob.day))
        m = metrics.loc[pid]
        squad.append({**{k: v for k, v in p.items() if k != "photo"}, "pid": pid, "age": age,
                      "photo": photo(p["name"]), **ver["players"][pid],
                      "actual": actual.get(pkey(p["name"]), "Not listed"),
                      "value": {k: (None if pd.isna(m[k]) else float(m[k])) for k in
                                ("matches_2026", "faced_2026", "bowled_2026", "runs_above_avg",
                                 "runs_above_repl", "value_cr", "surplus_cr")},
                      "rank_bat": bat_idx.get(pid), "rank_bowl": bowl_idx.get(pid), "card": cards[pid]})

    top_cards = {r["pid"]: cards[r["pid"]] for r in bat[:12] + bowl[:12] if r["pid"] in cards}
    sens = {f: pd.read_csv(REPORTS / "validation" / f"sensitivity_{f}.csv").drop(columns="variant_top10").to_dict("records")
            for f in ("batters", "bowlers")}
    hp = {r: {k: params[r][k] for k in ("eligible", "hyper_pool", "kappa", "kappa_mle", "kappa_lo", "kappa_hi",
                                        "sd_ord", "sd_level", "sd_lift", "rel_runs_p", "rel_wkt_p",
                                        "rel_runs_o", "rel_wkt_o")} for r in ("bat", "bowl")}

    data = {
        "generated": TODAY.isoformat(),
        "counts": {"batters": n_bat, "bowlers": n_bowl},
        "batters": bat, "bowlers": bowl, "top_cards": top_cards,
        "squad": squad, "needs": ver["needs"], "lessons": ver["lessons"],
        "purse": {k: cfg[k] for k in ("purse_total_cr", "purse_note", "squad_max", "overseas_max", "season")},
        "auction": auction, "retentions": {"announced": ret["announced"], "rr": ret["rr"], "trades": ret["trades"]},
        "validation": {k: val[k] for k in ("batters", "bowlers", "spot_checks")},
        "pressure_def": val["pressure_definition"],
        "composition": pd.read_csv(REPORTS / "validation" / "pressure_composition.csv").to_dict("records"),
        "deciles": pd.read_csv(REPORTS / "validation" / "outcomes_by_li_decile.csv").round(2).to_dict("records"),
        "chases": chases,
        "sensitivity": sens, "hp": hp, "weights": wc, "verification": verif,
        "params": {k: params[k] for k in ("weights", "min_pressure_balls", "min_pressure_matches",
                                          "active_since", "bootstrap")},
        "ctx": ctx, "sources": sources,
    }
    (DASH / "data.js").write_text("window.DATA = " + json.dumps(data, default=float) + ";\n", encoding="utf-8")
    (REPORTS / "rr" / "dashboard_data.json").write_text(json.dumps(data, default=float, indent=1), encoding="utf-8")
    miss = [p["name"] for p in squad if not p["photo"]] + [r["name"] for r in bat[:10] + bowl[:10] if not r["photo"]]
    print(f"dashboard/data.js written ({(DASH / 'data.js').stat().st_size / 1e6:.2f} MB) · "
          f"{len(squad)} squad · {len(top_cards)} top cards · {len(auction['board']['bowl']) + len(auction['board']['bat'])} auction targets")
    print("missing photos:", miss or "none")


if __name__ == "__main__":
    main()
