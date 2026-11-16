"""Shared ball-by-ball schema + match-state features.

Both the provided dataset and Cricsheet are normalised to the columns in ``SCHEMA`` and then
passed through :func:`add_match_state`, so every downstream model sees identical features.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SCHEMA = [
    "source", "match_id", "competition", "match_format", "season", "date", "venue",
    "innings", "over", "batting_team", "bowling_team",
    "batter", "non_striker", "bowler", "batter_id", "bowler_id",
    "runs_batter", "runs_extras", "runs_total", "is_wide", "is_noball", "is_legal",
    "is_four", "is_six", "is_wicket", "wicket_kind", "player_out", "bowler_wicket",
    "target", "innings_balls", "winner", "is_knockout",
]

BOWLER_CREDITED = {
    "caught", "bowled", "lbw", "stumped", "caught and bowled", "hit wicket",
}


def add_match_state(df: pd.DataFrame) -> pd.DataFrame:
    """Add pre-delivery state: score, wickets, balls left, required rate, phase, outcome label.

    Expects rows sorted in delivery order within (match_id, innings).
    """
    df = df.copy()
    g = df.groupby(["match_id", "innings"], sort=False)

    df["legal_ball_no"] = g["is_legal"].cumsum()                       # after this ball
    df["balls_bowled"] = df["legal_ball_no"] - df["is_legal"].astype(int)  # before this ball
    df["score"] = g["runs_total"].cumsum() - df["runs_total"]
    df["wickets"] = g["is_wicket"].cumsum() - df["is_wicket"].astype(int)
    df["wickets_in_hand"] = 10 - df["wickets"]
    df["innings_balls"] = df["innings_balls"].fillna(120)
    df["balls_left"] = (df["innings_balls"] - df["balls_bowled"]).clip(lower=0)
    df["crr"] = np.where(df["balls_bowled"] > 0, 6 * df["score"] / df["balls_bowled"].clip(lower=1), 0.0)

    chase = df["innings"] == 2
    df["runs_required"] = np.where(chase, df["target"] - df["score"], np.nan)
    df["rrr"] = np.where(chase, 6 * df["runs_required"] / df["balls_left"].clip(lower=1), np.nan)
    df["rrr_minus_crr"] = df["rrr"] - df["crr"]

    over = df["balls_bowled"] // 6
    df["phase"] = np.select([over < 6, over < 15], ["powerplay", "middle"], "death")

    # partnership / batter-level context
    df["wkt_seq"] = g["is_wicket"].cumsum() - df["is_wicket"].astype(int)
    pg = df.groupby(["match_id", "innings", "wkt_seq"], sort=False)
    df["partnership_runs"] = pg["runs_total"].cumsum() - df["runs_total"]
    bg = df.groupby(["match_id", "innings", "batter"], sort=False)
    df["batter_runs_before"] = bg["runs_batter"].cumsum() - df["runs_batter"]
    df["batter_balls_before"] = bg["is_legal"].cumsum() - df["is_legal"].astype(int)

    # outcome label for win-probability models
    df["batting_team_won"] = (df["winner"] == df["batting_team"]).astype("Int8")
    df.loc[df["winner"].isna(), "batting_team_won"] = pd.NA
    return df


# Feature set used by the win-probability / expected-runs models
WP_FEATURES = [
    "innings", "balls_bowled", "balls_left", "score", "wickets", "wickets_in_hand",
    "crr", "target", "runs_required", "rrr", "rrr_minus_crr",
    "partnership_runs", "is_t20i", "is_knockout",
]


def model_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["is_t20i"] = (out["match_format"] == "T20I").astype(int)
    out["is_knockout"] = out["is_knockout"].fillna(0).astype(int)
    for c in ("target", "runs_required", "rrr", "rrr_minus_crr"):
        out[c] = out[c].fillna(-1)
    return out
