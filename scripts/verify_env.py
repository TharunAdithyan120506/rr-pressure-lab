"""Check that the environment, data, models and deliverables are all in place."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

PKGS = ["numpy", "pandas", "pyarrow", "scipy", "statsmodels", "sklearn", "xgboost", "lightgbm", "catboost",
        "torch", "tabpfn", "shap", "matplotlib", "docx"]
FILES = [
    ("data/raw/provided/ball_by_ball.csv", "supplied deliveries"),
    ("data/processed/provided_deliveries.parquet", "supplied data, normalised"),
    ("data/processed/cricsheet_deliveries.parquet", "Cricsheet data, normalised"),
    ("data/processed/player_id_map.csv", "player identity map"),
    ("data/processed/provided_scored_v2.parquet", "every ball with win probability and leverage"),
    ("data/processed/provided_final.parquet", "every ball with opponent-adjusted value"),
    ("models/trained/ctx/wp_f0.json", "win-probability model (fold 0)"),
    ("models/trained/ctx/metrics_ctx.json", "context-model metrics"),
    ("reports/rankings/batters_full.csv", "batter ratings"),
    ("reports/rankings/bowlers_full.csv", "bowler ratings"),
    ("reports/rankings/top10_batters.csv", "top 10 batters"),
    ("reports/rankings/top10_bowlers.csv", "top 10 bowlers"),
    ("reports/validation/validation.json", "reliability and sensitivity results"),
    ("reports/rr/cards.json", "player evidence cards"),
    ("reports/rr/squad_metrics.csv", "RR squad value table"),
    ("reports/research/sources.json", "research log"),
    ("reports/SUBMISSION.txt", "submission sheet"),
    ("reports/Methodology_Report.docx", "methodology report"),
    ("dashboard/index.html", "dashboard"),
    ("dashboard/data.js", "dashboard data"),
]


def main() -> int:
    bad = 0
    print(f"python {sys.version.split()[0]}")
    missing = []
    for p in PKGS:
        try:
            importlib.import_module(p)
        except Exception:
            missing.append(p)
    print(f"  [{'ok' if not missing else '!!'}] {len(PKGS) - len(missing)}/{len(PKGS)} packages" + (f" missing: {missing}" if missing else ""))
    bad += bool(missing)

    import torch
    print(f"  [{'ok' if torch.cuda.is_available() else '--'}] CUDA " +
          (torch.cuda.get_device_name(0) if torch.cuda.is_available() else "not available; everything runs on CPU"))

    for f, what in FILES:
        p = ROOT / f
        ok = p.exists()
        bad += not ok
        print(f"  [{'ok' if ok else '!!'}] {what:<42} {f}" + (f"  ({p.stat().st_size / 1e6:.1f} MB)" if ok else "  MISSING"))

    figs = list((ROOT / "reports" / "figures").glob("*.png"))
    photos = list((ROOT / "dashboard" / "photos").glob("*.png"))
    print(f"  [{'ok' if len(figs) >= 9 else '!!'}] {len(figs)} report figures · {len(photos)} dashboard photos")
    tab = list((ROOT / "models/pretrained/tabpfn").glob("*.safetensors"))
    print(f"  [{'ok' if tab else '--'}] TabPFN weights ({len(tab)} file{'s' if len(tab) != 1 else ''}; optional)")

    # consistency: the lists in the report, dashboard and submission must agree
    try:
        import pandas as pd
        data = json.loads((ROOT / "reports/rr/dashboard_data.json").read_text())
        sub = (ROOT / "reports/SUBMISSION.txt").read_text(encoding="utf-8")
        for key, fname in (("batters", "batters"), ("bowlers", "bowlers")):
            top = pd.read_csv(ROOT / f"reports/rankings/top10_{fname}.csv")["name"].tolist()
            assert len(set(top)) == 10, f"{fname}: duplicate player in the top 10"
            assert [p["name"] for p in data[key][:10]] == top, f"{fname}: dashboard disagrees with the rankings"
            for n in top:
                assert n in sub, f"{fname}: {n} missing from the submission sheet"
        print("  [ok] top-10 lists agree across rankings, dashboard and submission sheet; no duplicates")
    except Exception as e:
        bad += 1
        print(f"  [!!] consistency check failed: {e}")

    print("\nREADY" if not bad else f"\n{bad} problem(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
