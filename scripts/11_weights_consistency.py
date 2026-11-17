"""Choose the rating weights from the data, and test whether 'consistency' is a real player trait.

The brief asks for players who "deliver most consistently when it matters", measured "compared with
their usual performance levels". That is two claims to test, not assume:

  1. How much weight should Lift (pressure minus a player's own everyday level) carry next to Level
     (how good he is on pressure balls)? We pick the weight that best predicts a player's pressure
     performance in matches the estimate never saw, instead of choosing a number by hand.

  2. Is consistency a trait at all? We fit a dispersion model: after accounting for how many balls
     each player faced, do players differ in match-to-match volatility more than chance allows?

Writes reports/validation/weights_consistency.json
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
from scipy import optimize, stats  # noqa: E402

from rr_pressure.paths import PROCESSED, REPORTS  # noqa: E402
from rr_pressure.ratings import Rater, player_match  # noqa: E402

GRID = np.round(np.arange(0, 1.01, 0.05), 2)
REPS = 60
OUT = REPORTS / "validation"


def wcorr(x, y, w):
    mx, my = np.average(x, weights=w), np.average(y, weights=w)
    cov = np.average((x - mx) * (y - my), weights=w)
    return float(cov / np.sqrt(np.average((x - mx) ** 2, weights=w) * np.average((y - my) ** 2, weights=w)))


def weight_sweep(R: Rater, reps: int = REPS, seed: int = 17, min_test: int = 40) -> dict:
    """Estimate on a random half of the matches, predict pressure value per ball in the other half."""
    rng = np.random.default_rng(seed)
    e, M = R.elig, len(R.matches)
    acc = {w: [] for w in GRID}
    acc_raw, acc_ord = [], []
    for _ in range(reps):
        m = (rng.random(M) < 0.5).astype(float)
        a = R.components(R._agg(m))[e]
        b = R._agg(1 - m)
        n = b["n_p"][e]
        k = n >= min_test
        if k.sum() < 20:
            continue
        y = ((b["r_p"][e] + b["w_p"][e]) / np.maximum(n, 1))[k]
        zl, zf, nk = a["z_level"].to_numpy()[k], a["z_lift"].to_numpy()[k], n[k]
        for w in GRID:
            acc[w].append(wcorr(w * zl + (1 - w) * zf, y, nk))
        acc_raw.append(wcorr(a["raw_level"].to_numpy()[k], y, nk))
        acc_ord.append(wcorr(a["raw_ordinary"].to_numpy()[k], y, nk))
    curve = {float(w): float(np.mean(v)) for w, v in acc.items() if v}
    best = max(curve, key=curve.get)
    # standard error of the difference, so we can say which weights are indistinguishable
    bv = np.array(acc[round(best, 2)])
    within = []
    for w in GRID:
        v = np.array(acc[w])
        if len(v) == len(bv):
            d = bv - v
            se = d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else 0.0
            if d.mean() <= 1.96 * se:
                within.append(float(w))
    return {"curve": curve, "best_w_level": float(best), "best_corr": curve[best],
            "indistinguishable_from_best": within,
            "baseline_raw_pressure_mean": float(np.mean(acc_raw)),
            "baseline_ordinary_mean": float(np.mean(acc_ord)), "reps": len(bv)}


def consistency_test(pm: pd.DataFrame, R: Rater, min_balls: int = 8) -> dict:
    """Do players differ in match-to-match volatility beyond what sampling noise explains?

    Per player-match we have total pressure value s and balls n. Under a pure-noise model the
    within-player variance of s/n is sigma^2/n with sigma^2 common to all players. We fit a
    log-linear dispersion model, log sigma_i^2 = mu + u_i, and test whether var(u_i) > 0 by
    comparing the observed spread of each player's dispersion estimate with its sampling spread
    (a chi-square / Bartlett-style test).
    """
    d = pm[pm["n_p"] >= min_balls].copy()
    d.attrs = {}
    d["v"] = (d["r_p"] + d["w_p"]) / d["n_p"]
    elig = set(R.players[R.elig])
    d = d[d["pid"].isin(elig)]
    g = d.groupby("pid")
    keep = g["v"].size() >= 8
    d = d[d["pid"].isin(keep[keep].index)]
    g = d.groupby("pid")
    # player mean and weighted residual variance, scaled so each match contributes n * (v - mbar)^2
    mbar = g.apply(lambda t: np.average(t["v"], weights=t["n_p"]))
    d["res2"] = d["n_p"] * (d["v"] - d["pid"].map(mbar)) ** 2
    k = g.size()
    s2 = d.groupby("pid")["res2"].sum() / (k - 1)          # estimate of sigma_i^2 (runs^2 per ball)
    pooled = float(d["res2"].sum() / (k.sum() - len(k)))
    # Bartlett's test for equal variances across players
    stat = (k.sum() - len(k)) * np.log(pooled) - ((k - 1) * np.log(s2)).sum()
    cfac = 1 + (np.sum(1 / (k - 1)) - 1 / (k.sum() - len(k))) / (3 * (len(k) - 1))
    stat = float(stat / cfac)
    dof = len(k) - 1
    p = float(stats.chi2.sf(stat, dof))
    # how big is the spread of true dispersion, if any? var(log s2) minus its sampling variance
    obs = float(np.var(np.log(s2)))
    samp = float(np.mean(2 / (k - 1)))                      # var of log chi2_k/k is ~2/k
    tau2 = obs - samp
    # does dispersion persist? split a player's matches in two and correlate the two estimates
    rng = np.random.default_rng(5)
    rs = []
    for _ in range(40):
        d["h"] = rng.random(len(d)) < 0.5
        parts = []
        for h in (True, False):
            t = d[d["h"] == h]
            gg = t.groupby("pid")
            mb = gg.apply(lambda x: np.average(x["v"], weights=x["n_p"]))
            r2 = (t["n_p"] * (t["v"] - t["pid"].map(mb)) ** 2).groupby(t["pid"]).sum()
            cnt = gg.size()
            v = (r2 / (cnt - 1)).replace([np.inf, -np.inf], np.nan)
            parts.append(np.log(v.where(v > 0)))
        j = pd.DataFrame({"a": parts[0], "b": parts[1]}).dropna()
        j = j[j.index.isin(k[k >= 10].index)]
        if len(j) > 20:
            rs.append(stats.spearmanr(j.iloc[:, 0], j.iloc[:, 1])[0])
    return {"players": int(len(k)), "matches": int(len(d)),
            "pooled_sigma2_per_ball": pooled,
            "bartlett_chi2": stat, "dof": dof, "p_value": p,
            "var_log_dispersion_observed": obs, "expected_from_noise": samp,
            "excess_variance_tau2": tau2,
            "split_half_persistence_of_volatility": float(np.mean(rs)) if rs else None}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pr = pd.read_parquet(PROCESSED / "provided_final.parquet")
    res = {}
    for role, label in (("bat", "batters"), ("bowl", "bowlers")):
        pm, meta = player_match(pr, role)
        R = Rater(pm, meta)
        w = weight_sweep(R)
        c = consistency_test(pm, R)
        res[label] = {"weights": w, "consistency": c}
        print(f"\n=== {label}")
        print(f"  best Level weight {w['best_w_level']:.2f} (held-out r = {w['best_corr']:.3f}); "
              f"weights statistically indistinguishable from it: "
              f"{min(w['indistinguishable_from_best']):.2f}-{max(w['indistinguishable_from_best']):.2f}")
        print("  curve:", {k: round(v, 3) for k, v in w["curve"].items() if round(k * 20) % 2 == 0})
        print(f"  baselines: raw pressure {w['baseline_raw_pressure_mean']:.3f}, ordinary {w['baseline_ordinary_mean']:.3f}")
        print(f"  consistency: Bartlett chi2={c['bartlett_chi2']:.0f} dof={c['dof']} p={c['p_value']:.3g}; "
              f"excess var(log dispersion)={c['excess_variance_tau2']:.3f} "
              f"(observed {c['var_log_dispersion_observed']:.3f} v noise {c['expected_from_noise']:.3f}); "
              f"volatility split-half r={c['split_half_persistence_of_volatility']}")
    both = [res[l]["weights"]["best_w_level"] for l in ("batters", "bowlers")]
    res["recommended_w_level"] = float(np.mean(both))
    (OUT / "weights_consistency.json").write_text(json.dumps(res, indent=1))
    print(f"\nrecommended Level weight (mean of both roles): {res['recommended_w_level']:.2f}")


if __name__ == "__main__":
    main()
