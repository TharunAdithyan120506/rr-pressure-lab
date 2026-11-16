"""Loaders that normalise the provided competition data and Cricsheet JSON into ``SCHEMA``."""
from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from .features import BOWLER_CREDITED, SCHEMA
from .paths import CRICSHEET, RAW

# --------------------------------------------------------------------------------------
# Provided dataset (IPL + T20I, 2022+)
# --------------------------------------------------------------------------------------
PROVIDED_NOBALL = {"Overstep", "other"}  # 'other' behaves as a no-ball re-bowl (verified in build)


def load_provided_tables(raw: Path = RAW) -> dict[str, pd.DataFrame]:
    names = ["ball_by_ball", "matches", "competitions", "teams", "playing_eleven",
             "competition_team_player_mapping", "RR_players"]
    return {n: pd.read_csv(raw / f"{n}.csv", low_memory=False) for n in names}


def load_provided(raw: Path = RAW) -> pd.DataFrame:
    t = load_provided_tables(raw)
    b, m, c = t["ball_by_ball"], t["matches"], t["competitions"]
    team_name = t["teams"].drop_duplicates("team_id").set_index("team_id")["team_name"]

    m = m.merge(c, on="comp_id", how="left")
    b = b[b["innings"].isin([1, 2])].merge(m, on="match_id", how="left")
    b = b.sort_values(["match_id", "innings", "innings_ball_num"], kind="stable")

    extras = b["extras_type"].fillna("None")
    is_wide = extras.eq("wide")
    is_nb = extras.isin(PROVIDED_NOBALL)
    kind = b["dismissal_type"].fillna("").str.lower().replace(
        {"stump": "stumped", "runout": "run out"})

    out = pd.DataFrame({
        "source": "provided",
        "match_id": "p" + b["match_id"].astype(str),
        "competition": b["comp_name"],
        "match_format": b["match_format"],
        "season": b["season"].astype(str),
        "date": pd.to_datetime(b["match_date"]),
        "venue": b["venue_id"].astype(str),
        "innings": b["innings"].astype(int),
        "over": b["overid"].astype(int) - 1,
        "batting_team": b["batting_team_id"].map(team_name),
        "bowling_team": b["bowling_team_id"].map(team_name),
        "batter": b["striker_name"], "non_striker": b["non_striker_name"], "bowler": b["bowler_name"],
        "batter_id": b["striker_id"].astype(str), "bowler_id": b["bowler_id"].astype(str),
        "runs_batter": b["runs"].astype(int),
        "runs_extras": (b["extras1_runs"].fillna(0) + b["extras_2_runs"].fillna(0)).astype(int),
        "is_wide": is_wide, "is_noball": is_nb, "is_legal": ~(is_wide | is_nb),
        "is_four": b["is_four"].astype(bool), "is_six": b["is_six"].astype(bool),
        "is_wicket": b["is_wicket"].astype(bool),
        "wicket_kind": kind.replace("", np.nan),
        "player_out": b["dismissed_player_id"].astype("Int64").astype(str).replace("<NA>", np.nan),
        "winner": b["win_team_id"].map(team_name),
        "is_knockout": b["knock_out"].fillna(0).astype(int),
        # extra provided-only context kept for analysis
        "pace_or_spin": b["pace_or_spin"], "bowling_type": b["bowling_type"],
        "batting_type": b["batting_type"], "batting_order": b["batting_order"],
    })
    out["runs_total"] = out["runs_batter"] + out["runs_extras"]
    out["bowler_wicket"] = out["is_wicket"] & out["wicket_kind"].isin(BOWLER_CREDITED)

    # innings length (balls) and chase target, honouring rain revisions
    first_tot = (out[out.innings == 1].groupby("match_id")["runs_total"].sum() + 1)
    mm = m.set_index("p" + m["match_id"].astype(str))
    rev_t = mm["revised_target"]
    out["target"] = np.where(out.innings == 2,
                             out["match_id"].map(rev_t).fillna(out["match_id"].map(first_tot)),
                             np.nan)
    out["innings_balls"] = np.where(out.innings == 1,
                                    out["match_id"].map(mm["first_inn_revised_overs"]),
                                    out["match_id"].map(mm["second_inn_revised_overs"]))
    out["innings_balls"] = pd.Series(out["innings_balls"]).fillna(120).values
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------------------
# Cricsheet JSON (all T20 history)
# --------------------------------------------------------------------------------------
LEAGUE_FORMAT = {"t20i": "T20I"}


