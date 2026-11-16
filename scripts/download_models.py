"""Fetch pretrained model weights into models/pretrained/.

There are no public pretrained cricket models, so the domain models (win probability,
expected runs) are trained from scratch on Cricsheet data (scripts/train_baselines.py).
What *is* pretrained and useful here:

  * TabPFN (Prior Labs) – a transformer pretrained on millions of synthetic tabular tasks;
    strong zero-tuning classifier/regressor for small-sample problems such as per-player
    or per-venue sub-models. Weights are hosted on Hugging Face.

Run:  python scripts/download_models.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "models" / "pretrained" / "tabpfn"
DEST.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("TABPFN_MODEL_CACHE_DIR", str(DEST))


def _patch_windows_auth() -> None:
    """TabPFN's login waits on stdin with select.select(), which only works on Unix.

    Replace it on Windows with a loop that waits for the browser callback and also accepts
    a pasted API key via msvcrt (not echoed to the screen).
    """
    if os.name != "nt":
        return
    import msvcrt
    import time

    from tabpfn import browser_auth

    def _poll_for_token(auth_event, received_token):
        sys.stdout.write("Waiting for browser sign-in (or paste API key + Enter): ")
        sys.stdout.flush()
        buf: list[str] = []
        while not auth_event.is_set():
            while msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch in ("\r", "\n"):
                    tok = "".join(buf).strip()
                    if tok:
                        print()
                        return tok
                    buf.clear()
                elif ch == "\x03":
                    raise KeyboardInterrupt
                elif ch == "\x08":
                    if buf:
                        buf.pop()
                else:
                    buf.append(ch)
            time.sleep(0.2)
        print("\nBrowser sign-in received.")
        return received_token[0]

    browser_auth._poll_for_token = _poll_for_token


def main() -> int:
    import numpy as np
    _patch_windows_auth()
    ok = True
    try:
        from tabpfn import TabPFNClassifier, TabPFNRegressor
        rng = np.random.default_rng(0)
        X = rng.normal(size=(64, 4))
        y = (X[:, 0] > 0).astype(int)
        TabPFNClassifier(device="cpu").fit(X, y).predict_proba(X[:2])  # triggers weight download
        TabPFNRegressor(device="cpu").fit(X, X[:, 1]).predict(X[:2])
        print(f"[ok] TabPFN classifier + regressor weights cached in {DEST}")
    except Exception as e:
        ok = False
        print(f"[FAIL] TabPFN: {type(e).__name__}: {e}")
        print("  TabPFN weights are licence-gated: register at https://ux.priorlabs.ai/account,\n"
              "  accept the licence, copy your API key, then run this script in a normal terminal\n"
              "  and paste the key when prompted. The project works without TabPFN.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
