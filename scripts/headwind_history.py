"""Dated project outcomes, each with its county as it stood before the request.

The Renewable Headwind Model (docs/headwind_model.md) needs what the record
score fit lacked (data/model/record_score_fit.md): several hundred project
outcomes with dates, and the county's record as of a date before each one.
This script builds both, under config/headwind_model_registration.json.

Outcomes come from two places:

  queue      LBNL Queued Up requests (data/reference/queue_projects.csv) that
             withdrew or reached commercial operation, each with its own
             request date and withdrawal or operation date. Thousands of
             rows, opposed or not.
  contested  contested projects (data/processed/contested_projects.csv) with
             a confirmed outcome (blocked_confirmed or advanced_confirmed), a
             county and a year. About 180 rows, all of which drew opposition.

The county snapshot for each row is taken as of 1 January of the row's year
(the request year for queue rows, the outcome year for contested rows):
local restrictions on the row's technology with a year before it, the share
of neighbouring counties with a severe one, the county's earlier queue
requests and how many had withdrawn by the request date, operating MW, and
the static census and election covariates. Nothing dated in the row's own
year or later enters its snapshot.

Output (internal, staff only): data/model/headwind_history.csv, one row per
outcome, with a source column ("queue" or "contested"). Associations only.

Usage: python scripts/headwind_history.py [--selftest]
"""
from __future__ import annotations

import bisect
import json
import math
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import county_labels  # noqa: E402
import geo  # noqa: E402
import headwind_inputs  # noqa: E402
from common import PROCESSED_DIR, ROOT, read_csv, write_csv  # noqa: E402

REGISTRATION_PATH = ROOT / "config" / "headwind_model_registration.json"
QUEUE_PATH = ROOT / "data" / "reference" / "queue_projects.csv"
FACILITIES_PATH = ROOT / "data" / "reference" / "facilities.csv"
COVARIATES_PATH = ROOT / "data" / "reference" / "county_covariates.csv"
RESTRICTIONS_PATH = PROCESSED_DIR / "restrictions.csv"
DC_EVENTS_PATH = ROOT / "data" / "reference" / "data_center_events.csv"
CONTESTED_PATH = PROCESSED_DIR / "contested_projects.csv"
OUT_PATH = ROOT / "data" / "model" / "headwind_history.csv"

REG = json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
FIRST_YEAR, LAST_YEAR = 2010, 2019
# Amendment of 2026-11-20 (withdrawn_3y): requests to 2022, withdrawn within
# three years, in regions that date at least 90% of their withdrawals.
LAST_YEAR_3Y, HORIZON_DAYS, DATED_SHARE_MIN = 2022, 1096, 0.9
PRIOR_WEIGHT, PRIOR_SHARE = 5.0, 0.8
TECHS = ("solar", "wind", "battery_storage")
COUNTY_VARS = ["severe_before", "standards_before", "undated_rule", "neighbor_severe_share",
               "prior_withdrawal_share", "log1p_prior_requests", "log1p_operating_mw",
               "log_density", "log_income", "pct_bachelors_plus", "margin",
               # Amendment of 2026-11-20 (inputs): time-matched opposition and queue history.
               "log1p_contested_before", "log1p_dc_events_before", "state_prior_withdrawal_share",
               "neighbor_prior_withdrawal_share"]
# Plug-in inputs (config/headwind_inputs.json) the registration lists, as in_<id>.
COUNTY_VARS += headwind_inputs.names(reg=REG)
ELECTION_YEARS = (2000, 2004, 2008, 2012, 2016, 2020, 2024)
FIELDS = ["row_id", "source", "state", "county_fips", "region", "technology", "capacity_mw",
          "year", "start_date", "outcome", "outcome_date", "y", "in_fit", "y_3y", "in_fit_3y"] + COUNTY_VARS


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def techs_of(v: str) -> set[str]:
    return {t for t in re.split(r"[;,]", v or "") if t in TECHS}


# ── Local rules by county and technology ────────────────────────────────────

def rules_by_county(rows: list[dict]) -> dict[str, list[tuple[int | None, int, set[str]]]]:
    """fips -> [(year or None, severity, technologies)] for every restriction
    that touches the county."""
    out: dict[str, list] = defaultdict(list)
    for r in rows:
        sev = int(_f(r.get("severity_score")) or 0)
        if sev < 1:
            continue
        y = county_labels.year_of(r)
        for f in county_labels.counties_of(r):
            out[f].append((y, sev, techs_of(r.get("technology", ""))))
    return out


