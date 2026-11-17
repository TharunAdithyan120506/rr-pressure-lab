"""Player pressure ratings.

Pipeline
1. add_components     per-ball value split into a RUNS part and a WICKET part (both in runs),
                      centred within competition tier x season x innings x phase.
2. opponent_adjust    ridge "adjusted plus-minus" on each part: credit for opponent quality.
3. player_match       per (player, match) sums in pressure / ordinary balls.
4. Rater              multivariate empirical-Bayes shrinkage of four talents per player
                      (runs & wicket value, under pressure & in ordinary play), then
                      Level and Lift -> composite; cluster bootstrap over matches ->
                      confidence band, P(top 10) and the conservative final score.

Why four talents: run-scoring value is highly repeatable (split-half r ~ 0.7 for batters) while
dismissal value is much noisier (~0.3) and the two trade off. Shrinking them separately lets
each count in proportion to how much real signal it carries.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold

# Level = estimated true pressure performance; Lift = pressure minus the player's own everyday level.
# The split is not hand-picked. scripts/11_weights_consistency.py sweeps it and measures how well
# each mix predicts a player's pressure performance in matches the estimate never saw. The curve is
# flat near its peak, so a band of weights is statistically indistinguishable from the optimum
# (batters: optimum 0.65, band from 0.50;
# bowlers: optimum 0.90, band from 0.60). The brief asks explicitly for
# performance "compared with their usual performance levels", so we take the midpoint between the
# optimum and the most Lift-leaning weight the data still supports.
WEIGHTS = {"level": 0.6, "lift": 0.4}                      # batters
WEIGHTS_BOWL = {"level": 0.75, "lift": 0.25}                 # bowlers
ROLE_WEIGHTS = {"bat": WEIGHTS, "bowl": WEIGHTS_BOWL}
MIN_PRESSURE_BALLS = 100
MIN_PRESSURE_MATCHES = 15
ACTIVE_SINCE = "2025-01-01"
HYPER_MIN_P, HYPER_MIN_O = 50, 150   # pool used to estimate the talent covariance
# Pressure talent = ordinary talent + lift. KAPPA is the spread of lift relative to the spread
# of ordinary talent. Its likelihood is flat between ~0 and ~0.8 (best fit 0.4-0.6 for every
# pressure cut-off tested), so it is fixed at 0.5 rather than re-estimated per run.
KAPPA = 0.5
MIN_BALLS_MATCH = 3          # pressure balls in a match for it to count as a "pressure appearance"
RECENTER_KEYS = ["is_ipl", "is_t20i", "year", "innings", "phase"]


# --------------------------------------------------------------------------------------
# 1. value components
# --------------------------------------------------------------------------------------
def add_components(pr: pd.DataFrame) -> pd.DataFrame:
    """Runs and wicket value per ball, relative to the same tier, season, innings and phase.

    The expectation models are trained on all T20 cricket; the supplied T20Is are mostly
    full-member games where scoring runs higher, so raw values carry a tier offset that the
    centring removes.
    """
    pr = pr.copy()
    f = pr["faced"]
    pr["vr_bat"] = np.where(f, pr["runs_batter"] - pr["xr_bat"], 0.0)
    pr["vw_bat"] = np.where(f, -(pr["striker_out"] - pr["xw_bat"]) * pr["wcost"], 0.0)
    pr["vr_bowl"] = -(pr["bowler_runs"] - pr["xr_bowl"])
    pr["vw_bowl"] = (pr["bowler_wicket"] - pr["xw_bowl"]) * pr["wcost"]
    for c in ("vr_bat", "vw_bat"):
        m = pr[f].groupby(RECENTER_KEYS)[c].transform("mean")
        pr.loc[f, c] = pr.loc[f, c] - m
    for c in ("vr_bowl", "vw_bowl"):
        pr[c] = pr[c] - pr.groupby(RECENTER_KEYS)[c].transform("mean")
    pr["rv_bat"] = pr["vr_bat"] + pr["vw_bat"]
    pr["rv_bowl"] = pr["vr_bowl"] + pr["vw_bowl"]
    return pr


# --------------------------------------------------------------------------------------
# 2. opponent adjustment
# --------------------------------------------------------------------------------------
ELO_SCALE = 30.0   # the team-strength column is up-weighted so the ridge penalty leaves it ~unshrunk


def _ridge_effects(d: pd.DataFrame, y: str, opp_elo: str, alphas=(100, 300, 1000, 3000)):
    """value ~ batter effect + bowler effect + opposition team strength (Elo)."""
    bi, bnames = pd.factorize(d["batter_id"])
    wi, wnames = pd.factorize(d["bowler_id"])
    n, nb, nw = len(d), len(bnames), len(wnames)
    ez = ((d[opp_elo] - 1500.0) / 100.0).to_numpy()
    X = sparse.csr_matrix((np.r_[np.ones(2 * n), ez * ELO_SCALE],
                           (np.r_[np.arange(n), np.arange(n), np.arange(n)], np.r_[bi, nb + wi, np.full(n, nb + nw)])),
                          shape=(n, nb + nw + 1))
    yv = d[y].to_numpy()
    best, best_a = np.inf, alphas[0]
    for a in alphas:
        err = 0.0
        for tr, te in GroupKFold(4).split(X, yv, d["match_id"]):
            m = Ridge(alpha=a, solver="sparse_cg", max_iter=200, tol=1e-4).fit(X[tr], yv[tr])
            err += ((yv[te] - m.predict(X[te])) ** 2).sum()
        if err < best:
            best, best_a = err, a
    m = Ridge(alpha=best_a, solver="sparse_cg", max_iter=500, tol=1e-5).fit(X, yv)
    elo_coef = m.coef_[-1] * ELO_SCALE          # value per 100 Elo points of opposition strength
    return pd.Series(m.coef_[:nb], index=bnames), pd.Series(m.coef_[nb:nb + nw], index=wnames), best_a, elo_coef


def opponent_adjust(pr: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Add *_adj columns (value net of opponent quality) and return overall player quality.

    Two layers of opponent credit: the individual opponent (bowler faced / batter bowled to)
    and the strength of the opposing team (Elo), which covers opponents with too few balls
    to be rated individually - mostly associate-nation players.
    """
    pr = add_components(pr)
    f = pr[pr["faced"]]
    info = {"alpha": {}, "elo_coef_per_100": {}}
    bat_q = bowl_q = 0.0
    ez_bowl = (pr["bowl_elo"] - 1500.0) / 100.0      # strength of the side bowling at the batter
    ez_bat = (pr["bat_elo"] - 1500.0) / 100.0        # strength of the side batting against the bowler
    for c in ("vr_bat", "vw_bat"):
        own, opp, a, k = _ridge_effects(f, c, "bowl_elo")          # opp = bowler's effect on batter value
        pr[c + "_adj"] = np.where(pr["faced"], pr[c] - pr["bowler_id"].map(opp).fillna(0.0) - k * ez_bowl, 0.0)
        bat_q, info["alpha"][c], info["elo_coef_per_100"][c] = bat_q + own, a, float(k)
    for c in ("vr_bowl", "vw_bowl"):
        opp, own, a, k = _ridge_effects(pr, c, "bat_elo")          # opp = batter's effect on bowler value
        pr[c + "_adj"] = pr[c] - pr["batter_id"].map(opp).fillna(0.0) - k * ez_bat
        bowl_q, info["alpha"][c], info["elo_coef_per_100"][c] = bowl_q + own, a, float(k)
    # centre the adjusted values again so the average ball is still worth zero
    for c in ("vr_bat_adj", "vw_bat_adj"):
        pr.loc[pr["faced"], c] -= pr.loc[pr["faced"], c].mean()
    for c in ("vr_bowl_adj", "vw_bowl_adj"):
        pr[c] -= pr[c].mean()
    pr["rv_bat_adj"] = pr["vr_bat_adj"] + pr["vw_bat_adj"]
    pr["rv_bowl_adj"] = pr["vr_bowl_adj"] + pr["vw_bowl_adj"]
    info.update(bat_quality=bat_q, bowl_quality=bowl_q)
    return pr, info


