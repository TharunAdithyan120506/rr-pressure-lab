"""Match-context features shared by both data sources: era, competition tier, venue scoring
factor, team strength (Elo), and the per-ball targets used by the expectation models."""
from __future__ import annotations

import zlib

import numpy as np
import pandas as pd

from .features import WP_FEATURES

# state + era + competition + venue: used for expected runs / wickets (no team strength, so a
# player is not penalised or flattered for the team he plays in; opponents are handled later).
CTX_FEATURES = WP_FEATURES + ["year", "is_ipl", "venue_factor"]
# win probability additionally knows how strong the two teams are
WP2_FEATURES = CTX_FEATURES + ["bat_elo", "bowl_elo", "elo_diff"]
# crr is included so wicket cost compares like-for-like scoring so far (less confounding)
REM_FEATURES = ["balls_left", "wickets", "crr", "year", "is_ipl", "is_t20i", "venue_factor"]

ALIASES = {
    "royal challengers bangalore": "royal challengers bengaluru",
    "delhi daredevils": "delhi capitals",
    "kings xi punjab": "punjab kings",
    "rising pune supergiants": "rising pune supergiant",
    "united states of america": "usa", "u.s.a.": "usa",
    "united arab emirates": "uae", "u.a.e.": "uae",
}


def norm_team(s: pd.Series) -> pd.Series:
    out = s.fillna("").str.lower().str.strip()
    return out.replace(ALIASES)


def add_basic_context(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["year"] = df["date"].dt.year
    df["is_ipl"] = ((df["source"] == "cricsheet_ipl") | df["competition"].fillna("").str.startswith("IPL")).astype(int)
    df["is_t20i"] = (df["match_format"] == "T20I").astype(int)
    df["is_knockout"] = df["is_knockout"].fillna(0).astype(int)
    df["striker_out"] = (df["is_wicket"] & (df["player_out"] == df["batter_id"])).astype(int)
    df["bowler_runs"] = df["runs_batter"] + np.where(df["is_wide"] | df["is_noball"], df["runs_extras"], 0)
    df["faced"] = ~df["is_wide"]
    df["venue"] = df["venue"].fillna("unknown")
    # venue scoring factor: runs/ball above the same tier+year average, shrunk (k balls)
    base = df.groupby(["is_ipl", "is_t20i", "year"])["runs_total"].transform("mean")
    rel = df["runs_total"] - base
    g = rel.groupby(df["venue"])
    df["venue_factor"] = g.transform("sum") / (g.transform("count") + 1500)
    return df


FULL_MEMBERS = {"india", "australia", "england", "south africa", "new zealand", "pakistan", "sri lanka",
                "west indies", "bangladesh", "afghanistan", "ireland", "zimbabwe"}
ASSOCIATE_START = 1250.0   # associates start 250 below full members (~80% expected loss), clubs at 1500


def match_table(df: pd.DataFrame) -> pd.DataFrame:
    m = (df.groupby("match_id", sort=False)
           .agg(date=("date", "first"), t1=("batting_team", "first"), t2=("bowling_team", "first"),
                winner=("winner", "first"), intl=("is_t20i", "max")).reset_index())
    for c in ("t1", "t2", "winner"):
        m[c] = norm_team(m[c])
    return m


def compute_elo(matches: pd.DataFrame, k: float = 24.0) -> pd.DataFrame:
    """Pre-match Elo for both sides of every match (long format). `matches` from match_table()."""
    m = matches.sort_values("date", kind="stable")
    rating: dict[str, float] = {}

    def start(team: str, intl: int) -> float:
        return ASSOCIATE_START if intl and team not in FULL_MEMBERS else 1500.0
    rows = []
    for mid, date, t1, t2, w, intl in m[["match_id", "date", "t1", "t2", "winner", "intl"]].itertuples(index=False):
        r1 = rating.setdefault(t1, start(t1, intl))
        r2 = rating.setdefault(t2, start(t2, intl))
        e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
        n1, n2 = r1, r2
        if w in (t1, t2):
            s1 = 1.0 if w == t1 else 0.0
            n1, n2 = r1 + k * (s1 - e1), r2 - k * (s1 - e1)
            rating[t1], rating[t2] = n1, n2
        rows.append((mid, date, t1, r1, n1))
        rows.append((mid, date, t2, r2, n2))
    return pd.DataFrame(rows, columns=["match_id", "date", "team", "elo_pre", "elo_post"])


def attach_elo(df: pd.DataFrame, elo: pd.DataFrame, match_col: str = "match_id") -> pd.DataFrame:
    """Look up pre-match Elo by (match, team). `match_col` lets the supplied data use its Cricsheet twin."""
    key = elo.drop_duplicates(["match_id", "team"]).set_index(["match_id", "team"])["elo_pre"]
    df = df.copy()
    for side, col in (("batting_team", "bat_elo"), ("bowling_team", "bowl_elo")):
        idx = pd.MultiIndex.from_arrays([df[match_col], norm_team(df[side])])
        df[col] = key.reindex(idx).to_numpy()
    return df


def attach_elo_provided(pr: pd.DataFrame, cs: pd.DataFrame, elo: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    """Paired matches copy the Elo of their Cricsheet twin (by innings, so team spellings never
    matter); unpaired matches are in the Elo table under their own id."""
    pr = pr.copy()
    twin = pairs.set_index("match_id_p")["match_id_c"]
    pr["cs_match"] = pr["match_id"].map(twin)
    per_inn = cs.groupby(["match_id", "innings"])[["bat_elo", "bowl_elo"]].first()
    idx = pd.MultiIndex.from_arrays([pr["cs_match"], pr["innings"]])
    own = attach_elo(pr, elo)
    for col in ("bat_elo", "bowl_elo"):
        pr[col] = pd.Series(per_inn[col].reindex(idx).to_numpy(), index=pr.index).fillna(own[col]).fillna(1500.0)
    pr["elo_diff"] = pr["bat_elo"] - pr["bowl_elo"]
    return pr


def fold_of(match_ids: pd.Series, n: int = 5) -> np.ndarray:
    return match_ids.map(lambda s: zlib.crc32(str(s).encode()) % n).to_numpy()
