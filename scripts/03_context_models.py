"""Context models v2 (GPU, 5-fold cross-fitted by match) + Leverage Index + per-ball run value.

Every ball is scored by models that never saw its own match, so "expected" values and win
probabilities are out-of-sample.

Models (XGBoost, cuda):
  wp        P(batting side wins | state, era, venue, team Elo)
  xr_bat    E[batter runs | ball faced]          xw_bat   P(striker dismissed | ball faced)
  xr_bowl   E[runs charged to bowler]            xw_bowl  P(bowler takes wicket)
  rem       E[runs still to come in innings]  (monotone in balls left / wickets) -> wicket cost

Outputs: data/processed/provided_scored_v2.parquet, cricsheet_scored_v2.parquet,
         models/trained/ctx/*.json, pressure_def.json, metrics_ctx.json, wp_calibration.csv
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xgboost as xgb  # noqa: E402
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score  # noqa: E402

from rr_pressure.context import (CTX_FEATURES, REM_FEATURES, WP2_FEATURES, add_basic_context,  # noqa: E402
                                 attach_elo, attach_elo_provided, compute_elo, fold_of, match_table)
from rr_pressure.features import WP_FEATURES, model_frame  # noqa: E402
from rr_pressure.paths import PROCESSED, TRAINED  # noqa: E402
from rr_pressure.pressure import KNOCKOUT_MULT, leverage, outcome_table, rule_based_pressure  # noqa: E402

END_FEATURES = ["runs_required", "balls_left", "wickets_in_hand"]
CTX = TRAINED / "ctx"
CTX.mkdir(exist_ok=True)
NF = 5
# --reuse loads saved fold models; --refit a,b retrains only those (e.g. --reuse --refit rem)
REUSE = "--reuse" in sys.argv
REFIT = sys.argv[sys.argv.index("--refit") + 1].split(",") if "--refit" in sys.argv else []
BASE = dict(n_estimators=500, learning_rate=0.06, max_depth=7, min_child_weight=100, subsample=0.8,
            colsample_bytree=0.8, tree_method="hist", device="cuda", max_bin=256, verbosity=0)


def fit(X, y, clf: bool, **kw):
    cls = xgb.XGBClassifier if clf else xgb.XGBRegressor
    p = dict(BASE, **kw)
    if clf:
        p["eval_metric"] = "logloss"
    return cls(**p).fit(X.to_numpy(np.float32), y.to_numpy(np.float32))


def pred(m, X) -> np.ndarray:
    A = X.to_numpy(np.float32)
    return m.predict_proba(A)[:, 1] if isinstance(m, xgb.XGBClassifier) else m.predict(A)


SPECS = {  # name: (features, target, row filter, classifier?, extra params)
    "wp": (WP2_FEATURES, "batting_team_won", lambda d: d["batting_team_won"].notna(), True, {}),
    "xr_bat": (CTX_FEATURES, "runs_batter", lambda d: d["faced"], False, {}),
    "xw_bat": (CTX_FEATURES, "striker_out", lambda d: d["faced"], True, {}),
    "xr_bowl": (CTX_FEATURES, "bowler_runs", lambda d: d["match_id"].notna(), False, {}),
    "xw_bowl": (CTX_FEATURES, "bowler_wicket", lambda d: d["match_id"].notna(), True, {}),
    # dedicated endgame model: fine-grained and monotone (fewer runs / more balls / more wickets = better)
    "wp_end": (END_FEATURES, "batting_team_won", lambda d: (d["innings"] == 2) & (d["balls_left"] <= 30)
               & d["batting_team_won"].notna(), True,
               {"monotone_constraints": "(-1,1,1)", "min_child_weight": 5, "max_depth": 5, "n_estimators": 300}),
    "rem": (REM_FEATURES, "rem_runs", lambda d: (d["innings"] == 1) & (d["innings_balls"] == 120)
            & d["winner"].notna(), False, {"monotone_constraints": "(1,-1,0,0,0,0,0)", "max_depth": 6}),
}


def prep() -> tuple[pd.DataFrame, pd.DataFrame]:
    cs = pd.read_parquet(PROCESSED / "cricsheet_deliveries.parquet")
    pr = pd.read_parquet(PROCESSED / "provided_deliveries.parquet")
    pairs = pd.read_csv(PROCESSED / "match_pairs.csv")
    cs, pr = add_basic_context(cs), add_basic_context(pr)
    # Elo over Cricsheet plus the supplied matches Cricsheet lacks (it carries no Afghanistan games)
    unpaired = pr[~pr["match_id"].isin(pairs["match_id_p"])]
    elo = compute_elo(pd.concat([match_table(cs), match_table(unpaired)], ignore_index=True))
    elo.to_parquet(PROCESSED / "team_elo.parquet", index=False)
    cs = attach_elo(cs, elo)
    cs[["bat_elo", "bowl_elo"]] = cs[["bat_elo", "bowl_elo"]].fillna(1500.0)
    cs["elo_diff"] = cs["bat_elo"] - cs["bowl_elo"]
    pr = attach_elo_provided(pr, cs, elo, pairs)
    cs, pr = model_frame(cs), model_frame(pr)
    tot = cs.groupby(["match_id", "innings"])["runs_total"].transform("sum")
    cs["rem_runs"] = tot - cs["score"]
    cs["fold"] = fold_of(cs["match_id"], NF)
    cfold = cs.drop_duplicates("match_id").set_index("match_id")["fold"]
    pr["fold"] = pr["cs_match"].map(cfold).fillna(-1).astype(int)
    for d in (cs, pr):
        d["bowler_wicket"] = d["bowler_wicket"].astype(int)
        d["batting_team_won"] = d["batting_team_won"].astype("float")
    return cs, pr


def holdout_metrics(cs: pd.DataFrame) -> dict:
    d = cs[cs["batting_team_won"].notna()]
    tr, va = d[d["date"] < "2024-01-01"], d[d["date"] >= "2024-01-01"]
    out = {}
    for name, feats in (("wp_v1_state_only", WP_FEATURES), ("wp_v2_context", WP2_FEATURES)):
        m = fit(tr[feats], tr["batting_team_won"], True)
        p = pred(m, va[feats])
        y = va["batting_team_won"].astype(int)
        out[name] = dict(auc=roc_auc_score(y, p), logloss=log_loss(y, p), brier=brier_score_loss(y, p))
        if name.endswith("context"):
            b = pd.cut(p, np.linspace(0, 1, 11), include_lowest=True)
            cal = pd.DataFrame({"p": p, "y": y.values}).groupby(b, observed=True).agg(
                pred=("p", "mean"), actual=("y", "mean"), n=("y", "size"))
            cal.to_csv(CTX / "wp_calibration.csv", index=False)
    return out


def score(d: pd.DataFrame, models: dict, table: pd.DataFrame) -> pd.DataFrame:
    """Out-of-fold predictions; fold -1 (no Cricsheet twin) uses the average of all fold models."""
    d = d.copy()
    cols = ["wp", "xr_bat", "xw_bat", "xr_bowl", "xw_bowl", "rem0", "rem1", "li_raw"]
    res = {c: np.zeros(len(d)) for c in cols}
    for k in sorted(d["fold"].unique()):
        pos = np.flatnonzero((d["fold"] == k).to_numpy())
        sub = d.iloc[pos]
        ms = [models[k]] if k >= 0 else [models[j] for j in range(NF)]

        def avg(name, X):
            return np.mean([pred(m[name], X) for m in ms], axis=0)

        def wp_fn(fr):
            """Main model, blended into the endgame model over the last 4 overs of a chase."""
            base = avg("wp", fr[WP2_FEATURES])
            m = ((fr["innings"] == 2) & (fr["balls_left"] <= 24)).to_numpy()
            if m.any():
                e = avg("wp_end", fr.loc[m, END_FEATURES])
                w = np.clip((24 - fr.loc[m, "balls_left"].to_numpy()) / 12, 0, 1)
                base[m] = (1 - w) * base[m] + w * e
            return base

        wp = wp_fn(sub)
        res["wp"][pos] = wp
        for n in ("xr_bat", "xw_bat", "xr_bowl", "xw_bowl"):
            res[n][pos] = avg(n, sub[CTX_FEATURES])
        nxt = sub[REM_FEATURES].copy()
        nxt["balls_left"] = (nxt["balls_left"] - 1).clip(lower=0)
        res["rem0"][pos] = avg("rem", nxt)
        nxt["wickets"] = nxt["wickets"] + 1
        res["rem1"][pos] = np.where(nxt["wickets"] >= 10, 0.0, avg("rem", nxt))
        res["li_raw"][pos] = leverage(sub, wp, wp_fn, table)
    for c in cols:
        d[c] = res[c]
    d["wcost"] = (d["rem0"] - d["rem1"]).clip(1.5, 9.0)   # capped: extreme states are extrapolation
    d["rv_bat"] = (d["runs_batter"] - d["xr_bat"]) - (d["striker_out"] - d["xw_bat"]) * d["wcost"]
    d["rv_bowl"] = -((d["bowler_runs"] - d["xr_bowl"]) - (d["bowler_wicket"] - d["xw_bowl"]) * d["wcost"])
    # win probability added
    g = d.groupby(["match_id", "innings"], sort=False)["wp"]
    nxt = g.shift(-1)
    inn2 = 1 - d[d["innings"] == 2].groupby("match_id")["wp"].first()
    end = np.where(d["innings"] == 1, d["match_id"].map(inn2), d["batting_team_won"])
    d["wp_after"] = nxt.fillna(pd.Series(end, index=d.index)).fillna(d["wp"])
    d["wpa"] = d["wp_after"] - d["wp"]
    return d.drop(columns=["rem0", "rem1"])


def main() -> None:
    t0 = time.time()
    cs, pr = prep()
    print(f"prepared: cricsheet {len(cs):,} | provided {len(pr):,} "
          f"(provided matches without twin: {pr[pr.fold < 0].match_id.nunique()})  [{time.time() - t0:.0f}s]")
    mpath = CTX / "metrics_ctx.json"
    metrics = json.loads(mpath.read_text()) if REUSE and mpath.exists() and "wp" not in REFIT else holdout_metrics(cs)
    print(json.dumps(metrics, indent=1))

    models: dict[int, dict] = {}
    for k in range(NF):
        tr = cs[cs["fold"] != k]
        models[k] = {}
        for name, (feats, target, filt, clf, kw) in SPECS.items():
            path = CTX / f"{name}_f{k}.json"
            if REUSE and path.exists() and name not in REFIT:
                models[k][name] = (xgb.XGBClassifier if clf else xgb.XGBRegressor)()
                models[k][name].load_model(str(path))
                continue
            d = tr[filt(tr)]
            models[k][name] = fit(d[feats], d[target], clf, **kw)
            models[k][name].save_model(str(path))
        print(f"fold {k} trained  [{time.time() - t0:.0f}s]")

    table = outcome_table(cs[cs["year"] >= 2018])
    table.to_csv(CTX / "outcome_table.csv")
    pr = score(pr, models, table)
    cs = score(cs, models, table)

    li_mean = float(pr["li_raw"].mean())
    for d in (pr, cs):
        d["li"] = d["li_raw"] / li_mean
        d["li_adj"] = d["li"] * np.where(d["is_knockout"] == 1, KNOCKOUT_MULT, 1.0)
        d["rule_pressure"] = rule_based_pressure(d)
    q = {f"q{int(x * 100)}": float(pr["li_adj"].quantile(x)) for x in (0.5, 0.7, 0.8, 0.85, 0.9)}
    (CTX / "pressure_def.json").write_text(json.dumps({"li_mean_raw": li_mean, "knockout_mult": KNOCKOUT_MULT, **q}, indent=1))
    for d in (pr, cs):
        d["pressure"] = d["li_adj"] >= q["q80"]

    # out-of-fold quality of the per-ball models on the supplied data
    f = pr[pr["faced"]]
    metrics["oof_on_supplied"] = dict(
        wp_auc=roc_auc_score(pr["batting_team_won"].dropna().astype(int), pr.loc[pr["batting_team_won"].notna(), "wp"]),
        xr_bat_bias=float((f["runs_batter"] - f["xr_bat"]).mean()),
        xw_bat_bias=float((f["striker_out"] - f["xw_bat"]).mean()),
        xr_bowl_bias=float((pr["bowler_runs"] - pr["xr_bowl"]).mean()),
        wcost_mean=float(pr["wcost"].mean()),
    )
    (CTX / "metrics_ctx.json").write_text(json.dumps(metrics, indent=1))
    print(json.dumps(metrics["oof_on_supplied"], indent=1), q)

    pr.to_parquet(PROCESSED / "provided_scored_v2.parquet", index=False)
    cs.to_parquet(PROCESSED / "cricsheet_scored_v2.parquet", index=False)
    print(f"done [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()
