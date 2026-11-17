"""Auction board: who is actually available on 16 December, and who RR should chase.

Uses the official 17 November retention lists (configs/retentions_2027.json) to work out the
auction pool, then ranks that pool with the pressure ratings, scores it against RR's remaining
needs, and checks our pre-deadline calls against what RR really did.

Writes reports/rr/auction.json
"""
from __future__ import annotations

import json
import sys
import unicodedata
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from rr_pressure.paths import PROCESSED, REPORTS, ROOT  # noqa: E402

OUT = REPORTS / "rr"
PURSE_TOTAL = 130.0     # reported 2027 auction purse (unconfirmed)
SQUAD_MAX, OVERSEAS_MAX = 25, 8


def _norm(n: str) -> str:
    n = unicodedata.normalize("NFKD", str(n)).encode("ascii", "ignore").decode().lower()
    return "".join(c for c in n if c.isalnum() or c == " ").strip()


def key(n: str) -> str:
    """One canonical key per player, whichever list the name came from."""
    k = _norm(n)
    return ALIAS.get(k, k)


ALIAS = {  # ratings-table name -> retention-list name
    "varun chakravarthy": "varun chakaravarthy", "mitchell marsh": "mitch marsh",
    "mitchell santner": "mitch santner", "namboori tilak varma": "tilak varma",
    "mohammed shami": "mohammad shami", "lhuandre pretorius": "lhuandre pretorius",
    "digvesh rathi": "digvesh singh rathi", "yash raj punja": "yash punja",
    "aman rao perala": "aman rao", "thangarasu natarajan": "t natarajan",
    "yudhvir singh charak": "yudhvir singh", "yash punja": "yash raj punja",
    "aman rao perala": "aman rao", "t natarajan": "thangarasu natarajan",
    "lhuandre pretorius": "lhuan dre pretorius", "mahendra singh dhoni": "ms dhoni",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ret = json.loads((ROOT / "configs" / "retentions_2027.json").read_text(encoding="utf-8"))
    squad = json.loads((ROOT / "configs" / "rr_squad.json").read_text(encoding="utf-8"))["players"]
    verd = json.loads((ROOT / "configs" / "rr_verdicts.json").read_text(encoding="utf-8"))
    bat = pd.read_csv(REPORTS / "rankings" / "batters_full.csv", dtype={"pid": str})
    bowl = pd.read_csv(REPORTS / "rankings" / "bowlers_full.csv", dtype={"pid": str})
    photos = json.loads((ROOT / "dashboard" / "photos" / "index.json").read_text(encoding="utf-8"))
    pmap = {key(k): v for k, v in photos.items()}

    rate = {}
    for t, role in ((bat, "bat"), (bowl, "bowl")):
        for _, r in t.iterrows():
            k = key(r["name"])
            rate.setdefault(k, {"name": r["name"]})[role] = {
                "rank": int(r["rank"]), "of": len(t), "rating": round(float(r["rating"]), 1),
                "level": round(float(r["level"]), 4), "lift": round(float(r["lift"]), 4),
                "n_p": int(r["n_p"]), "pct": round(100 * float((t["level"] < r["level"]).mean()), 1),
                **({"sr_p": round(float(r["sr_p"]), 1), "sr_o": round(float(r["sr_o"]), 1),
                    "avg_p": round(float(r["avg_p"]), 1)} if role == "bat" else
                   {"econ_p": round(float(r["econ_p"]), 2), "econ_o": round(float(r["econ_o"]), 2),
                    "wkts_p": int(r["wkts_p"])})}

    # ---- 1. scorecard: our 16 Nov calls vs what RR actually did on the 17th -------------------
    rr = ret["rr"]
    kept = {key(n) for n in rr["retained"]} | {key(t["name"]) for t in rr["traded_in"]}
    gone = {key(n) for n in rr["released"]} | {key(t["name"]) for t in rr["traded_out"]}
    traded = {key(t["name"]) for t in rr["traded_out"]}
    rows = []
    for p in squad:
        v = verd["players"][str(p["pid"])]
        k = key(p["name"])
        actual = "Retained" if k in kept else ("Traded out" if k in traded else
                                               ("Released" if k in gone else "Not listed"))
        ours = v["verdict"]
        agree = (ours == "Retain" and actual == "Retained") or \
                (ours in ("Release", "Release & rebuy") and actual == "Released") or \
                (ours == "Trade chip" and actual == "Traded out")
        rows.append({"pid": str(p["pid"]), "name": p["name"], "salary": p["salary"],
                     "ours": ours, "confidence": v["confidence"], "actual": actual, "agree": bool(agree),
                     "headline": v["headline"], "photo": pmap.get(k)})
    sc = pd.DataFrame(rows)
    agree_n = int(sc["agree"].sum())
    scorecard = {"players": len(sc), "agreed": agree_n, "rate": round(agree_n / len(sc), 3),
                 "by_confidence": {c: {"n": int((sc.confidence == c).sum()),
                                       "agreed": int(sc[sc.confidence == c]["agree"].sum())}
                                   for c in ("High", "Medium", "Low")},
                 "misses": sc[~sc["agree"]][["name", "ours", "actual", "confidence"]].to_dict("records"),
                 "rows": sc.to_dict("records")}

    # ---- 2. the auction pool: everyone released league-wide ------------------------------------
    pool = []
    for team, names in ret["notable_releases_by_team"].items():
        for n in names:
            clean = n.split(" (")[0].strip()
            pool.append({"name": clean, "released_by": team})
    for n in rr["released"]:
        pool.append({"name": n, "released_by": "RR"})
    seen, items = set(), []
    for p in pool:
        k = key(p["name"])
        if k in seen:
            continue
        seen.add(k)
        r = rate.get(k, {})
        best = max([r.get("bat", {}).get("pct", -1), r.get("bowl", {}).get("pct", -1)])
        items.append({**p, "photo": pmap.get(k), "bat": r.get("bat"), "bowl": r.get("bowl"),
                      "rated": bool(r), "best_pct": None if best < 0 else best})
    rated = [i for i in items if i["rated"]]
    rated.sort(key=lambda i: -(i["best_pct"] or 0))

    # ---- 3. RR's squad after retention, and what is missing -------------------------------------
    sal = {key(p["name"]): p["salary"] for p in squad}
    sal[key("Mohammed Shami")] = 10.0        # LSG's 2026 price, carried in the trade
    sal[key("Manimaran Siddharth")] = 0.3
    keep_rows = []
    for n in rr["retained"] + [t["name"] for t in rr["traded_in"]]:
        k = key(n)
        r = rate.get(k, {})
        keep_rows.append({"name": n, "salary": sal.get(k), "photo": pmap.get(k),
                          "bat": r.get("bat"), "bowl": r.get("bowl")})
    spent = float(np.nansum([k["salary"] or np.nan for k in keep_rows]))
    left = PURSE_TOTAL - spent
    n_kept = len(keep_rows)
    overseas_kept = ["Jofra Archer", "Nandre Burger", "Dasun Shanaka", "Donovan Ferreira", "Lhuan-dre Pretorius"]

    # ---- 4. needs, scored from the retained squad's own pressure numbers -------------------------
    def best_of(names, role):
        vals = [(n, rate.get(key(n), {}).get(role)) for n in names]
        return [(n, v) for n, v in vals if v]

    kb = best_of([k["name"] for k in keep_rows], "bowl")
    kt = best_of([k["name"] for k in keep_rows], "bat")
    needs = [
        {"need": "A death-overs bowler who does not leak under pressure",
         "evidence": "Of the bowlers RR kept, " + ", ".join(
             f"{n} goes at {v['econ_p']} on pressure balls against {v['econ_o']} otherwise"
             for n, v in sorted(kb, key=lambda x: -x[1]["n_p"])[:3]) + ".",
         "target_role": "bowl"},
        {"need": "A middle-order batter who can score against spin when the game tightens",
         "evidence": "RR's kept middle order drops under pressure: " + ", ".join(
             f"{n} {v['sr_p']:.0f} v {v['sr_o']:.0f}" for n, v in
             sorted([x for x in kt if x[1]["n_p"] >= 150], key=lambda x: x[1]["sr_p"] - x[1]["sr_o"])[:3]) + " (strike rate, pressure v ordinary).",
         "target_role": "bat"},
        {"need": "A second overseas quick to share the new ball with Archer",
         "evidence": "Only Burger and Shanaka remain overseas with the ball, and RR have "
                     f"{OVERSEAS_MAX - len(overseas_kept)} overseas slots open.",
         "target_role": "bowl"},
    ]

    # ---- 5. shortlist: pool players who answer a need ---------------------------------------------
    def short(role, n=8, min_balls=100):
        out = []
        for i in rated:
            r = i.get(role)
            if not r or r["n_p"] < min_balls:
                continue
            out.append({**{k: i[k] for k in ("name", "released_by", "photo")}, "role": role, **r,
                        "fit": round(r["pct"], 1)})
        return sorted(out, key=lambda x: -x["fit"])[:n]

    board = {"bowl": short("bowl"), "bat": short("bat")}

    data = {"generated": "2026-11-18", "purse": {"total": PURSE_TOTAL, "spent": round(spent, 2),
                                                 "left": round(left, 2), "kept": n_kept,
                                                 "slots": SQUAD_MAX - n_kept, "overseas_kept": len(overseas_kept),
                                                 "overseas_slots": OVERSEAS_MAX - len(overseas_kept)},
            "scorecard": scorecard, "retained": keep_rows, "needs": needs, "board": board,
            "pool_size": len(items), "pool_rated": len(rated),
            "pool": rated[:40], "auction": ret["auction"]}
    (OUT / "auction.json").write_text(json.dumps(data, indent=1, default=float), encoding="utf-8")

    print(f"our calls matched RR's actual list on {agree_n}/{len(sc)} players ({agree_n / len(sc):.0%})")
    print(" misses:", [f"{m['name']}: we said {m['ours']}, they {m['actual'].lower()}" for m in scorecard["misses"]])
    print(f"\nRR kept {n_kept}, committing ~Rs {spent:.1f} cr; ~Rs {left:.1f} cr left for {SQUAD_MAX - n_kept} slots")
    print(f"auction pool: {len(items)} released players league-wide, {len(rated)} of them rated by our model")
    for role in ("bowl", "bat"):
        print(f"\ntop {role} targets:")
        for b in board[role][:6]:
            extra = f"econ {b.get('econ_p')} under pressure" if role == "bowl" else f"SR {b.get('sr_p')} under pressure"
            print(f"  {b['name']:22s} ({b['released_by']:4s})  {b['pct']:.0f}th pct  {extra}")


if __name__ == "__main__":
    main()
