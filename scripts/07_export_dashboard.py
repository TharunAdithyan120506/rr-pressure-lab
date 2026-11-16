"""Bundle everything the dashboard needs into dashboard/data.js (window.DATA) and copy photos.

The dashboard is a static site: open dashboard/index.html directly, no server needed.
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from rr_pressure.paths import REPORTS, ROOT, TRAINED  # noqa: E402

DASH = ROOT / "dashboard"
TODAY = date(2026, 11, 16)
BAT_COLS = ["pid", "rank", "name", "team", "rating", "rating_lo", "rating_hi", "p_top10", "level", "ordinary", "lift", "n_p", "m_p",
            "ipl_share", "sr_p", "sr_o", "avg_p", "avg_o", "bnd_pct_p", "bnd_pct_o", "dot_pct_p", "dot_pct_o", "runs_p", "balls_p",
            "runs_vs_exp_p", "wpa_p"]
BOWL_COLS = ["pid", "rank", "name", "team", "rating", "rating_lo", "rating_hi", "p_top10", "level", "ordinary", "lift", "n_p", "m_p",
             "ipl_share", "econ_p", "econ_o", "wkts_p", "wkts_o", "sr_p", "sr_o", "dot_pct_p", "dot_pct_o", "bnd_pct_p", "bnd_pct_o",
             "balls_p", "runs_saved_p", "wpa_p"]


def ranking(fname: str, cols: list[str]) -> tuple[list[dict], dict]:
    t = pd.read_csv(REPORTS / "rankings" / f"{fname}_full.csv", dtype={"pid": str})
    sd = t["score"].std()
    t["rating_lo"] = (100 + 15 * t["lo"] / sd).round(1)
    t["rating_hi"] = (100 + 15 * t["hi"] / sd).round(1)
    t = t[cols].round(3)
    by_pid = {r["pid"]: {"rank": int(r["rank"]), "rating": r["rating"], "of": len(t), "p_top10": r["p_top10"]} for r in t.to_dict("records")}
    return json.loads(t.head(30).to_json(orient="records")), by_pid


def main() -> None:
    DASH.mkdir(exist_ok=True)
    (DASH / "photos").mkdir(exist_ok=True)
    cfg = json.loads((ROOT / "configs" / "rr_squad.json").read_text(encoding="utf-8"))
    ver = json.loads((ROOT / "configs" / "rr_verdicts.json").read_text(encoding="utf-8"))
    cards = json.loads((REPORTS / "rr" / "cards.json").read_text(encoding="utf-8"))
    metrics = pd.read_csv(REPORTS / "rr" / "squad_metrics.csv", dtype={"pid": str}).set_index("pid")
    val = json.loads((REPORTS / "validation" / "validation.json").read_text(encoding="utf-8"))
    params = json.loads((REPORTS / "rankings" / "rating_params.json").read_text(encoding="utf-8"))
    ctx = json.loads((TRAINED / "ctx" / "metrics_ctx.json").read_text(encoding="utf-8"))
    sources = json.loads((REPORTS / "research" / "sources.json").read_text(encoding="utf-8"))["sources"]

    bat, bat_rank = ranking("batters", BAT_COLS)
    bowl, bowl_rank = ranking("bowlers", BOWL_COLS)

    squad = []
    for p in cfg["players"]:
        pid = str(p["pid"])
        if p["photo"]:
            shutil.copy(ROOT / "photos" / p["photo"], DASH / "photos" / p["photo"])
        dob = date.fromisoformat(p["dob"])
        age = TODAY.year - dob.year - ((TODAY.month, TODAY.day) < (dob.month, dob.day))
        m = metrics.loc[pid]
        squad.append({**p, "pid": pid, "age": age, **ver["players"][pid],
                      "value": {k: (None if pd.isna(m[k]) else float(m[k])) for k in
                                ("matches_2026", "faced_2026", "bowled_2026", "runs_above_avg", "runs_above_repl", "value_cr", "surplus_cr")},
                      "rank_bat": bat_rank.get(pid), "rank_bowl": bowl_rank.get(pid), "card": cards[pid]})

    top_cards = {r["pid"]: cards[r["pid"]] for r in bat[:10] + bowl[:10] if r["pid"] in cards}
    sens = {f: pd.read_csv(REPORTS / "validation" / f"sensitivity_{f}.csv").drop(columns="variant_top10").to_dict("records")
            for f in ("batters", "bowlers")}
    comp = pd.read_csv(REPORTS / "validation" / "pressure_composition.csv").to_dict("records")
    dec = pd.read_csv(REPORTS / "validation" / "outcomes_by_li_decile.csv").round(2).to_dict("records")
    hp = {r: {k: params[r][k] for k in ("eligible", "hyper_pool", "kappa", "kappa_mle", "kappa_lo", "kappa_hi", "sd_ord", "sd_level",
                                         "sd_lift", "rel_runs_p", "rel_wkt_p", "rel_runs_o", "rel_wkt_o", "design_effect")}
          for r in ("bat", "bowl")}
    data = {
        "generated": TODAY.isoformat(),
        "purse": {k: cfg[k] for k in ("purse_total_cr", "purse_note", "squad_max", "overseas_max", "season")},
        "squad": squad, "needs": ver["needs"], "scenarios": ver["scenarios"], "lessons": ver["lessons"],
        "batters": bat, "bowlers": bowl, "top_cards": top_cards,
        "validation": {k: val[k] for k in ("batters", "bowlers", "spot_checks")},
        "pressure_def": val["pressure_definition"], "composition": comp, "deciles": dec, "sensitivity": sens,
        "hp": hp, "params": {k: params[k] for k in ("weights", "min_pressure_balls", "min_pressure_matches", "active_since", "bootstrap")},
        "ctx": ctx, "sources": sources,
    }
    (DASH / "data.js").write_text("window.DATA = " + json.dumps(data, default=float) + ";\n", encoding="utf-8")
    (REPORTS / "rr" / "dashboard_data.json").write_text(json.dumps(data, default=float, indent=1), encoding="utf-8")
    print(f"dashboard/data.js written ({(DASH / 'data.js').stat().st_size / 1e6:.2f} MB), {len(squad)} squad players, "
          f"{len(top_cards)} top-10 cards, {len(list((DASH / 'photos').glob('*.png')))} photos")


if __name__ == "__main__":
    main()
