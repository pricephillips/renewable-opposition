"""Cost ledger: the observed span of each contested project, priced at published rates.

Ported from pricephillips/data-center-map cost_translation.py (spec 025, the
cost ledger) for solar, wind and battery storage. It is case-level observed-
cost accounting: it prices what each project's own record shows (the span
from its first interconnection request to its decision, or to the run date
for a pending project) and estimates nothing about what opposition did. No
figure here is the effect of opposition, and no row compares a project with
one that saw none.

Reads (read only)
  config/cost_anchors.json               the anchor registry: ranges, units,
                                         source URLs, as-of and re-verify-by
                                         dates, by technology
  data/processed/contested_projects.csv  outcome, technology, MW, resolution
                                         date
  data/reference/queue_matches.csv       each project's Queued Up requests
                                         and the date of the first one

Writes (internal: no page, report or headline figure reads them)
  data/cost/cost_ledger.csv        one row per contested project: ranges, or
                                   the reason it is withheld
  data/cost/cost_anchors.csv       the registry as CSV
  data/cost/cost_methodology.md    every formula, the precision rule and the
                                   ledger's counts

Rules
  - Every dollar figure is a low-high range from the anchors' low and high
    values and the precision-widened span; never a point estimate.
  - The span starts at the project's first interconnection request when the
    queue match is strong (LBNL Queued Up dates the request to the day), else
    at a day- or month-precision date in event_date_text. A year-precision
    start is withheld. A decided project's span ends at its resolution date;
    a pending one's at the run date (accrued_to_date).
  - Capital basis is the per-MW anchor for the project's technology times a
    stated MW: the record's own capacity_mw, else the matched federal plant
    inventory entry's, else the strongly matched queue request's. MW is never
    imputed, and never derived from acres or dollars.
  - Destroyed value (construction escalation, development capital at risk on
    a block) stays apart from deferred revenue exposure (gross revenue that
    arrives later: an upper bound, never a cost and never in a total).
  - A blocked project is never built and never earns, so it carries capital
    at risk only.
  - A stale anchor (past its reverify_by date) warns and is flagged on every
    row that used it; a published anchor without a source URL fails the run.
  - The run fails if its own outputs use outcome scorekeeping words or say a
    figure was caused by or attributable to anything.

Usage
  python scripts/cost_ledger.py [--as-of YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import calendar
import csv
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import write_csv  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ANCHORS_JSON = ROOT / "config" / "cost_anchors.json"
PROJECTS_CSV = ROOT / "data" / "processed" / "contested_projects.csv"
QUEUE_MATCHES_CSV = ROOT / "data" / "reference" / "queue_matches.csv"
OUT_LEDGER = ROOT / "data" / "cost" / "cost_ledger.csv"
OUT_ANCHORS = ROOT / "data" / "cost" / "cost_anchors.csv"
OUT_METHOD = ROOT / "data" / "cost" / "cost_methodology.md"

DAYS_PER_MONTH = 30.44
HOURS_PER_YEAR = 8760
TECHNOLOGIES = ("solar", "wind", "battery_storage")
# Technologies whose revenue is energy sold (MWh); storage earns a capacity
# payment per kW-month instead.
ENERGY_TECHS = ("solar", "wind")
# Anchors every priced technology needs; a technology-specific anchor is
# "<base>_<technology>" and wins over a shared "<base>".
TECH_ANCHORS = ("capex_per_mw", "construction_escalation", "fixed_om_kw_year", "project_life_years")
ENERGY_ANCHORS = ("capacity_factor", "ppa_price_mwh")
STORAGE_ANCHORS = ("capacity_price_kw_month",)
SHARED_ANCHORS = ("carrying_rate", "predevelopment_share")
ANCHOR_COLS = ["anchor_id", "technology", "description", "value_low", "value_high", "unit",
               "source", "source_date", "confidence", "source_url", "reverify_by"]

DECIDED = {"blocked_confirmed": "blocked", "advanced_confirmed": "advanced",
           "restricted_conditional": "advanced"}
UNVERIFIED = ("blocked_unverified", "advanced_unverified")
WITHHELD_REASONS = ("technology_not_priced", "outcome_needs_review", "outcome_unverified",
                    "no_start_date", "start_year_precision", "start_from_possible_queue_match",
                    "no_end_date", "nonpositive_span", "no_capacity_mw")

LEDGER_COLS = [
    "project_id", "project_name", "state", "county", "county_fips", "technology",
    "priced_technology", "outcome", "span_kind",
    "start_date", "start_source", "start_precision", "end_date", "end_source", "end_precision",
    "span_days", "span_days_low", "span_days_high",
    "capacity_mw", "mw_source", "capex_low", "capex_high",
    "escalation_cost_low", "escalation_cost_high",
    "block_sunk_cost_low", "block_sunk_cost_high",
    "deferred_revenue_exposure_low", "deferred_revenue_exposure_high",
    "deferral_npv_cost_low", "deferral_npv_cost_high",
    "total_economic_cost_low", "total_economic_cost_high",
    "stale_anchors", "review_flags", "withheld_reason", "note",
]
DOLLAR_COLS = [c for c in LEDGER_COLS if c.endswith(("_low", "_high")) and not c.startswith("span_")]

BANNED = re.compile(r"\b(win|wins|loss|losses|lost|caused by|attributable to|due to opposition)\b",
                    re.IGNORECASE)
OFFSHORE = re.compile(r"\boff-?shore\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Anchor registry
# ---------------------------------------------------------------------------

class AnchorError(ValueError):
    pass


def required_ids() -> list[str]:
    """Every anchor id the ledger can ask for: per technology, the shared
    or technology-specific form must exist (checked in validate_anchors)."""
    return list(SHARED_ANCHORS)


def validate_anchors(anchors: list[dict]) -> dict[str, dict]:
    """Check every required field; return anchors by id."""
    by_id: dict[str, dict] = {}
    for a in anchors:
        aid = a.get("anchor_id", "?")
        for f in ("anchor_id", "description", "unit", "source", "source_date", "confidence",
                  "reverify_by"):
            if not str(a.get(f) or "").strip():
                raise AnchorError(f"anchor {aid}: missing {f}")
        if aid in by_id:
            raise AnchorError(f"anchor {aid}: duplicate id")
        if a["confidence"] not in ("published", "assumption"):
            raise AnchorError(f"anchor {aid}: confidence must be published or assumption")
        if a["confidence"] == "published" and not str(a.get("source_url") or "").startswith("http"):
            raise AnchorError(f"anchor {aid}: published anchor needs a source_url")
        lo, hi = a.get("value_low"), a.get("value_high")
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (lo, hi)) \
                or not 0 <= lo <= hi:
            raise AnchorError(f"anchor {aid}: needs 0 <= value_low <= value_high")
        if not re.fullmatch(r"\d{4}-\d{2}", a["source_date"]):
            raise AnchorError(f"anchor {aid}: source_date must be YYYY-MM")
        try:
            date.fromisoformat(a["reverify_by"])
        except ValueError:
            raise AnchorError(f"anchor {aid}: reverify_by must be YYYY-MM-DD") from None
        tech = a.get("technology", "")
        if tech and tech not in TECHNOLOGIES:
            raise AnchorError(f"anchor {aid}: technology must be one of {', '.join(TECHNOLOGIES)}")
        if tech and not aid.endswith("_" + tech):
            raise AnchorError(f"anchor {aid}: a {tech} anchor's id ends in _{tech}")
        by_id[aid] = a
    missing = [i for i in required_ids() if i not in by_id]
    for tech in TECHNOLOGIES:
        bases = TECH_ANCHORS + (ENERGY_ANCHORS if tech in ENERGY_TECHS else STORAGE_ANCHORS)
        missing += [f"{b}_{tech}" for b in bases if f"{b}_{tech}" not in by_id and b not in by_id]
    if missing:
        raise AnchorError(f"anchors missing: {', '.join(missing)}")
    return by_id


def load_anchors(path: Path = ANCHORS_JSON) -> dict[str, dict]:
    with open(path, encoding="utf-8") as fh:
        return validate_anchors(json.load(fh)["anchors"])


def anchor(anchors: dict, base: str, tech: str) -> dict:
    """The technology's own anchor when there is one, else the shared one."""
    return anchors.get(f"{base}_{tech}") or anchors[base]


