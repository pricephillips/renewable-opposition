"""The published state_policies entity: state siting law, one row per state and policy.

Rows are drafted in data/review/state_policies_candidates.csv from Lawrence Berkeley
National Laboratory's "Laws in Order: An Inventory of State Renewable Energy
Siting Policies" (June 2024; Regulatory Assistance Project for LBNL and DOE,
CC BY-NC 4.0) and from the Sabin Center's state-level entries, and each row is
checked against the statute itself (state code or session law), never the
inventory. build_seed_outputs.py calls build() and writes
data/processed/state_policies.csv and .json, and data/processed/state_policies_held.csv.

Columns
  policy_id        <ST>-<policy_type>-<n>
  state, technology (semicolon list: solar, wind, battery_storage)
  policy_type      siting_authority | local_preemption | state_setback_standard |
                   local_opt_out | state_moratorium | other
  who_decides      state_board | local_government | hybrid (required on a
                   siting_authority row)
  state_body       the state board or agency that decides, when one does
  threshold_mw     technology:MW pairs, "solar:50;wind:5", where a size
                   threshold splits state and local authority
  summary, statute_citation, statute_url, lbnl_reference, sabin_record_ids,
  amendments_note  amendments after the 2024 inventory, through the review date
  drafted_by, drafted_on, draft_access, draft_note
  reviewer, reviewed_on, review_access, review_archived_url, review_verdict,
  review_note      the recorded review (docs/AGENT_REVIEW.md)

A row publishes only when it has a recorded review by someone other than its
drafter, that review read the statute (review_access opened or archived) and
its verdict is confirmed. Published rows are evidence_level primary_source and
verification verified. Every other row is held, with the reason, in
data/processed/state_policies_held.csv. A structural error (an unknown
policy_type, a malformed threshold, a non-http URL, a repeated policy_id)
stops the build.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PROCESSED_DIR, REVIEW_DIR, STATE_CODES, read_csv  # noqa: E402

SEED_PATH = REVIEW_DIR / "state_policies_candidates.csv"
HELD_PATH = PROCESSED_DIR / "state_policies_held.csv"

POLICY_TYPES = ("siting_authority", "local_preemption", "state_setback_standard", "local_opt_out",
                "state_moratorium", "other")
WHO_DECIDES = ("state_board", "local_government", "hybrid")
TECHS = ("solar", "wind", "battery_storage")
VERDICTS = ("confirmed", "contradicts", "unverifiable")
ACCESS = ("opened", "archived", "snippet")
READ = ("opened", "archived")
FIELDS = [
    "policy_id", "state", "technology", "policy_type", "who_decides", "state_body", "threshold_mw", "summary",
    "statute_citation", "statute_url", "lbnl_reference", "sabin_record_ids", "amendments_note", "drafted_by",
    "drafted_on", "draft_access", "draft_note", "reviewer", "reviewed_on", "review_access",
    "review_archived_url", "review_verdict", "review_note",
]
OUT_FIELDS = ["id"] + FIELDS[1:13] + ["evidence_level", "verification", "reviewer", "reviewed_on",
                                      "review_access", "review_archived_url", "source", "source_url"]
HELD_FIELDS = ["policy_id", "state", "policy_type", "technology", "statute_citation", "reason"]
LBNL_SOURCE = ("Laws in Order: An Inventory of State Renewable Energy Siting Policies (LBNL / RAP, "
               "June 2024), CC BY-NC 4.0")
_URL = re.compile(r"^https?://[^\s/]+\.[^\s]+$")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_THRESHOLD = re.compile(r"^(solar|wind|battery_storage):\d+(?:\.\d+)?$")


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def validate(rows: list[dict]) -> list[str]:
    """Structural errors; any one stops the build."""
    errors, seen = [], {}
    for i, r in enumerate(rows, start=2):
        where = f"{SEED_PATH.name}: row {i}"
        pid = _s(r.get("policy_id"))
        if not pid:
            errors.append(f"{where}: policy_id is blank")
        elif pid in seen:
            errors.append(f"{where}: policy_id {pid} repeats row {seen[pid]}")
        seen[pid] = i
        if _s(r.get("state")) not in STATE_CODES:
            errors.append(f"{where}: state {r.get('state')!r} is not a state code")
        ptype = _s(r.get("policy_type"))
        if ptype not in POLICY_TYPES:
            errors.append(f"{where}: policy_type {ptype!r} must be one of {', '.join(POLICY_TYPES)}")
        who = _s(r.get("who_decides"))
        if who and who not in WHO_DECIDES:
            errors.append(f"{where}: who_decides {who!r} must be one of {', '.join(WHO_DECIDES)}")
        if ptype == "siting_authority" and not who:
            errors.append(f"{where}: a siting_authority row needs who_decides")
        techs = [t for t in _s(r.get("technology")).split(";") if t]
        if not techs or any(t not in TECHS for t in techs):
            errors.append(f"{where}: technology {r.get('technology')!r} must list {', '.join(TECHS)}")
        for part in [p for p in _s(r.get("threshold_mw")).split(";") if p]:
            if not _THRESHOLD.match(part.strip()):
                errors.append(f"{where}: threshold_mw part {part!r} is not technology:MW")
        for f in ("statute_url", "review_archived_url"):
            if _s(r.get(f)) and not all(_URL.match(u) for u in _s(r.get(f)).split()):
                errors.append(f"{where}: {f} must be http(s)")
        if not _s(r.get("summary")) or not _s(r.get("drafted_by")):
            errors.append(f"{where}: summary and drafted_by are required")
        for f, allowed in (("review_access", ACCESS), ("draft_access", ACCESS), ("review_verdict", VERDICTS)):
            if _s(r.get(f)) and _s(r.get(f)) not in allowed:
                errors.append(f"{where}: {f} {r.get(f)!r} must be one of {', '.join(allowed)}")
        for f in ("drafted_on", "reviewed_on"):
            if _s(r.get(f)) and not _ISO.match(_s(r.get(f))):
                errors.append(f"{where}: {f} {r.get(f)!r} is not YYYY-MM-DD")
        if _s(r.get("review_access")) == "archived" and not _s(r.get("review_archived_url")):
            errors.append(f"{where}: review_access archived needs review_archived_url")
        if "—" in " ".join(_s(v) for v in r.values()):
            errors.append(f"{where}: contains an em dash")
    return errors


def hold_reason(r: dict) -> str:
    """'' when the row may publish, else why it is held."""
    reviewer, drafter = _s(r.get("reviewer")), _s(r.get("drafted_by"))
    if not reviewer:
        return "no recorded review"
    if reviewer == drafter:
        return "self-review: the reviewer drafted the row"
    if not _s(r.get("statute_url")):
        return "no statute URL"
    if _s(r.get("review_access")) not in READ:
        return f"review saw the statute only as {_s(r.get('review_access')) or 'nothing recorded'}"
    verdict = _s(r.get("review_verdict"))
    if verdict != "confirmed":
        note = _s(r.get("review_note"))
        return f"review verdict {verdict or 'blank'}" + (f": {note[:300]}" if note else "")
    if not _s(r.get("reviewed_on")):
        return "review has no date"
    return ""


def build(rows: list[dict] | None = None) -> tuple[list[dict], list[dict], list[str]]:
    """(published rows, held rows, errors)."""
    rows = read_csv(SEED_PATH) if rows is None else rows
    errors = validate(rows)
    if errors:
        return [], [], errors
    published, held = [], []
    for r in rows:
        why = hold_reason(r)
        if why:
            held.append({**{k: _s(r.get(k)) for k in HELD_FIELDS if k != "reason"}, "reason": why})
            continue
        out = {k: _s(r.get(k)) for k in FIELDS}
        out["id"] = out.pop("policy_id")
        out["evidence_level"] = "primary_source"
        out["verification"] = "verified"
        out["source"] = _s(r.get("statute_citation")) or LBNL_SOURCE
        out["source_url"] = _s(r.get("statute_url")).split()[0]
        published.append({k: out.get(k, "") for k in OUT_FIELDS})
    published.sort(key=lambda r: (r["state"], POLICY_TYPES.index(r["policy_type"]), r["id"]))
    held.sort(key=lambda r: (r["state"], r["policy_id"]))
    return published, held, []


def framework(rows: list[dict], state: str) -> list[dict]:
    """A state's published policy rows, siting authority first."""
    return sorted((r for r in rows if r.get("state") == state),
                  key=lambda r: (POLICY_TYPES.index(r["policy_type"]) if r.get("policy_type") in POLICY_TYPES
                                 else 99, r.get("id", "")))
