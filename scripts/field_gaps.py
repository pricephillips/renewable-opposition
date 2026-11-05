#!/usr/bin/env python3
"""
field_gaps.py

Finds gaps in the published data: columns that are empty more often than
they should be, columns that vanished, files that went missing or shrank.

Other checks measure whether a record exists at all (coverage_audit.py
compares the two moratorium sources) or whether the review pipeline is
still producing work (pipeline_freshness.py). None of them notices when the
rows are there but their fields are not: a build change that blanks the
county FIPS on a third of the rows, a source that stops sending dates, a
join that drops the source URL. This check does.

How it works. The config lists, for each file, the columns a reader relies
on and a ceiling for each: the largest share of rows that may be empty
(blank, or one of the config's blank_values such as "nan"). A ceiling is
set from the data as it stood when the column was added, plus a margin, so
it catches a column getting worse, not one that has always been sparse.
A column that was never empty keeps a ceiling of 0. Each run reports five
kinds of gap:

  missing_file     a listed file is not there
  unreadable_file  a listed file is not UTF-8 text a CSV reader can parse
  row_drop         the file has fewer rows than its min_rows
  missing_column   a listed column is not in the file's header
  blank_rise       a column is empty on more rows than its ceiling allows

When data improves, lower the ceilings: --suggest prints the config with
every ceiling and min_rows recomputed from the current files.

field-gaps.yml runs this weekly. On any gap it opens (or updates) one issue
labelled field-gaps with the report; when a later run finds none, it closes
that issue. The run itself stays green either way.

Reads    the config, and the files it lists
Writes   nothing in the repository; --report PATH writes the markdown
         report, --github-output PATH appends status, count and title

Usage
  python scripts/field_gaps.py [--config PATH] [--root DIR] [--report PATH]
                               [--github-output PATH] [--strict]
  python scripts/field_gaps.py --suggest [--config PATH]
  python scripts/field_gaps.py --selftest

Exit 0 when the check ran (gaps or not; 1 with --strict when there are
gaps), 2 when the config is invalid.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config", "field_gaps.json")
LABEL = "field-gaps"
DEFAULT_BLANKS = ("", "nan", "none", "null", "n/a", "na")
MARGIN = 0.02          # added to the current share when --suggest sets a ceiling
ROW_FLOOR = 0.95       # --suggest sets min_rows to this share of the current count

csv.field_size_limit(2**31 - 1)


class ConfigError(ValueError):
    pass


def load_config(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    validate(cfg)
    return cfg


def validate(cfg: dict) -> None:
    files = cfg.get("files")
    if not isinstance(files, list) or not files:
        raise ConfigError("config needs a non-empty files list")
    seen = set()
    for i, entry in enumerate(files):
        where = f"files[{i}]"
        path = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(path, str) or not path:
            raise ConfigError(f"{where}: needs a path")
        if path in seen:
            raise ConfigError(f"{where}: {path} is listed twice")
        seen.add(path)
        rows = entry.get("min_rows", 0)
        if not isinstance(rows, int) or isinstance(rows, bool) or rows < 0:
            raise ConfigError(f"{path}: min_rows must be a whole number, 0 or more")
        cols = entry.get("columns")
        if not isinstance(cols, dict) or not cols:
            raise ConfigError(f"{path}: needs a non-empty columns object")
        for col, ceiling in cols.items():
            if (not isinstance(ceiling, (int, float)) or isinstance(ceiling, bool)
                    or not 0 <= ceiling <= 1):
                raise ConfigError(f"{path}: ceiling for {col!r} must be between 0 and 1")
    blanks = cfg.get("blank_values", list(DEFAULT_BLANKS))
    if not isinstance(blanks, list) or not all(isinstance(b, str) for b in blanks):
        raise ConfigError("blank_values must be a list of strings")


def read_csv(path: str) -> tuple[list[str], list[dict]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return [h.strip() for h in (reader.fieldnames or [])], rows


def blank_counts(header: list[str], rows: list[dict], columns, blanks) -> dict:
    """Empty-row count for each requested column that is in the header."""
    blanks = {b.strip().lower() for b in blanks}
    # DictReader keys keep the raw header text; map stripped names back to it.
    raw = {}
    if rows:
        for key in rows[0].keys():
            if key is not None:
                raw[key.strip()] = key
    out = {}
    for col in columns:
        if col not in header:
            continue
        key = raw.get(col, col)
        out[col] = sum(1 for r in rows if (r.get(key) or "").strip().lower() in blanks)
    return out


def check(cfg: dict, root: str = ROOT) -> dict:
    blanks = cfg.get("blank_values", list(DEFAULT_BLANKS))
    files, findings = [], []
    for entry in cfg["files"]:
        path, cols = entry["path"], entry["columns"]
        rec = {"path": path, "rows": None, "min_rows": entry.get("min_rows", 0), "columns": []}
        files.append(rec)
        full = os.path.join(root, path)
        if not os.path.isfile(full):
            findings.append({"kind": "missing_file", "path": path})
            continue
        try:
            header, rows = read_csv(full)
        except (UnicodeDecodeError, csv.Error) as exc:
            findings.append({"kind": "unreadable_file", "path": path, "error": str(exc)[:200]})
            continue
        n = rec["rows"] = len(rows)
        if n < rec["min_rows"]:
            findings.append({"kind": "row_drop", "path": path, "rows": n,
                             "min_rows": rec["min_rows"]})
        counts = blank_counts(header, rows, cols, blanks)
        for col, ceiling in cols.items():
            if col not in counts:
                findings.append({"kind": "missing_column", "path": path, "column": col})
                rec["columns"].append({"column": col, "blank": None, "share": None,
                                       "ceiling": ceiling})
                continue
            share = counts[col] / n if n else 1.0
            rec["columns"].append({"column": col, "blank": counts[col], "share": share,
                                   "ceiling": ceiling})
            if share > ceiling + 1e-9:
                findings.append({"kind": "blank_rise", "path": path, "column": col,
                                 "blank": counts[col], "rows": n, "share": share,
                                 "ceiling": ceiling})
    return {"files": files, "findings": findings}


def suggest_ceiling(share: float) -> float:
    """0 stays 0; anything else gets the margin, rounded up to the next 0.01."""
    if share <= 0:
        return 0.0
    return min(1.0, math.ceil(round((share + MARGIN) * 100, 6)) / 100)


def suggest(cfg: dict, root: str = ROOT) -> dict:
    """The config with ceilings and min_rows recomputed from the current files.
    A file or column that cannot be read keeps what the config had."""
    result = check(cfg, root)
    out = json.loads(json.dumps(cfg))
    by_path = {f["path"]: f for f in result["files"]}
    for entry in out["files"]:
        rec = by_path[entry["path"]]
        if rec["rows"] is None:
            continue
        entry["min_rows"] = int(math.floor(rec["rows"] * ROW_FLOOR))
        for c in rec["columns"]:
            if c["share"] is not None:
                entry["columns"][c["column"]] = suggest_ceiling(c["share"])
    return out


def _pct(x: float | None) -> str:
    return "" if x is None else f"{x * 100:.1f}%"


def describe(f: dict) -> str:
    k = f["kind"]
    if k == "missing_file":
        return f"`{f['path']}` is missing."
    if k == "unreadable_file":
        return f"`{f['path']}` cannot be read as a UTF-8 CSV ({f['error']})."
    if k == "row_drop":
        return f"`{f['path']}` has {f['rows']} rows, fewer than its floor of {f['min_rows']}."
    if k == "missing_column":
        return f"`{f['path']}` has no column `{f['column']}`."
    return (f"`{f['path']}` column `{f['column']}` is empty on {f['blank']} of "
            f"{f['rows']} rows ({_pct(f['share'])}), above its ceiling of {_pct(f['ceiling'])}.")


def title(result: dict) -> str:
    n = len(result["findings"])
    return f"Data gaps: {n} field check{'s' if n != 1 else ''} failed"


def report(result: dict, today: str, config_rel: str) -> str:
    findings = result["findings"]
    lines = [f"# {title(result) if findings else 'Data gaps: none found'}", "",
             f"Checked {today} by `scripts/field_gaps.py` against `{config_rel}`.", ""]
    if findings:
        lines += ["## Gaps", ""] + [f"- {describe(f)}" for f in findings] + [""]
        lines += ["A ceiling is the largest share of rows a column may leave empty. "
                  "Fix the data or the step that blanked it. If the new level is expected, "
                  "raise the ceiling in the config and say why in the pull request.", ""]
    else:
        lines += ["Every listed file is present, has at least its floor of rows, and every "
                  "listed column is within its ceiling.", ""]
    lines += ["## Every column checked", "", "<details><summary>Show the table</summary>", "",
              "| File | Rows | Column | Empty | Share | Ceiling |",
              "|---|---:|---|---:|---:|---:|"]
    for rec in result["files"]:
        rows = "missing" if rec["rows"] is None else str(rec["rows"])
        if not rec["columns"]:
            lines.append(f"| `{rec['path']}` | {rows} |  |  |  |  |")
        for c in rec["columns"]:
            empty = "no column" if c["share"] is None else str(c["blank"])
            lines.append(f"| `{rec['path']}` | {rows} | `{c['column']}` | {empty} | "
                         f"{_pct(c['share'])} | {_pct(c['ceiling'])} |")
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--root", default=ROOT, help="the folder the config's paths are relative to")
    ap.add_argument("--report", help="write the markdown report here")
    ap.add_argument("--github-output", help="append status, count and title here")
    ap.add_argument("--strict", action="store_true", help="exit 1 when there are gaps")
    ap.add_argument("--suggest", action="store_true",
                    help="print the config with ceilings recomputed from the current files")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"field_gaps: invalid config: {exc}", file=sys.stderr)
        return 2
    if args.suggest:
        print(json.dumps(suggest(cfg, args.root), indent=2, ensure_ascii=False))
        return 0
    result = check(cfg, args.root)
    rel = os.path.relpath(os.path.abspath(args.config), ROOT).replace(os.sep, "/")
    text = report(result, dt.date.today().isoformat(), rel)
    n = len(result["findings"])
    checked = sum(len(f["columns"]) for f in result["files"])
    print(f"field_gaps: {n} gap(s) in {len(result['files'])} files, {checked} columns checked")
    for f in result["findings"]:
        print(f"  {f['kind']}: {describe(f)}")
    if args.report:
        with open(args.report, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write(f"status={'gaps' if n else 'ok'}\ncount={n}\ntitle={title(result)}\n")
    return 1 if (args.strict and n) else 0


def selftest() -> int:
    tmp = tempfile.mkdtemp(prefix="field_gaps_")

    def write(name: str, text: str) -> None:
        with open(os.path.join(tmp, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)

    # BOM on the first header, a padded header, "nan" and spaces count as empty.
    write("a.csv", "﻿id, county ,url\n1,Kent,http://x\n2,nan,http://y\n3,  ,\n4,Sussex,http://z\n")
    base = {"files": [{"path": "a.csv", "min_rows": 4,
                       "columns": {"id": 0.0, "county": 0.5, "url": 0.25}}]}
    validate(base)
    r = check(base, tmp)
    assert r["findings"] == [], r["findings"]
    cols = {c["column"]: c for c in r["files"][0]["columns"]}
    assert cols["county"]["blank"] == 2 and cols["url"]["blank"] == 1, cols

    tight = json.loads(json.dumps(base))
    tight["files"][0]["columns"]["county"] = 0.4
    kinds = [f["kind"] for f in check(tight, tmp)["findings"]]
    assert kinds == ["blank_rise"], kinds

    gone = json.loads(json.dumps(base))
    gone["files"][0]["columns"]["state"] = 0.1
    gone["files"][0]["min_rows"] = 5
    gone["files"].append({"path": "b.csv", "columns": {"id": 0}})
    kinds = sorted(f["kind"] for f in check(gone, tmp)["findings"])
    assert kinds == ["missing_column", "missing_file", "row_drop"], kinds

    # A file that is not UTF-8 is a finding, not a crash.
    with open(os.path.join(tmp, "c.csv"), "wb") as fh:
        fh.write(b"id\n\xff\xfe\x00\n")
    bad_file = {"files": [{"path": "c.csv", "columns": {"id": 0}}]}
    kinds = [f["kind"] for f in check(bad_file, tmp)["findings"]]
    assert kinds == ["unreadable_file"], kinds
    assert "cannot be read" in report(check(bad_file, tmp), "2026-01-01", "cfg.json")

    # Custom blank values replace the defaults.
    custom = json.loads(json.dumps(base))
    custom["blank_values"] = [""]
    custom["files"][0]["columns"]["county"] = 0.25
    assert check(custom, tmp)["findings"] == []

    # Suggested ceilings: 0 stays 0, else share + margin rounded up.
    assert suggest_ceiling(0) == 0.0
    assert suggest_ceiling(0.10) == 0.12, suggest_ceiling(0.10)
    assert suggest_ceiling(0.101) == 0.13
    assert suggest_ceiling(0.995) == 1.0
    s = suggest(gone, tmp)
    assert s["files"][0]["min_rows"] == 3 and s["files"][0]["columns"]["county"] == 0.52, s
    assert s["files"][0]["columns"]["state"] == 0.1 and s["files"][1] == gone["files"][1], s

    for bad in ({"files": []},
                {"files": [{"path": "a.csv", "columns": {}}]},
                {"files": [{"path": "a.csv", "columns": {"id": 1.5}}]},
                {"files": [{"path": "a.csv", "min_rows": -1, "columns": {"id": 0}}]},
                {"files": [{"path": "a.csv", "columns": {"id": 0}},
                           {"path": "a.csv", "columns": {"id": 0}}]}):
        try:
            validate(bad)
        except ConfigError:
            continue
        raise AssertionError(f"accepted a bad config: {bad}")

    text = report(check(gone, tmp), "2026-01-01", "cfg.json")
    assert "Data gaps: 3 field checks failed" in text and "no column" in text, text
    assert "\u2014" not in text and "\r" not in text

    # main(): outputs for the workflow, --strict, and an invalid config.
    write("cfg.json", json.dumps(tight))
    out = os.path.join(tmp, "out.txt")
    rep = os.path.join(tmp, "report.md")
    argv = ["--config", os.path.join(tmp, "cfg.json"), "--root", tmp]
    assert main(argv + ["--github-output", out, "--report", rep]) == 0
    assert main(argv + ["--strict"]) == 1
    with open(out, encoding="utf-8") as fh:
        kv = dict(line.split("=", 1) for line in fh.read().splitlines())
    assert kv["status"] == "gaps" and kv["count"] == "1", kv
    write("bad.json", "{")
    assert main(["--config", os.path.join(tmp, "bad.json")]) == 2
    with open(rep, encoding="utf-8") as fh:
        assert "above its ceiling of 40.0%" in fh.read()

    # The repository's own config is valid (structure only; data is not read).
    if os.path.isfile(CONFIG):
        load_config(CONFIG)
    shutil.rmtree(tmp, ignore_errors=True)
    print("field_gaps selftest: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
