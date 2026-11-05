"""The CFO view of the cost layer: unit costs of a siting slip for solar, wind and storage.

Ported from pricephillips/data-center-map cost_cfo.py (spec 025, iteration 3).
A CFO deciding where to site needs unit costs to apply to their own sites,
not other developers' histories priced one by one. This module turns the
anchor registry into those unit costs. It predicts nothing: no probability of
a block or a slip is multiplied into any figure. The reader applies their own
slip scenarios to published rates. No figure here is the effect of
opposition; a slip is a slip, whatever its reason.

Reads (read only)
  config/cost_anchors.json      through cost_ledger.load_anchors
  data/cost/cost_ledger.csv     observed spans of the priced ledger rows, for
                                the brief's descriptive timeline section

Writes (internal: no page, report or headline figure reads them)
  data/cost/cost_rate_card.csv  per technology, per MW: one month of slip
                                (escalation and the economic cost of
                                deferral), gross revenue deferred per month,
                                capital at risk on a block, and the federal
                                tax credit at stake at the placed-in-service
                                deadline
  data/cost/cost_scenarios.csv  a 100 MW project slipping 3, 6, 12, 18 and 24
                                months, per technology
  data/cost/cost_sensitivity.csv the reference case's delay cost with each
                                anchor moved low to high, the others at
                                midpoints
  data/cost/cost_brief.md       the brief built from all of the above

Usage
  python scripts/cost_cfo.py [--as-of YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics as st
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cost_ledger as cl  # noqa: E402
from common import write_csv  # noqa: E402

ROOT = cl.ROOT
LEDGER_CSV = cl.OUT_LEDGER
OUT_RATE = ROOT / "data" / "cost" / "cost_rate_card.csv"
OUT_SCEN = ROOT / "data" / "cost" / "cost_scenarios.csv"
OUT_SENS = ROOT / "data" / "cost" / "cost_sensitivity.csv"
OUT_BRIEF = ROOT / "data" / "cost" / "cost_brief.md"

SCENARIO_MW = 100
SCENARIO_MONTHS = (3, 6, 12, 18, 24)
REFERENCE_MONTHS = 12
FEW = 10   # fewer observed spans than this: the quartiles are marked as resting on few projects
DEADLINE_KINDS = ("begin_construction", "termination", "continuity", "phase_down")
TECH_LABEL = {"solar": "Solar PV", "wind": "Land-based wind", "battery_storage": "Battery storage"}
TECH_TEXT = {"solar": "solar PV", "wind": "land-based wind", "battery_storage": "battery storage"}

RATE_COLS = ["technology", "capex_per_mw_low", "capex_per_mw_high",
             "escalation_per_mw_month_low", "escalation_per_mw_month_high",
             "deferral_cost_per_mw_month_low", "deferral_cost_per_mw_month_high",
             "delay_cost_per_mw_month_low", "delay_cost_per_mw_month_high",
             "gross_revenue_deferred_per_mw_month_low", "gross_revenue_deferred_per_mw_month_high",
             "capital_at_risk_per_mw_low", "capital_at_risk_per_mw_high",
             "credit_at_deadline_per_mw_low", "credit_at_deadline_per_mw_high", "stale_anchors"]
SCEN_COLS = ["technology", "mw", "slip_months", "escalation_low", "escalation_high",
             "deferral_cost_low", "deferral_cost_high", "delay_cost_low", "delay_cost_high",
             "gross_revenue_deferred_low", "gross_revenue_deferred_high"]
SENS_COLS = ["technology", "anchor_id", "confidence", "delay_cost_at_anchor_low",
             "delay_cost_at_anchor_high", "swing"]


def slip_costs(anchors: dict, tech: str, mw: float, months: float) -> dict:
    c = cl.capex(anchors, tech, mw)
    e = cl.escalation(anchors, tech, c, (months, months))
    n = cl.deferral_npv(anchors, tech, mw, (months, months))
    g = cl.annual_revenue(anchors, tech, mw)
    return {"escalation": e, "deferral": n, "delay": (e[0] + n[0], e[1] + n[1]),
            "gross": (g[0] * months / 12, g[1] * months / 12), "capex": c}


def credit_rate(anchors: dict, tech: str) -> dict | None:
    return anchors.get(f"credit_rate_{tech}") or anchors.get("credit_rate")


def tech_anchor_ids(anchors: dict, tech: str) -> set[str]:
    return ({cl.anchor(anchors, b, tech)["anchor_id"] for b in ("capex_per_mw", "construction_escalation")}
            | cl.deferral_anchor_ids(tech, anchors) | {"predevelopment_share"})


def rate_card(anchors: dict, stale: set[str], credit_techs: frozenset = frozenset()) -> list[dict]:
    out = []
    for tech in cl.TECHNOLOGIES:
        s = slip_costs(anchors, tech, 1, 1)
        sh = anchors["predevelopment_share"]
        row = {"technology": tech}
        for name, (lo, hi) in (("capex_per_mw", s["capex"]), ("escalation_per_mw_month", s["escalation"]),
                               ("deferral_cost_per_mw_month", s["deferral"]),
                               ("delay_cost_per_mw_month", s["delay"]),
                               ("gross_revenue_deferred_per_mw_month", s["gross"]),
                               ("capital_at_risk_per_mw", (s["capex"][0] * sh["value_low"],
                                                           s["capex"][1] * sh["value_high"]))):
            row[f"{name}_low"], row[f"{name}_high"] = f"{lo:.0f}", f"{hi:.0f}"
        used = tech_anchor_ids(anchors, tech)
        cr = credit_rate(anchors, tech)
        if cr and tech in credit_techs:
            used.add(cr["anchor_id"])
            row["credit_at_deadline_per_mw_low"] = f"{s['capex'][0] * cr['value_low']:.0f}"
            row["credit_at_deadline_per_mw_high"] = f"{s['capex'][1] * cr['value_high']:.0f}"
        row["stale_anchors"] = ";".join(sorted(used & stale))
        out.append(row)
    return out


def scenarios(anchors: dict) -> list[dict]:
    out = []
    for tech in cl.TECHNOLOGIES:
        for mo in SCENARIO_MONTHS:
            s = slip_costs(anchors, tech, SCENARIO_MW, mo)
            row = {"technology": tech, "mw": SCENARIO_MW, "slip_months": mo}
            for name, key in (("escalation", "escalation"), ("deferral_cost", "deferral"),
                              ("delay_cost", "delay"), ("gross_revenue_deferred", "gross")):
                row[f"{name}_low"], row[f"{name}_high"] = f"{s[key][0]:.0f}", f"{s[key][1]:.0f}"
            out.append(row)
    return out


def _at(anchors: dict, aid: str, value: float) -> dict:
    """Every anchor at its midpoint, `aid` at `value`."""
    out = {}
    for k, a in anchors.items():
        v = value if k == aid else (a["value_low"] + a["value_high"]) / 2
        out[k] = {**a, "value_low": v, "value_high": v}
    return out


def sensitivity(anchors: dict) -> list[dict]:
    out = []
    for tech in cl.TECHNOLOGIES:
        rows = []
        for aid in sorted(tech_anchor_ids(anchors, tech) - {"predevelopment_share"}):
            a = anchors[aid]
            lo = slip_costs(_at(anchors, aid, a["value_low"]), tech, SCENARIO_MW, REFERENCE_MONTHS)["delay"][0]
            hi = slip_costs(_at(anchors, aid, a["value_high"]), tech, SCENARIO_MW, REFERENCE_MONTHS)["delay"][0]
            rows.append({"technology": tech, "anchor_id": aid, "confidence": a["confidence"],
                         "delay_cost_at_anchor_low": f"{lo:.0f}", "delay_cost_at_anchor_high": f"{hi:.0f}",
                         "swing": f"{abs(hi - lo):.0f}"})
        out += sorted(rows, key=lambda r: -float(r["swing"]))
    return out


# ---------------------------------------------------------------------------
# Federal tax credit deadlines (config/cost_anchors.json "credit_deadlines")
# ---------------------------------------------------------------------------

def load_deadlines(path: Path = cl.ANCHORS_JSON) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh).get("credit_deadlines") or []
    for d in rows:
        for f in ("deadline_id", "kind", "technologies", "rule", "date", "source", "source_url", "reverify_by"):
            if not d.get(f):
                raise cl.AnchorError(f"credit deadline {d.get('deadline_id', '?')}: missing {f}")
        if d["kind"] not in DEADLINE_KINDS:
            raise cl.AnchorError(f"credit deadline {d['deadline_id']}: kind must be one of {', '.join(DEADLINE_KINDS)}")
        if not str(d["source_url"]).startswith("http"):
            raise cl.AnchorError(f"credit deadline {d['deadline_id']}: source_url must be a URL")
        date.fromisoformat(d["date"])
        date.fromisoformat(d["reverify_by"])
    return rows


def credit_techs(deadlines: list[dict]) -> frozenset:
    """Technologies with a termination date: the credit is at stake at that
    date. A phase-down or a construction-start date is listed, not priced."""
    return frozenset(t for d in deadlines if d.get("kind") == "termination" for t in d["technologies"])


# ---------------------------------------------------------------------------
# Observed spans (descriptive, from the ledger)
# ---------------------------------------------------------------------------

def observed_spans(path: Path = LEDGER_CSV) -> list[dict]:
    """Quartiles of the recorded span, first interconnection request to
    decision, of the ledger's priced decided rows, by technology."""
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh)
                if not r["withheld_reason"] and r["span_kind"] == "request_to_decision"]
    out = []
    for tech in cl.TECHNOLOGIES:
        days = sorted(int(r["span_days"]) for r in rows if r["priced_technology"] == tech)
        if not days:
            continue
        q = st.quantiles(days, n=4, method="inclusive") if len(days) > 1 else [days[0]] * 3
        out.append({"technology": tech, "n": len(days), "q1": q[0], "median": q[1], "q3": q[2]})
    return out


