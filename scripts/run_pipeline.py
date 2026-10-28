"""Run the pipeline's stages in order: one command instead of a list to remember.

  python scripts/run_pipeline.py                  build: promote, build, worklists, gates, diff
  python scripts/run_pipeline.py refresh          re-fetch every input, rebuild the seeds, then build
  python scripts/run_pipeline.py refresh --only fetch_facilities
                                                  one input, then build
  python scripts/run_pipeline.py refresh --only fetch_facilities --skip-build
                                                  that input alone
  python scripts/run_pipeline.py refresh --only fetch_queued_up --only queue_matches --skip-build
                                                  that input and one build stage after it
  python scripts/run_pipeline.py intake           live intake: fetch the sources an extractor reads
                                                  (or that are watched), then parse new raw files
                                                  into review-queue leads; no build
  python scripts/run_pipeline.py --list           print the stages
  python scripts/run_pipeline.py --dry-run        print what would run

The build stages are exactly what the Build dashboard data workflow runs
(.github/workflows/build-data.yml calls this script), so a local run and CI
cannot drift apart. The refresh stages fetch from the network and rewrite the
seeds and the reference files; run them on purpose, and read
data/processed/diff_summary.md afterwards. The intake stages are what the
Live intake workflow runs (.github/workflows/intake.yml): they write only
data/raw/ and review-queue leads, which nothing publishes until a reviewer
triages them, so intake never runs the build.

Stops at the first stage that fails and exits with its code. With --summary
FILE (the workflow passes $GITHUB_STEP_SUMMARY), each stage's output that a
reviewer should see is appended to FILE as well as printed.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (name, command, what it does, append its output to --summary)
REFRESH = [
    ("fetch_moratorium_nation", ["scripts/fetch_moratorium_nation.py"],
     "Moratorium Nation rows of restrictions_seed.csv", False),
    ("fetch_sabin_edition", ["scripts/fetch_sabin_edition.py"], "Sabin edition files into data/raw/", False),
    ("extract_sabin_edition", ["scripts/extract_sabin_edition.py"], "Sabin extraction and reconciliation", False),
    ("sabin_crosswalk", ["scripts/sabin_crosswalk.py"], "2025 ids onto the current edition", False),
    ("build_sabin_seeds", ["scripts/build_sabin_seeds.py"], "Sabin rows of the seeds", False),
    ("fetch_nrel_ordinances", ["scripts/fetch_nrel_ordinances.py"], "NREL spreadsheets (schema guard)", False),
    ("nrel_ordinances", ["scripts/nrel_ordinances.py"], "NREL restrictions (after the Sabin build)", False),
    ("fetch_county_covariates", ["scripts/fetch_county_covariates.py"],
     "ACS, Gazetteer and MEDSL into data/reference/county_covariates.csv", True),
    ("fetch_queued_up", ["scripts/fetch_queued_up.py"],
     "LBNL Queued Up into data/reference/queue_projects.csv", True),
    ("county_labels", ["scripts/county_labels.py"],
     "county restriction model labels into data/model/county_labels.csv", True),
    ("county_restriction_model", ["scripts/county_restriction_model.py"],
     "the registered county restriction model (internal outputs in data/model/)", True),
    ("fetch_facilities", ["scripts/fetch_facilities.py"],
     "EIA-860M, USWTDB and USPVDB into data/reference/facilities.csv", True),
]
BUILD = [
    ("promote_reviewed", ["scripts/promote_reviewed.py"], "complete review rows into the seeds", True),
    ("build_seed_outputs", ["scripts/build_seed_outputs.py"], "validate, QC and write data/processed/", False),
    ("county_typology", ["scripts/county_typology.py"], "one category per county", False),
    ("county_record_score", ["scripts/county_record_score.py"],
     "the county record score, rescored on each build (internal, data/model/)", False),
    # Reads the contested projects just built, so the committed matches follow
    # every outcome a review changes, not only the monthly fetch.
    ("queue_matches", ["scripts/queue_matches.py"],
     "contested projects matched to their Queued Up requests", True),
    ("codebook", ["scripts/codebook.py"], "docs/codebook.md from the rules' own constants", False),
    ("verification_worklist", ["scripts/verification_worklist.py"], "rank what to verify next", False),
    ("adjacency_worklist", ["scripts/adjacency_worklist.py"], "neighbor watch", False),
    ("coverage_delta", ["scripts/coverage_delta.py"], "column coverage gate", False),
    ("snapshot_manifest", ["scripts/snapshot_manifest.py"], "dated, hashed record of each output", False),
    ("headline_history", ["scripts/headline_history.py"], "headline figures by day, for the history", False),
    ("processed_diff", ["scripts/processed_diff.py"], "what this build changed", False),
    ("operations_summary", ["scripts/operations_summary.py"], "what the pipeline did and holds, in one file", False),
]
INTAKE = [
    # 600 s leaves the parse and the commit well inside intake.yml's 15 minutes.
    ("fetch_intake", ["scripts/fetch.py", "--intake", "--budget-s", "600"],
     "live sources an extractor reads, and watched upstreams, into data/raw/", True),
    ("parse", ["scripts/parse.py"], "new raw files into review-queue leads (review_status lead)", True),
]
STAGES = {"build": BUILD, "refresh": REFRESH + BUILD, "intake": INTAKE}


def run(stage: tuple, summary: Path | None, dry_run: bool) -> int:
    name, cmd, what, to_summary = stage
    argv = [sys.executable, *cmd]
    print(f"== {name}: {what}", flush=True)
    if dry_run:
        print("   " + " ".join(cmd))
        return 0
    if not (to_summary and summary):
        return subprocess.run(argv, cwd=ROOT).returncode
    # Stream line by line, so a job killed mid-stage still has its log and
    # the part of the summary written so far.
    with subprocess.Popen(argv, cwd=ROOT, stdout=subprocess.PIPE, text=True, bufsize=1) as proc, \
            summary.open("a", encoding="utf-8") as f:
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            f.write(line)
            f.flush()
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mode", nargs="?", default="build", choices=sorted(STAGES))
    ap.add_argument("--only", action="append", default=[],
                    help="a refresh stage to run (repeatable); the build stages always run. "
                         "With --skip-build it may also name a build stage, run after the refresh stages")
    ap.add_argument("--skip-build", action="store_true", help="run only the --only stages")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--summary", type=Path, help="also append reviewer-facing output to this file")
    args = ap.parse_args()
    stages = STAGES[args.mode]
    if args.only:
        pool = REFRESH + BUILD if args.skip_build else REFRESH
        known = {s[0] for s in pool}
        bad = [o for o in args.only if o not in known]
        if bad:
            ap.error(f"unknown stage(s) {bad}; choose from {sorted(known)}"
                     + ("" if args.skip_build else ", or name a build stage with --skip-build"))
        stages = [s for s in pool if s[0] in args.only] + ([] if args.skip_build else BUILD)
    if args.list:
        for mode, group in (("refresh", REFRESH), ("build", BUILD), ("intake", INTAKE)):
            for name, _, what, _ in group:
                print(f"{mode:8} {name:26} {what}")
        return 0
    for stage in stages:
        code = run(stage, args.summary, args.dry_run)
        if code:
            print(f"Stage {stage[0]} failed (exit {code}); stopping.", file=sys.stderr)
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