def local_flags(rules: list, techs: set[str], year: int) -> dict[str, int]:
    on = [(y, s) for y, s, t in rules if t & techs]
    return {
        "severe_before": int(any(y is not None and y < year and s >= 3 for y, s in on)),
        "standards_before": int(any(y is not None and y < year and s <= 2 for y, s in on)),
        "undated_rule": int(any(y is None for y, _ in on)),
    }


def first_severe_year(rules_by: dict) -> dict[str, int]:
    """fips -> the year of its first dated severe restriction, any technology."""
    out = {}
    for f, rules in rules_by.items():
        ys = [y for y, s, _ in rules if s >= 3 and y is not None]
        if ys:
            out[f] = min(ys)
    return out


def neighbor_share(fips: str, year: int, first_severe: dict[str, int], nbr_cache: dict) -> float:
    if fips not in nbr_cache:
        nbr_cache[fips] = geo.neighbors(fips)
    nbrs = nbr_cache[fips]
    if not nbrs:
        return 0.0
    return sum(1 for n in nbrs if first_severe.get(n, 9999) < year) / len(nbrs)


# ── The county's queue history ──────────────────────────────────────────────

class QueueHistory:
    """For each county, and each state, its requests' dates and the dates they
    resolved, so a snapshot can count only what had happened before a given
    date. State keys are "state:<postal code>"."""

    def __init__(self, rows: list[dict]):
        self.requests: dict[str, list[str]] = defaultdict(list)
        self.withdrawn: dict[str, list[str]] = defaultdict(list)
        self.resolved: dict[str, list[str]] = defaultdict(list)
        for q in rows:
            f, d = q.get("county_fips"), q.get("request_date")
            if not f or not d:
                continue
            for key in (f, f"state:{q.get('state', '')}"):
                self.requests[key].append(d)
                if q["status"] == "withdrawn" and q.get("withdrawn_date"):
                    self.withdrawn[key].append(q["withdrawn_date"])
                    self.resolved[key].append(q["withdrawn_date"])
                elif q["status"] == "operational" and q.get("operational_date"):
                    self.resolved[key].append(q["operational_date"])
        for d in (self.requests, self.withdrawn, self.resolved):
            for v in d.values():
                v.sort()

    def counts(self, key: str, day: str) -> tuple[int, int, int]:
        """(requests made, withdrawals dated, resolutions dated) before day."""
        return (bisect.bisect_left(self.requests.get(key, []), day),
                bisect.bisect_left(self.withdrawn.get(key, []), day),
                bisect.bisect_left(self.resolved.get(key, []), day))

    @staticmethod
    def share(n_wd: int, n_res: int) -> float:
        return (n_wd + PRIOR_WEIGHT * PRIOR_SHARE) / (n_res + PRIOR_WEIGHT)

    def before(self, fips: str, day: str) -> dict[str, float]:
        n_req, n_wd, n_res = self.counts(fips, day)
        return {"prior_withdrawal_share": self.share(n_wd, n_res), "log1p_prior_requests": math.log1p(n_req)}

    def pooled_share(self, keys: list[str], day: str) -> float:
        wd = res = 0
        for k in keys:
            _, w, r = self.counts(k, day)
            wd, res = wd + w, res + r
        return self.share(wd, res)


def margin_before(cov: dict, year: int) -> float | None:
    """D minus R margin in the last presidential election before the year
    (the earliest on file for a year before 2001)."""
    past = [y for y in ELECTION_YEARS if y < year] or [ELECTION_YEARS[0]]
    return _f(cov.get(f"margin_dr_{past[-1]}"))


def years_by_county(pairs) -> dict[str, list[int]]:
    out: dict[str, list[int]] = defaultdict(list)
    for f, y in pairs:
        if f and y is not None:
            out[f].append(y)
    for v in out.values():
        v.sort()
    return out


# ── Operating MW at the end of a year ───────────────────────────────────────

def operating_by_year(rows: list[dict]) -> dict[str, list[tuple[int, int | None, float]]]:
    """fips -> [(start year, retirement year or None, MW)] for solar and wind
    plants. An operating plant's year is its start; a retired plant's year is
    its retirement (registration amendment of 2026-10-16 to the county
    model), so its start is unknown and it counts from the beginning."""
    out: dict[str, list] = defaultdict(list)
    for p in rows:
        if not p.get("county_fips") or not ({"solar", "wind"} & techs_of(p.get("technology", ""))):
            continue
        y = _f(p.get("year"))
        mw = _f(p.get("capacity_mw")) or 0.0
        if p["status"] == "operating" and y:
            out[p["county_fips"]].append((int(y), None, mw))
        elif p["status"] == "retired" and y:
            out[p["county_fips"]].append((0, int(y), mw))
    return out


