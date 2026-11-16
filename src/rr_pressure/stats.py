"""Conventional batting / bowling splits used as evidence next to the model ratings."""
from __future__ import annotations

import numpy as np
import pandas as pd

def bat_split(d: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    d = d[d["faced"]]
    g = d.groupby(by, observed=True)
    t = g.agg(balls=("is_legal", "sum"), runs=("runs_batter", "sum"), outs=("striker_out", "sum"),
              fours=("is_four", "sum"), sixes=("is_six", "sum"),
              dots=("runs_batter", lambda x: (x == 0).sum()), xruns=("xr_bat", "sum"),
              rv=("rv_bat_adj", "sum"), wpa=("wpa", "sum"), inns=("match_id", "nunique"))
    t["sr"] = 100 * t["runs"] / t["balls"].clip(lower=1)
    t["avg"] = t["runs"] / t["outs"].clip(lower=1)
    t["bnd_pct"] = 100 * (t["fours"] + t["sixes"]) / t["balls"].clip(lower=1)
    t["dot_pct"] = 100 * t["dots"] / t["balls"].clip(lower=1)
    t["bpd"] = t["balls"] / t["outs"].clip(lower=1)
    t["runs_vs_exp"] = t["runs"] - t["xruns"]
    t["rv_per100"] = 100 * t["rv"] / t["balls"].clip(lower=1)
    return t


def bowl_split(d: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    g = d.groupby(by, observed=True)
    t = g.agg(balls=("is_legal", "sum"), runs=("bowler_runs", "sum"), wkts=("bowler_wicket", "sum"),
              dots=("bowler_runs", lambda x: (x == 0).sum()),
              bnd=("runs_batter", lambda x: (x >= 4).sum()), xruns=("xr_bowl", "sum"),
              rv=("rv_bowl_adj", "sum"), wpa=("wpa", lambda x: -x.sum()), inns=("match_id", "nunique"))
    t["econ"] = 6 * t["runs"] / t["balls"].clip(lower=1)
    t["sr"] = t["balls"] / t["wkts"].clip(lower=1)
    t["avg"] = t["runs"] / t["wkts"].clip(lower=1)
    t["dot_pct"] = 100 * t["dots"] / t["balls"].clip(lower=1)
    t["bnd_pct"] = 100 * t["bnd"] / t["balls"].clip(lower=1)
    t["runs_saved"] = t["xruns"] - t["runs"]
    t["rv_per100"] = 100 * t["rv"] / t["balls"].clip(lower=1)
    return t


def wide(t: pd.DataFrame, flag: str = "pressure") -> pd.DataFrame:
    """(player, flag) rows -> one row per player with _p / _o suffixes."""
    u = t.unstack(flag)
    u.columns = [f"{c}_{'p' if f else 'o'}" for c, f in u.columns]
    return u
