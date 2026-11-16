"""Model zoo for the pressure framework.

Pressure is defined from models of the match state:
  * Win-probability model  P(batting side wins | state)  -> leverage = how much one ball
    can swing win probability (high leverage == high pressure).
  * Expected-runs / wicket-risk models  E[runs | state], P(wicket | state)  -> player
    performance is measured *relative to expectation* in the same context.

Three families are provided so results can be cross-checked:
  1. Gradient boosting (LightGBM / XGBoost / CatBoost) – strong tabular baselines.
  2. ``WinProbMLP`` – PyTorch feed-forward net with monotonic-friendly inputs.
  3. ``InningsGRU`` – sequence model over the ball-by-ball trajectory of an innings.
"""
from __future__ import annotations

import numpy as np
import torch
from torch import nn


def device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


# --------------------------------------------------------------------------------------
# Gradient boosting factories
# --------------------------------------------------------------------------------------
def lgbm_classifier(**kw):
    import lightgbm as lgb
    params = dict(n_estimators=800, learning_rate=0.03, num_leaves=63, min_child_samples=200,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1)
    params.update(kw)
    return lgb.LGBMClassifier(**params)


def lgbm_regressor(**kw):
    import lightgbm as lgb
    params = dict(n_estimators=800, learning_rate=0.03, num_leaves=63, min_child_samples=200,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1)
    params.update(kw)
    return lgb.LGBMRegressor(**params)


def xgb_classifier(**kw):
    import xgboost as xgb
    params = dict(n_estimators=800, learning_rate=0.03, max_depth=6, subsample=0.8,
                  colsample_bytree=0.8, tree_method="hist", eval_metric="logloss",
                  device="cuda" if torch.cuda.is_available() else "cpu")
    params.update(kw)
    return xgb.XGBClassifier(**params)


def catboost_classifier(**kw):
    from catboost import CatBoostClassifier
    params = dict(iterations=1500, learning_rate=0.05, depth=6, verbose=0,
                  task_type="GPU" if torch.cuda.is_available() else "CPU")
    params.update(kw)
    return CatBoostClassifier(**params)


# --------------------------------------------------------------------------------------
# PyTorch models
# --------------------------------------------------------------------------------------
class WinProbMLP(nn.Module):
    """Tabular MLP -> logit of batting side winning (or any binary target)."""

    def __init__(self, n_features: int, hidden: tuple[int, ...] = (256, 128, 64), dropout: float = 0.1):
        super().__init__()
        layers, d = [], n_features
        for h in hidden:
            layers += [nn.Linear(d, h), nn.BatchNorm1d(h), nn.SiLU(), nn.Dropout(dropout)]
            d = h
        layers.append(nn.Linear(d, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


class InningsGRU(nn.Module):
    """Sequence model over an innings: per-ball state features -> per-ball win-prob logits.

    Input: (batch, balls, n_features) padded; returns (batch, balls) logits.
    Multi-task heads also predict next-ball runs (regression) and wicket (binary).
    """

    def __init__(self, n_features: int, hidden: int = 128, layers: int = 2, dropout: float = 0.1):
        super().__init__()
        self.inp = nn.Sequential(nn.Linear(n_features, hidden), nn.SiLU())
        self.gru = nn.GRU(hidden, hidden, num_layers=layers, batch_first=True, dropout=dropout)
        self.win = nn.Linear(hidden, 1)
        self.runs = nn.Linear(hidden, 1)
        self.wkt = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor):
        h, _ = self.gru(self.inp(x))
        return self.win(h).squeeze(-1), self.runs(h).squeeze(-1), self.wkt(h).squeeze(-1)


def train_mlp(X: np.ndarray, y: np.ndarray, X_val: np.ndarray, y_val: np.ndarray,
              epochs: int = 20, batch: int = 4096, lr: float = 2e-3, verbose: bool = True) -> WinProbMLP:
    """Minimal training loop (standardise X beforehand)."""
    dev = device()
    model = WinProbMLP(X.shape[1]).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=epochs * (len(X) // batch + 1))
    lossf = nn.BCEWithLogitsLoss()
    Xt, yt = torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)
    Xv, yv = torch.tensor(X_val, dtype=torch.float32, device=dev), torch.tensor(y_val, dtype=torch.float32, device=dev)
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(Xt))
        for i in range(0, len(Xt), batch):
            idx = perm[i:i + batch]
            xb, yb = Xt[idx].to(dev), yt[idx].to(dev)
            opt.zero_grad()
            loss = lossf(model(xb), yb)
            loss.backward()
            opt.step()
            sched.step()
        if verbose:
            model.eval()
            with torch.no_grad():
                vl = lossf(model(Xv), yv).item()
            print(f"epoch {ep + 1:02d}  val_logloss={vl:.4f}")
    return model
