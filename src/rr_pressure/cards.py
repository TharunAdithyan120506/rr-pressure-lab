"""Per-player evidence cards (stats + model outputs) used by the dashboard and the report."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .ratings import Rater, player_match
from .stats import bat_split, bowl_split

BAT_KEEP = ["balls", "runs", "outs", "sr", "avg", "bnd_pct", "dot_pct", "runs_vs_exp", "rv_per100", "wpa", "inns"]
BOWL_KEEP = ["balls", "runs", "wkts", "econ", "sr", "avg", "dot_pct", "bnd_pct", "runs_saved", "rv_per100", "wpa", "inns"]


def _row(t: pd.DataFrame, keep: list[str]) -> dict | None:
    if t.empty or t["balls"].iloc[0] == 0:
        return None
    r = t.iloc[0]
    return {k: (None if pd.isna(r[k]) else round(float(r[k]), 2)) for k in keep}


def _splits(d: pd.DataFrame, fn, keep: list[str]) -> dict:
    """Standard set of splits for one player's balls in one role."""
    out = {}
    one = d.assign(_k=1)
    out["all"] = _row(fn(one, ["_k"]), keep)
    out["pressure"] = _row(fn(one[one.pressure], ["_k"]), keep)
    out["ordinary"] = _row(fn(one[~one.pressure], ["_k"]), keep)
    out["ipl"] = _row(fn(one[one.is_ipl == 1], ["_k"]), keep)
    out["t20i"] = _row(fn(one[one.is_t20i == 1], ["_k"]), keep)
    out["ipl_2026"] = _row(fn(one[(one.is_ipl == 1) & (one.year == 2026)], ["_k"]), keep)
    out["ipl_pressure"] = _row(fn(one[(one.is_ipl == 1) & one.pressure], ["_k"]), keep)
    for col, name in (("phase", "phase"), ("pace_or_spin", "vs_type"), ("innings", "innings")):
        t = fn(d, [col])
        out[name] = {str(k): _row(t.loc[[k]], keep) for k in t.index}
        tp = fn(d[d.pressure], [col])
        out[name + "_pressure"] = {str(k): _row(tp.loc[[k]], keep) for k in tp.index}
    ty = fn(d[d.is_ipl == 1], ["year"])
    out["ipl_by_year"] = {str(int(k)): _row(ty.loc[[k]], keep) for k in ty.index}
    return out


