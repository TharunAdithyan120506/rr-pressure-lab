import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw" / "provided"
EXTERNAL = DATA / "external"
CRICSHEET = EXTERNAL / "cricsheet"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
MODELS = ROOT / "models"
PRETRAINED = MODELS / "pretrained"
TRAINED = MODELS / "trained"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"

for _p in (INTERIM, PROCESSED, PRETRAINED, TRAINED, FIGURES):
    _p.mkdir(parents=True, exist_ok=True)

# TabPFN loads its weights from the project folder (models/pretrained/tabpfn)
os.environ.setdefault("TABPFN_MODEL_CACHE_DIR", str(PRETRAINED / "tabpfn"))
