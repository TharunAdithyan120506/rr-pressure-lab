"""Pressure ratings for every eligible batter and bowler in the supplied data.

Outputs
  data/processed/provided_final.parquet        ball-level table with opponent-adjusted run value
  data/processed/player_quality.csv            overall (all-balls) ridge quality, every player
  reports/rankings/batters_full.csv, bowlers_full.csv, top10_batters.csv, top10_bowlers.csv
  reports/rankings/rating_params.json          variance components, eligibility, weights
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

from rr_pressure.paths import PROCESSED, REPORTS  # noqa: E402
from rr_pressure.ratings import (ACTIVE_SINCE, MIN_PRESSURE_BALLS, MIN_PRESSURE_MATCHES, WEIGHTS, Rater,  # noqa: E402
                                 opponent_adjust, player_match)
from rr_pressure.stats import bat_split, bowl_split, wide  # noqa: E402

OUT = REPORTS / "rankings"
OUT.mkdir(parents=True, exist_ok=True)
B = 1000


def main() -> None:
    pr = pd.read_parquet(PROCESSED / "provided_scored_v2.parquet")
    pr, info = opponent_adjust(pr)
    pr.to_parquet(PROCESSED / "provided_final.parquet", index=False)

    q = pd.concat([
        pd.DataFrame({"role": "bat", "quality": info["bat_quality"]}).assign(
            name=lambda d: d.index.map(pr.groupby("batter_id")["batter"].last()),
            balls=lambda d: d.index.map(pr[pr.faced].groupby("batter_id").size())),
        pd.DataFrame({"role": "bowl", "quality": info["bowl_quality"]}).assign(
            name=lambda d: d.index.map(pr.groupby("bowler_id")["bowler"].last()),
            balls=lambda d: d.index.map(pr.groupby("bowler_id").size())),
    ]).rename_axis("pid").reset_index()
    q.to_csv(PROCESSED / "player_quality.csv", index=False)

    params = {"weights": WEIGHTS, "min_pressure_balls": MIN_PRESSURE_BALLS,
              "min_pressure_matches": MIN_PRESSURE_MATCHES, "active_since": ACTIVE_SINCE,
              "bootstrap": B, "ridge_alpha": info["alpha"], "elo_coef_per_100": info["elo_coef_per_100"]}
    print("opposition-strength effect (runs/ball per +100 Elo):", {k: round(v, 4) for k, v in info["elo_coef_per_100"].items()})
    for role, split, idc, team in (("bat", bat_split, "batter_id", "batting_team"),
                                   ("bowl", bowl_split, "bowler_id", "bowling_team")):
        pm, meta = player_match(pr, role)
        R = Rater(pm, meta)
        res = R.run(B=B)
        st = wide(split(pr, [idc, "pressure"]))
        res = res.join(st, how="left")
        last = pr.sort_values("date").groupby(idc).agg(team=(team, "last"), last_date=("date", "max"))
        res = res.join(last)
        res["rating"] = (100 + 15 * res["score"] / res["score"].std()).round(1)
        name = "batters" if role == "bat" else "bowlers"
        res.rename_axis("pid").to_csv(OUT / f"{name}_full.csv")
        res.head(10).rename_axis("pid").to_csv(OUT / f"top10_{name}.csv")
        hp = {k: (v.tolist() if isinstance(v, np.ndarray) else float(v)) for k, v in R.hp.items()}
        params[role] = {"eligible": int(R.elig.sum()), **hp}
        show = (["rank", "name", "team", "rating", "score", "level", "level_runs", "level_wkt", "lift", "n_p", "m_p", "p_top10"]
                + (["sr_p", "sr_o", "avg_p", "avg_o"] if role == "bat" else ["econ_p", "econ_o", "wkts_p", "sr_p"]))
        print(f"\n=== {name.upper()}  eligible={R.elig.sum()}  pool={hp['hyper_pool']}  kappa={hp['kappa']} "
              f"(mle {hp['kappa_mle']}, 95% {hp['kappa_lo']}-{hp['kappa_hi']})  sd ordinary/level/lift="
              f"{hp['sd_ord']:.3f}/{hp['sd_level']:.3f}/{hp['sd_lift']:.3f}  rel runs/wkt pressure={hp['rel_runs_p']:.2f}/"
              f"{hp['rel_wkt_p']:.2f} ordinary={hp['rel_runs_o']:.2f}/{hp['rel_wkt_o']:.2f}  "
              f"design_effect={np.round(hp['design_effect'], 2).tolist()}")
        print(res[show].head(25).round(3).to_string(index=False))
    (OUT / "rating_params.json").write_text(json.dumps(params, indent=1))


if __name__ == "__main__":
    main()
