"""Weekly LegiScan state bill feed: bills on solar, wind and battery storage siting.

LegiScan (https://legiscan.com/legiscan) tracks every bill in all 50 state
legislatures. This script finds the bills that could change state siting law
for solar, wind or battery storage (setbacks, moratoria, preemption of local
rules, state siting boards) and lists them as leads for review in
data/review/state_bill_leads.csv. A lead is never a state_policies row: a
reviewer reads the bill, and only an enacted bill read in the statute or
session law can change data/review/state_policies_candidates.csv
(scripts/state_policies.py, docs/AGENT_REVIEW.md).

How it keeps the work small (three steps, cheapest first):
  1. getDatasetList (one query) gives a hash for every state session. A
     session whose hash matches data/reference/legiscan_sessions.csv has not
     changed since the last run and is skipped.
  2. getMasterList (one query per changed session) lists every bill in it with
     its title, description, status and a change hash. The bills are filtered
     here, in plain code, by the terms in config/legiscan.json: a bill is kept
     when its text holds a technology term and a siting term.
  3. getBill (one query per kept bill whose change hash is new) adds the
     subjects, the state's own bill page and the latest text. Capped by
     max_bill_lookups_per_run; the rest are looked up next week.
A quiet week costs one query. No Claude run is started: the leads wait for a
reviewer like any other intake lead.

The key's monthly allowance is shared with pricephillips/data-centers, whose
weekly bill sync uses the same LegiScan account. Two guards keep this feed from
wasting it: a run stops at run_query_cap queries (config/legiscan.json), and
the first time LegiScan answers that the monthly limit is reached, the run
stops calling at once (LegiScan counts refused calls too) and keeps what it
already read. Neither is an error: the run exits 0 and the next run picks up.

The API key comes from the LEGISCAN_API_KEY environment variable (a
repository secret). Without it the script says so and exits 0. The key is
sent as a query parameter, as LegiScan requires, so no URL that carries it is
ever logged or stored: errors are reported with the key replaced by ***.

Outputs (both carry the run date; the leads keep their review columns):
  data/review/state_bill_leads.csv   one row per kept bill, newest status
  data/reference/legiscan_sessions.csv  the session hashes last seen, with
                                        bills listed and kept per session

Usage
  python scripts/fetch_legiscan.py                 the weekly run
  python scripts/fetch_legiscan.py --states VT,NH  only these states
  python scripts/fetch_legiscan.py --max-bills 20  fewer bill lookups
  python scripts/fetch_legiscan.py --force         ignore stored session hashes
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import REVIEW_DIR, ROOT, STATE_CODES, read_csv, write_csv  # noqa: E402

CONFIG_PATH = ROOT / "config" / "legiscan.json"
LEADS_PATH = REVIEW_DIR / "state_bill_leads.csv"
SESSIONS_PATH = ROOT / "data" / "reference" / "legiscan_sessions.csv"
KEY_ENV = "LEGISCAN_API_KEY"
USER_AGENT = ("renewable-opposition-pipeline/0.1 "
              "(research; contact: github.com/pricephillips/renewable-opposition)")
TIMEOUT_S = 90
RETRY_STATUSES = (429, 500, 502, 503, 504)
BACKOFF_S = (10, 30)

# LegiScan's status codes (https://api.legiscan.com/dl/, API manual).
STATUS = {"0": "N/A", "1": "Introduced", "2": "Engrossed", "3": "Enrolled", "4": "Passed",
          "5": "Vetoed", "6": "Failed"}

LEAD_FIELDS = [
    "bill_id", "state", "session", "bill_number", "title", "description", "technology",
    "matched_terms", "status", "status_date", "last_action", "last_action_date", "subjects",
    "legiscan_url", "state_url", "text_url", "change_hash", "first_seen", "last_seen",
    "review_status", "reviewer", "reviewed_on", "policy_id", "review_note",
]
# Set by reviewers; a run never overwrites them.
REVIEW_FIELDS = ("review_status", "reviewer", "reviewed_on", "policy_id", "review_note")
SESSION_FIELDS = ["session_id", "state", "session_name", "year_start", "year_end", "special",
                  "dataset_hash", "dataset_date", "checked_on", "bills_listed", "bills_kept"]
_STATE_IN_URL = re.compile(r"legiscan\.com/([A-Z]{2})/", re.I)


class LegiScanError(RuntimeError):
    pass


class LegiScanLimitReached(LegiScanError):
    """The month's query allowance or this run's cap is used up: stop calling."""


_LIMIT_MESSAGE = re.compile(r"exceeded maximum query count", re.I)


def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _term_pattern(terms: list[str]) -> re.Pattern | None:
    terms = [t for t in terms if t]
    if not terms:
        return None
    alts = "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
    return re.compile(r"\b(?:" + alts + r")[\w-]*", re.I)


class Matcher:
    """Keeps a bill when its text holds a technology term and a siting term."""

    def __init__(self, cfg: dict):
        self.tech = {tech: _term_pattern(terms) for tech, terms in cfg["technology_terms"].items()}
        self.siting = _term_pattern(cfg["siting_terms"])

    def match(self, text: str) -> tuple[list[str], list[str]] | None:
        """(technologies, matched terms), or None when the bill is not kept."""
        techs, terms = [], []
        for tech, pat in self.tech.items():
            found = pat.findall(text) if pat else []
            if found:
                terms += [f.lower() for f in found]
                if tech != "unspecified":
                    techs.append(tech)
        if not terms:
            return None
        siting = self.siting.findall(text) if self.siting else []
        if not siting:
            return None
        terms += [s.lower() for s in siting]
        return techs, list(dict.fromkeys(terms))


class Client:
    def __init__(self, key: str, api_url: str, delay_s: float = 0.2, max_queries: int | None = None):
        self.key, self.api_url, self.delay_s = key, api_url, delay_s
        self.max_queries = max_queries
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.queries = 0

    def _clean(self, text: str) -> str:
        return text.replace(self.key, "***") if self.key else text

    def call(self, op: str, **params) -> dict:
        query = {"key": self.key, "op": op, **params}
        for attempt in range(len(BACKOFF_S) + 1):
            if self.max_queries is not None and self.queries >= self.max_queries:
                raise LegiScanLimitReached(f"{op}: this run's cap of {self.max_queries} queries is reached")
            if self.queries:
                time.sleep(self.delay_s)
            self.queries += 1
            try:
                resp = self.session.get(self.api_url, params=query, timeout=TIMEOUT_S)
            except requests.RequestException as e:
                err = f"{op}: {type(e).__name__}: {self._clean(str(e))}"
                if attempt < len(BACKOFF_S):
                    time.sleep(BACKOFF_S[attempt])
                    continue
                raise LegiScanError(err) from None
            if resp.status_code in RETRY_STATUSES and attempt < len(BACKOFF_S):
                time.sleep(BACKOFF_S[attempt])
                continue
            if resp.status_code != 200:
                raise LegiScanError(f"{op}: HTTP {resp.status_code}")
            try:
                body = resp.json()
            except ValueError:
                raise LegiScanError(f"{op}: the response is not JSON") from None
            if body.get("status") != "OK":
                msg = (body.get("alert") or {}).get("message", "no message")
                if _LIMIT_MESSAGE.search(str(msg)):
                    raise LegiScanLimitReached(f"{op}: LegiScan's monthly query limit is reached: "
                                               f"{self._clean(str(msg))}")
                raise LegiScanError(f"{op}: LegiScan answered {body.get('status')}: {self._clean(str(msg))}")
            return body
        raise LegiScanError(f"{op}: gave up after retries")


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def current_sessions(datasets: list[dict], today: date, cfg: dict) -> list[dict]:
    keep = []
    for d in datasets:
        if cfg.get("current_sessions_only", True) and int(d.get("year_end") or 0) < today.year:
            continue
        keep.append(d)
    return keep


def state_of(entry: dict) -> str:
    m = _STATE_IN_URL.search(_s(entry.get("url")) or _s(entry.get("state_link")))
    return (_s(entry.get("state")) or (m.group(1) if m else "")).upper()


def wanted_state(state: str, states: set[str] | None, cfg: dict) -> bool:
    if state == "US":
        return bool(cfg.get("include_federal")) and (not states or "US" in states)
    if state not in STATE_CODES:
        return False
    return not states or state in states


def bill_text(entry: dict) -> str:
    subjects = " ".join(_s(s.get("subject_name")) for s in entry.get("subjects") or [] if isinstance(s, dict))
    return " ".join(x for x in (_s(entry.get("title")), _s(entry.get("description")), subjects) if x)


def lead_from_master(entry: dict, session: dict, state: str, techs: list[str], terms: list[str],
                     today: str) -> dict:
    return {
        "bill_id": _s(entry.get("bill_id")), "state": state,
        "session": _s(session.get("session_name")), "bill_number": _s(entry.get("number")),
        "title": _s(entry.get("title")), "description": _s(entry.get("description")),
        "technology": ";".join(techs), "matched_terms": ";".join(terms),
        "status": STATUS.get(_s(entry.get("status")), _s(entry.get("status"))),
        "status_date": _s(entry.get("status_date")), "last_action": _s(entry.get("last_action")),
        "last_action_date": _s(entry.get("last_action_date")), "legiscan_url": _s(entry.get("url")),
        "change_hash": _s(entry.get("change_hash")), "first_seen": today, "last_seen": today,
    }


def add_bill_detail(lead: dict, bill: dict) -> None:
    lead["subjects"] = ";".join(_s(s.get("subject_name")) for s in bill.get("subjects") or []
                                if isinstance(s, dict) and _s(s.get("subject_name")))
    lead["state_url"] = _s(bill.get("state_link"))
    texts = [t for t in bill.get("texts") or [] if isinstance(t, dict)]
    if texts:
        latest = max(texts, key=lambda t: _s(t.get("date")))
        lead["text_url"] = _s(latest.get("state_link")) or _s(latest.get("url"))
    lead["change_hash"] = _s(bill.get("change_hash")) or "looked-up"


def merge_lead(old: dict | None, new: dict) -> dict:
    if not old:
        new.setdefault("review_status", "lead")
        return new
    merged = dict(old)
    for k, v in new.items():
        if k in REVIEW_FIELDS or k == "first_seen":
            continue
        if v or k not in ("subjects", "state_url", "text_url"):
            merged[k] = v
    merged["review_status"] = old.get("review_status") or "lead"
    return merged


def run(client, cfg: dict, today: date, states: set[str] | None = None, max_bills: int | None = None,
        force: bool = False) -> dict:
    stamp = today.isoformat()
    matcher = Matcher(cfg)
    known_sessions = {r["session_id"]: r for r in read_csv(SESSIONS_PATH)}
    leads = {r["bill_id"]: r for r in read_csv(LEADS_PATH)}
    max_bills = cfg.get("max_bill_lookups_per_run", 400) if max_bills is None else max_bills

    datasets = []
    # getDatasetList is not caught: when even that is refused, nothing was
    # read and main() reports the stop.
    for st in sorted(states) if states else [None]:
        body = client.call("getDatasetList", **({"state": st} if st else {}))
        for d in body.get("datasetlist") or []:
            if isinstance(d, dict):
                datasets.append({**d, "_state": st or ""})
    sessions = current_sessions(datasets, today, cfg)
    stats = {"sessions_current": len(sessions), "sessions_checked": 0, "sessions_unchanged": 0,
             "bills_listed": 0, "bills_kept": 0, "new_leads": 0, "bills_looked_up": 0,
             "lookups_deferred": 0, "errors": [], "stopped": ""}
    try:
        _read_sessions(client, cfg, sessions, states, force, matcher, known_sessions, leads, stamp, stats)
    except LegiScanLimitReached as e:
        # Sessions read before the stop keep their new hashes; the rest are
        # read next run.
        stats["stopped"] = str(e)
    pending = [bid for bid, lead in leads.items() if not lead.get("change_hash")
               and wanted_state(lead.get("state", ""), states, cfg)]
    if not stats["stopped"]:
        try:
            _look_up_bills(client, matcher, pending[:max_bills], leads, stats)
        except LegiScanLimitReached as e:
            stats["stopped"] = str(e)
    stats["lookups_deferred"] = max(0, len(pending) - stats["bills_looked_up"])

    rows = sorted(leads.values(), key=lambda r: (r.get("state", ""), r.get("session", ""),
                                                 r.get("bill_number", "")))
    write_csv(LEADS_PATH, rows, LEAD_FIELDS)
    write_csv(SESSIONS_PATH, sorted(known_sessions.values(), key=lambda r: (r.get("state", ""),
                                                                              r.get("session_id", ""))),
              SESSION_FIELDS)
    stats["queries"] = client.queries
    stats["leads_total"] = len(rows)
    return stats


def _read_sessions(client, cfg, sessions, states, force, matcher, known_sessions, leads, stamp, stats):
    for d in sessions:
        sid = _s(d.get("session_id"))
        prev = known_sessions.get(sid)
        state = d["_state"] or (prev.get("state", "") if prev else "")
        if state and not wanted_state(state, states, cfg):
            continue
        if prev and not force and prev.get("dataset_hash") == _s(d.get("dataset_hash")):
            stats["sessions_unchanged"] += 1
            continue
        try:
            ml = client.call("getMasterList", id=sid).get("masterlist") or {}
        except LegiScanLimitReached:
            raise
        except LegiScanError as e:
            stats["errors"].append(str(e))
            continue
        session = ml.get("session") or {}
        entries = [v for k, v in ml.items() if k != "session" and isinstance(v, dict)]
        state = state or next((state_of(e) for e in entries if state_of(e)), "")
        if not wanted_state(state, states, cfg):
            continue
        stats["sessions_checked"] += 1
        kept = 0
        for e in entries:
            hit = matcher.match(bill_text(e))
            if not hit:
                continue
            kept += 1
            new = lead_from_master(e, session or d, state, *hit, stamp)
            old = leads.get(new["bill_id"])
            if old is None:
                stats["new_leads"] += 1
            elif old.get("change_hash") == new["change_hash"]:
                old["last_seen"] = stamp
                continue
            # A blank change hash marks a bill whose detail is still to be
            # looked up; getBill fills it in.
            new["change_hash"] = ""
            leads[new["bill_id"]] = merge_lead(old, new)
        stats["bills_listed"] += len(entries)
        stats["bills_kept"] += kept
        known_sessions[sid] = {
            "session_id": sid, "state": state,
            "session_name": _s(session.get("session_name") or d.get("session_name")),
            "year_start": _s(d.get("year_start")), "year_end": _s(d.get("year_end")),
            "special": _s(d.get("special")), "dataset_hash": _s(d.get("dataset_hash")),
            "dataset_date": _s(d.get("dataset_date")), "checked_on": stamp,
            "bills_listed": len(entries), "bills_kept": kept,
        }


def _look_up_bills(client, matcher, bill_ids, leads, stats):
    for bill_id in bill_ids:
        try:
            bill = client.call("getBill", id=bill_id).get("bill") or {}
        except LegiScanLimitReached:
            raise
        except LegiScanError as e:
            stats["errors"].append(str(e))
            continue
        stats["bills_looked_up"] += 1
        lead = leads[bill_id]
        add_bill_detail(lead, bill)
        hit = matcher.match(bill_text({**bill, "title": lead["title"], "description": lead["description"]}))
        if hit:
            lead["technology"] = ";".join(hit[0])
            lead["matched_terms"] = ";".join(hit[1])


def summary_text(stats: dict) -> str:
    lines = [
        "## LegiScan state bill feed",
        "",
        f"- Queries used: {stats['queries']}",
        f"- Current sessions: {stats['sessions_current']} "
        f"({stats['sessions_checked']} changed and read, {stats['sessions_unchanged']} unchanged)",
        f"- Bills listed in changed sessions: {stats['bills_listed']}; kept by the term filter: "
        f"{stats['bills_kept']} ({stats['new_leads']} new)",
        f"- Bill details looked up: {stats['bills_looked_up']} (deferred to next run: {stats['lookups_deferred']})",
        f"- Leads in data/review/state_bill_leads.csv: {stats['leads_total']}",
    ]
    if stats.get("stopped"):
        lines.append(f"- Stopped early, to be continued next run: {stats['stopped']}")
    for e in stats["errors"][:20]:
        lines.append(f"- Error: {e}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--states", help="comma-separated state codes; default all")
    ap.add_argument("--max-bills", type=int, help="cap on getBill lookups this run")
    ap.add_argument("--force", action="store_true", help="read every current session, changed or not")
    args = ap.parse_args(argv)

    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        print(f"{KEY_ENV} is not set; the LegiScan feed is skipped.")
        return 0
    cfg = load_config()
    states = {s.strip().upper() for s in args.states.split(",") if s.strip()} if args.states else None
    if states and (bad := sorted(s for s in states if s not in STATE_CODES | {"US"})):
        print(f"Unknown state code(s): {', '.join(bad)}", file=sys.stderr)
        return 2
    client = Client(key, cfg["api_url"], max_queries=cfg.get("run_query_cap"))
    try:
        stats = run(client, cfg, date.today(), states, args.max_bills, args.force)
    except LegiScanLimitReached as e:
        # Nothing was read. Not a failure of this feed: the next run retries,
        # and the other intake stages keep their results.
        print(f"## LegiScan state bill feed\n\n- Skipped: {e}\n")
        return 0
    except LegiScanError as e:
        print(f"LegiScan feed failed: {e}", file=sys.stderr)
        return 1
    # run_pipeline.py copies this to the workflow's job summary.
    print(summary_text(stats))
    # Partial failures (one session or bill) are reported, not fatal: the next
    # run retries them because their hashes were not stored.
    return 0


if __name__ == "__main__":
    sys.exit(main())