def stale_ids(anchors: dict[str, dict], as_of: date) -> set[str]:
    return {i for i, a in anchors.items() if as_of > date.fromisoformat(a["reverify_by"])}


# ---------------------------------------------------------------------------
# Economics shared with the CFO view (scripts/cost_cfo.py)
# ---------------------------------------------------------------------------

def capex(anchors: dict, tech: str, mw: float) -> tuple[float, float]:
    a = anchor(anchors, "capex_per_mw", tech)
    return mw * a["value_low"], mw * a["value_high"]


def annual_revenue(anchors: dict, tech: str, mw: float) -> tuple[float, float]:
    """Gross revenue a year: energy (MW x capacity factor x 8760 h x PPA price)
    for solar and wind, a capacity payment (MW x 1000 kW x price x 12) for
    storage."""
    if tech in ENERGY_TECHS:
        cf, price = anchor(anchors, "capacity_factor", tech), anchor(anchors, "ppa_price_mwh", tech)
        return (mw * cf["value_low"] * HOURS_PER_YEAR * price["value_low"],
                mw * cf["value_high"] * HOURS_PER_YEAR * price["value_high"])
    cap = anchor(anchors, "capacity_price_kw_month", tech)
    return mw * 1000 * cap["value_low"] * 12, mw * 1000 * cap["value_high"] * 12


