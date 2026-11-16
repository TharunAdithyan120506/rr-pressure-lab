"""Evidence cards for the RR squad and for the top-10 ranked players, plus the squad value table.

Outputs  reports/rr/cards.json          one card per RR player and per top-10 player
         reports/rr/squad_metrics.csv   one row per RR player (usage, model value, salary)
Static squad facts (salary, role, age) live in configs/rr_squad.json.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from rr_pressure.cards import CardBuilder, cricsheet_form  # noqa: E402
from rr_pressure.paths import PROCESSED, RAW, REPORTS, ROOT  # noqa: E402

OUT = REPORTS / "rr"
OUT.mkdir(parents=True, exist_ok=True)
REPLACEMENT = -0.08      # runs per ball: a freely available squad player (~1 talent SD below average)
PRESSURE_SHARE = 0.20


def main() -> None:
    squad = json.loads((ROOT / "configs" / "rr_squad.json").read_text(encoding="utf-8"))["players"]
    pr = pd.read_parquet(PROCESSED / "provided_final.parquet")
    cs = pd.read_parquet(PROCESSED / "cricsheet_scored_v2.parquet",
                         columns=["source", "match_id", "date", "batter_id", "bowler_id", "faced", "is_legal", "runs_batter",
                                  "striker_out", "bowler_runs", "bowler_wicket", "pressure", "batter", "bowler"])
    pmap = pd.read_csv(PROCESSED / "player_id_map.csv", dtype=str).set_index("pid")
    pe = pd.read_csv(RAW / "playing_eleven.csv")
    m = pd.read_csv(RAW / "matches.csv").merge(pd.read_csv(RAW / "competitions.csv"), on="comp_id")
    ipl26 = set(m[m.comp_name == "IPL 2026"].match_id)
    played = pe[pe.match_id.isin(ipl26) & (pe.is_played == True)].groupby("player_id").size()  # noqa: E712

    cb = CardBuilder(pr)
    cards, rows = {}, []
    for p in squad:
        pid = str(p["pid"])
        c = cb.card(pid)
        cid = p.get("cid") or (pmap["cid"].get(pid) if pid in pmap.index else None)
        c["form"] = cricsheet_form(cs, cid) if isinstance(cid, str) else {}
        c["ipl26_matches"] = int(played.get(p["pid"], 0))
        cards[pid] = c
        d26 = pr[(pr.is_ipl == 1) & (pr.year == 2026)]
        faced = int(((d26.batter_id == pid) & d26.faced).sum())
        bowled = int((d26.bowler_id == pid).sum())
        bm = (c["bat"] or {}).get("model") or {}
        wm = (c["bowl"] or {}).get("model") or {}
        bat_pb = PRESSURE_SHARE * bm.get("level", 0) + (1 - PRESSURE_SHARE) * bm.get("ordinary", 0) if bm else 0.0
        bowl_pb = PRESSURE_SHARE * wm.get("level", 0) + (1 - PRESSURE_SHARE) * wm.get("ordinary", 0) if wm else 0.0
        raa = bat_pb * faced + bowl_pb * bowled
        rar = raa - REPLACEMENT * (faced + bowled)
        rows.append({"pid": pid, "name": p["name"], "salary": p["salary"], "matches_2026": c["ipl26_matches"],
                     "faced_2026": faced, "bowled_2026": bowled, "bat_per_ball": round(bat_pb, 4),
                     "bowl_per_ball": round(bowl_pb, 4), "runs_above_avg": round(raa, 1), "runs_above_repl": round(rar, 1),
                     "bat_level_pct": bm.get("level_pct"), "bowl_level_pct": wm.get("level_pct"),
                     "bat_n_p": bm.get("n_p"), "bowl_n_p": wm.get("n_p")})
    t = pd.DataFrame(rows)
    # what RR's own wage bill implies a run above replacement is worth
    rate = t["salary"].sum() / t["runs_above_repl"].clip(lower=0).sum()
    t["value_cr"] = (t["runs_above_repl"].clip(lower=0) * rate).round(2)
    t["surplus_cr"] = (t["value_cr"] - t["salary"]).round(2)
    t.to_csv(OUT / "squad_metrics.csv", index=False)
    print(f"implied price: Rs {rate * 100:.1f} lakh per run above replacement")
    print(t.sort_values("surplus_cr", ascending=False).to_string(index=False))

    # top-10 players' cards
    for fname in ("batters", "bowlers"):
        top = pd.read_csv(REPORTS / "rankings" / f"top10_{fname}.csv", dtype={"pid": str})
        for pid in top["pid"]:
            if pid not in cards:
                cards[pid] = cb.card(pid)
    (OUT / "cards.json").write_text(json.dumps(cards, default=float), encoding="utf-8")
    print("cards:", len(cards))


if __name__ == "__main__":
    main()