# --------------------------------------------------------------------------------------
# 3. per player-match table
# --------------------------------------------------------------------------------------
def player_match(pr: pd.DataFrame, role: str, pressure_col: str = "pressure") -> tuple[pd.DataFrame, pd.DataFrame]:
    if role == "bat":
        d, pid, name = pr[pr["faced"]], "batter_id", "batter"
    else:
        d, pid, name = pr, "bowler_id", "bowler"
    p = d[pressure_col].to_numpy().astype(float)
    r, w = d[f"vr_{role}_adj"].to_numpy(), d[f"vw_{role}_adj"].to_numpy()
    t = pd.DataFrame({"pid": d[pid].to_numpy(), "match_id": d["match_id"].to_numpy(),
                      "n_p": p, "r_p": r * p, "w_p": w * p,
                      "n_o": 1 - p, "r_o": r * (1 - p), "w_o": w * (1 - p),
                      "wpa_p": d["wpa"].to_numpy() * p * (1 if role == "bat" else -1)})
    pm = t.groupby(["pid", "match_id"], sort=False).sum().reset_index()
    pm["app"] = (pm["n_p"] >= MIN_BALLS_MATCH).astype(float)
    pm["pos"] = pm["app"] * ((pm["r_p"] + pm["w_p"]) > 0)
    meta = d.groupby(pid).agg(name=(name, "last"), last_date=("date", "max"),
                              ipl_share=("is_ipl", "mean")).rename_axis("pid")
    # per-ball sampling covariance of (runs part, wicket part) in each condition
    X = np.c_[r, w]
    pm.attrs["C_p"] = np.cov(X[p == 1].T)
    pm.attrs["C_o"] = np.cov(X[p == 0].T)
    return pm, meta