def revenue_anchor_ids(tech: str) -> set[str]:
    bases = ENERGY_ANCHORS if tech in ENERGY_TECHS else STORAGE_ANCHORS
    return {f"{b}_{tech}" for b in bases}


def escalation(anchors: dict, tech: str, c: tuple[float, float],
               months: tuple[float, float]) -> tuple[float, float]:
    """capital basis x annual escalation x months / 12."""
    e = anchor(anchors, "construction_escalation", tech)
    return c[0] * e["value_low"] * months[0] / 12, c[1] * e["value_high"] * months[1] / 12


def deferral_npv(anchors: dict, tech: str, mw: float,
                 months: tuple[float, float]) -> tuple[float, float]:
    """Present value given up when the project's net revenue stream starts
    `months` later. Net revenue = gross revenue - fixed O&M (MW x 1000 kW x
    $/kW-year), floored at 0; stream value = net x (1 - (1 + r)^-L) / r over
    the project life L; cost = value x (1 - (1 + r)^-(months / 12)), r the
    cost of capital (carrying_rate). The cost rises with revenue, life and
    delay and falls with O&M, but is not monotone in r, so each bound takes
    the extreme over both ends of the r range."""
    rev = annual_revenue(anchors, tech, mw)
    om = anchor(anchors, "fixed_om_kw_year", tech)
    life = anchor(anchors, "project_life_years", tech)
    r = anchors["carrying_rate"]

    def cost(revenue, om_kw, term, rate, mo):
        net = max(0.0, revenue - mw * 1000 * om_kw)
        if rate <= 0:
            return 0.0
        value = net * (1 - (1 + rate) ** -term) / rate
        return value * (1 - (1 + rate) ** -(mo / 12))
    lows = [cost(rev[0], om["value_high"], life["value_low"], rate, months[0])
            for rate in (r["value_low"], r["value_high"])]
    highs = [cost(rev[1], om["value_low"], life["value_high"], rate, months[1])
             for rate in (r["value_low"], r["value_high"])]
    return min(lows), max(highs)


