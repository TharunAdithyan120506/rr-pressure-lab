"""Download IPL squad headshots listed in configs/ipl_photos.json into dashboard/photos/.

Images belong to the IPL / BCCI; they are used here only to illustrate an unofficial analysis.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "dashboard" / "photos"
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.iplt20.com/teams"}


def slug(name: str) -> str:
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")


def main() -> int:
    cfg = json.loads((ROOT / "configs" / "ipl_photos.json").read_text(encoding="utf-8"))
    DEST.mkdir(parents=True, exist_ok=True)
    force = "--force" in sys.argv
    index, ok, skip, fail = {}, 0, 0, []
    for name, path in cfg["players"].items():
        fn = f"{slug(name)}.png"
        index[name] = fn
        out = DEST / fn
        if out.exists() and out.stat().st_size > 1000 and not force:
            skip += 1
            continue
        url = cfg["base"].replace("{path}", urllib.parse.quote(path, safe=""))
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r, open(out, "wb") as f:
                shutil.copyfileobj(r, f)
            if out.stat().st_size < 1000:
                out.unlink()
                raise ValueError("empty image")
            ok += 1
        except Exception as e:
            fail.append((name, str(e)[:60]))
    (DEST / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(f"downloaded {ok}, already had {skip}, failed {len(fail)}")
    for n, e in fail[:10]:
        print("  FAIL", n, e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