def _parse_match(args: tuple[str, str]) -> list[dict]:
    path, league = args
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    info = d["info"]
    if info.get("gender") != "male":
        return []
    reg = info.get("registry", {}).get("people", {})
    outcome = info.get("outcome", {})
    winner = outcome.get("winner") or outcome.get("eliminator")
    event = info.get("event", {}) or {}
    stage = str(event.get("stage", "") or "")
    ko = int(any(k in stage.lower() for k in ("final", "qualifier", "eliminator", "semi")))
    mid = "c" + Path(path).stem
    teams = info.get("teams", [])
    default_balls = int(info.get("overs", 20)) * int(info.get("balls_per_over", 6))
    rows = []
    for inn_no, inn in enumerate(d.get("innings", []), start=1):
        if inn.get("super_over") or inn_no > 2:
            continue
        bat = inn["team"]
        bowl = next((t for t in teams if t != bat), None)
        tgt = inn.get("target", {})
        target = tgt.get("runs") if inn_no == 2 else None
        inn_balls = default_balls
        if tgt.get("overs"):
            o = float(tgt["overs"])
            inn_balls = int(o) * 6 + round((o - int(o)) * 10)
        for ov in inn.get("overs", []):
            for dl in ov["deliveries"]:
                ex = dl.get("extras", {})
                wk = dl.get("wickets", [])
                kind = wk[0]["kind"] if wk else None
                r = dl["runs"]
                rows.append({
                    "source": f"cricsheet_{league}", "match_id": mid,
                    "competition": event.get("name", league), "match_format": LEAGUE_FORMAT.get(league, "T20"),
                    "season": str(info.get("season")), "date": info["dates"][0], "venue": info.get("venue"),
                    "innings": inn_no, "over": ov["over"], "batting_team": bat, "bowling_team": bowl,
                    "batter": dl["batter"], "non_striker": dl["non_striker"], "bowler": dl["bowler"],
                    "batter_id": reg.get(dl["batter"]), "bowler_id": reg.get(dl["bowler"]),
                    "runs_batter": r["batter"], "runs_extras": r["extras"], "runs_total": r["total"],
                    "is_wide": "wides" in ex, "is_noball": "noballs" in ex,
                    "is_legal": not ("wides" in ex or "noballs" in ex),
                    "is_four": r["batter"] == 4 and not r.get("non_boundary"),
                    "is_six": r["batter"] == 6 and not r.get("non_boundary"),
                    "is_wicket": bool(wk), "wicket_kind": kind,
                    "player_out": reg.get(wk[0]["player_out"]) if wk else None,
                    "bowler_wicket": kind in BOWLER_CREDITED if kind else False,
                    "target": target, "innings_balls": inn_balls, "winner": winner, "is_knockout": ko,
                })
    return rows


def load_cricsheet(leagues: list[str] | None = None, root: Path = CRICSHEET, workers: int = 8) -> pd.DataFrame:
    leagues = leagues or sorted(p.name for p in root.iterdir()
                                if p.is_dir() and p.name not in ("zips", "register"))
    jobs = [(str(p), lg) for lg in leagues for p in sorted((root / lg).glob("*.json"))]
    rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(_parse_match, jobs, chunksize=64):
            rows.extend(r)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    # ~8% of chases carry no target in the JSON (and a few carry an impossible one):
    # fall back to first-innings total + 1.
    df["target"] = pd.to_numeric(df["target"], errors="coerce")
    i2 = df["innings"] == 2
    fallback = df["match_id"].map(df[df["innings"] == 1].groupby("match_id")["runs_total"].sum() + 1)
    df.loc[i2 & df["target"].isna(), "target"] = fallback
    g2 = df[i2].groupby("match_id")
    overshoot = g2["runs_total"].sum() - g2["target"].first()
    df.loc[i2 & df["match_id"].isin(overshoot[overshoot > 6].index), "target"] = fallback
    return df.reset_index(drop=True)[SCHEMA]
