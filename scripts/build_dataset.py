"""Build processed parquet datasets.

Outputs (data/processed/):
    provided_deliveries.parquet   provided IPL+T20I 2022+ data, normalised + match-state features
    cricsheet_deliveries.parquet  all downloaded Cricsheet T20 data, same schema + features
    player_id_map.csv             provided player_id -> Cricsheet registry id
    match_pairs.csv               provided match_id <-> Cricsheet match_id
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rr_pressure.features import add_match_state  # noqa: E402
from rr_pressure.loaders import load_cricsheet, load_provided  # noqa: E402
from rr_pressure.paths import PROCESSED  # noqa: E402
from rr_pressure.player_map import build_player_map  # noqa: E402


def main() -> None:
    t = time.time()
    prov = load_provided()
    # sanity: complete overs should contain 6 legal balls
    lc = prov.groupby(["match_id", "innings", "over"])["is_legal"].sum()
    print(f"provided: {len(prov):,} balls, {prov.match_id.nunique()} matches | "
          f"overs with 6 legal balls: {(lc == 6).mean():.1%}")
    prov = add_match_state(prov)
    prov.to_parquet(PROCESSED / "provided_deliveries.parquet", index=False)

    cs = load_cricsheet()
    print(f"cricsheet: {len(cs):,} balls, {cs.match_id.nunique()} matches, "
          f"{cs.date.min().date()} -> {cs.date.max().date()}")
    cs = add_match_state(cs.sort_values(["match_id", "innings"], kind="stable"))
    cs.to_parquet(PROCESSED / "cricsheet_deliveries.parquet", index=False)
    print(cs.groupby("source").match_id.nunique().to_string())

    pmap, pairs = build_player_map(prov, cs)
    pmap.to_csv(PROCESSED / "player_id_map.csv", index=False)
    pairs.to_csv(PROCESSED / "match_pairs.csv", index=False)
    print(f"matched {len(pairs)}/{prov.match_id.nunique()} provided matches to Cricsheet")
    print(pmap["method"].value_counts().to_string())
    print(f"done in {time.time() - t:.0f}s")


if __name__ == "__main__":
    main()
