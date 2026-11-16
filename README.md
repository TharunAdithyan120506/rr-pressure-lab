<div align="center">

# Who delivers under pressure

**SupeRR Selector Season 2 · Round 1** — a ball-by-ball method for measuring batting and bowling
when the match is on the line, built on IPL and T20 International data from 2022 to 2026.

[**Live dashboard**](#the-dashboard) · [**Analysis notebook**](notebooks/RR_pressure_analysis.ipynb) · [**Methodology report**](reports/Methodology_Report.pdf) · [**Submission**](reports/SUBMISSION.txt)

</div>

---

## The answer

| # | Batters under pressure | Rating | | # | Bowlers under pressure | Rating |
|---|---|---|---|---|---|---|
| 1 | **Vaibhav Sooryavanshi** | 163.0 | | 1 | **Jasprit Bumrah** | 141.0 |
| 2 | Abhishek Sharma | 137.6 | | 2 | Sunil Narine | 138.8 |
| 3 | Tim David | 130.8 | | 3 | Kuldeep Yadav | 125.8 |
| 4 | Suryakumar Yadav | 128.7 | | 4 | Nathan Ellis | 122.6 |
| 5 | Priyansh Arya | 128.2 | | 5 | Bhuvneshwar Kumar | 120.4 |
| 6 | Heinrich Klaasen | 125.3 | | 6 | Axar Patel | 119.2 |
| 7 | Finn Allen | 121.4 | | 7 | Josh Hazlewood | 118.9 |
| 8 | Andre Russell | 120.7 | | 8 | Matheesha Pathirana | 117.5 |
| 9 | Josh Inglis | 120.1 | | 9 | Varun Chakravarthy | 117.0 |
| 10 | Nicholas Pooran | 120.0 | | 10 | Krunal Pandya | 116.2 |

*100 = the average qualified player; 15 points = one standard deviation. 110 batters and 112 bowlers qualified.*

---

## How pressure is defined

Pressure is **measured, not asserted**.

1. **Win probability before every ball.** A gradient-boosted model trained on 9,606 T20 matches
   estimates the batting side's chance of winning from the score, wickets, balls left, target, venue,
   season and both teams' strength. The last four overs of a chase use a separate, finer endgame
   model. Tested on matches from 2024 onward that it never saw: **AUC 0.835**, and calibrated.

2. **Leverage Index.** For each ball, how far would that win probability move across the ball's
   possible outcomes (dot, 1, 2, 4, 6, wicket)? Divided by the average swing, that is the ball's
   Leverage Index — **LI 1.0 is an average ball**. Knockout matches get a 1.25× multiplier.

3. **The pressure set.** The top 20% of balls by Leverage Index. The definition earns its keep:

   | | Pressure balls | Ordinary balls |
   |---|---|---|
   | Win probability moved per ball | **4.0%** | 1.2% |
   | Strike rate | **135** | 141 |
   | Dot balls | **39.9%** | 36.4% |

   Those balls carry **46% of all the win probability that moves in a match**, and the side that wins
   them wins the match **74%** of the time. Spot-checked against known finishes, leverage peaks
   exactly where the game was decided (the 2023 IPL final at 4 needed off 1 → LI 14.1).

---

## How players are rated

| Step | What happens |
|---|---|
| **Against expectation** | Each ball is compared with what an average player does in that exact situation — expected runs and expected wicket chance, from models that never saw that match. Wickets are converted to runs using what a wicket costs at that point of an innings. |
| **Against the opponent** | A ridge regression (adjusted plus-minus) credits the batter, the bowler and the opposing team's strength, so runs against a strong attack count for more than runs against a weak one. |
| **Runs and wickets apart** | Run-scoring value repeats far better than dismissal value (0.73 vs 0.33 split-half), so they are tracked separately and each counts for what it is worth. |
| **Level and Lift** | **Level** = true performance on pressure balls. **Lift** = how that compares with the player's own everyday standard. One hierarchical model shrinks both for sample size. |
| **Conservative scoring** | Rating = 70% Level + 30% Lift, then 1,000 bootstrap resamples of whole matches; the score is a lower quartile, so nobody is carried by two hot games. |

**Eligibility:** 100+ pressure balls across 15+ matches, and active since 2025.

### The honest finding

**Being good under pressure is mostly being good.** True pressure talent and everyday talent
correlate at about 0.9. Ranking players on their pressure balls alone produces a list that does not
repeat (split-half reliability 0.18 for batters). Lift is real but small — its likelihood is flat
between 0 and 0.8 — so the top tens are led by excellent players who *don't fade*, not by modest
players with a handful of memorable finishes.

| Reliability check | Batters | Bowlers |
|---|---|---|
| Split-half reliability of the rating | 0.55 | 0.60 |
| …of raw pressure averages | 0.18 | 0.16 |
| Predicts pressure results in held-out matches | **0.26** | **0.22** |
| …using raw pressure averages instead | 0.16 | 0.10 |

The rating also survives the method being changed: shifting the pressure cut-off to the top 30%, 15%
or 10%, dropping the opponent adjustment, dropping Lift entirely, or switching to a plain cricketing
rule for pressure all keep 8–10 of each top 10. Full table in the report, §7.2.

---

## The dashboard

A dark, interactive site covering the Rajasthan Royals squad — the same method applied to a real
decision: **who to keep before the IPL 2027 mini-auction.**

- **Squad** — 27 player cards, filterable by role and verdict
- **Player page** — pressure vs ordinary splits, phase and pace/spin breakdowns, season history,
  biggest pressure days, percentile meters, and the reasoning behind each call with source links
- **Purse planner** — toggle any player in or out and watch the purse, squad slots and overseas count update
- **Top 10** — both lists with bootstrap confidence ranges and per-player evidence
- **Method** — the whole approach, with its limits stated

```bash
# locally
python -m http.server 8777 --directory dashboard   # → http://localhost:8777
```

**Deploy to Vercel:** import this repo and deploy — `vercel.json` already points the output at
`dashboard/`, so the site is all that is served. No build step, no configuration.

### The calls

Retain 14 · release 10 · release-and-rebuy 2 · 1 trade chip, leaving about **₹63 crore for 11 slots**.

- **Clearest release:** Shimron Hetmyer — ₹11 crore for 78 runs at a strike rate of 113 in 2026, dropped by the final league game.
- **Biggest bargains, already at the club:** Sooryavanshi (₹1.1 cr), Brijesh Sharma (₹0.3 cr) and Donovan Ferreira (₹1 cr) — about ₹47 crore of surplus value between them. That is the 2008 Royals formula.
- **The three needs the data shows:** a second strike bowler who holds up at the death; a middle-order batter who scores against spin under pressure; a frontline spinner to share with Jadeja.

Every verdict is reasoned against the data first, then cross-referenced with public reporting. News
informs the retain/release calls only — **it never touches a rating**. Each source is logged with a
reliability tier (official / established outlet / rumour) in
[`reports/research/sources.json`](reports/research/sources.json).

---

## Repo layout

```
dashboard/     the site Vercel serves (index.html, app.js, styles.css, data.js, photos/)
notebooks/     RR_pressure_analysis.ipynb — the analysis, runs from committed files alone
reports/       rankings · validation · rr · research · figures · methodology report · submission
src/rr_pressure/   loaders · features · context · pressure · ratings · stats · cards
scripts/       the pipeline, 00 → 10
configs/       rr_squad.json (salaries, roles, ages) · rr_verdicts.json (the calls)
```

Raw data (1.2 GB) and trained model weights (956 MB) are not committed — `run_all.py` rebuilds them.

## Reproducing it

```bash
python -m venv .venv
.venv/Scripts/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python run_all.py --download        # ~25 min on an RTX 4060
```

| Step | Script | What it does |
|---|---|---|
| 00 | `download_data.py` | Cricsheet: 9,606 T20 matches + player register (ODC-By 1.0) |
| 01 | `build_dataset.py` | normalise both sources, add match state, map player identities |
| 02 | `download_models.py` | TabPFN v3.5 weights (optional) |
| 03 | `03_context_models.py` | win-probability, expected-runs, wicket and endgame models; leverage per ball |
| 04 | `04_pressure_ratings.py` | opponent adjustment, talent model, bootstrap, the rankings |
| 05 | `05_validation.py` | split-half, held-out and sensitivity tests |
| 06–10 | `06…10_*.py` | squad analysis, dashboard bundle, figures, report, submission sheet |

`scripts/verify_env.py` checks packages, GPU, every output, and that the top-10 lists agree across
the rankings, the dashboard and the submission sheet.

## Data and limits

- **The rankings use only the supplied competition data** (200,961 deliveries, 867 matches, 2022–26).
  [Cricsheet](https://cricsheet.org/) (ODC-By 1.0) trains the context models and provides the
  recent-form panels.
- **Handling worth knowing:** `runs` is the batter's runs (add both extras columns for the ball
  total); `Overstep` and `other` extras behave as no-balls; rain-revised overs are stored in balls
  (114 = 19 overs); super overs are dropped.
- **Not measured:** fielding, wicketkeeping, captaincy, the pitch on the day, the partner at the
  other end, intent. Places 6–10 in both lists are close calls, and the report says so.
- **Purse figures are reported, not official** — the ₹130 crore 2027 purse and the retention
  predictions were unconfirmed when this was written (16 November 2026, the day before the deadline).

Unofficial analysis, not affiliated with Rajasthan Royals or the IPL.
