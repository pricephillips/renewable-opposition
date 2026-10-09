"""Measure NREL's accuracy on a fixed random sample before relying on it.

  draw     Picks SAMPLE_SIZE NREL-derived restriction instruments with
           random.Random(SEED) from the sorted list of every NREL restriction in
           data/seed/restrictions_seed.csv, and writes
           data/review/nrel_sample.csv: one row per restricting feature of each
           sampled instrument (the values its restriction rests on), with the
           ordinance URL NREL cites. The seed and the SHA-256 of the NREL files
           drawn from are written on every row, so the draw can be repeated.
  review   A reviewing agent that did not build the rows (docs/AGENT_REVIEW.md)
           opens each ordinance and records, per sampled feature, a row in
           data/review/nrel_sample_review.csv: standard_id, instrument_id,
           feature, nrel_value, document_value, verdict (confirmed |
           contradicts | unverifiable), access, archived_url, document_url,
           checked_on, reviewer, note.
  apply    An instrument whose every sampled feature is confirmed, from the
           ordinance itself (access opened or archived), gets a row in
           data/review/restriction_sources.csv (verdict confirmed), so the build
           makes it primary_source and verified. Any other instrument stays
           unverified and on the restriction worklist.
  report   docs/nrel_sample_report.md: the error rate by feature
           (contradicts / (confirmed + contradicts)), unverifiable rows apart,
           and how many instruments passed.

Usage
  python scripts/nrel_sample.py draw
  python scripts/nrel_sample.py apply
  python scripts/nrel_sample.py report
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import REVIEW_DIR, ROOT, SEED_DIR, read_csv, write_csv  # noqa: E402

SEED = 20261009
SAMPLE_SIZE = 60
RESTRICTIONS_PATH = SEED_DIR / "restrictions_seed.csv"
STANDARDS_PATH = SEED_DIR / "siting_standards_seed.csv"
SAMPLE_PATH = REVIEW_DIR / "nrel_sample.csv"
REVIEW_PATH = REVIEW_DIR / "nrel_sample_review.csv"
SOURCES_PATH = REVIEW_DIR / "restriction_sources.csv"
REPORT_PATH = ROOT / "docs" / "nrel_sample_report.md"
RAW_MANIFEST = ROOT / "data" / "raw" / "manifest.csv"

SAMPLE_FIELDS = ["sample_rank", "instrument_id", "standard_id", "state", "jurisdiction", "technology",
                 "severity_score", "restriction_type", "feature", "value", "units", "min_setback_ft", "section",
                 "ordinance_year", "ordinance_url", "nrel_summary", "sample_seed", "nrel_raw_sha256"]
REVIEW_FIELDS = ["standard_id", "instrument_id", "feature", "nrel_value", "document_value", "verdict", "access",
                 "archived_url", "document_url", "checked_on", "reviewer", "note"]
VERDICTS = ("confirmed", "contradicts", "unverifiable")
READ = ("opened", "archived")


def nrel_hashes() -> str:
    """The SHA-256 of the NREL files the seed rows were built from."""
    out = {}
    for r in read_csv(RAW_MANIFEST):
        if r.get("source_id", "").startswith("nrel_") and r.get("content_hash") and not r.get("error"):
            out[r["source_id"]] = r["content_hash"]
    return ";".join(f"{k}={v}" for k, v in sorted(out.items()))


def draw(restrictions: list[dict], standards: list[dict], seed: int = SEED, size: int = SAMPLE_SIZE,
         raw_sha: str = "") -> list[dict]:
    ids = sorted({r["nrel_id"] for r in restrictions if r.get("nrel_id")})
    picked = random.Random(seed).sample(ids, min(size, len(ids)))
    by_id = {r["nrel_id"]: r for r in restrictions if r.get("nrel_id")}
    feats: dict[str, list[dict]] = {}
    for s in standards:
        if s.get("restricting") == "yes":
            feats.setdefault(s["nrel_id"], []).append(s)
    out = []
    for rank, nid in enumerate(picked, 1):
        r = by_id[nid]
        for s in sorted(feats.get(nid, []), key=lambda x: x["feature"]):
            out.append({"sample_rank": rank, "instrument_id": f"nrel:{nid}", "standard_id": s["standard_id"],
                        "state": r["state"], "jurisdiction": r["jurisdiction"], "technology": r["technology"],
                        "severity_score": r["severity_score"], "restriction_type": r["restriction_type"],
                        "feature": s["feature"], "value": s["value"], "units": s["units"],
                        "min_setback_ft": s["min_setback_ft"], "section": s["section"],
                        "ordinance_year": s["ordinance_year"], "ordinance_url": s["ordinance_url"],
                        "nrel_summary": s["summary"], "sample_seed": seed, "nrel_raw_sha256": raw_sha})
    return out


def review_problems(reviews: list[dict], sample: list[dict]) -> list[str]:
    """Rows that break docs/AGENT_REVIEW.md: unknown verdict or access, no
    reviewer, a feature not in the sample."""
    sampled = {s["standard_id"] for s in sample}
    out = []
    for i, r in enumerate(reviews, start=2):
        where = f"{REVIEW_PATH.name}: row {i}"
        if r.get("standard_id") not in sampled:
            out.append(f"{where}: {r.get('standard_id')!r} is not in the sample")
        if r.get("verdict") not in VERDICTS:
            out.append(f"{where}: verdict {r.get('verdict')!r} must be one of {', '.join(VERDICTS)}")
        if r.get("access") not in READ + ("snippet", ""):
            out.append(f"{where}: access {r.get('access')!r}")
        if r.get("verdict") in ("confirmed", "contradicts") and r.get("access") not in READ:
            out.append(f"{where}: a {r.get('verdict')} verdict needs the ordinance read (opened or archived)")
        if not r.get("reviewer"):
            out.append(f"{where}: reviewer is blank")
    return out


def passing(sample: list[dict], reviews: list[dict]) -> dict[str, list[dict]]:
    """instrument_id -> its review rows, for instruments whose every sampled
    feature is confirmed from the ordinance itself."""
    by_feature = {r["standard_id"]: r for r in reviews}
    feats: dict[str, list[str]] = {}
    for s in sample:
        feats.setdefault(s["instrument_id"], []).append(s["standard_id"])
    out = {}
    for iid, sids in feats.items():
        rows = [by_feature.get(sid) for sid in sids]
        if rows and all(r and r.get("verdict") == "confirmed" and r.get("access") in READ for r in rows):
            out[iid] = rows
    return out


def apply(sample: list[dict], reviews: list[dict], sources: list[dict]) -> tuple[list[dict], int]:
    """sources plus a confirmed row for every passing instrument not yet listed."""
    listed = {r.get("instrument_id") for r in sources}
    by_iid = {s["instrument_id"]: s for s in sample}
    added = 0
    for iid, rows in sorted(passing(sample, reviews).items()):
        if iid in listed:
            continue
        s = by_iid[iid]
        url = next((r["document_url"] for r in rows if r.get("document_url")), s["ordinance_url"].split()[0])
        access = "archived" if any(r.get("access") == "archived" for r in rows) else "opened"
        sources.append({
            "instrument_id": iid, "jurisdiction": s["jurisdiction"], "state": s["state"],
            "primary_source_url": url, "verdict": "confirmed",
            "checked_on": max(r.get("checked_on", "") for r in rows),
            "note": (f"NREL accuracy sample (seed {s['sample_seed']}): every sampled feature confirmed against the "
                     "ordinance: " + "; ".join(f"{r['feature']} {r['document_value']}" for r in rows)),
            "reviewer": "; ".join(sorted({r["reviewer"] for r in rows})), "access": access,
            "archived_url": next((r["archived_url"] for r in rows if r.get("archived_url")), ""),
        })
        added += 1
    return sources, added


def report(sample: list[dict], reviews: list[dict]) -> str:
    by_feature = {r["standard_id"]: r for r in reviews}
    stats: dict[str, dict[str, int]] = {}
    for s in sample:
        r = by_feature.get(s["standard_id"])
        v = r["verdict"] if r else "not reviewed"
        stats.setdefault(s["feature"], {}).setdefault(v, 0)
        stats[s["feature"]][v] += 1
    instruments = {s["instrument_id"] for s in sample}
    passed = passing(sample, reviews)
    seed = sample[0]["sample_seed"] if sample else SEED
    lines = ["# NREL accuracy sample", "",
             f"Written by `scripts/nrel_sample.py report`. {len(instruments)} NREL-derived restriction instruments "
             f"drawn with `random.Random({seed})` from the sorted list of every NREL restriction "
             f"({sample[0]['nrel_raw_sha256'] if sample else ''}). Each sampled feature was checked against the "
             "ordinance NREL cites by a reviewing agent that did not build the rows (`docs/AGENT_REVIEW.md`).", "",
             "Error rate: contradicted features divided by features with a verdict of confirmed or contradicted. "
             "Unverifiable features (the ordinance could not be read, or does not contain the provision) are "
             "listed apart and are never counted as passes.", "",
             "| Feature | Sampled | Confirmed | Contradicted | Unverifiable | Not reviewed | Error rate |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    tot: dict[str, int] = {}
    for feat in sorted(stats):
        st = stats[feat]
        for k, v in st.items():
            tot[k] = tot.get(k, 0) + v
        lines.append(_row(feat, st))
    lines.append(_row("**All features**", tot))
    lines += ["", f"Instruments whose every sampled feature was confirmed: {len(passed)} of {len(instruments)}. "
              "They are now verified (data/review/restriction_sources.csv). The rest stay unverified on the "
              "restriction worklist."]
    unver = [r for r in reviews if r.get("verdict") == "unverifiable"]
    if unver:
        lines += ["", "## Unverifiable", ""]
        lines += [f"- {r['instrument_id']} {r['feature']}: {r.get('note', '')[:240]}" for r in unver]
    contra = [r for r in reviews if r.get("verdict") == "contradicts"]
    if contra:
        lines += ["", "## Contradicted", ""]
        lines += [f"- {r['instrument_id']} {r['feature']}: NREL {r.get('nrel_value')}, ordinance "
                  f"{r.get('document_value')}. {r.get('note', '')[:240]}" for r in contra]
    return "\n".join(lines) + "\n"


def _row(label: str, st: dict[str, int]) -> str:
    c, x = st.get("confirmed", 0), st.get("contradicts", 0)
    rate = f"{x / (c + x) * 100:.0f}%" if c + x else "n/a"
    return (f"| {label} | {sum(st.values())} | {c} | {x} | {st.get('unverifiable', 0)} | "
            f"{st.get('not reviewed', 0)} | {rate} |")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("step", choices=("draw", "apply", "report"))
    args = ap.parse_args()
    if args.step == "draw":
        rows = draw(read_csv(RESTRICTIONS_PATH), read_csv(STANDARDS_PATH), raw_sha=nrel_hashes())
        write_csv(SAMPLE_PATH, rows, SAMPLE_FIELDS)
        print(f"Wrote {SAMPLE_PATH.relative_to(ROOT)}: {len({r['instrument_id'] for r in rows})} instruments, "
              f"{len(rows)} features (seed {SEED})")
        return 0
    sample, reviews = read_csv(SAMPLE_PATH), read_csv(REVIEW_PATH)
    problems = review_problems(reviews, sample)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    if args.step == "apply":
        sources, added = apply(sample, reviews, read_csv(SOURCES_PATH))
        write_csv(SOURCES_PATH, sources, list(read_csv(SOURCES_PATH)[0].keys()))
        print(f"Added {added} confirmed instrument(s) to {SOURCES_PATH.relative_to(ROOT)}")
        return 0
    REPORT_PATH.write_text(report(sample, reviews), encoding="utf-8")
    print(f"Wrote {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