def operating_mw(plants: list, end_of: int) -> float:
    return sum(mw for start, retired, mw in plants if start <= end_of and (retired is None or retired > end_of))


# ── Static covariates ───────────────────────────────────────────────────────

def static_covariates(rows: list[dict]) -> dict[str, dict[str, float | None]]:
    def log(v):
        x = _f(v)
        return math.log(x) if x and x > 0 else None
    return {c["county_fips"]: {"log_density": log(c["pop_density_sqmi"]), "log_income": log(c["median_hh_income"]),
                               "pct_bachelors_plus": _f(c["pct_bachelors_plus"]), "_cov": c,
                               "state": c["state"]}
            for c in rows}


# ── Rows ────────────────────────────────────────────────────────────────────

def dated_regions(queue: list[dict]) -> set[str]:
    """Regions where at least DATED_SHARE_MIN of withdrawn requests carry a
    withdrawal date (the withdrawn_3y frame)."""
    n, dated = defaultdict(int), defaultdict(int)
    for q in queue:
        if q["status"] == "withdrawn":
            n[q["region"]] += 1
            dated[q["region"]] += bool(q.get("withdrawn_date"))
    return {g for g in n if dated[g] / n[g] >= DATED_SHARE_MIN}


def within(start: str, end: str, days: int) -> bool:
    return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days <= days


def queue_rows(queue: list[dict]) -> list[dict]:
    regions = dated_regions(queue)
    out = []
    for q in queue:
        techs = techs_of(q.get("technology", ""))
        if not techs or q.get("offshore") or not q.get("county_fips") or not q.get("request_date"):
            continue
        year = int(q["request_date"][:4])
        if not FIRST_YEAR <= year <= LAST_YEAR_3Y:
            continue
        status = q["status"]
        y, od = "", ""
        if status == "withdrawn" and q.get("withdrawn_date"):
            y, od = 1, q["withdrawn_date"]
        elif status == "operational" and q.get("operational_date"):
            y, od = 0, q["operational_date"]
        in_fit = int(y != "" and year <= LAST_YEAR)
        y3 = ""
        if q["region"] in regions and not (status == "withdrawn" and not q.get("withdrawn_date")):
            y3 = int(status == "withdrawn" and within(q["request_date"], q["withdrawn_date"], HORIZON_DAYS))
        out.append({"row_id": q["queue_project_id"], "source": "queue", "state": q["state"],
                    "county_fips": q["county_fips"], "region": q["region"], "technology": ";".join(sorted(techs)),
                    "capacity_mw": q["capacity_mw"], "year": year, "start_date": q["request_date"],
                    "outcome": status, "outcome_date": od, "y": y if year <= LAST_YEAR else "", "in_fit": in_fit,
                    "y_3y": y3, "in_fit_3y": int(y3 != "")})
    return out


def contested_year(p: dict) -> int | None:
    for v in (p.get("resolution_date"), p.get("event_date_text")):
        m = re.search(r"(19|20)\d\d", v or "")
        if m:
            return int(m.group(0))
    return None


def contested_rows(projects: list[dict]) -> list[dict]:
    out = []
    for p in projects:
        if p.get("outcome") not in ("blocked_confirmed", "advanced_confirmed") or not p.get("county_fips"):
            continue
        techs = techs_of(p.get("technology", ""))
        year = contested_year(p)
        if not techs or year is None:
            continue
        fips = county_labels.counties_of({"county_fips_all": p["county_fips"]})[0]
        out.append({"row_id": p["id"], "source": "contested", "state": p["state"], "county_fips": fips,
                    "region": "", "technology": ";".join(sorted(techs)), "capacity_mw": p.get("capacity_mw", ""),
                    "year": year, "start_date": f"{year}-01-01", "outcome": p["outcome"],
                    "outcome_date": p.get("resolution_date", ""), "y": int(p["outcome"] == "blocked_confirmed"),
                    "in_fit": 0, "y_3y": "", "in_fit_3y": 0})
    return out