# ---------------------------------------------------------------------------
# Brief
# ---------------------------------------------------------------------------

def m(x) -> str:
    x = float(x)
    if abs(x) >= 1e9:
        return f"${x / 1e9:,.2f}B"
    if abs(x) >= 1e6:
        return f"${x / 1e6:,.1f}M"
    if abs(x) >= 1e3:
        return f"${x / 1e3:,.0f}K"
    return f"${x:,.0f}"


def rng(row: dict, name: str) -> str:
    lo, hi = row.get(f"{name}_low", ""), row.get(f"{name}_high", "")
    return f"{m(lo)} to {m(hi)}" if lo != "" and hi != "" else "not priced"


def long_date(d) -> str:
    """A date for running text, e.g. October 27, 2026; tables keep ISO dates."""
    d = date.fromisoformat(d) if isinstance(d, str) else d
    return f"{d:%B} {d.day}, {d.year}"


def pct(x: float) -> str:
    return f"{x * 100:.1f}%".replace(".0%", "%")


def years(days: float) -> str:
    return f"{days / 365.25:.1f} years"


def brief(anchors: dict, rate: list[dict], scen: list[dict], sens: list[dict],
          deadlines: list[dict], spans: list[dict], stale: set[str], as_of: date) -> str:
    sh = anchors["predevelopment_share"]
    L = [
        "# Cost of a siting slip: solar, wind and storage",
        "",
        f"Generated {long_date(as_of)} by `scripts/cost_cfo.py`. **Internal, not for client delivery.** No",
        "decision has been made about quoting these figures outside the company. (Price decided on",
        "October 27, 2026 how the data center rate card may be quoted.) Until Price decides for this brief,",
        "every section stays internal.",
        "",
        "These are unit costs from published figures and Hawthorn's stated assumptions, for a project whose",
        "schedule slips, whatever the reason; a slip is a delay to the schedule, measured in months. Each input is an",
        "anchor (a low-high value in `config/cost_anchors.json`). The figures do not measure what opposition",
        "does to a project, and no probability of a slip or a block is multiplied into them. Every cost",
        "figure is a low-high range, except in the sensitivity tables, which hold the other anchors at their",
        "midpoints. Apply your own slip scenario to your own site.",
        "",
        "## One month of slip, per MW (national rates)",
        "",
        "National rates means every anchor is a national figure; none is regional yet. Delay cost is construction",
        "escalation plus the economic cost of deferring the project's net revenue (gross revenue less fixed",
        "operation and maintenance (O&M) cost), discounted at the cost of capital (the annual rate used to",
        "discount future revenue). Capital at risk (development spending before construction, estimated as",
        f"an assumed {pct(sh['value_low'])} to {pct(sh['value_high'])} of installed cost) is what a blocked "
        "project would not recover.",
        "",
        "| Technology | Delay cost per MW per month | of which escalation | of which deferral | "
        "Capital at risk per MW if blocked |",
        "|---|---|---|---|---|",
    ]
    for r in rate:
        L.append(f"| {TECH_LABEL[r['technology']]} | {rng(r, 'delay_cost_per_mw_month')} | "
                 f"{rng(r, 'escalation_per_mw_month')} | {rng(r, 'deferral_cost_per_mw_month')} | "
                 f"{rng(r, 'capital_at_risk_per_mw')} |")
    L += ["", "Gross revenue deferred, for comparison only (revenue that arrives later, not a cost, and never "
          "added to the delay cost): "
          + "; ".join(f"{TECH_TEXT[r['technology']]} {rng(r, 'gross_revenue_deferred_per_mw_month')}"
                      " per MW per month" for r in rate) + ".", ""]

    L += ["## A 100 MW project, national rates", ""]
    for tech in cl.TECHNOLOGIES:
        L += [f"**{TECH_LABEL[tech]}**", "", "| Slip | Escalation | Deferral | Delay cost |", "|---|---|---|---|"]
        for s in (s for s in scen if s["technology"] == tech):
            L.append(f"| {s['slip_months']} months | {rng(s, 'escalation')} | {rng(s, 'deferral_cost')} | "
                     f"{rng(s, 'delay_cost')} |")
        L.append("")
    L += ["Every component scales with MW; `data/cost/cost_scenarios.csv` has each technology.", ""]

    if deadlines:
        L += ["## Federal tax credit deadlines", "",
              "The clean electricity credits change at a date rather than by the month. Each deadline",
              "changes what a project can claim: see the Rule column. Whether a given project qualifies is a",
              "tax question for the project's own counsel.", "",
              "| Applies to | Rule | Date | Source |", "|---|---|---|---|"]
        for d in deadlines:
            techs = ", ".join(TECH_TEXT[t] for t in d["technologies"])
            passed = " (passed)" if date.fromisoformat(d["date"]) < as_of else ""
            L.append(f"| {techs} | {d['rule']} | {d['date']}{passed} | {d['source_url']} |")
        L += [""]
        priced = [r for r in rate if r.get("credit_at_deadline_per_mw_low")]
        if priced:
            cr = anchors.get("credit_rate", {})
            term = [d for d in deadlines if d["kind"] == "termination"]
            when = long_date(term[0]["date"]) if term else "the placed-in-service"
            L += [f"The table below (also in `data/cost/cost_rate_card.csv`) is the 48E credit at "
                  f"{pct(cr.get('value_high', 0))} (prevailing wage and apprenticeship requirements met) times "
                  f"the full per-MW capital cost: an upper bound on the credit at stake at the {when} "
                  "placed-in-service date.", ""]
            L += ["| Technology | Credit at stake per MW |", "|---|---|"]
            L += [f"| {TECH_LABEL[r['technology']]} | {rng(r, 'credit_at_deadline_per_mw')} |" for r in priced]
            L.append("")

    L += ["## Which anchor moves the delay cost most", "",
          f"A 100 MW project slipping {REFERENCE_MONTHS} months, national rates, every anchor at its midpoint "
          "except the one moved from its low to its high value. Largest swing first.", ""]
    for tech in cl.TECHNOLOGIES:
        L += [f"**{TECH_LABEL[tech]}**", "", "| Anchor | Confidence | At its low | At its high | Swing |",
              "|---|---|---|---|---|"]
        for s in (s for s in sens if s["technology"] == tech):
            L.append(f"| `{s['anchor_id']}` | {s['confidence']} | {m(s['delay_cost_at_anchor_low'])} | "
                     f"{m(s['delay_cost_at_anchor_high'])} | {m(s['swing'])} |")
        L.append("")

    L += ["## How long these spans have run (observed, descriptive)", "",
          "From `data/cost/cost_ledger.csv`: the recorded span from a contested project's start date (its",
          "first interconnection request, or a dated event in the record) to its decision, for the priced",
          "rows with a confirmed outcome. These",
          "are the tracked sample's own histories, not a forecast and not an effect of opposition; most",
          "contested projects have no dated first request and are not in it.", ""]
    if spans:
        L += ["| Technology | Projects | First quartile | Median | Third quartile |", "|---|---|---|---|---|"]
        for s in spans:
            few = " (few projects)" if s["n"] < FEW else ""
            L.append(f"| {TECH_LABEL[s['technology']]} | {s['n']}{few} | {years(s['q1'])} | "
                     f"{years(s['median'])} | {years(s['q3'])} |")
        L.append("")
    else:
        L += ["No priced decided row in the ledger yet.", ""]

    L += ["## Assumptions and sources", "",
          "| Anchor | Low | High | Unit | Confidence | As of | Re-verify by |", "|---|---|---|---|---|---|---|"]
    for aid in sorted(anchors):
        a = anchors[aid]
        mark = " (stale)" if aid in stale else ""
        L.append(f"| `{aid}`{mark} | {cl.fmt_value(a['value_low'])} | {cl.fmt_value(a['value_high'])} | {a['unit']} | "
                 f"{a['confidence']} | {a['source_date']} | {a['reverify_by']} |")
    assumed = [f"`{aid}`" for aid in sorted(anchors) if anchors[aid]["confidence"] == "assumption"]
    L += ["", "Hawthorn's assumptions, not published figures, each with its basis in the methodology: "
          + ", ".join(assumed) + ". Sources and what each figure includes: `data/cost/cost_methodology.md`.", ""]
    if stale:
        L += ["**Stale anchors** on the run date: " + ", ".join(f"`{s}`" for s in sorted(stale))
              + ". Re-verify each one before using any figure that rests on it.", ""]
    else:
        nxt = min(anchors.values(), key=lambda a: a["reverify_by"])
        L += [f"No anchor was past its re-verify date on {long_date(as_of)}. The next one due is "
              f"`{nxt['anchor_id']}`, on {long_date(nxt['reverify_by'])}.", ""]

    L += ["## Applying these to a site", "",
          "1. Pick the technology and the site's MW. Multiply the per-MW figures by the MW.",
          "2. Choose the slip you want to price (months) and multiply the per-month delay cost by it; for a",
          "   long slip, read `data/cost/cost_scenarios.csv` instead: the deferral cost grows a little less",
          "   than in proportion to the slip, so months times the monthly figure overstates it.",
          "3. If the site could be blocked, the development capital at risk is the per-MW figure times the MW.",
          "4. For solar and wind, check the slip against the tax credit deadlines above: a slip that crosses",
          "   one puts the credit at stake, whatever its length.",
          "5. Keep gross revenue deferred out of any total.", ""]
    return "\n".join(L)


