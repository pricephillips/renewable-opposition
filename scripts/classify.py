"""Derived fields that decide what a record counts as. Pure functions: no I/O.

build_seed_outputs.py stamps these onto every processed row; qc_gate.py and
headline_metrics.py read them. They are derived, never stored in a seed, so a
rule change here reaches every record on the next build.

instrument_id   What one count means. A seed row is one technology of one
                instrument, so a moratorium covering solar, wind and battery
                storage is three rows but one instrument:
                  restrictions        mn:<moratorium_id> or sabin:<source_record_id>
                  contested_projects  sabin:<source_record_id>
                  cases               case:<case_id>
                A row with none of those keys is its own instrument (its id).

scope           restrictions only. Whether the instrument is aimed at
                renewables or bundles them with data centers:
                  renewables_only            sectors (or text) name no data centers
                  multi_sector_data_centers  Moratorium Nation's sectors include
                                             data_center, or the text names data
                                             centers alongside a renewable technology
                  data_center_only           the text names data centers and no
                                             renewable technology at all: the
                                             sector tag is not supported by the
                                             record, so qc_gate holds it for review
                Moratorium Nation's `sectors` is authoritative when present; the
                text test is the fallback (Sabin rows) and the contradiction check.

evidence_level  How far the record is from a primary source, best first:
                  primary_source     a reviewer confirmed the record against a
                                     primary_source_url (the ordinance, minutes,
                                     permit decision): resolutions.py
                  confirmed          contested project whose outcome is *_confirmed
                  court_record       case with a court or docket URL
                  compiled_record    Moratorium Nation row with no [VERIFY] tag;
                                     cites its legal basis but links the inventory
                  compiled_flagged   Moratorium Nation row with [VERIFY] tags
                  report_citation    cites the Sabin report as a whole
"""
from __future__ import annotations

import re

RENEWABLE_TEXT = re.compile(
    r"solar|photovolt|\bpv\b|\bwind(?:s|farms?|mills?|power)?\b|turbine|batter|energy storage|\bbess\b|renewable", re.I)
DATA_CENTER_TEXT = re.compile(
    r"data[ -]?cent(?:er|re)s?|data processing facilit|crypto|bitcoin|hyperscale", re.I)
TEXT_FIELDS = ("description", "long_description", "notes", "legal_basis")

EVIDENCE_ORDER = ("primary_source", "confirmed", "court_record", "compiled_record",
                  "compiled_flagged", "report_citation")
SCOPES = ("renewables_only", "multi_sector_data_centers", "data_center_only")


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def _text(row: dict) -> str:
    return " ".join(_s(row.get(f)) for f in TEXT_FIELDS)


def instrument_id(entity: str, row: dict) -> str:
    if entity == "restrictions":
        if _s(row.get("moratorium_id")):
            return f"mn:{_s(row['moratorium_id'])}"
        if _s(row.get("source_record_id")):
            return f"sabin:{_s(row['source_record_id'])}"
    elif entity == "contested_projects" and _s(row.get("source_record_id")):
        return f"sabin:{_s(row['source_record_id'])}"
    elif entity == "cases" and _s(row.get("case_id")):
        return f"case:{_s(row['case_id'])}"
    return _s(row.get("id"))


def scope(row: dict) -> str:
    text = _text(row)
    names_renewable = bool(RENEWABLE_TEXT.search(text))
    names_data_center = bool(DATA_CENTER_TEXT.search(text))
    if names_data_center and not names_renewable:
        return "data_center_only"
    sectors = {s for s in _s(row.get("sectors")).split(";") if s}
    if "data_center" in sectors or names_data_center:
        return "multi_sector_data_centers"
    return "renewables_only"


def evidence_level(entity: str, row: dict) -> str:
    if _s(row.get("primary_source_url")) and _s(row.get("primary_source_verdict")) != "contradicts":
        return "primary_source"
    if entity == "contested_projects":
        return "confirmed" if _s(row.get("outcome")).endswith("_confirmed") else "report_citation"
    if entity == "cases":
        return "court_record" if _s(row.get("case_source_url")) or _s(row.get("source_url")) \
            else "report_citation"
    if _s(row.get("moratorium_id")):
        return "compiled_flagged" if _s(row.get("needs_verification")) == "yes" else "compiled_record"
    return "report_citation"


def stamp(entity: str, row: dict) -> dict:
    """Add the derived fields to row in place and return it."""
    row["instrument_id"] = instrument_id(entity, row)
    if entity == "restrictions":
        row["scope"] = scope(row)
    row["evidence_level"] = evidence_level(entity, row)
    return row
