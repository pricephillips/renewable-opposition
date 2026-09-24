"""Extractor for the CourtListener v4 search API (source_id courtlistener_renewables).

Input: one raw JSON page of opinion search results, as stored by fetch.py.
Output: one ``case`` candidate per result that mentions a renewable technology
in its case name or snippet. Candidates land in data/review/queue.csv with
review_status 'pending'; a reviewer confirms the project, state, technology
and severity before scripts/promote_reviewed.py moves them into cases_seed.csv.

Only facts present in the API response are filled: case name, court,
docket number, filing date and the opinion URL. Nothing is inferred beyond
court_level (from the court id) and technology (from keywords).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SITE = "https://www.courtlistener.com"

TECH_PATTERNS = {
    "wind": r"\bwind (?:farm|energy|turbine|project|facilit)",
    "solar": r"\bsolar (?:farm|energy|panel|project|facilit|array)",
    "battery_storage": r"\b(?:battery|energy) storage\b",
}

# CourtListener court ids for federal courts of appeals and the U.S. Supreme Court.
FEDERAL_APPELLATE = {f"ca{i}" for i in range(1, 12)} | {"cadc", "cafc"}


def court_level(court_id: str, court_name: str) -> str:
    cid, name = (court_id or "").lower(), (court_name or "").lower()
    if cid == "scotus":
        return "federal_supreme"
    if cid in FEDERAL_APPELLATE:
        return "federal_appellate"
    if "district court" in name and ("united states" in name or "u.s." in name or cid.endswith("d")):
        return "federal_district"
    if "supreme court" in name and "new york" not in name:
        return "state_supreme"
    if "appeal" in name or "appellate" in name:
        return "state_appellate"
    return ""


def technologies(text: str) -> list[str]:
    return [t for t, pat in TECH_PATTERNS.items() if re.search(pat, text, re.I)]


def _snippet(result: dict) -> str:
    parts = [result.get("snippet") or ""]
    for op in result.get("opinions") or []:
        parts.append(op.get("snippet") or "")
    text = " ".join(p for p in parts if p)
    return re.sub(r"<[^>]+>", "", text).strip()


def extract(raw_path: Path, source: dict) -> list[dict]:
    payload = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    out = []
    for r in payload.get("results", []):
        name = r.get("caseName") or r.get("case_name") or ""
        snippet = _snippet(r)
        techs = technologies(f"{name} {snippet}")
        if not techs:
            continue
        url = r.get("absolute_url") or ""
        if url.startswith("/"):
            url = SITE + url
        docket = r.get("docketNumber") or r.get("docket_number") or ""
        court = r.get("court") or r.get("court_citation_string") or ""
        out.append({
            "entity_type": "case",
            "project_name": name,
            "technology": ";".join(techs),
            "description": f"{name} ({court}{', ' + docket if docket else ''})",
            "source_url": url,
            "court_level": court_level(r.get("court_id", ""), court),
            "filing_date": r.get("dateFiled") or "",
            "docket_number": docket,
            "evidence_text": snippet[:1000],
        })
    return out
