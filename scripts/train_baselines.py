"""Train the match-state models that define pressure, then score the provided deliveries.

Models (trained on Cricsheet T20 history, time-split validation):
  wp_lgbm.txt      P(batting side wins | pre-ball state)
  xruns_lgbm.txt   E[runs off this ball | state]
  xwkt_lgbm.txt    P(wicket on this ball | state)
  wp_mlp.pt        PyTorch MLP win-probability (GPU if available) – deep cross-check

Output: data/processed/provided_deliveries_scored.parquet with columns
  wp_before, wp_after, wpa, leverage, xruns, xwkt
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error, roc_auc_score  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from rr_pressure.features import WP_FEATURES, model_frame  # noqa: E402
from rr_pressure.models import device, lgbm_classifier, lgbm_regressor, train_mlp  # noqa: E402
from rr_pressure.paths import PROCESSED, TRAINED  # noqa: E402

SPLIT_DATE = pd.Timestamp("2024-01-01")


def shifted_state(df: pd.DataFrame, runs: int, wicket: int) -> pd.DataFrame:
    """Hypothetical state after a legal ball producing `runs` / `wicket`."""
    s = df.copy()
    s["score"] += runs
    s["wickets"] += wicket
    s["wickets_in_hand"] -= wicket
    s["balls_bowled"] += 1
    s["balls_left"] = (s["balls_left"] - 1).clip(lower=0)
    s["crr"] = 6 * s["score"] / s["balls_bowled"].clip(lower=1)
    chase = s["innings"] == 2
    s.loc[chase, "runs_required"] = s.loc[chase, "target"] - s.loc[chase, "score"]
    s.loc[chase, "rrr"] = 6 * s.loc[chase, "runs_required"] / s.loc[chase, "balls_left"].clip(lower=1)
    s.loc[chase, "rrr_minus_crr"] = s.loc[chase, "rrr"] - s.loc[chase, "crr"]
    s["partnership_runs"] = np.where(wicket, 0, s["partnership_runs"] + runs)
    return s


def main() -> None:
    t0 = time.time()
    cs = model_frame(pd.read_parquet(PROCESSED / "cricsheet_deliveries.parquet"))
    cs = cs[cs["batting_team_won"].notna()]
    tr, va = cs[cs["date"] < SPLIT_DATE], cs[cs["date"] >= SPLIT_DATE]
    print(f"train {len(tr):,} balls | valid {len(va):,} balls | device={device()}")
    X, Xv = tr[WP_FEATURES], va[WP_FEATURES]
    metrics = {}

    # 1) win probability
    wp = lgbm_classifier().fit(X, tr["batting_team_won"].astype(int))
    p = wp.predict_proba(Xv)[:, 1]
    yv = va["batting_team_won"].astype(int)
    metrics["wp_lgbm"] = dict(logloss=log_loss(yv, p), brier=brier_score_loss(yv, p), auc=roc_auc_score(yv, p))
    wp.booster_.save_model(str(TRAINED / "wp_lgbm.txt"))

    # 2) expected runs / wicket probability per ball (legal + illegal deliveries)
    xr = lgbm_regressor().fit(X, tr["runs_total"])
    metrics["xruns_lgbm"] = dict(mae=mean_absolute_error(va["runs_total"], xr.predict(Xv)))
    xr.booster_.save_model(str(TRAINED / "xruns_lgbm.txt"))
    xw = lgbm_classifier().fit(X, tr["is_wicket"].astype(int))
    pw = xw.predict_proba(Xv)[:, 1]
    metrics["xwkt_lgbm"] = dict(logloss=log_loss(va["is_wicket"].astype(int), pw),
                                auc=roc_auc_score(va["is_wicket"].astype(int), pw))
    xw.booster_.save_model(str(TRAINED / "xwkt_lgbm.txt"))

    # 3) deep cross-check: PyTorch MLP win probability
    sc = StandardScaler().fit(X)
    mlp = train_mlp(sc.transform(X), tr["batting_team_won"].astype(int).values,
                    sc.transform(Xv), yv.values, epochs=8, verbose=True)
    mlp.eval()
    with torch.no_grad():
        pm = torch.sigmoid(mlp(torch.tensor(sc.transform(Xv), dtype=torch.float32, device=device()))).cpu().numpy()
    metrics["wp_mlp"] = dict(logloss=log_loss(yv, pm), brier=brier_score_loss(yv, pm), auc=roc_auc_score(yv, pm))
    torch.save(mlp.state_dict(), TRAINED / "wp_mlp.pt")
    joblib.dump(sc, TRAINED / "wp_mlp_scaler.joblib")

    (TRAINED / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))

    # 4) score provided data: WP before/after, WPA, leverage, expected runs & wicket risk
    pr = model_frame(pd.read_parquet(PROCESSED / "provided_deliveries.parquet"))
    P = pr[WP_FEATURES]
    pr["wp_before"] = wp.predict_proba(P)[:, 1]
    pr["xruns"] = xr.predict(P)
    pr["xwkt"] = xw.predict_proba(P)[:, 1]
    wp4 = wp.predict_proba(shifted_state(P, 4, 0)[WP_FEATURES])[:, 1]
    wpw = wp.predict_proba(shifted_state(P, 0, 1)[WP_FEATURES])[:, 1]
    pr["leverage"] = np.abs(wp4 - wpw)  # swing between a boundary and a wicket
    nxt = pr.groupby(["match_id", "innings"])["wp_before"].shift(-1)
    # end of innings 1 -> (1 - chasing side's WP at first ball); end of innings 2 -> actual result
    inn2_start = 1 - pr[pr.innings == 2].groupby("match_id")["wp_before"].first()
    end = np.where(pr["innings"] == 1, pr["match_id"].map(inn2_start), pr["batting_team_won"].astype(float))
    pr["wp_after"] = nxt.fillna(pd.Series(end, index=pr.index)).fillna(pr["wp_before"])
    pr["wpa"] = pr["wp_after"] - pr["wp_before"]
    pr.to_parquet(PROCESSED / "provided_deliveries_scored.parquet", index=False)
    print(f"scored provided deliveries -> provided_deliveries_scored.parquet  ({time.time() - t0:.0f}s)")
    print(pr["leverage"].describe().round(3).to_string())


if __name__ == "__main__":
    main()