def snapshot(rows: list[dict], restrictions: list[dict], queue: list[dict], facilities: list[dict],
             covariates: list[dict], contested: list[dict] = (), dc_events: list[dict] = ()) -> list[dict]:
    rules = rules_by_county(restrictions)
    first_sev = first_severe_year(rules)
    hist = QueueHistory(queue)
    plants = operating_by_year(facilities)
    static = static_covariates(covariates)
    fights = years_by_county((f, contested_year(p)) for p in contested
                             for f in county_labels.counties_of({"county_fips_all": p.get("county_fips", "")})[:1])
    dc = years_by_county((e.get("county_fips"), int(e["date"][:4]) if (e.get("date") or "")[:4].isdigit() else None)
                         for e in dc_events)
    nbr_cache: dict = {}
    for r in rows:
        f, year = r["county_fips"], int(r["year"])
        r.update(local_flags(rules.get(f, []), techs_of(r["technology"]), year))
        r["neighbor_severe_share"] = round(neighbor_share(f, year, first_sev, nbr_cache), 4)
        r.update({k: round(v, 4) for k, v in hist.before(f, r["start_date"]).items()})
        r["log1p_operating_mw"] = round(math.log1p(operating_mw(plants.get(f, []), year - 1)), 4)
        s = static.get(f, {})
        for k in ("log_density", "log_income", "pct_bachelors_plus"):
            v = s.get(k)
            r[k] = "" if v is None else round(v, 4)
        m = margin_before(s.get("_cov", {}), year)
        r["margin"] = "" if m is None else round(m, 4)
        r["log1p_contested_before"] = round(math.log1p(bisect.bisect_left(fights.get(f, []), year)), 4)
        r["log1p_dc_events_before"] = round(math.log1p(bisect.bisect_left(dc.get(f, []), year)), 4)
        r["state_prior_withdrawal_share"] = round(hist.pooled_share([f"state:{r['state']}"], r["start_date"]), 4)
        r["neighbor_prior_withdrawal_share"] = round(hist.pooled_share(nbr_cache.get(f, []), r["start_date"]), 4)
    return headwind_inputs.apply(rows, headwind_inputs.load(reg=REG, every=True))


def build() -> list[dict]:
    queue = read_csv(QUEUE_PATH)
    projects = read_csv(CONTESTED_PATH)
    rows = queue_rows(queue) + contested_rows(projects)
    return snapshot(rows, read_csv(RESTRICTIONS_PATH), queue, read_csv(FACILITIES_PATH), read_csv(COVARIATES_PATH),
                    projects, read_csv(DC_EVENTS_PATH))


# ── Self-test ───────────────────────────────────────────────────────────────

