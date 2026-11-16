"""Figures for the methodology report (reports/figures/*.png)."""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from rr_pressure.paths import FIGURES, PROCESSED, REPORTS, TRAINED  # noqa: E402

PINK, BLUE, NAVY, MUTED, TRACK = "#E0187F", "#2A4FB0", "#0B1F4B", "#667089", "#E7EAF1"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": "#C9CFDD",
                     "axes.labelcolor": NAVY, "text.color": NAVY, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
                     "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlecolor": NAVY})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIGURES / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("figure:", name)


def fig_leverage(pr):
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.2))
    d = pr["li_adj"].clip(upper=6)
    ax[0].hist(d, bins=60, color=BLUE, alpha=.85)
    thr = json.loads((TRAINED / "ctx" / "pressure_def.json").read_text())["q80"]
    ax[0].axvline(thr, color=PINK, lw=2)
    ax[0].text(thr + .12, ax[0].get_ylim()[1] * .82, f"pressure cut-off\nLI = {thr:.2f}", color=PINK, fontsize=8, fontweight="bold")
    ax[0].set(xlabel="Leverage Index (1.0 = average ball)", ylabel="balls", title="How much is at stake, ball by ball")
    t = pr.groupby(["innings", "phase"])["li"].mean().unstack()[["powerplay", "middle", "death"]]
    x = np.arange(3)
    ax[1].bar(x - .19, t.loc[1], .36, color=BLUE, label="Batting first")
    ax[1].bar(x + .19, t.loc[2], .36, color=PINK, label="Chasing")
    ax[1].axhline(1, color=MUTED, ls=":", lw=1)
    ax[1].set(xticks=x, ylabel="average Leverage Index", title="Where the pressure sits")
    ax[1].set_xticklabels(["powerplay", "middle", "death"])
    ax[1].legend(frameon=False, fontsize=8)
    save(fig, "01_leverage")


def fig_separation(val):
    d = pd.read_csv(REPORTS / "validation" / "outcomes_by_li_decile.csv")
    fig, ax = plt.subplots(1, 3, figsize=(9, 2.9))
    x = np.arange(1, 11)
    for a, (c, lab, col) in zip(ax, [("strike_rate", "strike rate", BLUE), ("dot_pct", "dot balls (%)", NAVY),
                                     ("mean_abs_wpa_pct", "win probability moved per ball (%)", PINK)]):
        a.plot(x, d[c], color=col, lw=2, marker="o", ms=4)
        a.set(xlabel="leverage decile (10 = most at stake)", title=lab, xticks=[1, 4, 7, 10])
    save(fig, "02_separation")


def fig_calibration():
    c = pd.read_csv(TRAINED / "ctx" / "wp_calibration.csv")
    fig, ax = plt.subplots(figsize=(3.6, 3.4))
    ax.plot([0, 1], [0, 1], color=MUTED, ls=":", lw=1)
    ax.plot(c["pred"], c["actual"], color=BLUE, lw=2, marker="o", ms=5)
    ax.set(xlabel="predicted win probability", ylabel="actual win rate",
           title="Win-probability model\n(unseen 2024-26 matches)", xlim=(0, 1), ylim=(0, 1))
    save(fig, "03_calibration")


def fig_top10(fname, title, unit):
    t = pd.read_csv(REPORTS / "rankings" / f"{fname}_full.csv").head(10).iloc[::-1]
    sd = pd.read_csv(REPORTS / "rankings" / f"{fname}_full.csv")["score"].std()
    lo, hi, mid = 100 + 15 * t["lo"] / sd, 100 + 15 * t["hi"] / sd, t["rating"]
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    y = np.arange(len(t))
    ax.hlines(y, lo, hi, color="#B9C3DE", lw=4)
    ax.scatter(mid, y, color=NAVY, zorder=3, s=36)
    ax.axvline(100, color=MUTED, ls=":", lw=1)
    ax.set(yticks=y, xlabel="pressure rating (100 = average ranked player)", title=title)
    ax.set_yticklabels([f"{int(r['rank'])}. {r['name']}" for _, r in t.iterrows()], fontsize=8.5)
    for yi, (m, p) in enumerate(zip(mid, t["p_top10"])):
        ax.text(m, yi + .28, f"{m:.0f}  ·  {p:.0%} top-10", fontsize=7.5, color=MUTED, ha="center")
    ax.text(.99, .02, unit, transform=ax.transAxes, ha="right", fontsize=7.5, color=MUTED)
    save(fig, f"04_top10_{fname}")