# --------------------------------------------------------------------------------------
# 4. rating + bootstrap
# --------------------------------------------------------------------------------------
A_LEVEL = np.array([1.0, 1.0, 0.0, 0.0])
A_ORD = np.array([0.0, 0.0, 1.0, 1.0])


def _psd(A: np.ndarray) -> np.ndarray:
    ev, V = np.linalg.eigh((A + A.T) / 2)
    return (V * np.clip(ev, 1e-8, None)) @ V.T


@dataclass
class Rater:
    """Hierarchical model:  x_i ~ N(theta_i, D_i),  theta_i ~ N(mu, Sigma)

    x_i     observed per-ball means of player i: (runs value, wicket value) under pressure and
            in ordinary play (4 numbers).
    D_i     sampling noise, from match-to-match variation pooled over players (so balls in the
            same match are not treated as independent). Scales with 1/balls.
    Sigma   spread of TRUE talent:  pressure talent = ordinary talent + lift, where
            ordinary talent ~ N(mu_o, Sigma_o)   (Sigma_o fitted by maximum likelihood, EM)
            lift            ~ N(0, kappa^2 Sigma_o), independent of ordinary talent.

    Outputs (posterior means):
    level   true pressure performance, runs per ball above an average player
    lift    how much better the player is under pressure than in ordinary play
            ("rises or dips when it matters"), after shrinkage.
    """
    pm: pd.DataFrame
    meta: pd.DataFrame
    weights: dict = field(default_factory=lambda: dict(WEIGHTS))
    min_balls: int = MIN_PRESSURE_BALLS
    min_matches: int = MIN_PRESSURE_MATCHES
    active_since: str | None = ACTIVE_SINCE
    borrow: bool = True      # False = shrink the pressure sample alone (ignore ordinary balls)
    kappa: float = KAPPA     # sd(lift talent) / sd(ordinary talent)

    def __post_init__(self):
        self.players, pidx = np.unique(self.pm["pid"], return_inverse=True)
        self.matches, midx = np.unique(self.pm["match_id"], return_inverse=True)
        self._pidx = pidx
        self.cols = ["n_p", "r_p", "w_p", "n_o", "r_o", "w_o", "wpa_p", "app", "pos"]
        shape = (len(self.players), len(self.matches))
        self.S = {c: sparse.csr_matrix((self.pm[c].to_numpy(), (pidx, midx)), shape=shape) for c in self.cols}
        self.S["m_p"] = sparse.csr_matrix(((self.pm["n_p"] > 0).astype(float).to_numpy(), (pidx, midx)), shape=shape)
        self.C_p, self.C_o = self.pm.attrs["C_p"], self.pm.attrs["C_o"]
        base = self._agg(np.ones(len(self.matches)))
        last = self.meta["last_date"].reindex(self.players)
        active = np.ones(len(self.players), bool) if self.active_since is None else (last >= self.active_since).to_numpy()
        self.elig = (base["n_p"] >= self.min_balls) & (base["m_p"] >= self.min_matches) & active
        self.base = base
        self.hp = self._hyper(base)

    def _agg(self, w: np.ndarray) -> dict:
        return {c: np.asarray(M @ w).ravel() for c, M in self.S.items()}

    @staticmethod
    def _x(a: dict) -> tuple[np.ndarray, np.ndarray]:
        n_p, n_o = np.maximum(a["n_p"], 1e-9), np.maximum(a["n_o"], 1e-9)
        return np.c_[a["r_p"] / n_p, a["w_p"] / n_p, a["r_o"] / n_o, a["w_o"] / n_o], np.c_[n_p, n_p, n_o, n_o]

    @staticmethod
    def _D(N: np.ndarray, K: np.ndarray) -> np.ndarray:
        r = 1 / np.sqrt(N)
        return K[None] * r[:, :, None] * r[:, None, :]

    @staticmethod
    def _em(x: np.ndarray, D: np.ndarray, iters: int = 300) -> tuple[np.ndarray, np.ndarray]:
        """Maximum-likelihood mean and covariance of true talent given noisy observations."""
        mu, S = x.mean(0), _psd(np.cov(x.T) - D.mean(0))
        for _ in range(iters):
            A = S[None] + D
            u = np.linalg.solve(A, (x - mu)[:, :, None])[:, :, 0]
            m = mu + u @ S
            V = S[None] - S[None] @ np.linalg.solve(A, np.broadcast_to(S, A.shape))
            mu = m.mean(0)
            S = _psd((m - mu).T @ (m - mu) / len(x) + V.mean(0))
        return mu, S

    def _sigma(self, So: np.ndarray, kappa: float) -> np.ndarray:
        Sig = np.block([[(1 + kappa ** 2) * So, So], [So, So]])
        if not self.borrow:
            Sig[:2, 2:] = 0
            Sig[2:, :2] = 0
        return Sig

    def _hyper(self, a: dict) -> dict:
        pool = (a["n_p"] >= HYPER_MIN_P) & (a["n_o"] >= HYPER_MIN_O)   # wider than the ranking pool
        self.hyper_pool = pool
        x, N = self._x(a)
        # --- noise: pooled match-clustered covariance per ball ---------------------------------
        pm, i = self.pm, self._pidx
        Nm = np.c_[pm["n_p"], pm["n_p"], pm["n_o"], pm["n_o"]]
        e = np.c_[pm["r_p"], pm["w_p"], pm["r_o"], pm["w_o"]] - x[i] * Nm
        k = pool[i]
        rt = np.sqrt(N[pool])
        K = (e[k].T @ e[k]) / (rt[:, :, None] * rt[:, None, :]).sum(0)
        if not self.borrow:
            K[:2, 2:] = 0
            K[2:, :2] = 0
        K = _psd(K)
        # --- ordinary-play talent (well identified): EM -----------------------------------------
        xp, D = x[pool], self._D(N[pool], K)
        mu_o, So = self._em(xp[:, 2:], D[:, 2:, 2:])
        wt = N[pool][:, 0] / N[pool][:, 0].sum()
        mu = np.r_[wt @ xp[:, :2], mu_o]
        # --- lift spread: profile likelihood of kappa (reported; the rating uses the fixed KAPPA) -
        grid = np.round(np.arange(0, 1.21, 0.1), 2)
        ll = []
        for kq in grid:
            A = np.block([[(1 + kq ** 2) * So, So], [So, So]])[None] + D
            r = (xp - mu)[:, :, None]
            ll.append(-0.5 * (np.linalg.slogdet(A)[1] + (r.transpose(0, 2, 1) @ np.linalg.solve(A, r))[:, 0, 0]).sum())
        ll = np.array(ll)
        inside = grid[ll >= ll.max() - 1.92]
        sd_o = float(np.sqrt(So.sum()))
        Sig = self._sigma(So, self.kappa)
        el = self.elig
        Nmed = np.median(N[el], axis=0)
        rel = np.diag(Sig) / (np.diag(Sig) + np.diag(K) / Nmed)
        r = a["pos"][el] / np.maximum(a["app"][el], 1)
        p0 = a["pos"][el].sum() / a["app"][el].sum()
        iid = np.r_[np.diag(self.C_p), np.diag(self.C_o)]
        return dict(mu=mu, Sig=Sig, K=K, So=So, kappa=self.kappa, sd_ord=sd_o,
                    sd_level=sd_o * np.sqrt(1 + self.kappa ** 2), sd_lift=sd_o * self.kappa,
                    corr_true=1 / np.sqrt(1 + self.kappa ** 2),
                    kappa_mle=float(grid[ll.argmax()]), kappa_lo=float(inside.min()), kappa_hi=float(inside.max()),
                    kappa_grid=grid, kappa_loglik=ll - ll.max(),
                    rel_runs_p=rel[0], rel_wkt_p=rel[1], rel_runs_o=rel[2], rel_wkt_o=rel[3],
                    design_effect=np.diag(K) / iid,
                    noise_corr_pressure_vs_ordinary_runs=K[0, 2] / np.sqrt(K[0, 0] * K[2, 2]),
                    p0=p0, var_cons=np.var(r) - (p0 * (1 - p0) / np.maximum(a["app"][el], 1)).mean(),
                    hyper_pool=int(pool.sum()))

    def components(self, a: dict, only_elig: bool = False) -> pd.DataFrame:
        hp = self.hp
        x, N = self._x(a)
        idx = self.players
        cons = a["pos"] / np.maximum(a["app"], 1)
        if only_elig:
            x, N, idx, cons = x[self.elig], N[self.elig], idx[self.elig], cons[self.elig]
        Sig, mu = hp["Sig"], hp["mu"]
        A = Sig[None] + self._D(N, hp["K"])
        u = np.linalg.solve(A, (x - mu)[:, :, None])[:, :, 0]
        post = mu + u @ Sig                                   # posterior mean of the four talents
        # posterior covariance V = Sig - Sig A^-1 Sig: how much genuine uncertainty is left about
        # this player's talent. The bootstrap below measures something different (how much the
        # estimate moves when his matches are resampled), so both are reported.
        V = Sig[None] - Sig[None] @ np.linalg.solve(A, np.broadcast_to(Sig, A.shape))
        level, ordinary = post @ A_LEVEL, post @ A_ORD
        lift = (level - mu @ A_LEVEL) - (ordinary - mu @ A_ORD)
        # standardise in units of TRUE-talent spread, so a part with little real signal adds little
        z_level = (level - mu @ A_LEVEL) / hp["sd_level"]
        z_lift = lift / hp["sd_lift"] if hp["sd_lift"] > 0 else np.zeros_like(lift)
        w = self.weights
        comp = w["level"] * z_level + w["lift"] * z_lift
        # the composite is a fixed linear function of the four talents, so its posterior SD is c'Vc
        c = w["level"] * A_LEVEL / hp["sd_level"] + (w["lift"] * (A_LEVEL - A_ORD) / hp["sd_lift"]
                                                     if hp["sd_lift"] > 0 else 0)
        post_sd = np.sqrt(np.maximum(np.einsum("i,nij,j->n", c, V, c), 0))
        return pd.DataFrame({"level": level, "ordinary": ordinary, "lift": lift, "post_sd": post_sd,
                             "level_runs": post[:, 0], "level_wkt": post[:, 1],
                             "raw_level": x[:, 0] + x[:, 1], "raw_ordinary": x[:, 2] + x[:, 3], "cons": cons,
                             "z_level": z_level, "z_lift": z_lift, "composite": comp}, index=idx)

    def run(self, B: int = 1000, seed: int = 7) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        e, M = self.elig, len(self.matches)
        res = self.components(self.base, only_elig=True)
        comps = np.zeros((e.sum(), B))
        for b in range(B):
            w = np.bincount(rng.integers(0, M, M), minlength=M).astype(float)
            comps[:, b] = self.components(self._agg(w), only_elig=True)["composite"].to_numpy()
        ranks = (-comps).argsort(0).argsort(0) + 1
        res["name"] = self.meta["name"].reindex(res.index)
        res["boot_mean"], res["boot_sd"] = comps.mean(1), comps.std(1)
        # 90% credible interval for true talent, from the posterior; the bootstrap quantiles are
        # kept separately because they answer a different question (stability, not uncertainty)
        res["lo"] = res["composite"] - 1.645 * res["post_sd"]
        res["hi"] = res["composite"] + 1.645 * res["post_sd"]
        res["boot_lo"], res["boot_hi"] = np.quantile(comps, 0.05, axis=1), np.quantile(comps, 0.95, axis=1)
        res["score"] = np.quantile(comps, 0.25, axis=1)          # conservative: 75% sure to be at least this
        res["p_top10"] = (ranks <= 10).mean(1)
        res["p_top20"] = (ranks <= 20).mean(1)
        for c in ("n_p", "n_o", "m_p", "app", "pos"):
            res[c] = self.base[c][e]
        res["ipl_share"] = self.meta["ipl_share"].reindex(res.index)
        res = res.sort_values("score", ascending=False)
        res.insert(0, "rank", np.arange(1, len(res) + 1))
        return res
