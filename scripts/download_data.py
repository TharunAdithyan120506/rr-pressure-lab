"""Download open ball-by-ball T20 data from Cricsheet (https://cricsheet.org).

Cricsheet data is released under the Open Data Commons Attribution License (ODC-By 1.0).
The provided competition data covers 2022+; Cricsheet extends history back to 2005-2008,
which gives far richer player baselines and enough matches to train win-probability /
expected-runs models that define "pressure".

Usage:
    python scripts/download_data.py               # default set (IPL, T20I, major leagues)
    python scripts/download_data.py --only ipl t20i
    python scripts/download_data.py --force       # re-download
"""
from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "external" / "cricsheet"
BASE = "https://cricsheet.org/downloads/"

# key -> (zip filename, description)
DATASETS = {
    "ipl": ("ipl_male_json.zip", "Indian Premier League (2008-)"),
    "t20i": ("t20s_male_json.zip", "Men's T20 Internationals"),
    "bbl": ("bbl_male_json.zip", "Big Bash League"),
    "psl": ("psl_male_json.zip", "Pakistan Super League"),
    "cpl": ("cpl_male_json.zip", "Caribbean Premier League"),
    "sa20": ("sat_male_json.zip", "SA20"),
    "ilt20": ("ilt_male_json.zip", "International League T20"),
    "blast": ("ntb_male_json.zip", "Vitality T20 Blast"),
    "smat": ("sma_male_json.zip", "Syed Mushtaq Ali Trophy (Indian domestic T20)"),
    "lpl": ("lpl_male_json.zip", "Lanka Premier League"),
    "bpl": ("bpl_male_json.zip", "Bangladesh Premier League"),
    "mlc": ("mlc_male_json.zip", "Major League Cricket"),
}
REGISTER = {
    "people.csv": "https://cricsheet.org/register/people.csv",
    "names.csv": "https://cricsheet.org/register/names.csv",
}
UA = {"User-Agent": "rr-pressure-research/1.0 (python-urllib)"}


def fetch(url: str, dest: Path, force: bool) -> None:
    if dest.exists() and dest.stat().st_size > 0 and not force:
        print(f"  [skip] {dest.name} already present ({dest.stat().st_size/1e6:.1f} MB)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)
    tmp.replace(dest)
    print(f"  [ok]   {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")


def safe_extract(zip_path: Path, target: Path) -> int:
    """Extract only .json/.txt members, refusing path traversal."""
    target.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for m in z.infolist():
            name = Path(m.filename).name
            if m.is_dir() or not name.lower().endswith((".json", ".txt")):
                continue
            with z.open(m) as src, open(target / name, "wb") as dst:
                shutil.copyfileobj(src, dst)
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", choices=list(DATASETS), help="subset of datasets")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    keys = args.only or list(DATASETS)

    print("Player register:")
    for fname, url in REGISTER.items():
        fetch(url, OUT / "register" / fname, args.force)

    failed = []
    for key in keys:
        zname, desc = DATASETS[key]
        print(f"{key}: {desc}")
        zpath = OUT / "zips" / zname
        try:
            fetch(BASE + zname, zpath, args.force)
            n = safe_extract(zpath, OUT / key)
            print(f"  extracted {n} files -> data/external/cricsheet/{key}/")
        except Exception as e:  # network / 404 – keep going
            print(f"  [FAIL] {e}")
            failed.append(key)
    if failed:
        print("Failed:", failed)
    return 1 if failed and len(failed) == len(keys) else 0


if __name__ == "__main__":
    sys.exit(main())
