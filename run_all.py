"""Run the whole pipeline end to end.

    .venv/Scripts/python run_all.py            # everything except the Cricsheet download
    .venv/Scripts/python run_all.py --download # including it
    .venv/Scripts/python run_all.py --from 04  # resume from a step
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
STEPS = [
    ("00", "download_data.py", "Cricsheet ball-by-ball data and player register"),
    ("01", "build_dataset.py", "normalise both sources, match state, player identity map"),
    ("02", "download_models.py", "TabPFN pretrained weights (optional, needs a Prior Labs key)"),
    ("03", "03_context_models.py", "win probability, expected runs, wickets, endgame; leverage"),
    ("04", "04_pressure_ratings.py", "opponent adjustment, talent model, bootstrap, rankings"),
    ("05", "05_validation.py", "split-half, held-out and sensitivity checks"),
    ("06", "06_rr_squad.py", "RR squad metrics and player evidence cards"),
    ("07", "07_export_dashboard.py", "dashboard data bundle"),
    ("08", "08_figures.py", "report figures"),
    ("09", "09_report.py", "methodology report (docx)"),
    ("10", "10_submission.py", "submission sheet"),
]
SKIP_BY_DEFAULT = {"00", "02"}


def main() -> int:
    args = sys.argv[1:]
    start = args[args.index("--from") + 1] if "--from" in args else "00"
    only_download = "--download" in args
    t0 = time.time()
    for num, script, what in STEPS:
        if num < start or (num in SKIP_BY_DEFAULT and not only_download and num != start):
            print(f"[{num}] skipped: {what}")
            continue
        print(f"\n=== [{num}] {script}: {what}")
        r = subprocess.run([PY, str(ROOT / "scripts" / script)], cwd=ROOT)
        if r.returncode:
            print(f"[{num}] FAILED (exit {r.returncode})")
            return r.returncode
    print(f"\nall steps done in {(time.time() - t0) / 60:.1f} min")
    return subprocess.run([PY, str(ROOT / "scripts" / "verify_env.py")], cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())