def generated_text(rate, scen, sens, text) -> dict[str, str]:
    return {"cost_brief.md": text,
            **{f"rate {r['technology']}": " ".join(map(str, r.values())) for r in rate}}


def run(as_of: date) -> int:
    try:
        anchors = cl.load_anchors()
        deadlines = load_deadlines()
    except cl.AnchorError as e:
        print(f"cost_cfo: {e}", file=sys.stderr)
        return 1
    stale = cl.stale_ids(anchors, as_of) | {d["deadline_id"] for d in deadlines
                                            if as_of > date.fromisoformat(d["reverify_by"])}
    rate = rate_card(anchors, stale, credit_techs(deadlines))
    scen, sens = scenarios(anchors), sensitivity(anchors)
    text = brief(anchors, rate, scen, sens, deadlines, observed_spans(), stale, as_of)
    hits = cl.banned_hits(generated_text(rate, scen, sens, text))
    if hits:
        print("cost_cfo: banned wording in its own outputs: " + "; ".join(hits[:5]), file=sys.stderr)
        return 1
    write_csv(OUT_RATE, rate, RATE_COLS)
    write_csv(OUT_SCEN, scen, SCEN_COLS)
    write_csv(OUT_SENS, sens, SENS_COLS)
    OUT_BRIEF.write_text(text, encoding="utf-8")
    for r in rate:
        print(f"cost_cfo: {r['technology']}: delay {rng(r, 'delay_cost_per_mw_month')} per MW per month; "
              f"at risk if blocked {rng(r, 'capital_at_risk_per_mw')} per MW")
    if stale:
        print("cost_cfo: STALE (re-verify before any use): " + ", ".join(sorted(stale)))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    return run(ap.parse_args().as_of)


if __name__ == "__main__":
    sys.exit(main())