def fig_pressure_vs_ordinary(fname, xlab, ylab, inv=False):
    t = pd.read_csv(REPORTS / "rankings" / f"{fname}_full.csv")
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    xo = t["econ_o"] if inv else t["sr_o"]
    xp = t["econ_p"] if inv else t["sr_p"]
    ax.scatter(xo, xp, s=18, color="#B9C3DE")
    top = t.head(10)
    ax.scatter(top["econ_o"] if inv else top["sr_o"], top["econ_p"] if inv else top["sr_p"], s=42, color=PINK, zorder=3)
    lims = [min(xo.min(), xp.min()) * .97, max(xo.max(), xp.max()) * 1.03]
    ax.plot(lims, lims, color=MUTED, ls=":", lw=1)
    for _, r in top.head(5).iterrows():
        ax.annotate(r["name"].split()[-1], (r["econ_o"] if inv else r["sr_o"], r["econ_p"] if inv else r["sr_p"]),
                    fontsize=7.5, color=NAVY, xytext=(4, 3), textcoords="offset points")
    ax.set(xlabel=xlab, ylabel=ylab, xlim=lims, ylim=lims,
           title=f"Pressure v ordinary balls\n({'bowlers' if inv else 'batters'}; pink = our top 10)")
    save(fig, f"05_scatter_{fname}")


def fig_reliability(val):
    fig, ax = plt.subplots(figsize=(6.2, 3.0))
    labels = ["Raw pressure\naverage", "Pressure sample\nonly, shrunk", "Our rating\n(borrows all balls)", "Everyday\nballs only"]
    keys = ["raw_pressure_average", "pressure_only_shrunk", "joint_shrunk_level (ours)", "ordinary_ball_average"]
    x = np.arange(4)
    for i, (role, col) in enumerate([("batters", BLUE), ("bowlers", PINK)]):
        v = [val[role]["holdout_prediction"][k] for k in keys]
        ax.bar(x + (i - .5) * .38, v, .36, color=col, label=role)
    ax.axhline(0, color=MUTED, lw=.8)
    ax.set(xticks=x, ylabel="correlation with later pressure results", title="What predicts pressure performance in unseen matches")
    ax.set_xticklabels(labels, fontsize=8)
    ax.legend(frameon=False, fontsize=8)
    save(fig, "06_reliability")


def fig_squad():
    t = pd.read_csv(REPORTS / "rr" / "squad_metrics.csv").sort_values("surplus_cr")
    t = t[(t["salary"] >= 0.5) | (t["surplus_cr"].abs() > 1)]
    fig, ax = plt.subplots(figsize=(6.6, 5.2))
    col = [PINK if v < 0 else BLUE for v in t["surplus_cr"]]
    ax.barh(t["name"], t["surplus_cr"], color=col, height=.68)
    ax.axvline(0, color=MUTED, lw=.9)
    ax.set(xlabel="output worth minus salary (Rs crore, IPL 2026)", title="RR squad: value against contract")
    for n, v in zip(t["name"], t["surplus_cr"]):
        ax.text(v + (.4 if v >= 0 else -.4), n, f"{v:+.1f}", va="center", ha="left" if v >= 0 else "right", fontsize=7.5, color=MUTED)
    ax.set_xlim(t["surplus_cr"].min() - 3, t["surplus_cr"].max() + 4)
    save(fig, "07_squad_value")


def main():
    pr = pd.read_parquet(PROCESSED / "provided_final.parquet", columns=["li", "li_adj", "innings", "phase"])
    val = json.loads((REPORTS / "validation" / "validation.json").read_text())
    fig_leverage(pr)
    fig_separation(val)
    fig_calibration()
    fig_top10("batters", "Top 10 batters under pressure", "bar = 90% range across 1,000 match resamples")
    fig_top10("bowlers", "Top 10 bowlers under pressure", "bar = 90% range across 1,000 match resamples")
    fig_pressure_vs_ordinary("batters", "strike rate, ordinary balls", "strike rate, pressure balls")
    fig_pressure_vs_ordinary("bowlers", "economy, ordinary balls", "economy, pressure balls", inv=True)
    fig_reliability(val)
    fig_squad()


if __name__ == "__main__":
    main()
