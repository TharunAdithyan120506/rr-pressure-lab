"""Map provided player IDs -> Cricsheet registry identifiers.

Strategy
1. Pair each provided match with its Cricsheet twin (date within +/-1 day, identical innings
   totals and wicket counts).
2. Inside paired matches, align deliveries by (innings, over, legal-ball index) and vote:
   provided striker_id <-> cricsheet batter_id, provided bowler_id <-> cricsheet bowler_id.
3. Players never aligned fall back to exact full-name matches in Cricsheet's names register.
"""
from __future__ import annotations

import pandas as pd

from .paths import CRICSHEET


def _sig(df: pd.DataFrame) -> pd.DataFrame:
    s = (df.groupby(["match_id", "innings"])
           .agg(runs=("runs_total", "sum"), wk=("is_wicket", "sum"), date=("date", "first"))
           .reset_index()
           .pivot(index="match_id", columns="innings", values=["runs", "wk", "date"]))
    s.columns = [f"{a}{b}" for a, b in s.columns]
    s["date"] = pd.to_datetime(s["date1"])
    return s.drop(columns=[c for c in s.columns if c.startswith("date") and c != "date"]).reset_index()


def pair_matches(prov: pd.DataFrame, cs: pd.DataFrame) -> pd.DataFrame:
    cs = cs[cs["date"] >= prov["date"].min() - pd.Timedelta(days=2)]
    a, b = _sig(prov), _sig(cs)
    keys = ["runs1", "wk1", "runs2", "wk2"]
    a[keys] = a[keys].fillna(-1)
    b[keys] = b[keys].fillna(-1)
    m = a.merge(b, on=keys, suffixes=("_p", "_c"))
    m = m[(m["date_p"] - m["date_c"]).abs() <= pd.Timedelta(days=1)]
    m = m.drop_duplicates("match_id_p", keep=False).drop_duplicates("match_id_c", keep=False)
    return m[["match_id_p", "match_id_c"]]


def _ball_index(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["k"] = df.groupby(["match_id", "innings", "over"]).cumcount()
    return df


def build_player_map(prov: pd.DataFrame, cs: pd.DataFrame) -> pd.DataFrame:
    pairs = pair_matches(prov, cs)
    p = _ball_index(prov[prov["match_id"].isin(pairs["match_id_p"])])
    c = _ball_index(cs[cs["match_id"].isin(pairs["match_id_c"])])
    p = p.merge(pairs, left_on="match_id", right_on="match_id_p").drop(columns=["match_id", "match_id_p"])
    c = c.rename(columns={"match_id": "match_id_c"})
    j = p.merge(c, on=["match_id_c", "innings", "over", "k"], suffixes=("_p", "_c"))
    votes = pd.concat([
        j[["batter_id_p", "batter_p", "batter_id_c", "batter_c"]].set_axis(["pid", "pname", "cid", "cname"], axis=1),
        j[["bowler_id_p", "bowler_p", "bowler_id_c", "bowler_c"]].set_axis(["pid", "pname", "cid", "cname"], axis=1),
    ]).dropna(subset=["cid"])
    v = votes.groupby(["pid", "pname", "cid", "cname"]).size().rename("votes").reset_index()
    tot = v.groupby("pid")["votes"].transform("sum")
    v["share"] = v["votes"] / tot
    best = v.sort_values("votes", ascending=False).drop_duplicates("pid")
    best = best[best["share"] >= 0.6].assign(method="ball_alignment")

    # fallback: exact full-name match in the names register
    names = pd.read_csv(CRICSHEET / "register" / "names.csv")
    names["key"] = names["name"].str.lower().str.strip()
    allp = pd.concat([prov[["batter_id", "batter"]].set_axis(["pid", "pname"], axis=1),
                      prov[["bowler_id", "bowler"]].set_axis(["pid", "pname"], axis=1)]).drop_duplicates("pid")
    miss = allp[~allp["pid"].isin(best["pid"])].copy()
    miss["key"] = miss["pname"].str.lower().str.strip()
    uniq = names.drop_duplicates("key", keep=False)
    fb = miss.merge(uniq, on="key").rename(columns={"identifier": "cid", "name": "cname"})
    fb = fb.assign(votes=0, share=1.0, method="name_exact")[best.columns]

    out = pd.concat([best, fb], ignore_index=True)
    unmatched = allp[~allp["pid"].isin(out["pid"])].assign(method="unmatched")
    return pd.concat([out, unmatched], ignore_index=True), pairs
