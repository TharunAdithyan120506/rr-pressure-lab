<div align="center">

# Pressure Lab

**Who delivers when the match is on the line.** Ball-by-ball pressure analytics for IPL and T20
International cricket, built for SupeRR Selector Season 2 — with an interactive dark dashboard
covering the top ten, the Rajasthan Royals squad, and the December mini-auction.

[**Dashboard**](#the-dashboard) · [**Notebook**](notebooks/RR_pressure_analysis.ipynb) · [**Report**](reports/Methodology_Report.pdf) · [**Submission**](reports/SUBMISSION.txt) · [**Verification**](#verification-17-checks-that-can-fail)

</div>

---

## The answer

| # | Batters under pressure | Rating | | # | Bowlers under pressure | Rating |
|---|---|---|---|---|---|---|
| 1 | **Vaibhav Sooryavanshi** | 163.0 | | 1 | **Jasprit Bumrah** | 145.7 |
| 2 | Tim David | 140.4 | | 2 | Sunil Narine | 135.2 |
| 3 | Abhishek Sharma | 137.7 | | 3 | Varun Chakravarthy | 127.3 |
| 4 | Heinrich Klaasen | 129.0 | | 4 | Rashid Khan | 123.7 |
| 5 | Suryakumar Yadav | 128.4 | | 5 | Josh Hazlewood | 123.6 |
| 6 | Finn Allen | 120.4 | | 6 | Nathan Ellis | 122.0 |
| 7 | Priyansh Arya | 119.7 | | 7 | Axar Patel | 121.0 |
| 8 | Andre Russell | 117.8 | | 8 | Kuldeep Yadav | 118.1 |
| 9 | Ashutosh Sharma | 115.3 | | 9 | Matheesha Pathirana | 117.9 |
| 10 | Josh Inglis | 115.1 | | 10 | Eshan Malinga | 117.0 |

*100 = the average qualified player, 15 points = one standard deviation. 111 batters and 115 bowlers qualified.*

---

## How pressure is defined

Pressure is **measured, not asserted** — four steps, each of which has a test that can fail.

**1 · Win probability before every ball.** A gradient-boosted model trained on 9,606 T20 matches
gives the batting side's chance of winning from the score, wickets, balls left, target, venue,
season and both teams' Elo. The last four overs of a chase blend into a separate endgame model that
is forced to respect common sense (fewer runs needed, more balls or more wickets can never hurt).
Raw probabilities came out over-confident, so a monotone calibration map is fitted on Cricsheet
matches that are *not* twins of the supplied ones. Result: **AUC 0.84**, calibrated to within
**1.4%** on matches from 2024 on that the model never saw.

**2 · Leverage Index.** For each ball, how far would that probability move across the ball's
possible outcomes (dot, 1, 2, 4, 6, wicket)? Divided by the average swing, that's the ball's
Leverage Index — **1.0 is an average ball**. A pressure ball is one in the top 20% (LI ≥ 1.50).

The definition earns its keep:

| | Pressure balls | Ordinary balls |
|---|---|---|
| Win probability moved per ball | **3.5%** | 1.2% |
| Strike rate | **135** | 141 |
| Dot balls | **39.4%** | 36.2% |

Those balls carry **44% of all the win probability that moves in a match**, and the side that wins
them wins the match **74%** of the time. Three in four pressure balls come in a chase — and the
single biggest cluster is the *powerplay* of a chase, not the death overs.

**3 · Value against expectation, then against the opponent.** Every ball is compared with what an
average player does in that exact situation — including **how set the batter is and where he walked
in**, so a finisher arriving fresh at the death isn't judged against a set batter's bar. Wickets are
converted to runs using what one costs at that point of an innings. A ridge regression then credits
the batter, the bowler and the opposing team's Elo, so runs against a strong attack count for more.

**4 · Level, Lift, and weights chosen by the data.** **Level** is true performance on pressure
balls; **Lift** is how that compares with the player's own everyday standard. One hierarchical model
shrinks both for sample size, using match-to-match variation for the noise so balls in the same
match aren't double-counted. The Level/Lift split is **not hand-picked** — we sweep it and keep the
mix that best predicts pressure performance in matches the estimate never saw:

| Role | Predictive optimum | Indistinguishable band | Chosen |
|---|---|---|---|
| Batters | 0.65 | 0.50 – 1.00 | 0.60 Level / 0.40 Lift |
| Bowlers | 0.90 | 0.60 – 1.00 | 0.75 Level / 0.25 Lift |

The brief asks for performance "compared with their usual performance levels", so within the band
that the data still supports we lean toward Lift.

### Is "consistency" a real trait?

The brief asks for players who deliver *most consistently*, so we tested it rather than assuming it.
A Bartlett test for unequal match-to-match volatility gives p = 0.15 (batters) and 0.08 (bowlers),
and volatility itself barely repeats across a split-half (r ≈ 0.13). **A weak, same-signed hint in
both roles — not significant, barely repeatable.** So consistency isn't rated as a separate skill.
It enters through the match bootstrap instead: the published score is a lower quantile, so nobody
carried by two freak games holds a high rank.

### The honest finding

**Being good under pressure is mostly being good.** Ranking players on their pressure balls alone
produces a list that does not repeat (split-half reliability 0.20 for batters), which is why the
rating borrows from every ball a player has faced.

| Reliability check | Batters | Bowlers |
|---|---|---|
| Split-half reliability of the rating | 0.56 | 0.57 |
| …of raw pressure averages | 0.20 | 0.17 |
| Predicts pressure results in held-out matches | **0.28** | **0.17** |
| …using raw pressure averages instead | 0.21 | 0.07 |
| …using only his pressure balls | 0.22 | 0.10 |

---

## Verification: 17 checks that can fail

Most ratings are never tested against a known answer. These are, and the suite exits non-zero if
anything breaks ([`scripts/13_verify_math.py`](scripts/13_verify_math.py)):

| | Check | Result |
|---|---|---|
| 1 | Leverage Index identity — mean LI must be exactly 1 | 1.0000 |
| 2 | Win-probability calibration on unseen matches | ECE 0.014 |
| 3 | Win probability is a martingale (WP before = mean WP after) | drift 0.0004/ball |
| 4 | Endgame monotonicity across a dense grid | 33/33 monotone |
| 5 | Expected values unbiased in every tier × season × innings × phase cell | max 8×10⁻¹⁷ |
| 6 | Zero-sum — batter value and bowler value must cancel | 10⁻¹³ |
| 7 | Out-of-fold integrity — no ball scored by a model trained on its match | 0 mismatches |
| 8a–d | **Simulated players with known talent**: does the rating recover it? | r = 0.58 / 0.77 vs 0.47 / 0.51 raw |
| 9 | **Credible interval coverage** on simulated truth | 86% / 94% for a nominal 90% |

Checks 8 and 9 generate players whose true talent is known by construction, simulate their balls
with the real noise structure, and ask whether the estimator recovers the truth. They also surfaced
two genuine flaws that are now fixed: the win-probability model was over-confident (hence the
calibration step), and the match bootstrap was being presented as an uncertainty interval when it
measures stability — the displayed interval is now a proper posterior credible interval, and the
bootstrap is reported separately for what it actually is.

**Known limitation the suite exposes:** at this pool size the rating spreads about 20% wider than
true talent (slope 0.80–0.85 instead of 1.00), so the very top and bottom are further apart than
reality. With more players the slope rises to 0.96.

---

## The dashboard

Dark, Royals-accented, built around full-size player cutouts. Four tabs:

- **01 Top 10** — the ranked ten with photos, a hero panel for whichever player you click, pressure
  vs ordinary splits, percentile meters, and how the ten were found
- **02 Royals** — all 27 squad players, our retain/release call on each, and **what RR actually did**
- **03 Auction** — purse after retention, the three gaps the data shows, and a target board built
  from every player released league-wide
- **04 Method** — the full method, the weight sweep, the consistency test, and all 17 checks

```bash
python -m http.server 8777 --directory dashboard   # → http://localhost:8777
```

**Deploy to Vercel:** import this repo and deploy. `vercel.json` already points the output at
`dashboard/`, so the site is all that's served — no build step, no configuration.

---

## Our calls vs what Rajasthan actually did

We published retain/release calls on **16 November**. RR announced their real list on the **17th**.

**22 of 27 matched (81%).** Every player we said to retain was retained. Every clear release —
Hetmyer, Deshpande, Milne, Maphaka, Kuldeep Sen, Yudhvir, Ravi Singh, Emanjot Chahal — went. We
flagged Sam Curran as a trade chip and noted the unconfirmed LSG rumour; he was traded to LSG, and
Mohammed Shami came the other way.

The five misses: we'd have moved on from **Jadeja**, **Bishnoi**, **Sandeep Sharma** and
**Shanaka** on the numbers, and RR kept all four. We'd have kept **Vignesh Puthur**; they released him.

RR kept 19, committing ~₹104.5 crore and leaving ~₹25.5 crore for 6 slots. The three gaps the data
still shows: a death bowler who doesn't leak under pressure, a middle-order batter who scores
against spin when the game tightens, and a second overseas quick alongside Archer.

---

## Repo layout

```
dashboard/     the site Vercel serves (index.html, app.js, styles.css, data.js, 274 photos)
notebooks/     RR_pressure_analysis.ipynb — runs from committed files alone
reports/       rankings · validation · rr · research · figures · report · submission
src/rr_pressure/   loaders · features · context · pressure · ratings · stats · cards
scripts/       the pipeline, 00 → 14
configs/       rr_squad · rr_verdicts · retentions_2027 · ipl_photos
```

Raw data (1.2 GB) and model weights (1 GB) aren't committed — `run_all.py` rebuilds them.

## Reproducing it

```bash
python -m venv .venv
.venv/Scripts/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python run_all.py --download        # ~35 min on an RTX 4060
```

| Step | Script | What it does |
|---|---|---|
| 00–01 | `download_data`, `build_dataset` | Cricsheet (9,606 T20s), normalise both sources, map player identities |
| 03 | `03_context_models` | win-probability, expected-runs, wicket, endgame models; calibration; leverage per ball |
| 04 | `04_pressure_ratings` | opponent adjustment, talent model, bootstrap, rankings |
| 05 | `05_validation` | split-half, held-out and 13 sensitivity variants |
| 11 | `11_weights_consistency` | sweeps the Level/Lift weights, tests whether consistency is real |
| 13 | `13_verify_math` | the 17-check verification suite |
| 06, 12, 14 | `06_rr_squad`, `12_photos`, `14_auction` | squad cards, IPL headshots, auction board + scorecard |
| 07–10 | `07…10_*` | dashboard bundle, figures, report, submission sheet |

`scripts/verify_env.py` checks packages, GPU, every output, that all 17 maths checks pass, and that
the top-10 lists agree across the rankings, the dashboard and the submission sheet.

## Data and limits

- **The rankings use only the supplied competition data** (200,961 deliveries, 867 matches, 2022–26).
  [Cricsheet](https://cricsheet.org/) (ODC-By 1.0) trains the context models and provides recent form.
- **Handling worth knowing:** `runs` is the batter's runs (add both extras columns for the ball
  total); `Overstep` and `other` extras behave as no-balls; rain-revised overs are stored in balls
  (114 = 19 overs); super overs are dropped.
- **Not measured:** fielding, wicketkeeping, captaincy, the pitch on the day, the partner at the
  other end, intent. Places 6–10 in both lists are close calls, and the report says so.
- **Player images** © IPL/BCCI, taken from the public squad pages on iplt20.com, used only to
  illustrate an unofficial analysis.
- **Purse figures are reported, not official** — the ₹130 crore 2027 purse is widely reported but
  unconfirmed. Retention and release lists are the official 17 November ones.

Unofficial analysis. Not affiliated with Rajasthan Royals, the IPL or the BCCI.