def deferral_anchor_ids(tech: str, anchors: dict) -> set[str]:
    ids = {anchor(anchors, b, tech)["anchor_id"] for b in ("fixed_om_kw_year", "project_life_years")}
    return ids | {anchor(anchors, b, tech)["anchor_id"] for b in
                  (ENERGY_ANCHORS if tech in ENERGY_TECHS else STORAGE_ANCHORS)} | {"carrying_rate"}


# ---------------------------------------------------------------------------
# Dates, technology and MW
# ---------------------------------------------------------------------------

def parse_partial(v: str) -> tuple[date | None, str]:
    """(date, precision) for YYYY-MM-DD, YYYY-MM (floored to the 1st) or
    YYYY; (None, "") for anything else."""
    s = (v or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        try:
            return date.fromisoformat(s), "day"
        except ValueError:
            return None, ""
    if re.fullmatch(r"\d{4}-\d{2}", s):
        y, m = int(s[:4]), int(s[5:])
        return (date(y, m, 1), "month") if 1 <= m <= 12 else (None, "")
    if re.fullmatch(r"\d{4}", s):
        return date(int(s), 1, 1), "year"
    return None, ""


def _month_slack(d: date, precision: str) -> int:
    return calendar.monthrange(d.year, d.month)[1] - 1 if precision == "month" else 0


def span_range(start: date, start_prec: str, end: date, end_prec: str) -> tuple[int, int]:
    """A month-precision date is stored as the 1st of its month, so the true
    date is on or after it: a month-precision start can only shorten the span
    (by up to the rest of the month), a month-precision end only lengthen it.
    The low end is floored at 1 day."""
    span = (end - start).days
    return max(1, span - _month_slack(start, start_prec)), span + _month_slack(end, end_prec)


def parse_mw(v) -> float | None:
    try:
        x = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return x if x > 0 else None


def priced_technology(r: dict) -> tuple[str, list[str]]:
    """The technology the row is priced as ("" when it is not priced) and its
    review flags. Every listed technology must be solar, wind or storage; a
    list is priced on its first entry. Offshore wind is not priced: its costs
    are not those of the land-based anchors."""
    techs = [t.strip() for t in (r.get("technology") or "").split(";") if t.strip()]
    if not techs or any(t not in TECHNOLOGIES for t in techs):
        return "", []
    text = " ".join(r.get(c) or "" for c in ("project_name", "description", "long_description"))
    if "wind" in techs and OFFSHORE.search(text):
        return "", ["offshore_wind"]
    flags = ["hybrid_priced_on_primary"] if len(techs) > 1 else []
    return techs[0], flags


def capacity(r: dict, qm: dict | None) -> tuple[float | None, str]:
    """A stated MW and where it comes from; never imputed."""
    mw = parse_mw(r.get("capacity_mw"))
    if mw:
        return mw, "record"
    if (r.get("facility_match") or "") == "strong":
        mw = parse_mw(r.get("facility_capacity_mw"))
        if mw:
            return mw, "federal_plant_inventory"
    if qm and qm.get("match") == "strong":
        mw = parse_mw(qm.get("queue_capacity_mw"))
        if mw:
            return mw, "queue_request"
    return None, ""


def load_queue_matches(path: Path = QUEUE_MATCHES_CSV) -> dict[str, dict]:
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        return {r["id"]: r for r in csv.DictReader(fh)}


def load_projects(path: Path = PROJECTS_CSV) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

def _rng(row: dict, name: str, lo: float, hi: float) -> None:
    row[f"{name}_low"], row[f"{name}_high"] = f"{lo:.0f}", f"{hi:.0f}"


def _start(r: dict, qm: dict | None) -> tuple[date | None, str, str, str]:
    """(date, precision, source, withheld reason if no usable start)."""
    possible = False
    if qm and qm.get("first_request_date"):
        d, p = parse_partial(qm["first_request_date"])
        if qm.get("match") == "strong" and d and p in ("day", "month"):
            return d, p, "queue_request", ""
        possible = qm.get("match") != "strong"
    d, p = parse_partial(r.get("event_date_text", ""))
    if d and p in ("day", "month"):
        return d, p, "event_date", ""
    if possible:
        return None, "", "", "start_from_possible_queue_match"
    if d and p == "year":
        return None, "", "", "start_year_precision"
    return None, "", "", "no_start_date"


def ledger_row(r: dict, qm: dict | None, anchors: dict, stale: set[str], as_of: date) -> dict:
    row = {c: "" for c in LEDGER_COLS}
    row["project_id"] = (r.get("id") or "").strip()
    for c in ("project_name", "state", "county", "county_fips", "technology", "outcome"):
        row[c] = (r.get(c) or "").strip()
    outcome = row["outcome"]
    tech, flags = priced_technology(r)
    row["priced_technology"] = tech
    decided = outcome in DECIDED
    row["span_kind"] = "request_to_decision" if decided else (
        "accrued_to_date" if outcome == "pending" else "")

    def withhold(reason: str) -> dict:
        row["withheld_reason"] = reason
        row["review_flags"] = ";".join(flags)
        row["note"] = f"Withheld: {reason.replace('_', ' ')}. No dollar figure."
        return row

    if not tech:
        return withhold("technology_not_priced")
    if outcome == "needs_review":
        return withhold("outcome_needs_review")
    if outcome in UNVERIFIED:
        return withhold("outcome_unverified")
    if not row["span_kind"]:
        return withhold("outcome_needs_review")

    start, s_prec, s_src, reason = _start(r, qm)
    if reason:
        return withhold(reason)
    row["start_date"], row["start_precision"], row["start_source"] = start.isoformat(), s_prec, s_src
    if decided:
        end, e_prec = parse_partial(r.get("resolution_date", ""))
        if not end or e_prec not in ("day", "month"):
            return withhold("no_end_date")
        row["end_source"] = "resolution_date"
    else:
        end, e_prec = as_of, "day"
        row["end_source"] = "run_date"
    row["end_date"], row["end_precision"] = end.isoformat(), e_prec
    span = (end - start).days
    row["span_days"] = str(span)
    if span < 1:
        return withhold("nonpositive_span")
    mw, mw_src = capacity(r, qm)
    if mw is None:
        return withhold("no_capacity_mw")
    row["capacity_mw"], row["mw_source"] = f"{mw:g}", mw_src

    s_lo, s_hi = span_range(start, s_prec, end, e_prec)
    row["span_days_low"], row["span_days_high"] = str(s_lo), str(s_hi)
    months = (s_lo / DAYS_PER_MONTH, s_hi / DAYS_PER_MONTH)

    used = {anchor(anchors, "capex_per_mw", tech)["anchor_id"]}
    c = capex(anchors, tech, mw)
    _rng(row, "capex", *c)
    notes = []
    if DECIDED.get(outcome) == "blocked":
        sh = anchors["predevelopment_share"]
        used.add("predevelopment_share")
        b = (c[0] * sh["value_low"], c[1] * sh["value_high"])
        _rng(row, "block_sunk_cost", *b)
        total = b
        notes.append("blocked: never built and never earns, so escalation and deferral do not apply")
    else:
        used.add(anchor(anchors, "construction_escalation", tech)["anchor_id"])
        e = escalation(anchors, tech, c, months)
        _rng(row, "escalation_cost", *e)
        rev = annual_revenue(anchors, tech, mw)
        used |= deferral_anchor_ids(tech, anchors)
        _rng(row, "deferred_revenue_exposure", rev[0] * months[0] / 12, rev[1] * months[1] / 12)
        n = deferral_npv(anchors, tech, mw, months)
        _rng(row, "deferral_npv_cost", *n)
        total = (e[0] + n[0], e[1] + n[1])
    _rng(row, "total_economic_cost", *total)

    row["stale_anchors"] = ";".join(sorted(used & stale))
    row["review_flags"] = ";".join(flags)
    start_text = {"queue_request": "the first interconnection request",
                  "event_date": "the dated event in the record"}[s_src]
    end_text = ("the resolution date" if decided
                else f"{as_of.isoformat()} (still pending, so the full span is at least this long)")
    mw_text = {"record": "the record's stated MW",
               "federal_plant_inventory": "the matched federal plant inventory entry's MW",
               "queue_request": "the matched interconnection request's MW"}[mw_src]
    if "hybrid_priced_on_primary" in flags:
        notes.append(f"priced as {tech.replace('_', ' ')} on the stated MW; "
                     "the other listed technologies are not priced")
    row["note"] = " ".join(
        [f"Prices the observed span from {start_text} to {end_text} at published rates "
         f"for {tech.replace('_', ' ')}, on {mw_text}."] + [n[0].upper() + n[1:] + "." for n in notes])
    return row


def build_ledger(projects: list[dict], queue: dict[str, dict], anchors: dict,
                 as_of: date) -> list[dict]:
    stale = stale_ids(anchors, as_of)
    rows = [ledger_row(r, queue.get(r.get("id", "")), anchors, stale, as_of) for r in projects]
    rows.sort(key=lambda x: x["project_id"])
    return rows


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

def fmt_usd(x: float) -> str:
    if abs(x) >= 1e9:
        return f"${x / 1e9:,.2f}B"
    if abs(x) >= 1e6:
        return f"${x / 1e6:,.1f}M"
    return f"${x:,.0f}"


def _count_table(title: str, counts: Counter, order=None) -> list[str]:
    keys = list(order) if order else sorted(counts)
    lines = [f"| {title} | Rows |", "|---|---|"]
    lines += [f"| `{k}` | {counts[k]} |" for k in keys if counts.get(k)]
    return lines


def methodology(anchors: dict, ledger: list[dict], stale: set[str], as_of: date) -> str:
    priced = [r for r in ledger if not r["withheld_reason"]]
    withheld = [r for r in ledger if r["withheld_reason"]]
    flags = Counter(f for r in ledger for f in r["review_flags"].split(";") if f)
    L = [
        "# Cost ledger: methodology",
        "",
        f"Generated {as_of.isoformat()} by `scripts/cost_ledger.py`. **Internal, not client-facing.**",
        "The ledger prices the observed span of each contested project at published rates. It does not",
        "estimate what opposition did to any project and makes no comparison with a project that saw",
        "none: it is case-level observed-cost accounting, ported from the data-center-map cost ledger",
        "(spec 025). Re-verify every anchor before any external use; the registry records when each one",
        "is due.",
        "",
        "## The ledger",
        "",
        f"`data/cost/cost_ledger.csv` holds one row per contested project in",
        f"`data/processed/contested_projects.csv`: {len(ledger)} rows, {len(priced)} priced and",
        f"{len(withheld)} withheld.",
        "",
        *_count_table("Priced by span", Counter(r["span_kind"] for r in priced)),
        "",
        *_count_table("Priced by technology", Counter(r["priced_technology"] for r in priced), TECHNOLOGIES),
        "",
        *_count_table("Priced by span start", Counter(r["start_source"] for r in priced)),
        "",
        *_count_table("Priced by MW source", Counter(r["mw_source"] for r in priced)),
        "",
        *_count_table("Withheld reason", Counter(r["withheld_reason"] for r in withheld), WITHHELD_REASONS),
        "",
    ]
    if flags:
        L += [*_count_table("Review flag", flags), ""]
    L += [
        "## Span",
        "",
        "- `request_to_decision`: a project with a confirmed outcome (`blocked_confirmed`,",
        "  `advanced_confirmed`, `restricted_conditional`), from the start date to its",
        "  `resolution_date`.",
        "- `accrued_to_date`: a pending project, from the start date to the run date. The project is",
        "  still open, so its full span is at least this long; the row prices only the part observed so",
        "  far.",
        "- Start date: the first interconnection request of the project's Queued Up match",
        "  (`data/reference/queue_matches.csv` `first_request_date`) when the match is `strong`, else a",
        "  day- or month-precision date in the record's `event_date_text`. A start from a `possible`",
        "  queue match, a year-only start and a missing start are withheld.",
        "- Unverified outcomes (`blocked_unverified`, `advanced_unverified`) and `needs_review` rows are",
        "  withheld: the span's end is not settled.",
        "- Precision. A month-precision date is stored as the first of its month, so the true date falls",
        "  on or after it. A month-precision start shortens the span by up to (days in that month - 1);",
        "  a month-precision end lengthens it by up to the same. The low end is floored at 1 day.",
        "  Months are days / 30.44.",
        "",
        "## Technology and capital basis",
        "",
        "- Solar, wind and battery storage are priced, each on its own anchors. A record that lists more",
        "  than one of them is priced on the first, on the stated MW, and flagged",
        "  `hybrid_priced_on_primary`. Transmission, geothermal and hydro are withheld as",
        "  `technology_not_priced`, and so is offshore wind (a wind record whose name or description",
        "  says offshore, flagged `offshore_wind`), whose costs are not those of land-based wind.",
        "- Capital basis: the per-MW anchor for the technology times a stated MW. The MW is the",
        "  record's `capacity_mw`, else the strongly matched federal plant inventory entry's",
        "  (`facility_capacity_mw`), else the strongly matched queue request's (`queue_capacity_mw`);",
        "  `mw_source` says which. MW is never imputed, and never derived from acres or dollars.",
        "",
        "## Components",
        "",
        "Low ends use every anchor's low value (the high value of fixed O&M, which lowers net revenue)",
        "and the shortest span; high ends use the opposite. Components 1 to 3 rise with span and with",
        "each anchor, so those bounds are exact; component 4 is not monotone in the cost of capital, so",
        "each of its bounds takes the extreme over both ends of that range.",
        "",
        "A `blocked_confirmed` project is never built and never earns, so it carries capital at risk",
        "only (component 2). Every other priced row carries components 1, 3 and 4.",
        "",
        "**1. Construction-cost escalation (destroyed value).**",
        "`capital_basis x construction_escalation x (span_months / 12)`.",
        "",
        "**2. Development capital at risk on a block (destroyed value, assumption-based).**",
        "`capital_basis x predevelopment_share`, on `blocked_confirmed` rows only.",
        "",
        "**3. Deferred revenue exposure (upper bound, not destroyed value).**",
        "Solar and wind: `MW x capacity_factor x 8760 h x ppa_price_mwh x (span_months / 12)`. Storage:",
        "`MW x 1000 kW x capacity_price_kw_month x span_months`. Gross revenue that arrives later. The",
        "economic cost is the time value of the deferral (component 4), not this face amount. Never",
        "added to the total.",
        "",
        "**4. Economic cost of deferral.**",
        "`net = annual gross revenue - MW x 1000 kW x fixed_om_kw_year` (floored at 0);",
        "`value = net x (1 - (1 + r)^-L) / r`; `cost = value x (1 - (1 + r)^-(span_months / 12))`, with",
        "`L` the project life (`project_life_years`) and `r` the cost of capital (`carrying_rate`). The",
        "present value given up when the project's net revenue stream starts later.",
        "",
        "**Total economic cost.** Components 1 and 4, or component 2 for a block; low ends added to low",
        "ends and high ends to high ends. Gross deferred revenue is never in it. For a pending row it is",
        "the cost of the span so far.",
        "",
        "Not yet in the ledger: carrying cost on capital already deployed (the data center ledger fills",
        "it from public records of land purchases and deposits), and the federal tax credit deadlines,",
        "which are a step at a date rather than a rate (see `data/cost/cost_brief.md`).",
        "",
        "## Anchors",
        "",
        "| Anchor | Low | High | Unit | Confidence | As of | Re-verify by |",
        "|---|---|---|---|---|---|---|",
    ]
    for aid in sorted(anchors):
        a = anchors[aid]
        mark = " (stale)" if aid in stale else ""
        L.append(f"| `{aid}`{mark} | {a['value_low']:g} | {a['value_high']:g} | {a['unit']} | "
                 f"{a['confidence']} | {a['source_date']} | {a['reverify_by']} |")
    L += ["", "Sources:", ""]
    for aid in sorted(anchors):
        a = anchors[aid]
        url = f" {a['source_url']}" if a.get("source_url") else ""
        L.append(f"- `{aid}`: {a['source']}{url}")
    L.append("")
    if stale:
        L += ["**Stale anchors** (past their re-verify-by date on the run date): "
              + ", ".join(f"`{s}`" for s in sorted(stale))
              + ". Re-verify each one, then move `reverify_by` forward in `config/cost_anchors.json`.", ""]
    else:
        L += [f"No anchor was past its re-verify-by date on {as_of.isoformat()}.", ""]
    return "\n".join(L)


# Columns copied from the published record; their words are the record's, not
# this module's, so the wording check skips them.
NAME_COLS = frozenset({"project_name", "state", "county"})


def banned_hits(texts: dict[str, str]) -> list[str]:
    return [f"{name}: '{m.group(0)}'" for name, t in texts.items() for m in [BANNED.search(t)] if m]


def generated_text(ledger: list[dict], method: str) -> dict[str, str]:
    texts = {"cost_methodology.md": method}
    for r in ledger:
        texts[f"cost_ledger.csv {r['project_id']}"] = " ".join(
            v for k, v in r.items() if k not in NAME_COLS)
    return texts


def anchor_rows(anchors: dict) -> list[dict]:
    return [{c: anchors[aid].get(c, "") for c in ANCHOR_COLS} for aid in sorted(anchors)]


def summary(ledger: list[dict], stale: set[str]) -> str:
    priced = [r for r in ledger if not r["withheld_reason"]]
    out = [f"cost ledger: {len(ledger)} rows, {len(priced)} priced, {len(ledger) - len(priced)} withheld"]
    for k, v in sorted(Counter(r["priced_technology"] for r in priced).items()):
        out.append(f"  priced {k}: {v}")
    for k, v in Counter(r["withheld_reason"] for r in ledger if r["withheld_reason"]).most_common():
        out.append(f"  withheld {k}: {v}")
    if stale:
        out.append("  STALE anchors (re-verify before any external use): " + ", ".join(sorted(stale)))
    return "\n".join(out)


def run(as_of: date) -> int:
    try:
        anchors = load_anchors()
    except AnchorError as e:
        print(f"cost_ledger: {e}", file=sys.stderr)
        return 1
    stale = stale_ids(anchors, as_of)
    ledger = build_ledger(load_projects(), load_queue_matches(), anchors, as_of)
    method = methodology(anchors, ledger, stale, as_of)
    hits = banned_hits(generated_text(ledger, method))
    if hits:
        print("cost_ledger: banned wording in its own outputs: " + "; ".join(hits[:5]), file=sys.stderr)
        return 1
    write_csv(OUT_LEDGER, ledger, LEDGER_COLS)
    write_csv(OUT_ANCHORS, anchor_rows(anchors), ANCHOR_COLS)
    OUT_METHOD.parent.mkdir(parents=True, exist_ok=True)
    OUT_METHOD.write_text(method, encoding="utf-8")
    print(summary(ledger, stale))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today(),
                    help="run date: pending spans end here and stale anchors are judged against it")
    return run(ap.parse_args().as_of)


if __name__ == "__main__":
    sys.exit(main())
