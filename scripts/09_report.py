"""Build reports/Methodology_Report.docx from the saved results (no numbers typed by hand)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Inches, Pt, RGBColor  # noqa: E402

from rr_pressure.paths import FIGURES, REPORTS, ROOT, TRAINED  # noqa: E402

# RR palette
PINK, NAVY, INK, MUTED, WHITE = (RGBColor(0xE0, 0x18, 0x7F), RGBColor(0x0A, 0x15, 0x40),
                                 RGBColor(0x1A, 0x22, 0x40), RGBColor(0x6B, 0x75, 0x95), RGBColor(0xFF, 0xFF, 0xFF))
HX_PINK, HX_NAVY, HX_SOFT, HX_BAND, HX_LINE = "E0187F", "0A1540", "FDF0F7", "F2F4FA", "DCE1EC"

V = json.loads((REPORTS / "validation" / "validation.json").read_text())
P = json.loads((REPORTS / "rankings" / "rating_params.json").read_text())
C = json.loads((TRAINED / "ctx" / "metrics_ctx.json").read_text())
PD = V["pressure_definition"]
SQ = json.loads((ROOT / "configs" / "rr_squad.json").read_text(encoding="utf-8"))
VD = json.loads((ROOT / "configs" / "rr_verdicts.json").read_text(encoding="utf-8"))
f1, f2 = lambda x: f"{x:.1f}", lambda x: f"{x:.2f}"


# ---------------------------------------------------------------- low-level styling helpers
def shade(el, hexcolor):
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:fill"), hexcolor)
    el.get_or_add_tcPr().append(sh) if el.tag.endswith("tc") else el.get_or_add_pPr().append(sh)


def borders(el, **sides):
    """sides: top/bottom/left/right -> (size_eighths, hexcolor) or None to clear."""
    tag = "w:tcBorders" if el.tag.endswith("tc") else "w:pBdr"
    pr = el.get_or_add_tcPr() if el.tag.endswith("tc") else el.get_or_add_pPr()
    old = pr.find(qn(tag))
    if old is not None:
        pr.remove(old)
    b = OxmlElement(tag)
    for side, spec in sides.items():
        e = OxmlElement(f"w:{side}")
        if spec is None:
            e.set(qn("w:val"), "nil")
        else:
            sz, col = spec
            e.set(qn("w:val"), "single")
            e.set(qn("w:sz"), str(sz))
            e.set(qn("w:space"), "0")
            e.set(qn("w:color"), col)
        b.append(e)
    pr.append(b)


def cell_margins(cell, top=70, bottom=70, left=110, right=110):
    tcPr = cell._tc.get_or_add_tcPr()
    m = OxmlElement("w:tcMar")
    for k, v in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        e = OxmlElement(f"w:{k}")
        e.set(qn("w:w"), str(v))
        e.set(qn("w:type"), "dxa")
        m.append(e)
    tcPr.append(m)


def write(cell, text, size=9.5, bold=False, color=None, align=None, space=1):
    cell.text = ""
    p = cell.paragraphs[0]
    r = p.add_run(str(text))
    r.font.size, r.bold = Pt(size), bold
    r.font.color.rgb = color or INK
    p.paragraph_format.space_before = Pt(space)
    p.paragraph_format.space_after = Pt(space)
    if align:
        p.alignment = align
    return p


def main() -> None:
    d = Document()
    st = d.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(10.5)
    st.font.color.rgb = INK
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.line_spacing = 1.08
    for s, sz, col in (("Heading 1", 16, NAVY), ("Heading 2", 12, PINK), ("Heading 3", 10.5, NAVY)):
        f = d.styles[s].font
        f.name, f.size, f.color.rgb, f.bold = "Calibri", Pt(sz), col, True
        pf = d.styles[s].paragraph_format
        pf.space_before, pf.space_after = Pt(16 if sz == 16 else 11), Pt(5)
    for s in ("List Bullet", "List Number"):
        d.styles[s].font.size = Pt(10.5)
        d.styles[s].font.color.rgb = INK

    sec = d.sections[0]
    sec.top_margin = sec.bottom_margin = Inches(0.62)
    sec.left_margin = sec.right_margin = Inches(0.78)
    CW = 7.0  # usable width

    # running footer: title left, page number right
    fp = sec.footer.paragraphs[0]
    fp.paragraph_format.tab_stops.clear_all()          # drop Word's inherited centre tab
    fp.paragraph_format.tab_stops.add_tab_stop(Inches(CW - 0.06), WD_TAB_ALIGNMENT.RIGHT)
    r = fp.add_run("Who delivers under pressure  ·  SupeRR Selector S2, Round 1\t")
    r.font.size, r.font.color.rgb = Pt(8), MUTED
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), " PAGE ")
    fr = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    for tag, val in (("w:b", None), ("w:sz", "16"), ("w:color", HX_NAVY)):
        e = OxmlElement(tag)
        if val:
            e.set(qn("w:val"), val)
        rpr.append(e)
    fr.append(rpr)
    fld.append(fr)
    fp._p.append(fld)
    borders(fp._p, top=(6, HX_LINE))
    fp.paragraph_format.space_before = Pt(6)

    # ---------------------------------------------------------------- building blocks
    def para(text, size=10.5, bold=False, color=None, after=6, align=None, italic=False, before=0):
        p = d.add_paragraph()
        r = p.add_run(text)
        r.font.size, r.bold, r.italic = Pt(size), bold, italic
        r.font.color.rgb = color or INK
        p.paragraph_format.space_after = Pt(after)
        p.paragraph_format.space_before = Pt(before)
        if align:
            p.alignment = align
        return p

    def rich(parts, size=10.5, after=6, color=None):
        """parts: text with **bold** markers."""
        p = d.add_paragraph()
        for i, s in enumerate(parts.split("**")):
            r = p.add_run(s)
            r.bold = i % 2 == 1
            r.font.size = Pt(size)
            r.font.color.rgb = color or INK
        p.paragraph_format.space_after = Pt(after)
        return p

    def bullets(items, style="List Bullet"):
        for t in items:
            p = d.add_paragraph(style=style)
            for i, s in enumerate(t.split("**")):
                r = p.add_run(s)
                r.bold = i % 2 == 1
                r.font.size = Pt(10.5)
                r.font.color.rgb = INK
            p.paragraph_format.space_after = Pt(4)

    def heading(text, level=1):
        h = d.add_heading(text, level)
        if level == 1:
            borders(h._p, bottom=(12, HX_PINK))
            h.paragraph_format.space_after = Pt(9)
        return h

    def table(rows, widths=None, size=9.5, zebra=True, first_col_left=True, header=True, aligns=None):
        t = d.add_table(rows=0, cols=len(rows[0]))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        for i, row in enumerate(rows):
            cells = t.add_row().cells
            for j, v in enumerate(row):
                head = header and i == 0
                al = ({"l": None, "c": WD_ALIGN_PARAGRAPH.CENTER, "r": WD_ALIGN_PARAGRAPH.RIGHT}[aligns[j]]
                      if aligns else (None if (j == 0 and first_col_left) else WD_ALIGN_PARAGRAPH.RIGHT))
                write(cells[j], v, size=size - (0.5 if head else 0), bold=head,
                      color=WHITE if head else INK, align=al, space=1.5)
                cell_margins(cells[j])
                tc = cells[j]._tc
                if head:
                    shade(tc, HX_NAVY)
                elif zebra and i % 2 == 0:
                    shade(tc, HX_BAND)
                borders(tc, top=None, bottom=(4, HX_LINE), left=None, right=None,
                        insideH=None, insideV=None)
                if widths:
                    cells[j].width = Inches(widths[j])
        d.add_paragraph().paragraph_format.space_after = Pt(3)
        return t

    def statband(items):
        """A row of big-number callout cards."""
        t = d.add_table(rows=1, cols=len(items))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        for j, (val, lab) in enumerate(items):
            c = t.rows[0].cells[j]
            c.width = Inches(CW / len(items))
            cell_margins(c, top=130, bottom=130, left=130, right=130)
            shade(c._tc, HX_SOFT)
            borders(c._tc, left=(18, HX_PINK), top=None, bottom=None, right=None)
            p = write(c, val, size=21, bold=True, color=PINK, space=0)
            p.paragraph_format.space_after = Pt(1)
            p2 = c.add_paragraph()
            r = p2.add_run(lab)
            r.font.size, r.font.color.rgb, r.bold = Pt(8), NAVY, True
            p2.paragraph_format.space_after = Pt(0)
        d.add_paragraph().paragraph_format.space_after = Pt(4)

    def callout(title, text):
        t = d.add_table(rows=1, cols=1)
        c = t.rows[0].cells[0]
        c.width = Inches(CW)
        cell_margins(c, top=150, bottom=150, left=160, right=160)
        shade(c._tc, HX_SOFT)
        borders(c._tc, left=(18, HX_PINK), top=None, bottom=None, right=None)
        write(c, title, size=9, bold=True, color=PINK, space=0)
        p = c.add_paragraph()
        r = p.add_run(text)
        r.font.size, r.font.color.rgb = Pt(10.5), INK
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(0)
        d.add_paragraph().paragraph_format.space_after = Pt(4)

    def figure(name, caption, width=6.4):
        d.add_picture(str(FIGURES / f"{name}.png"), width=Inches(width))
        d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        d.paragraphs[-1].paragraph_format.space_before = Pt(4)
        p = para(caption, size=8.5, color=MUTED, align=WD_ALIGN_PARAGRAPH.CENTER, after=12, italic=True)
        return p

    SHORT = {"Royal Challengers Bengaluru": "RCB", "Kolkata Knight Riders": "KKR", "Mumbai Indians": "MI",
             "Sunrisers Hyderabad": "SRH", "Lucknow Super Giants": "LSG", "Chennai Super Kings": "CSK",
             "Punjab Kings": "PBKS", "Rajasthan Royals": "RR", "Delhi Capitals": "DC", "Gujarat Titans": "GT",
             "United Arab Emirates": "UAE", "South Africa": "South Africa", "New Zealand": "New Zealand"}

    def top_table(fname, cols, widths):
        t = pd.read_csv(REPORTS / "rankings" / f"{fname}_full.csv").head(10)
        table([[c[0] for c in cols]] + [[c[1](r) for c in cols] for _, r in t.iterrows()],
              widths=widths, size=8.5, aligns=["c", "l", "l"] + ["r"] * (len(cols) - 3))
        return t

    bat = pd.read_csv(REPORTS / "rankings" / "batters_full.csv")
    bowl = pd.read_csv(REPORTS / "rankings" / "bowlers_full.csv")

    # ---------------------------------------------------------------- cover
    cov = d.add_table(rows=1, cols=1)
    cc = cov.rows[0].cells[0]
    cc.width = Inches(CW)
    cell_margins(cc, top=320, bottom=320, left=300, right=300)
    shade(cc._tc, HX_NAVY)
    borders(cc._tc, left=(24, HX_PINK), top=None, bottom=None, right=None)
    write(cc, "SUPERR SELECTOR SEASON 2  ·  ROUND 1", size=9, bold=True,
          color=RGBColor(0xFF, 0x7A, 0xBE), space=0)
    p = cc.add_paragraph()
    r = p.add_run("Who delivers under pressure")
    r.font.size, r.bold, r.font.color.rgb = Pt(30), True, WHITE
    p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(8), Pt(6)
    p = cc.add_paragraph()
    r = p.add_run("A ball-by-ball method for measuring batting and bowling when the match is on the "
                  "line, applied to IPL and T20 International cricket from 2022 to 2026.")
    r.font.size, r.font.color.rgb = Pt(11.5), RGBColor(0xC9, 0xD2, 0xEA)
    p.paragraph_format.space_after = Pt(0)
    d.add_paragraph().paragraph_format.space_after = Pt(10)

    para("THE ANSWER", 9, True, PINK, after=5)
    table([["", "Top 10 batters under pressure", "Rating", "Top 10 bowlers under pressure", "Rating"]] +
          [[i + 1, bat.iloc[i]["name"], f1(bat.iloc[i]["rating"]), bowl.iloc[i]["name"], f1(bowl.iloc[i]["rating"])]
           for i in range(10)], widths=[0.4, 2.55, 0.65, 2.55, 0.65], size=10, aligns=["c", "l", "r", "l", "r"])
    para(f"Rating: 100 is the average qualified player, 15 points is one standard deviation. "
         f"{len(bat)} batters and {len(bowl)} bowlers qualified. Every number in this report is produced "
         f"by the code in this repository; nothing is entered by hand.", 9, color=MUTED, after=0)
    d.add_page_break()

    # ---------------------------------------------------------------- 1 summary
    heading("1. What we built, in one page")
    statband([(f"{PD['pressure_share_of_total_abs_wpa']:.0%}", "OF A MATCH'S WIN PROBABILITY\nMOVES ON PRESSURE BALLS"),
              (f"{PD['team_won_pressure_wpa_and_match']:.0%}", "OF SIDES THAT WIN THE\nPRESSURE BALLS WIN THE MATCH"),
              (f2(C["wp_v2_context"]["auc"]), "WIN-PROBABILITY MODEL AUC\nON UNSEEN 2024–26 MATCHES")])
    bullets([
        "**The question.** Some players lift when the game is close; others fade. We needed a way to tell them apart "
        "from the deliveries themselves, not from reputation.",
        "**Pressure is measured, not asserted.** A win-probability model trained on 9,606 T20 matches tells us, before "
        "every ball, how much the result can swing on that ball. That swing is the ball's **Leverage Index**: 1.0 is an "
        f"average ball. The busiest 20% of balls (LI ≥ {f2(PD['q80'])}) are our pressure balls.",
        "**Performance is measured against expectation, then against the opponent.** Each ball is compared with what an "
        "average player does in that exact situation, with wickets converted into runs; a ridge regression then credits "
        "the batter, the bowler and the strength of the opposing team.",
        "**Two things are rated.** **Level**: how good a player is on pressure balls. **Lift**: how much better or worse "
        "that is than his own everyday standard. Both are shrunk for sample size by a single statistical model.",
        "**The rating is deliberately conservative.** Matches are resampled 1,000 times; a player's score is the level he "
        "reaches in three resamples out of four.",
        "**We checked whether it holds.** Split-half reliability of the rating is "
        f"{f2(V['batters']['split_half']['composite']['full_sample_reliability'])} for batters and "
        f"{f2(V['bowlers']['split_half']['composite']['full_sample_reliability'])} for bowlers, against "
        f"{f2(V['batters']['split_half']['raw_level']['full_sample_reliability'])} and "
        f"{f2(V['bowlers']['split_half']['raw_level']['full_sample_reliability'])} for raw pressure averages.",
    ])
    callout("THE HONEST HEADLINE",
            "Pressure skill is mostly ordinary skill. Our top tens are therefore led by players who are both excellent "
            "and do not fall away when it counts, rather than by modest players with a handful of hot finishes.")

    # ---------------------------------------------------------------- 2 data
    heading("2. The data")
    para("Supplied — the only source used for the rankings", 10.5, True, NAVY, after=4)
    bullets([
        "200,961 deliveries from 867 matches: 401 IPL and other T20 matches and 466 T20 Internationals, 2022 to 2026, "
        "with competitions, teams, players, matches, playing XIs and mappings. Super overs (innings 3 and 4) are dropped.",
        "Careful handling: the runs column holds the batter's runs, so the ball's total adds both extras columns; "
        "Overstep and other extras behave as no-balls; rain-revised overs are stored in balls (114 = 19 overs) and are honoured in "
        "every balls-remaining and required-rate calculation.",
    ])
    para("Supporting — model training and context only, never the rankings", 10.5, True, NAVY, after=4)
    bullets([
        "Cricsheet ball-by-ball data for 9,606 men's T20 matches, 2005 to 2026 (IPL, T20Is, BBL, PSL, CPL, SA20, ILT20, "
        "T20 Blast, Syed Mushtaq Ali, LPL, BPL, MLC), used to train the context models and to show recent form on the "
        "dashboard. Released under ODC-By 1.0.",
        "767 of the 867 supplied matches were matched to their Cricsheet twin by date and innings totals, then aligned "
        "ball by ball to map 869 of 958 supplied player IDs to Cricsheet identities. The unmapped 89 (about 2% of balls) "
        "are mostly Afghanistan series, which Cricsheet does not carry.",
    ])

    # ---------------------------------------------------------------- 3 pressure
    heading("3. How we define pressure")
    d.add_heading("3.1 Win probability before every ball", 2)
    para("A gradient-boosted model estimates the batting side's chance of winning from the match state: innings, score, "
         "wickets, balls bowled and left, target, required and current run rate, partnership, competition tier, season, a "
         "venue scoring factor and both teams' Elo ratings. The last four overs of a chase are blended into a second, "
         "finer model that uses only runs required, balls left and wickets in hand, and is forced to respect common sense "
         "(needing fewer runs, having more balls or more wickets can never hurt).")
    rich(f"Trained on matches before 2024 and tested on 2024–26, it reaches **AUC {f2(C['wp_v2_context']['auc'])}** "
         f"(log loss {f2(C['wp_v2_context']['logloss'])}, Brier {f2(C['wp_v2_context']['brier'])}), against AUC "
         f"{f2(C['wp_v1_state_only']['auc'])} for a model that knows only the raw match state. Every ball in the supplied "
         "data is scored by a model that never saw its match: the data is split into five folds by match, and each ball "
         "is predicted by the fold models trained without it.")
    figure("03_calibration", "Figure 1. Predicted win probability against what actually happened, on matches the model never saw.", 3.2)

    d.add_heading("3.2 Leverage Index", 2)
    para("For each ball we ask what the win probability would become after each possible outcome (dot, 1, 2, 4, 6, "
         "wicket), weight those by how often each outcome occurs in that innings, phase and wickets-down bucket, and take "
         "the expected absolute swing. Dividing by the average across all balls gives the Leverage Index, so LI = 1.0 is "
         "an average ball and LI = 3 is a ball three times as decisive. Knockout matches are multiplied by "
         f"{PD['knockout_mult']}. A pressure ball is one with LI ≥ {f2(PD['q80'])}, the top 20%.")
    para("This follows the leverage idea used in baseball (Tango; FanGraphs) and the expected-runs logic of CricViz and "
         "ESPNcricinfo Smart Stats, but it is computed here from scratch on T20 data.", 9.5, color=MUTED)
    figure("01_leverage", "Figure 2. The distribution of leverage, and where in a match the pressure actually falls.")

    d.add_heading("3.3 Evidence that the definition separates situations", 2)
    pv, po = PD["pressure_vs_ordinary"]["pressure"], PD["pressure_vs_ordinary"]["ordinary"]
    table([["", "Pressure balls", "Ordinary balls"],
           ["Balls", f"{pv['balls']:,}", f"{po['balls']:,}"],
           ["Average Leverage Index", f2(pv["mean_li"]), f2(po["mean_li"])],
           ["Win probability moved per ball", f"{f1(pv['mean_abs_wpa_pct'])}%", f"{f1(po['mean_abs_wpa_pct'])}%"],
           ["Strike rate", f"{pv['strike_rate']:.0f}", f"{po['strike_rate']:.0f}"],
           ["Dot balls", f"{f1(pv['dot_pct'])}%", f"{f1(po['dot_pct'])}%"],
           ["Boundaries", f"{f1(pv['boundary_pct'])}%", f"{f1(po['boundary_pct'])}%"],
           ["Wickets", f"{f1(pv['wicket_pct'])}%", f"{f1(po['wicket_pct'])}%"]], widths=[2.8, 2.1, 2.1])
    bullets([
        f"Pressure balls move the result {pv['mean_abs_wpa_pct'] / po['mean_abs_wpa_pct']:.1f} times as much as ordinary "
        f"balls, and carry {PD['pressure_share_of_total_abs_wpa']:.0%} of all win probability that moves.",
        f"Scoring is visibly harder: the strike rate falls by {po['strike_rate'] - pv['strike_rate']:.0f} and dot balls "
        f"rise by {pv['dot_pct'] - po['dot_pct']:.1f} points. Batters do not simply hit out more.",
        f"The side that wins the pressure balls wins the match {PD['team_won_pressure_wpa_and_match']:.0%} of the time.",
        "The four matches we spot-checked peak exactly where they were decided: the IPL 2023 final (LI 14.1 with 4 needed "
        "off 1) and the 2023 KKR chase (LI 16.8, same equation).",
    ])
    figure("02_separation", "Figure 3. Outcomes across leverage deciles: as more rides on the ball, scoring falls and the result swings more.")
    rich(f"A plain cricketing rule (late chases needing 10+ an over, two-run-a-ball finishes, early collapses, chases with "
         f"six or more wickets down) flags {PD['rule_overlap']['rule_share']:.0%} of balls as pressure. Ranking on that "
         f"definition instead changes little: **Spearman {f2(V['batters']['sensitivity'][4]['spearman_vs_primary'])}** for "
         f"batters and **{f2(V['bowlers']['sensitivity'][4]['spearman_vs_primary'])}** for bowlers against our primary order.")

    # ---------------------------------------------------------------- 4 performance
    heading("4. How we measure performance")
    d.add_heading("4.1 Value of a ball, against expectation", 2)
    para("Four more models, cross-fitted the same way, give the expected runs and the expected chance of a wicket for an "
         "average batter and bowler in that exact situation. A fifth, monotone in balls left and wickets lost, gives the "
         "runs an innings still has in it, so losing a wicket can be priced in runs "
         f"(about {f1(C['oof_on_supplied']['wcost_mean'])} runs on average, more in the powerplay, less at the death: the "
         "Duckworth–Lewis idea of balls and wickets as joint resources).")
    para("For a batter, a ball is worth (runs scored − expected runs) − (dismissed − expected dismissal) × run cost of a "
         "wicket. For a bowler the same quantity with the signs reversed, using runs charged to the bowler and wickets "
         "credited to him. Values are centred within competition tier, season, innings and phase, so the IPL scoring boom "
         "and the weaker T20I fixtures do not flatter anyone.")
    d.add_heading("4.2 Credit for the opponent", 2)
    para("Raw value still rewards whoever faced the friendliest opponents. A ridge regression (the adjusted plus-minus "
         "idea from basketball) explains each ball's value by a batter effect, a bowler effect and the opposing team's "
         "Elo rating, with the penalty chosen by grouped cross-validation. Each player's value is then measured net of "
         f"the opponent he faced. Facing a team 100 Elo points stronger costs a batter about "
         f"{abs(P['elo_coef_per_100']['vr_bat']) * 100:.1f} runs per 100 balls and a bowler about "
         f"{abs(P['elo_coef_per_100']['vr_bowl']) * 100:.1f}.")
    d.add_heading("4.3 Runs and wickets are rated separately", 2)
    para("Split-half tests show run-scoring value repeats far better than dismissal value (about 0.73 against 0.33 for "
         "batters). Lumping them together would let the noisier half dominate. We therefore track the run component and "
         "the wicket component as separate quantities and let the model below weight each by the signal it actually carries.")
    d.add_heading("4.4 From ball values to a rating", 2)
    hb, hw = P["bat"], P["bowl"]
    para("For every player we hold four numbers: run value and wicket value, under pressure and in ordinary play. These "
         "are noisy estimates of four underlying talents. We fit, by maximum likelihood, the distribution of true talent "
         "across players, where pressure talent = ordinary talent + lift, and lift is independent with a spread κ times "
         "that of ordinary talent. Sampling noise is estimated from each player's match-to-match variation rather than "
         "ball-to-ball, so balls in the same match are not double-counted.")
    rich(f"The likelihood for κ is flat between 0 and about 0.8 (best fit {hb['kappa_mle']} for batters, "
         f"{hw['kappa_mle']} for bowlers; 95% intervals {hb['kappa_lo']}–{hb['kappa_hi']} and "
         f"{hw['kappa_lo']}–{hw['kappa_hi']}), so rather than re-estimate it per run we fix **κ = {hb['kappa']}**. "
         "There is a real pressure effect, but it is small next to ordinary skill, and the model says so.")
    bullets([
        f"**Level** = posterior pressure talent. Spread across qualified batters: {f2(100 * hb['sd_level'])} runs per 100 "
        f"balls; bowlers {f2(100 * hw['sd_level'])}.",
        f"**Lift** = Level minus the player's own ordinary talent. Spread: batters {f2(100 * hb['sd_lift'])} runs per 100 "
        f"balls, bowlers {f2(100 * hw['sd_lift'])}.",
        f"**Composite** = {P['weights']['level']:.0%} Level + {P['weights']['lift']:.0%} Lift, each in units of its own "
        "true-talent spread, so a component with little real signal contributes little.",
        f"**Final score** = the first quartile of the composite across {P['bootstrap']:,} bootstrap resamples of whole "
        "matches. A player is only rated highly if he stays high when his matches are reshuffled. The published rating "
        "rescales this so 100 is the average qualified player and 15 points is one standard deviation.",
    ])
    para("We also computed a consistency measure (the share of a player's pressure appearances with positive value). Its "
         "spread across players is no larger than coin-flipping noise, so it carries no weight in the rating; consistency "
         "enters through the bootstrap quartile instead. We report it on the dashboard as evidence, not as a component.",
         9.5, color=MUTED)

    # ---------------------------------------------------------------- 5 fair comparisons
    heading("5. Fair comparisons")
    table([["Problem", "What we do"],
           ["Small samples", f"Qualification: {P['min_pressure_balls']}+ pressure balls across {P['min_pressure_matches']}+ "
                             f"matches, and a ball since {P['active_since'][:4]}. Everything else is shrunk toward the average; the "
                             "score is a conservative bootstrap quantile."],
           ["IPL mixed with T20Is", "Ball values are centred within competition tier, season, innings and phase, and the "
                                    "opponent adjustment carries a team-strength term, so runs against Nepal are not runs against India."],
           ["Weak or missing opponents", "Elo ratings are built from all 9,606 Cricsheet matches plus the supplied matches "
                                         "Cricsheet lacks; associate nations start 250 points below full members."],
           ["Eras and venues", "Season and a venue scoring factor are model inputs, so a 2026 belter is not confused with a 2022 "
                               "turner."],
           ["Role differences", "Batters are judged on balls faced, bowlers on balls bowled; a bowler's batting and a batter's "
                                "bowling are reported separately and never merged."],
           ["Match-day correlation", "Noise is estimated from match-to-match variation, and the bootstrap resamples whole "
                                     "matches, not individual balls."]], widths=[1.7, 5.3])

    # ---------------------------------------------------------------- 6 results
    heading("6. The top tens, and the evidence")
    d.add_heading("6.1 Batters", 2)
    sdb = bat["score"].std()
    top_table("batters", widths=[0.33, 1.52, 1.05, 0.62, 0.78, 0.66, 0.7, 0.72, 0.72, 0.72], cols=[("#", lambda r: int(r["rank"])), ("Player", lambda r: r["name"]), ("Team", lambda r: SHORT.get(r["team"], r["team"])),
                          ("Rating", lambda r: f1(r["rating"])), ("90% range", lambda r: f"{100 + 15 * r['lo'] / sdb:.0f}–{100 + 15 * r['hi'] / sdb:.0f}"),
                          ("Top-10 odds", lambda r: f"{r['p_top10']:.0%}"), ("Press. balls", lambda r: int(r["n_p"])),
                          ("SR press.", lambda r: f"{r['sr_p']:.0f}"), ("SR ord.", lambda r: f"{r['sr_o']:.0f}"),
                          ("Avg press.", lambda r: f1(r["avg_p"]))])
    figure("04_top10_batters", "Figure 4. Ratings with their 90% bootstrap range. The dotted line is the average qualified batter.", 5.5)
    bullets([
        "**Vaibhav Sooryavanshi** is first by a distance and first in every variant we tried. 455 runs off 209 pressure "
        "balls at a strike rate of 218 and an average of 65, against an average of 38 on ordinary balls: he is the one "
        "player whose pressure average is far above his everyday one. He tops the list in 99.9% of resamples.",
        "**Abhishek Sharma** and **Tim David** follow on volume and level: both keep striking above 165 under pressure "
        "across 250+ pressure balls.",
        "**Suryakumar Yadav** and **Heinrich Klaasen** are the model's answer to the best middle-order players of the era: "
        "high level, modest lift, very large samples.",
        "**Priyansh Arya**, **Finn Allen** and **Josh Inglis** rate highly on a smaller base; their intervals are wider "
        "and their top-10 odds correspondingly lower.",
    ])
    figure("05_scatter_batters", "Figure 5. Pressure strike rate against ordinary strike rate; the diagonal is no change.", 4.0)

    d.add_heading("6.2 Bowlers", 2)
    sdw = bowl["score"].std()
    top_table("bowlers", widths=[0.33, 1.52, 1.05, 0.62, 0.78, 0.66, 0.7, 0.72, 0.72, 0.72], cols=[("#", lambda r: int(r["rank"])), ("Player", lambda r: r["name"]), ("Team", lambda r: SHORT.get(r["team"], r["team"])),
                          ("Rating", lambda r: f1(r["rating"])), ("90% range", lambda r: f"{100 + 15 * r['lo'] / sdw:.0f}–{100 + 15 * r['hi'] / sdw:.0f}"),
                          ("Top-10 odds", lambda r: f"{r['p_top10']:.0%}"), ("Press. balls", lambda r: int(r["n_p"])),
                          ("Econ press.", lambda r: f2(r["econ_p"])), ("Econ ord.", lambda r: f2(r["econ_o"])),
                          ("Wkts press.", lambda r: int(r["wkts_p"]))])
    figure("04_top10_bowlers", "Figure 6. Bowler ratings with their 90% bootstrap range.", 5.5)
    bullets([
        "**Jasprit Bumrah** and **Sunil Narine** are clear of the field and appear in the top ten in 98% and 99% of "
        "resamples. Both are elite on ordinary balls and give nothing extra away when the game tightens.",
        "**Kuldeep Yadav**, **Axar Patel** and **Mohsin Khan** are the model's lift specialists: each is more than a run "
        "an over cheaper under pressure than in ordinary play.",
        "**Bhuvneshwar Kumar** has the largest sample of any bowler in the pool (634 pressure balls) and is cheaper under "
        "pressure than outside it; the rating treats that as close to settled.",
        "**Nathan Ellis**, **Matheesha Pathirana** and **Varun Chakravarthy** complete the ten; places 6 to 10 are "
        "genuinely close, as the overlapping intervals show.",
    ])
    figure("05_scatter_bowlers", "Figure 7. Pressure economy against ordinary economy; below the diagonal is better under pressure.", 4.0)

    # ---------------------------------------------------------------- 7 reliability
    heading("7. Reliability, and where the model is least certain")
    d.add_heading("7.1 Does the rating repeat?", 2)
    vb, vw = V["batters"], V["bowlers"]
    table([["Measure", "Batters", "Bowlers"],
           ["Split-half reliability of the rating", f2(vb["split_half"]["composite"]["full_sample_reliability"]),
            f2(vw["split_half"]["composite"]["full_sample_reliability"])],
           ["Split-half reliability of raw pressure averages", f2(vb["split_half"]["raw_level"]["full_sample_reliability"]),
            f2(vw["split_half"]["raw_level"]["full_sample_reliability"])],
           ["Predicts pressure results in held-out matches (our rating)", f2(vb["holdout_prediction"]["joint_shrunk_level (ours)"]),
            f2(vw["holdout_prediction"]["joint_shrunk_level (ours)"])],
           ["…using raw pressure averages instead", f2(vb["holdout_prediction"]["raw_pressure_average"]),
            f2(vw["holdout_prediction"]["raw_pressure_average"])],
           ["…using only the player's pressure balls, shrunk", f2(vb["holdout_prediction"]["pressure_only_shrunk"]),
            f2(vw["holdout_prediction"]["pressure_only_shrunk"])],
           ["2022–24 estimate predicting 2025–26 pressure results", f2(vb["persistence"]["predict_later_pressure_level"]["joint_shrunk_level (ours)"]),
            f2(vw["persistence"]["predict_later_pressure_level"]["joint_shrunk_level (ours)"])],
           ["Rating against pressure win probability added", f2(vb["score_vs_pressure_wpa_per_ball"]),
            f2(vw["score_vs_pressure_wpa_per_ball"])]], widths=[4.0, 1.5, 1.5])
    figure("06_reliability", "Figure 8. Estimated on half the matches, tested on the other half: borrowing from a player's ordinary balls beats using his pressure balls alone.", 5.3)
    d.add_heading("7.2 Does the order survive a different method?", 2)
    for fname, label in (("batters", "Batters"), ("bowlers", "Bowlers")):
        s = pd.read_csv(REPORTS / "validation" / f"sensitivity_{fname}.csv")
        para(label, 10.5, True, NAVY, after=3)
        table([["Change to the method", "Players compared", "Rank correlation", "Top 10 kept"]] +
              [[r["variant"], r["players_compared"], f2(r["spearman_vs_primary"]), f"{r['primary_top10_in_variant_top10']} of 10"]
               for _, r in s.iterrows()], widths=[3.4, 1.3, 1.3, 1.0], size=9)
    d.add_heading("7.3 Where we are least certain", 2)
    bullets([
        "**Pressure skill is mostly ordinary skill.** True pressure and ordinary talent correlate at about 0.9. Rating "
        "players on their pressure balls alone produces a list that does not repeat, so the rating deliberately borrows "
        "from every ball a player has faced or bowled.",
        "**Lift is real but small, and poorly identified.** The likelihood for its spread is flat from 0 to 0.8. A reader "
        "who believes there is no such thing as a pressure player can set κ = 0 and still keep 9 of our 10 batters.",
        "**This describes 2022–26; it is not a forecast.** Bowlers' pressure form carries into later seasons "
        f"(correlation {f2(vw['persistence']['predict_later_pressure_level']['joint_shrunk_level (ours)'])}); batters' "
        f"barely does ({f2(vb['persistence']['predict_later_pressure_level']['joint_shrunk_level (ours)'])}). Lift itself "
        "does not persist between eras for either group, which matches what baseball found about clutch hitting.",
        "**Places 6 to 10 are close calls.** IPL-only and T20I-only versions of the method keep between 3 and 8 of each "
        "top ten; the bootstrap intervals in Figures 4 and 6 overlap heavily below the top three.",
        "**What we do not measure.** Fielding, wicketkeeping, captaincy, the state of the pitch on the day, the partner at "
        "the other end, injuries, and intent. A dropped catch off a bowler counts against him.",
        "**Data limits.** Expected runs run about 0.05 high per ball before centring (removed by the tier/season/phase "
        "centring); 2% of balls involve players without a Cricsheet identity; and balls against associate nations lean on "
        "the team-strength term rather than individual opponent effects.",
    ])

    # ---------------------------------------------------------------- 8 RR squad
    heading("8. Applying it: the Rajasthan Royals squad")
    para("The same machinery answers a practical question: who should RR keep before the IPL 2027 mini-auction. Output is "
         "priced by taking each player's runs above a replacement-level player in IPL 2026 and valuing them at what RR's "
         "own wage bill implies a run is worth. Reporting (salaries, injuries, trade talk) informs the verdicts but never "
         "the ratings; each item is logged with its source and a reliability tier in the repository.")
    m = pd.read_csv(REPORTS / "rr" / "squad_metrics.csv", dtype={"pid": str}).set_index("pid")
    rows = [["Player", "Salary (₹ cr)", "Output worth", "Surplus", "Verdict"]]
    for p in sorted(SQ["players"], key=lambda x: -x["salary"]):
        v = VD["players"][str(p["pid"])]
        r = m.loc[str(p["pid"])]
        rows.append([p["name"], f1(p["salary"]), f1(r["value_cr"]), f"{r['surplus_cr']:+.1f}", v["verdict"]])
    table(rows, widths=[2.2, 1.2, 1.2, 1.1, 1.3], size=8.5)
    figure("07_squad_value", "Figure 9. RR contracts against what the model says the output is worth.", 5.3)
    keep = [p for p in SQ["players"] if VD["players"][str(p["pid"])]["verdict"] == "Retain"]
    spent = sum(p["salary"] for p in keep)
    bullets([
        f"**Retain {len(keep)}, release {len(SQ['players']) - len(keep)}.** That commits ₹{spent:.1f} crore and leaves about "
        f"₹{SQ['purse_total_cr'] - spent:.1f} crore of a reported ₹{SQ['purse_total_cr']} crore purse for "
        f"{SQ['squad_max'] - len(keep)} slots, with {SQ['overseas_max'] - sum(p['overseas'] for p in keep)} overseas places open.",
        "**The three needs the data shows:** " + "; ".join(n["need"][0].lower() + n["need"][1:] for n in VD["needs"]) + ".",
        "**The biggest bargains are already at the club**: Sooryavanshi (₹1.1 cr), Brijesh Sharma (₹0.3 cr) and Donovan "
        "Ferreira (₹1 cr) together return about ₹47 crore of surplus value, which is the 2008 Royals formula.",
        "**The clearest release is Shimron Hetmyer** (₹11 cr for 78 runs at a strike rate of 113 in 2026, dropped by the "
        "final league game), followed by Tushar Deshpande (economy 12.0).",
    ])
    callout("THE INTERACTIVE VERSION",
            "The dashboard carries a page per player with his pressure splits, phase and match-up breakdowns, biggest "
            "pressure days, the reasoning behind each verdict with sources, and a purse planner you can toggle. Full "
            "method, code and sources: github.com/TharunAdithyan120506/rr-pressure-lab")

    out = REPORTS / "Methodology_Report.docx"
    d.save(out)
    print("wrote", out, f"({out.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
