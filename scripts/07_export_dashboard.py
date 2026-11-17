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
        for r in rows:
            r["photo"] = photo(r["name"])
            r["team2027"] = team2027.get(pkey(r["name"]), r["team"])
        idx = {r["pid"]: {"rank": int(r["rank"]), "rating": r["rating"], "of": len(t),
                          "p_top10": r["p_top10"]} for r in json.loads(out.to_json(orient="records"))}
        return rows, idx, len(t)

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
