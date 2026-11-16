"""Submission sheet: the two ranked lists with the name spellings used by each source."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from rr_pressure.paths import PROCESSED, REPORTS  # noqa: E402


def main() -> None:
    pmap = pd.read_csv(PROCESSED / "player_id_map.csv", dtype=str).set_index("pid")
    lines = ["SupeRR Selector Season 2 - Round 1 submission",
             "Enter these in the Unstop dropdowns, rank 1 to 10. 'Also known as' lists other spellings of the same",
             "player, in case the dropdown uses a different one.", ""]
    for fname, label in (("batters", "TOP 10 BATTERS UNDER PRESSURE"), ("bowlers", "TOP 10 BOWLERS UNDER PRESSURE")):
        t = pd.read_csv(REPORTS / "rankings" / f"{fname}_full.csv", dtype={"pid": str}).head(10)
        lines += [label, "-" * len(label)]
        for _, r in t.iterrows():
            alt = pmap["cname"].get(r["pid"])
            alt = f"   (also known as: {alt})" if isinstance(alt, str) and alt != r["name"] else ""
            lines.append(f"{int(r['rank']):>2}. {r['name']:<24} {r['team']:<30} rating {r['rating']:.1f}{alt}")
        lines.append("")
    out = REPORTS / "SUBMISSION.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("wrote", out)


if __name__ == "__main__":
    main()
