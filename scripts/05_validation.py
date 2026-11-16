"""Reliability and sensitivity checks for the pressure ratings.

Writes reports/validation/validation.json plus CSV tables used by the report and dashboard.
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
from scipy.stats import pearsonr, spearmanr  # noqa: E402

from rr_pressure.paths import PROCESSED, REPORTS, TRAINED  # noqa: E402
from rr_pressure.ratings import Rater, player_match  # noqa: E402

OUT = REPORTS / "validation"
OUT.mkdir(parents=True, exist_ok=True)
RANK = REPORTS / "rankings"
SPLIT = "2025-01-01"


def wcorr(x, y, w):
    mx, my = np.average(x, weights=w), np.average(y, weights=w)
    return float(np.average((x - mx) * (y - my), weights=w)
                 / np.sqrt(np.average((x - mx) ** 2, weights=w) * np.average((y - my) ** 2, weights=w)))


def rate(pr, role, col="pressure", B=200, **kw):
    pm, meta = player_match(pr, role, col)
    R = Rater(pm, meta, **kw)
    return R, R.run(B=B)


def definition_evidence(pr: pd.DataFrame) -> dict:
    f = pr[pr["faced"]]

    def tab(g):
        return g.agg(balls=("is_legal", "sum"), strike_rate=("runs_batter", lambda x: 100 * x.mean()),
                     dot_pct=("runs_batter", lambda x: 100 * (x == 0).mean()),
                     boundary_pct=("runs_batter", lambda x: 100 * (x >= 4).mean()),
                     wicket_pct=("striker_out", lambda x: 100 * x.mean()),
                     mean_abs_wpa_pct=("wpa", lambda x: 100 * x.abs().mean()), mean_li=("li", "mean"))
    t = tab(f.groupby("pressure"))
    t.index = ["ordinary", "pressure"]
    t.round(3).to_csv(OUT / "pressure_vs_ordinary.csv")
    dec = tab(f.groupby(pd.qcut(f["li_adj"], 10, labels=False)))
    dec.round(3).to_csv(OUT / "outcomes_by_li_decile.csv")
    comp = pr.groupby(["innings", "phase"]).agg(balls=("li", "size"), mean_li=("li", "mean"),
                                                 share_pressure=("pressure", "mean"))
    comp["share_of_all_pressure"] = pr[pr.pressure].groupby(["innings", "phase"]).size() / pr.pressure.sum()
    comp.round(3).to_csv(OUT / "pressure_composition.csv")
    # match result link: how often does the side that wins the pressure balls win the match?
    m = pr[pr.pressure].groupby(["match_id", "batting_team"]).agg(wpa=("wpa", "sum"), won=("batting_team_won", "first"))
    m = m[m["won"].notna()]
    return {"pressure_vs_ordinary": t.round(3).to_dict("index"),
            "pressure_share_of_total_abs_wpa": float(pr.loc[pr.pressure, "wpa"].abs().sum() / pr["wpa"].abs().sum()),
            "team_won_pressure_wpa_and_match": float(((m["wpa"] > 0) == (m["won"] == 1)).mean()),
            "rule_overlap": {"p_li_given_rule": float(pr[pr.rule_pressure].pressure.mean()),
                             "p_rule_given_li": float(pr[pr.pressure].rule_pressure.mean()),
                             "rule_share": float(pr.rule_pressure.mean())}}


def split_half(R: Rater, reps: int = 40, seed: int = 3) -> dict:
    rng = np.random.default_rng(seed)
    e, M = R.elig, len(R.matches)
    out = {k: [] for k in ("composite", "level", "lift", "raw_level", "raw_lift")}
    for _ in range(reps):
        w = (rng.random(M) < 0.5).astype(float)
        a, b = R.components(R._agg(w))[e], R.components(R._agg(1 - w))[e]
        for k in ("composite", "level", "lift", "raw_level"):
            out[k].append(spearmanr(a[k], b[k])[0])
        out["raw_lift"].append(spearmanr(a["raw_level"] - a["raw_ordinary"], b["raw_level"] - b["raw_ordinary"])[0])
    res = {}
    for k, v in out.items():
        r = float(np.nanmean(v))
        res[k] = {"half_vs_half": round(r, 3), "full_sample_reliability": round(2 * r / (1 + r), 3)}
    return res


def holdout_prediction(pr: pd.DataFrame, role: str, reps: int = 30, seed: int = 5) -> dict:
    """Same-era test: estimate from a random half of the matches, predict pressure performance
    in the other half. Compares raw pressure stats with the shrunk estimates."""
    pm, meta = player_match(pr, role)
    R, R1 = Rater(pm, meta), Rater(pm, meta, borrow=False)
    e, M = R.elig, len(R.matches)
    rng = np.random.default_rng(seed)
    out = {k: [] for k in ("raw_pressure_average", "pressure_only_shrunk", "joint_shrunk_level (ours)", "ordinary_ball_average")}
    for _ in range(reps):
        w = (rng.random(M) < 0.5).astype(float)
        a, a1 = R.components(R._agg(w))[e], R1.components(R1._agg(w))[e]
        b = R._agg(1 - w)
        nb = b["n_p"][e]
        y = (b["r_p"][e] + b["w_p"][e]) / np.maximum(nb, 1)
        k = nb >= 30
        out["raw_pressure_average"].append(wcorr(a["raw_level"][k], y[k], nb[k]))
        out["pressure_only_shrunk"].append(wcorr(a1["level"][k], y[k], nb[k]))
        out["joint_shrunk_level (ours)"].append(wcorr(a["level"][k], y[k], nb[k]))
        out["ordinary_ball_average"].append(wcorr(a["raw_ordinary"][k], y[k], nb[k]))
    return {k: round(float(np.mean(v)), 3) for k, v in out.items()}


def persistence(pr: pd.DataFrame, role: str) -> dict:
    """Train on 2022-24, test on 2025-26: which estimate best predicts later pressure performance?"""
    A, Bp = pr[pr["date"] < SPLIT], pr[pr["date"] >= SPLIT]
    kw = dict(min_balls=60, min_matches=8, active_since=None)
    pmA, metaA = player_match(A, role)
    RA = Rater(pmA, metaA, **kw)
    cA = RA.components(RA.base)[RA.elig]
    RA1 = Rater(pmA, metaA, borrow=False, **kw)
    cA1 = RA1.components(RA1.base)[RA1.elig]
    pmB, _ = player_match(Bp, role)
    tb = pmB.groupby("pid")[["n_p", "r_p", "w_p", "n_o", "r_o", "w_o"]].sum()
    tb["s_p"], tb["s_o"] = tb["r_p"] + tb["w_p"], tb["r_o"] + tb["w_o"]
    tb = tb[tb["n_p"] >= 60]
    j = cA.join(tb, how="inner")
    y, w = j["s_p"] / j["n_p"], j["n_p"]
    yl = y - j["s_o"] / j["n_o"].clip(lower=1)
    return {"players": int(len(j)),
            "predict_later_pressure_level": {
                "raw_pressure_average": round(wcorr(j["raw_level"], y, w), 3),
                "pressure_only_shrunk": round(wcorr(cA1["level"].reindex(j.index), y, w), 3),
                "joint_shrunk_level (ours)": round(wcorr(j["level"], y, w), 3),
                "ordinary_ball_average": round(wcorr(j["raw_ordinary"], y, w), 3)},
            "lift_persistence": {"raw_lift_then_vs_later": round(wcorr(j["raw_level"] - j["raw_ordinary"], yl, w), 3),
                                 "shrunk_lift_then_vs_later": round(wcorr(j["lift"], yl, w), 3)}}


def sensitivity(pr: pd.DataFrame, role: str, primary: pd.DataFrame, q: dict) -> pd.DataFrame:
    variants = {}
    for name, thr in (("LI top 30%", q["q70"]), ("LI top 15%", q["q85"]), ("LI top 10%", q["q90"])):
        d = pr.assign(_p=pr["li_adj"] >= thr)
        variants[name] = rate(d, role, "_p")[1]
    d = pr.assign(_p=pr["li"] >= pr["li"].quantile(0.8))
    variants["no knockout multiplier"] = rate(d, role, "_p")[1]
    variants["rule-based pressure"] = rate(pr, role, "rule_pressure", min_balls=60, min_matches=10)[1]
    variants["pressure sample only (no borrowing)"] = rate(pr, role, borrow=False)[1]
    variants["level only (no lift)"] = rate(pr, role, weights={"level": 1.0, "lift": 0.0, "cons": 0.0})[1]
    variants["level 50 / lift 50"] = rate(pr, role, weights={"level": 0.5, "lift": 0.5, "cons": 0.0})[1]
    variants["no lift talent (kappa 0)"] = rate(pr, role, kappa=0.0)[1]
    variants["large lift talent (kappa 0.8)"] = rate(pr, role, kappa=0.8)[1]
    raw = pr.assign(vr_bat_adj=pr["vr_bat"], vw_bat_adj=pr["vw_bat"], vr_bowl_adj=pr["vr_bowl"], vw_bowl_adj=pr["vw_bowl"])
    variants["no opponent adjustment"] = rate(raw, role)[1]
    variants["IPL only"] = rate(pr[pr.is_ipl == 1], role, min_balls=60, min_matches=10)[1]
    variants["T20I only"] = rate(pr[pr.is_t20i == 1], role, min_balls=60, min_matches=10)[1]
    top = set(primary.index[:10])
    rows = []
    for name, v in variants.items():
        c = primary.index.intersection(v.index)
        rows.append({"variant": name, "players_compared": len(c),
                     "spearman_vs_primary": round(spearmanr(primary.loc[c, "score"], v.loc[c, "score"])[0], 3),
                     "primary_top10_in_variant_top10": len(top & set(v.index[:10])),
                     "primary_top10_in_variant_top20": len(top & set(v.index[:20])),
                     "variant_top10": "; ".join(v["name"].head(10))})
    return pd.DataFrame(rows)


def spot_checks(pr: pd.DataFrame) -> list[dict]:
    """Famous finishes: the LI peak should sit where the game was decided."""
    wanted = [("2023-05-29", "Chennai Super Kings", "IPL 2023 final, CSK chase v GT"),
              ("2023-04-09", "Kolkata Knight Riders", "IPL 2023, KKR chase v GT (Rinku Singh)"),
              ("2025-06-03", "Punjab Kings", "IPL 2025 final, PBKS chase v RCB"),
              ("2025-09-28", "India", "Asia Cup 2025 final, India chase v Pakistan")]
    out, keep = [], []
    for date, team, label in wanted:
        d = pr[(pr["date"].between(pd.Timestamp(date) - pd.Timedelta(days=1), pd.Timestamp(date) + pd.Timedelta(days=1)))
               & (pr["innings"] == 2) & (pr["batting_team"] == team)]
        if d.empty:
            continue
        d = d[d["match_id"] == d["match_id"].iloc[0]]
        pk = d.loc[d["li"].idxmax()]
        by_over = d.groupby("over")["li"].mean().round(2)
        out.append({"match": label, "balls": int(len(d)), "mean_li_first_10_overs": float(by_over[by_over.index < 10].mean()),
                    "mean_li_last_3_overs": float(by_over[by_over.index >= by_over.index.max() - 2].mean()),
                    "peak_li": float(pk["li"]), "peak_at_ball": int(pk["balls_bowled"]) + 1,
                    "peak_needed": f"{int(pk['runs_required'])} off {int(pk['balls_left'])}",
                    "wp_at_peak": float(pk["wp"]), "pressure_share": float(d["pressure"].mean())})
        keep.append(d[["match_id", "balls_bowled", "score", "wickets", "runs_required", "balls_left", "wp", "li",
                       "batter", "bowler", "runs_total", "is_wicket"]].assign(label=label))
    if keep:
        pd.concat(keep).to_csv(OUT / "spot_check_matches.csv", index=False)
    return out


def main() -> None:
    pr = pd.read_parquet(PROCESSED / "provided_final.parquet")
    q = json.loads((TRAINED / "ctx" / "pressure_def.json").read_text())
    res = {"pressure_definition": {**q, **definition_evidence(pr)}, "spot_checks": spot_checks(pr)}
    for role, fname in (("bat", "batters"), ("bowl", "bowlers")):
        primary = pd.read_csv(RANK / f"{fname}_full.csv", dtype={"pid": str}).set_index("pid")
        R, _ = rate(pr, role, B=2)
        sens = sensitivity(pr, role, primary, q)
        sens.to_csv(OUT / f"sensitivity_{fname}.csv", index=False)
        wpa_pb = primary["wpa_p"] / primary["balls_p"].clip(lower=1)
        res[fname] = {"split_half": split_half(R), "holdout_prediction": holdout_prediction(pr, role),
                      "persistence": persistence(pr, role),
                      "score_vs_pressure_wpa_per_ball": round(float(spearmanr(primary["score"], wpa_pb)[0]), 3),
                      "sensitivity": sens.drop(columns="variant_top10").to_dict("records")}
        print(f"\n=== {fname}")
        print(json.dumps({k: v for k, v in res[fname].items() if k != "sensitivity"}, indent=1))
        print(sens.to_string(index=False))
    (OUT / "validation.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res["pressure_definition"], indent=1, default=float))
    print(json.dumps(res["spot_checks"], indent=1, default=float))


if __name__ == "__main__":
    main()
