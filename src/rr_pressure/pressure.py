"""Pressure definition: Leverage Index (LI).

LI of a ball = expected absolute swing in the batting side's win probability over the ball's
possible outcomes, divided by the average swing of all balls. LI = 1 is an average ball;
LI = 2 means the result is twice as sensitive to what happens next.
(Same construction as baseball's Leverage Index, Tango et al., "The Book", 2007.)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

OUTCOMES = [("W", 0, 1), ("0", 0, 0), ("1", 1, 0), ("2", 2, 0), ("4", 4, 0), ("6", 6, 0)]
KNOCKOUT_MULT = 1.25


def shift_state(df: pd.DataFrame, runs: int, wicket: int) -> pd.DataFrame:
    """Match state after one more legal ball that yields `runs` / `wicket`."""
    s = df.copy()
    s["score"] = s["score"] + runs
    s["wickets"] = s["wickets"] + wicket
    s["wickets_in_hand"] = s["wickets_in_hand"] - wicket
    s["balls_bowled"] = s["balls_bowled"] + 1
    s["balls_left"] = (s["balls_left"] - 1).clip(lower=0)
    s["crr"] = 6 * s["score"] / s["balls_bowled"].clip(lower=1)
    chase = (s["innings"] == 2).to_numpy()
    rr = np.where(chase, s["target"] - s["score"], -1.0)
    s["runs_required"] = rr
    rrr = np.where(chase, 6 * rr / s["balls_left"].clip(lower=1), -1.0)
    s["rrr"] = rrr
    s["rrr_minus_crr"] = np.where(chase, rrr - s["crr"], -1.0)
    s["partnership_runs"] = 0 if wicket else s["partnership_runs"] + runs
    return s


def terminal_override(s: pd.DataFrame, wp: np.ndarray) -> np.ndarray:
    """Force known results for finished chases."""
    wp = wp.copy()
    chase = (s["innings"] == 2).to_numpy()
    req = s["runs_required"].to_numpy()
    done_win = chase & (req <= 0)
    out_of_balls = chase & (s["balls_left"].to_numpy() <= 0) & (req > 0)
    all_out = chase & (s["wickets"].to_numpy() >= 10) & (req > 0)
    wp[out_of_balls | all_out] = 0.0
    wp[(out_of_balls | all_out) & (req == 1)] = 0.5  # scores level -> super over
    wp[done_win] = 1.0
    return wp


def outcome_table(cs: pd.DataFrame) -> pd.DataFrame:
    """Empirical outcome frequencies by innings x phase x wickets-down bucket."""
    d = cs[cs["is_legal"]].copy()
    r = d["runs_total"].clip(upper=6).replace({3: 2, 5: 4})
    d["oc"] = np.where(d["is_wicket"], "W", r.astype(int).astype(str))
    d["wb"] = pd.cut(d["wickets"], [-1, 2, 5, 10], labels=[0, 1, 2]).astype(int)
    t = (d.groupby(["innings", "phase", "wb"])["oc"].value_counts(normalize=True)
           .unstack(fill_value=0.0))
    return t[[o for o, _, _ in OUTCOMES]]


def leverage(df: pd.DataFrame, wp_now: np.ndarray, predict_wp, table: pd.DataFrame) -> np.ndarray:
    """Raw leverage = sum_o p_o * |WP_o - mean WP| ; `predict_wp(frame)` returns WP for a state frame."""
    wb = pd.cut(df["wickets"], [-1, 2, 5, 10], labels=[0, 1, 2]).astype(int)
    idx = pd.MultiIndex.from_arrays([df["innings"], df["phase"], wb])
    probs = table.reindex(idx).to_numpy()
    probs = np.nan_to_num(probs, nan=1 / len(OUTCOMES))
    wps = np.zeros((len(df), len(OUTCOMES)))
    for j, (_, r, w) in enumerate(OUTCOMES):
        s = shift_state(df, r, w)
        wps[:, j] = terminal_override(s, predict_wp(s))
    mean = (probs * wps).sum(1, keepdims=True)
    return (probs * np.abs(wps - mean)).sum(1)


def rule_based_pressure(df: pd.DataFrame) -> pd.Series:
    """Plain cricketing definition used as an independent cross-check of LI."""
    chase = df["innings"] == 2
    late_chase = chase & (df["balls_left"] <= 36) & (df["rrr"] >= 10) & (df["rrr"] <= 18) & (df["wickets"] < 10)
    tight_finish = chase & (df["balls_left"] <= 24) & (df["runs_required"] <= 2.0 * df["balls_left"]) \
        & (df["runs_required"] >= 0.9 * df["balls_left"])
    collapse = (df["balls_bowled"] <= 60) & (df["wickets"] >= 3) & (df["balls_bowled"] <= 14 * df["wickets"])
    few_wkts = chase & (df["wickets"] >= 6) & (df["rrr"] >= 7) & (df["rrr"] <= 15)
    return late_chase | tight_finish | collapse | few_wkts