class CardBuilder:
    def __init__(self, pr: pd.DataFrame):
        self.pr = pr
        self.raters, self.post = {}, {}
        for role in ("bat", "bowl"):
            pm, meta = player_match(pr, role)
            R = Rater(pm, meta)
            c = R.components(R.base)
            c["n_p"], c["n_o"], c["m_p"] = R.base["n_p"], R.base["n_o"], R.base["m_p"]
            c["eligible"] = R.elig
            e = c[c["eligible"]]
            c["level_pct"] = c["level"].map(lambda v: float((e["level"] < v).mean() * 100))
            c["ordinary_pct"] = c["ordinary"].map(lambda v: float((e["ordinary"] < v).mean() * 100))
            c["lift_pct"] = c["lift"].map(lambda v: float((e["lift"] < v).mean() * 100))
            self.raters[role], self.post[role] = R, c

    def model(self, role: str, pid: str) -> dict | None:
        c = self.post[role]
        if pid not in c.index:
            return None
        r = c.loc[pid]
        return {k: (bool(r[k]) if k == "eligible" else round(float(r[k]), 4)) for k in
                ("level", "ordinary", "lift", "level_runs", "level_wkt", "raw_level", "raw_ordinary",
                 "n_p", "n_o", "m_p", "level_pct", "ordinary_pct", "lift_pct", "eligible")}

    def moments(self, pid: str, role: str, n: int = 4) -> list[dict]:
        """Matches where the player moved win probability most on pressure balls."""
        pr = self.pr
        if role == "bat":
            d = pr[(pr["batter_id"] == pid) & pr["faced"] & pr["pressure"]]
            sign, opp = 1, "bowling_team"
        else:
            d = pr[(pr["bowler_id"] == pid) & pr["pressure"]]
            sign, opp = -1, "batting_team"
        if d.empty:
            return []
        g = d.groupby("match_id").agg(date=("date", "first"), comp=("competition", "first"), opp=(opp, "first"),
                                      balls=("is_legal", "sum"), runs=("runs_batter" if role == "bat" else "bowler_runs", "sum"),
                                      wk=("striker_out" if role == "bat" else "bowler_wicket", "sum"),
                                      wpa=("wpa", "sum"), li=("li", "mean"))
        g["wpa"] = sign * g["wpa"]
        best = g.nlargest(n, "wpa")
        worst = g.nsmallest(1, "wpa")
        rows = []
        for kind, t in (("best", best), ("worst", worst)):
            for _, r in t.iterrows():
                rows.append({"kind": kind, "date": str(r["date"].date()), "comp": r["comp"], "opp": r["opp"],
                             "balls": int(r["balls"]), "runs": int(r["runs"]), "wk": int(r["wk"]),
                             "wpa_pct": round(100 * float(r["wpa"]), 1), "li": round(float(r["li"]), 2)})
        return rows

    def card(self, pid: str) -> dict:
        pr = self.pr
        f = pr[(pr["batter_id"] == pid)]
        b = pr[(pr["bowler_id"] == pid)]
        out = {"pid": pid, "bat": None, "bowl": None}
        if len(f[f["faced"]]) > 0:
            out["bat"] = {"splits": _splits(f, bat_split, BAT_KEEP), "model": self.model("bat", pid),
                          "moments": self.moments(pid, "bat")}
        if len(b) > 0:
            out["bowl"] = {"splits": _splits(b, bowl_split, BOWL_KEEP), "model": self.model("bowl", pid),
                           "moments": self.moments(pid, "bowl")}
        return out


def cricsheet_form(cs: pd.DataFrame, cid: str, since: str = "2025-01-01") -> dict:
    """Recent T20 record across every Cricsheet league (domestic leagues and internationals)."""
    out = {}
    d = cs[(cs["batter_id"] == cid) & cs["faced"] & (cs["date"] >= since)]
    if len(d):
        g = d.groupby("source").agg(balls=("is_legal", "sum"), runs=("runs_batter", "sum"), outs=("striker_out", "sum"),
                                    inns=("match_id", "nunique"))
        g.loc["all"] = g.sum()
        g["sr"] = (100 * g["runs"] / g["balls"].clip(lower=1)).round(1)
        g["avg"] = (g["runs"] / g["outs"].clip(lower=1)).round(1)
        out["bat"] = {k.replace("cricsheet_", ""): {c: float(v) for c, v in r.items()} for k, r in g.iterrows()}
        p = d[d["pressure"]]
        if len(p):
            out["bat_pressure"] = {"balls": int(p["is_legal"].sum()), "sr": round(100 * p["runs_batter"].sum() / max(p["is_legal"].sum(), 1), 1),
                                   "avg": round(p["runs_batter"].sum() / max(p["striker_out"].sum(), 1), 1)}
    d = cs[(cs["bowler_id"] == cid) & (cs["date"] >= since)]
    if len(d):
        g = d.groupby("source").agg(balls=("is_legal", "sum"), runs=("bowler_runs", "sum"), wkts=("bowler_wicket", "sum"),
                                    inns=("match_id", "nunique"))
        g.loc["all"] = g.sum()
        g["econ"] = (6 * g["runs"] / g["balls"].clip(lower=1)).round(2)
        g["sr"] = (g["balls"] / g["wkts"].clip(lower=1)).round(1)
        out["bowl"] = {k.replace("cricsheet_", ""): {c: float(v) for c, v in r.items()} for k, r in g.iterrows()}
        p = d[d["pressure"]]
        if len(p):
            out["bowl_pressure"] = {"balls": int(p["is_legal"].sum()), "econ": round(6 * p["bowler_runs"].sum() / max(p["is_legal"].sum(), 1), 2),
                                    "wkts": int(p["bowler_wicket"].sum())}
    return out