def _selftest() -> int:
    rules = rules_by_county([
        {"severity_score": "4", "date_enacted_iso": "2015-03-01", "date_text": "", "technology": "wind",
         "county_fips_all": "01001"},
        {"severity_score": "2", "date_enacted_iso": "", "date_text": "adopted 2012", "technology": "solar",
         "county_fips_all": "01001"},
        {"severity_score": "3", "date_enacted_iso": "", "date_text": "", "technology": "solar",
         "county_fips_all": "01001"},
    ])
    r = rules["01001"]
    assert local_flags(r, {"wind"}, 2015) == {"severe_before": 0, "standards_before": 0, "undated_rule": 0}, \
        "a rule dated in the request year is not before it"
    assert local_flags(r, {"wind"}, 2016)["severe_before"] == 1
    assert local_flags(r, {"solar"}, 2013) == {"severe_before": 0, "standards_before": 1, "undated_rule": 1}, \
        "an undated severe rule never counts as before; it is flagged instead"
    assert first_severe_year(rules) == {"01001": 2015}

    hist = QueueHistory([
        {"county_fips": "01001", "request_date": "2010-01-01", "status": "withdrawn", "withdrawn_date": "2011-06-01"},
        {"county_fips": "01001", "request_date": "2010-05-01", "status": "operational", "operational_date": "2013-01-01"},
        {"county_fips": "01001", "request_date": "2012-01-01", "status": "active"},
    ])
    b = hist.before("01001", "2012-01-01")
    assert b["log1p_prior_requests"] == math.log1p(2), "the request on the snapshot date itself is not prior"
    assert abs(b["prior_withdrawal_share"] - (1 + 4) / (1 + 5)) < 1e-9, \
        "only the withdrawal resolved before the date counts; the 2013 operation is later"
    assert hist.before("09999", "2012-01-01")["prior_withdrawal_share"] == PRIOR_SHARE

    plants = operating_by_year([
        {"county_fips": "01001", "technology": "solar", "status": "operating", "year": "2014", "capacity_mw": "10"},
        {"county_fips": "01001", "technology": "wind", "status": "retired", "year": "2016", "capacity_mw": "5"},
    ])["01001"]
    assert operating_mw(plants, 2013) == 5 and operating_mw(plants, 2014) == 15 and operating_mw(plants, 2016) == 10

    rows = queue_rows([
        {"queue_project_id": "a", "technology": "solar", "offshore": "", "county_fips": "01001",
         "request_date": "2015-02-02", "status": "withdrawn", "withdrawn_date": "2016-01-01", "operational_date": "",
         "state": "AL", "region": "Southeast", "capacity_mw": "50"},
        {"queue_project_id": "b", "technology": "wind", "offshore": "", "county_fips": "01001",
         "request_date": "2023-02-02", "status": "withdrawn", "withdrawn_date": "2024-01-01", "operational_date": "",
         "state": "AL", "region": "Southeast", "capacity_mw": "50"},
        {"queue_project_id": "c", "technology": "battery_storage", "offshore": "", "county_fips": "01001",
         "request_date": "2018-02-02", "status": "active", "withdrawn_date": "", "operational_date": "",
         "state": "AL", "region": "Southeast", "capacity_mw": "50"},
    ])
    assert [r["row_id"] for r in rows] == ["a", "c"], "requests after 2022 are outside the frame"
    assert rows[0]["y"] == 1 and rows[1]["in_fit"] == 0, "an active request is kept but not fit"
    assert rows[0]["y_3y"] == 1 and rows[1]["y_3y"] == 0 and rows[1]["in_fit_3y"] == 1, \
        "withdrawn within three years is 1; an active request is 0 on the three-year label"
    late = queue_rows([{"queue_project_id": "d", "technology": "solar", "offshore": "", "county_fips": "01001",
                        "request_date": "2021-02-02", "status": "withdrawn", "withdrawn_date": "2025-01-01",
                        "operational_date": "", "state": "AL", "region": "PJM", "capacity_mw": "5"}])[0]
    assert late["in_fit"] == 0 and late["y"] == "" and late["y_3y"] == 0, \
        "a 2021 request is outside the primary frame; withdrawn after four years is 0 on the three-year label"
    assert contested_year({"resolution_date": "", "event_date_text": "Denied in March 2019"}) == 2019
    cov = {f"margin_dr_{y}": str(y) for y in ELECTION_YEARS}
    assert margin_before(cov, 2013) == 2012 and margin_before(cov, 2012) == 2008 and margin_before(cov, 1999) == 2000, \
        "the margin is the last election before the request year"
    h2 = QueueHistory([
        {"county_fips": "01001", "state": "AL", "request_date": "2010-01-01", "status": "withdrawn",
         "withdrawn_date": "2011-01-01"},
        {"county_fips": "01003", "state": "AL", "request_date": "2010-01-01", "status": "operational",
         "operational_date": "2011-06-01"},
    ])
    assert h2.counts("state:AL", "2012-01-01") == (2, 1, 2)
    assert abs(h2.pooled_share(["01001", "01003"], "2011-03-01") - (1 + 4) / (1 + 5)) < 1e-9, \
        "a neighbour's operation dated after the snapshot day is not counted"
    fights = years_by_county([("01001", 2014), ("01001", 2012), ("01003", None)])
    assert fights == {"01001": [2012, 2014]} and bisect.bisect_left(fights["01001"], 2014) == 1, \
        "a fight in the request year itself is not before it"
    print("headwind_history selftest: ok")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    rows = build()
    write_csv(OUT_PATH, rows, FIELDS)
    q = [r for r in rows if r["source"] == "queue"]
    c = [r for r in rows if r["source"] == "contested"]
    print(f"headwind_history: {len(q)} queue requests ({sum(r['in_fit'] for r in q)} resolved: "
          f"{sum(1 for r in q if r['y'] == 1)} withdrawn, {sum(1 for r in q if r['y'] == 0)} operational); "
          f"three-year label {sum(r['in_fit_3y'] for r in q)} requests "
          f"({sum(1 for r in q if r['y_3y'] == 1)} withdrawn within three years); "
          f"{len(c)} contested projects ({sum(r['y'] for r in c)} blocked) -> {OUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
