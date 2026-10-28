#!/usr/bin/env python3
"""
scripts/variable_registry.py

The variable registry here (spec 033 in pricephillips/data-centers, US5):
one JSON manifest per county or state variable under
config/variables/<id>.json, in the format data-centers uses. How an entry is
read, keyed, filtered, copied from state to county, transformed and bounded
is scripts/variable_core.py, copied byte for byte from data-centers and
pinned, with config/variable_manifest.schema.json, by
config/variable_format.lock. This file is the glue for this repository.

What a registered variable does here:
  - audience public (or client: this repository's outputs are all public,
    so the two are read alike): scripts/build_seed_outputs.py appends one
    column per variable to data/processed/county_summary.csv, after
    county_summary.FIELDS, and scripts/build_database.py loads the
    `variable` and `county_variable` tables and the v_county_variables view.
  - audience internal: nothing reads it yet.
  - the county model's pool is config/county_model_registration.json, a
    pre-registration. A manifest never enters it; a variable joins the
    model only through a new dated registration.
  - nothing here fetches a manifest's source: its file is written by a
    fetcher this repository already runs, so source.type is "none".

Rules --check enforces:
  1  schema-valid, id equals the file name, format_version and the lock's
     hashes match the shared files
  2  no column name repeats across entries, the registered model variables
     or the columns of data/processed/county_summary.csv
  3  the file exists, its keys parse for the grain, every declared column is
     present, and no key repeats after `where`
  4  every column passes its quality bounds over the county frame (the 2024
     counties, scripts/geo.py)
  5  a client or public entry has a license, an attribution and a
     definition, and its file is an outside source (OUTSIDE_SOURCES), never
     a record count of this repository's own
  6  source.type is "none"

Writes only config/variables/<id>.json, and only with --new.

Usage
  python scripts/variable_registry.py --check [--id ID]
  python scripts/variable_registry.py --draft ID
  python scripts/variable_registry.py --new ID --grain county|state
  python scripts/variable_registry.py --compare-lock PATH   the sibling's lock (variable-format.yml)
  python scripts/variable_registry.py --selftest
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import variable_core as vc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VARIABLES_DIR = Path("config") / "variables"
SCHEMA = Path("config") / "variable_manifest.schema.json"
LOCK = Path("config") / "variable_format.lock"
CORE = Path("scripts") / "variable_core.py"
REGISTRATION = Path("config") / "county_model_registration.json"
LAYERS = Path("config") / "layers.json"
NEW_PATH = ROOT / VARIABLES_DIR

# Rule 5: files a client or public variable may be read from. Fetched
# outside sources only. data/reference/data_center_events.csv is a copy of
# data-centers' opposition records, and data/processed/ is this repository's
# own record, so neither is here.
OUTSIDE_SOURCES = ("data/reference/county_covariates.csv",)
OUTSIDE_DIRS = ("data/reference/variables/",)
SHOWN = ("client", "public")


def _read_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _read_csv(path: Path):
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return None


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def outside_source(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    if rel.startswith("/") or ".." in rel.split("/"):
        return False
    return rel in OUTSIDE_SOURCES or rel.startswith(OUTSIDE_DIRS)


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def manifest_paths(root: Path = ROOT) -> list[Path]:
    return sorted((root / VARIABLES_DIR).glob("*.json"))


def _validator(root: Path):
    try:
        import jsonschema
        return jsonschema.Draft202012Validator(_read_json(root / SCHEMA))
    except Exception:  # noqa: BLE001 - reported as a problem by read_entries
        return None


def read_entries(root: Path = ROOT):
    """(entries, problems). An entry with a problem is flagged (entry.bad); a
    manifest that cannot be read at all is a problem and no entry."""
    entries, problems = [], []
    paths = manifest_paths(root)
    validator = _validator(root)
    if validator is None and paths:
        problems.append(f"{SCHEMA}: schema missing, unreadable or jsonschema not installed")
    for path in paths:
        stem = path.stem
        try:
            raw = _read_json(path)
        except (OSError, ValueError) as exc:
            problems.append(f"{stem}: file: unreadable ({type(exc).__name__})")
            continue
        bad = []
        if validator is not None:
            for err in sorted(validator.iter_errors(raw), key=lambda e: list(e.path)):
                where = "/".join(str(x) for x in err.path) or "(entry)"
                bad.append(f"{stem}: {where}: {err.message}")
        try:
            e = vc.parse_entry(raw, str(path.relative_to(root)))
        except (vc.ManifestError, ValueError, TypeError, AttributeError) as exc:
            problems.extend(bad or [f"{stem}: entry: {exc}"])
            continue
        if e.id != stem:
            bad.append(f"{stem}: id: {e.id!r} differs from the file name")
        problems.extend(bad)
        e.bad = bool(bad)
        entries.append(e)
    return entries, problems


def taken_names(root: Path = ROOT) -> dict[str, str]:
    """Names a registered column may not take, with what holds each."""
    out = {}
    try:
        for k in _read_json(root / REGISTRATION).get("variables", {}):
            if not k.startswith("_"):
                out[k] = f"{REGISTRATION} (the county model's registered pool)"
    except (OSError, ValueError):
        pass
    import county_summary
    for k in county_summary.FIELDS:
        out[k] = "data/processed/county_summary.csv"
    return out


def frame() -> dict[str, str]:
    """fips -> state abbreviation for the 2024 counties."""
    import geo
    return {f: vc.STATE_FIPS.get(f[:2], "") for f in geo.all_counties()}


def lock_problems(root: Path = ROOT) -> list[str]:
    try:
        lock = _read_json(root / LOCK)
    except (OSError, ValueError):
        return [f"{LOCK}: missing or unreadable"]
    probs = []
    if lock.get("format_version") != vc.FORMAT_VERSION:
        probs.append(f"{LOCK}: format_version {lock.get('format_version')} but "
                     f"variable_core.py is {vc.FORMAT_VERSION}")
    for key, rel in (("schema_sha256", SCHEMA), ("core_sha256", CORE)):
        try:
            got = sha256_file(root / rel)
        except OSError:
            probs.append(f"{rel}: missing")
            continue
        if got != lock.get(key):
            probs.append(f"{LOCK}: {key} {lock.get(key)} but {rel} is {got}; copy the file from "
                         "pricephillips/data-centers, or bump the lock there and here together")
    return probs


LOCK_KEYS = ("format_version", "schema_sha256", "core_sha256")


def compare_lock(root: Path, other: Path) -> list[str]:
    """Differences between this repository's lock and pricephillips/data-centers'
    (variable-format.yml fetches it), plus this repository's own lock problems."""
    probs = lock_problems(root)
    try:
        theirs = _read_json(other)
        mine = _read_json(root / LOCK)
    except (OSError, ValueError) as exc:
        return probs + [f"lock: cannot read ({type(exc).__name__}: {exc})"]
    probs += [f"{LOCK}: {k} is {mine.get(k)!r} here and {theirs.get(k)!r} in the sibling; copy "
              "the shared files and the lock so both repositories read one format"
              for k in LOCK_KEYS if mine.get(k) != theirs.get(k)]
    return probs


# --------------------------------------------------------------------------
# checking
# --------------------------------------------------------------------------

def check(root: Path = ROOT, only: str | None = None, fr: dict | None = None):
    """(problems, warnings), one line each, '<id>: <field>: <problem>'."""
    entries, probs = read_entries(root)
    probs = lock_problems(root) + probs
    warns: list[str] = []
    taken = taken_names(root)
    fr = frame() if fr is None else fr
    seen: dict[str, str] = {}
    for e in entries:
        if not e.enabled or e.bad:
            continue
        for c in e.columns:
            if c.name in taken:
                probs.append(f"{e.id}: columns/{c.col}/name: {c.name!r} is already used by "
                             f"{taken[c.name]}")
            elif c.name in seen:
                probs.append(f"{e.id}: columns/{c.col}/name: {c.name!r} is already used by "
                             f"{seen[c.name]}")
            else:
                seen[c.name] = e.id
    for e in entries:
        if (only and e.id != only) or e.bad:
            continue
        if e.format_version != vc.FORMAT_VERSION:
            probs.append(f"{e.id}: format_version: {e.format_version}, expected {vc.FORMAT_VERSION}")
        src = e.source or {}
        if src.get("type", "none") != "none":
            probs.append(f"{e.id}: source/type: nothing here fetches a manifest; write the file "
                         "with this repository's own fetcher and set the type to \"none\"")
        rel = e.file.replace("\\", "/")
        if rel.startswith("/") or ".." in rel.split("/"):
            probs.append(f"{e.id}: file: must be a path inside the repository")
            continue
        if e.audience in SHOWN:
            for k in ("license", "attribution"):
                if not str(src.get(k, "")).strip():
                    probs.append(f"{e.id}: source/{k}: required for audience {e.audience}")
            if not e.definition.strip():
                probs.append(f"{e.id}: definition: required for audience {e.audience}")
            if not outside_source(rel):
                probs.append(f"{e.id}: file: {rel} is not an outside source; a {e.audience} "
                             f"variable reads {', '.join(OUTSIDE_SOURCES + OUTSIDE_DIRS)}")
        rows = _read_csv(root / rel)
        if rows is None:
            probs.append(f"{e.id}: file: {rel} does not exist")
            continue
        if not rows:
            probs.append(f"{e.id}: file: {rel} is empty")
            continue
        header = set(rows[0])
        missing = [c.col for c in e.columns if c.col not in header]
        if missing:
            probs.append(f"{e.id}: columns: not in {rel}: {', '.join(missing)}")
        for col in e.where:
            if col not in header:
                probs.append(f"{e.id}: where: column {col!r} not in {rel}")
        if e.key not in header:
            probs.append(f"{e.id}: key: column {e.key!r} not in {rel}")
            continue
        bad_keys = vc.unparsed_keys(rows, e)
        if bad_keys:
            probs.append(f"{e.id}: key: {len(bad_keys)} value(s) are not a {e.grain} key, "
                         f"for example {bad_keys[0]!r}")
        try:
            idx = vc.select_rows(rows, e)
        except vc.DuplicateKeyError as exc:
            probs.append(f"{e.id}: where: {exc}")
            continue
        keys = sorted(set(fr.values())) if e.grain == "state" else sorted(fr)
        for c in e.columns:
            at = f"{e.id}: columns/{c.col}"
            if c.levels and c.unit != "category":
                probs.append(f"{at}/levels: only a category column has levels")
            if c.unit == "category" and c.transform != "identity":
                probs.append(f"{at}/transform: a category column takes no transform")
            if c.col in header:
                vals = [(idx.get(k) or {}).get(c.col, "") for k in keys]
                probs.extend(f"{at}/qc: {p}" for p in
                             vc.qc_problems(c.name, vals, c.qc, e.grain, c.unit, c.levels))
    if only:
        if not any(e.id == only for e in entries):
            probs.append(f"{only}: no such entry")
        mine = (f"{only}:", str(LOCK), str(SCHEMA), str(CORE))
        probs = [p for p in probs if p.startswith(mine)]
    return probs, warns


# --------------------------------------------------------------------------
# what the build reads
# --------------------------------------------------------------------------

def published(root: Path = ROOT, fr: dict | None = None):
    """(entries, notes): the enabled client or public entries that pass
    --check. One that does not is left out with a note, so a bad manifest
    never stops the build; validate.yml runs --check on every pull request."""
    entries, _ = read_entries(root)
    shown = [e for e in entries if e.enabled and e.audience in SHOWN]
    if not shown:
        return [], []
    probs, _ = check(root, fr=fr)
    global_probs = [p for p in probs if p.startswith((str(LOCK), str(SCHEMA), str(CORE)))]
    out, notes = [], []
    for e in shown:
        mine = [p for p in probs if p.startswith(f"{e.id}:")]
        if e.bad or mine or global_probs:
            notes.append(f"{e.id}: left out ({(mine + global_probs + ['schema problems'])[0]})")
        else:
            out.append(e)
    return out, notes


def county_values(entry, root: Path = ROOT, fr: dict | None = None) -> dict:
    """column name -> {fips: raw value as the file gives it, "" when missing}
    for every county of the frame; a state value is copied onto each county
    of its state."""
    fr = frame() if fr is None else fr
    idx = vc.select_rows(_read_csv(root / entry.file) or [], entry)
    out = {}
    for c in entry.columns:
        out[c.name] = {f: str((idx.get(st if entry.grain == "state" else f) or {})
                              .get(c.col, "") or "").strip()
                       for f, st in fr.items()}
    return out


CATALOG_FIELDS = ("variable_id", "label", "unit", "format", "basis", "definition", "source_title",
                  "source_url", "license", "attribution", "vintage")


def catalog_row(entry, column) -> dict:
    """The database's `variable` row for one column, in CATALOG_FIELDS order."""
    src = entry.source or {}
    return {"variable_id": column.name, "label": column.label, "unit": column.unit,
            "format": column.format, "basis": entry.grain, "definition": entry.definition,
            "source_title": src.get("title", ""), "source_url": src.get("url", ""),
            "license": src.get("license", ""), "attribution": src.get("attribution", ""),
            "vintage": str(src.get("vintage", ""))}


# --------------------------------------------------------------------------
# drafting and skeletons
# --------------------------------------------------------------------------

def draft(root: Path, entry_id: str) -> str:
    entries, _ = read_entries(root)
    e = next((x for x in entries if x.id == entry_id), None)
    if e is None:
        raise SystemExit(f"{entry_id}: no entry in {VARIABLES_DIR}")
    if e.bad:
        raise SystemExit(f"{entry_id}: the manifest has problems; run "
                         f"python scripts/variable_registry.py --check --id {entry_id}")
    lines = [f"# {LAYERS}, under \"files\", unless a pattern there already covers {e.file}:",
             f"\"{e.file}\": {{\"layer\": \"raw\", \"writers\": [\"scripts/<the fetcher>.py\"], "
             f"\"reason\": {json.dumps((e.source or {}).get('title', ''))}}},"]
    if e.audience in SHOWN:
        cols = ", ".join(c.name for c in e.columns)
        lines += ["", f"# Published: data/processed/county_summary.csv gains {cols}, and the "
                  "database's county_variable table their values; nothing to paste."]
    return "\n".join(lines)


def new_skeleton(root: Path, entry_id: str, grain: str) -> Path:
    if not vc.ID_RE.match(entry_id):
        raise SystemExit(f"{entry_id}: an id is lower case letters, digits and _, 3 to 41 long")
    path = NEW_PATH / f"{entry_id}.json" if root == ROOT else root / VARIABLES_DIR / f"{entry_id}.json"
    if path.exists():
        raise SystemExit(f"{path.relative_to(root)} exists")
    d = {"id": entry_id, "format_version": vc.FORMAT_VERSION, "enabled": True,
         "file": f"data/reference/variables/{entry_id}.csv",
         "key": "county_fips" if grain == "county" else "state", "grain": grain,
         "audience": "internal", "definition": "",
         "source": {"type": "none", "title": "", "url": "https://", "license": "",
                    "attribution": "", "vintage": ""},
         "columns": {"": {"name": "", "label": "", "unit": "none", "format": "dec1"}}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------

def selftest() -> int:
    fails = []

    def expect(name, ok):
        print(("PASS " if ok else "FAIL ") + name)
        if not ok:
            fails.append(name)

    expect("the lock matches the shared files here", lock_problems(ROOT) == [])
    with tempfile.TemporaryDirectory() as td:
        same = Path(td) / "same.lock"
        same.write_bytes((ROOT / LOCK).read_bytes())
        other = Path(td) / "other.lock"
        other.write_text(json.dumps({**_read_json(ROOT / LOCK), "core_sha256": "0" * 64}))
        expect("--compare-lock: the same lock passes; a different core hash is named",
               compare_lock(ROOT, same) == []
               and any("core_sha256" in p for p in compare_lock(ROOT, other)))
    expect("the core's own selftest passes", vc.selftest() == 0)
    fr = {"01001": "AL", "01003": "AL", "13001": "GA"}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for rel in (SCHEMA, LOCK, CORE):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes((ROOT / rel).read_bytes())
        (root / REGISTRATION).write_text(json.dumps({"variables": {"_note": "", "margin": {}}}))
        (root / "data" / "reference" / "variables").mkdir(parents=True)
        (root / "data" / "reference" / "variables" / "demo.csv").write_text(
            "county_fips,v,cls\n01001,1.5,low\n01003,2.5,high\n", encoding="utf-8")
        (root / "data" / "reference" / "variables" / "st.csv").write_text(
            "state,v\nAL,7\n", encoding="utf-8")

        def put(**over):
            d = {"id": "demo", "format_version": 1, "file": "data/reference/variables/demo.csv",
                 "key": "county_fips", "grain": "county", "audience": "public",
                 "definition": "A fixture value per county.",
                 "source": {"type": "none", "title": "Fixture", "url": "https://example.gov",
                            "license": "public domain", "attribution": "Fixture agency",
                            "vintage": "2024"},
                 "columns": {"v": {"name": "demo_v", "label": "Demo", "unit": "index",
                                   "format": "dec1", "qc": {"min": 0}}}}
            d.update(over)
            (root / VARIABLES_DIR).mkdir(parents=True, exist_ok=True)
            (root / VARIABLES_DIR / f"{d['id']}.json").write_text(json.dumps(d))
            return d

        def clear():
            for p in manifest_paths(root):
                p.unlink()

        put()
        probs, _ = check(root, fr=fr)
        expect("a clean public entry has no problems", probs == [])
        got, notes = published(root, fr=fr)
        vals = county_values(got[0], root, fr) if got else {}
        expect("published() returns it, and its values are raw text, blank when missing",
               [e.id for e in got] == ["demo"] and notes == []
               and vals == {"demo_v": {"01001": "1.5", "01003": "2.5", "13001": ""}})
        expect("catalog_row carries every catalog field",
               catalog_row(got[0], got[0].columns[0])["license"] == "public domain"
               and catalog_row(got[0], got[0].columns[0])["basis"] == "county")
        clear()
        put(id="st_demo", file="data/reference/variables/st.csv", key="state", grain="state",
            columns={"v": {"name": "st_v", "label": "S", "unit": "count", "format": "int"}})
        got, _ = published(root, fr=fr)
        expect("a state value is copied onto each county of its state, never filled",
               county_values(got[0], root, fr) == {"st_v": {"01001": "7", "01003": "7", "13001": ""}})
        cases = [
            ("rule 2: a registered model variable's name is refused",
             dict(columns={"v": {"name": "margin", "label": "x", "unit": "index", "format": "dec1"}}),
             "county model's registered pool"),
            ("rule 2: a county_summary column's name is refused",
             dict(columns={"v": {"name": "coverage", "label": "x", "unit": "index", "format": "dec1"}}),
             "county_summary.csv"),
            ("rule 3: a missing column is named",
             dict(columns={"nope": {"name": "demo_n", "label": "x", "unit": "index", "format": "dec1"}}),
             "not in data/reference/variables/demo.csv: nope"),
            ("rule 4: a value below min is counted",
             dict(columns={"v": {"name": "demo_v", "label": "x", "unit": "index", "format": "dec1",
                                 "qc": {"min": 2}}}), "below min 2"),
            ("rule 5: a public entry needs a definition", dict(definition=""), "definition: required"),
            ("rule 5: a public entry reading this repository's own records is refused",
             dict(file="data/processed/county_summary.csv"), "not an outside source"),
            ("rule 6: nothing here fetches", dict(source={"type": "csv_url", "title": "T",
                                                          "url": "https://x.gov", "vintage": "1",
                                                          "license": "x", "attribution": "y"}),
             "nothing here fetches"),
        ]
        for label, over, needle in cases:
            clear()
            put(**over)
            probs, _ = check(root, fr=fr)
            expect(label, any(needle in p for p in probs))
            got, notes = published(root, fr=fr)
            expect(label + " (and published() leaves it out with a note)",
                   got == [] and len(notes) == 1)
        clear()
        put()
        (root / VARIABLES_DIR / "demo.json").rename(root / VARIABLES_DIR / "other.json")
        probs, _ = check(root, fr=fr)
        expect("rule 1: id must equal the file name", any("differs from the file name" in p
                                                          for p in probs))
        clear()
        put()
        put(id="twin", columns={"v": {"name": "demo_v", "label": "x", "unit": "index",
                                      "format": "dec1"}})
        probs, _ = check(root, fr=fr)
        expect("rule 2: a name two entries claim is refused once",
               sum("already used by demo" in p for p in probs) == 1)
        clear()
        put(audience="internal")
        expect("an internal entry is never published", published(root, fr=fr) == ([], []))
        (root / LOCK).write_text(json.dumps({"format_version": 1, "schema_sha256": "x",
                                             "core_sha256": "y"}))
        expect("a lock that does not match is a problem", any("schema_sha256" in p
                                                              for p in lock_problems(root)))
        clear()
        put()
        got, notes = published(root, fr=fr)
        expect("a lock problem keeps every variable out of the build", got == [] and notes)
        path = new_skeleton(root, "fresh_var", "state")
        expect("--new writes a skeleton with every required field",
               json.loads(path.read_text())["key"] == "state")
        try:
            new_skeleton(root, "fresh_var", "state")
            expect("--new refuses to overwrite", False)
        except SystemExit:
            expect("--new refuses to overwrite", True)
    expect("outside_source: the allowlist and data/reference/variables/ only",
           outside_source("data/reference/county_covariates.csv")
           and outside_source("data/reference/variables/x.csv")
           and not outside_source("data/reference/data_center_events.csv")
           and not outside_source("data/processed/restrictions.csv")
           and not outside_source("data/reference/variables/../../processed/x.csv"))
    print(f"\n{'FAIL' if fails else 'PASS'}: {len(fails)} failed")
    return 1 if fails else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--id")
    ap.add_argument("--draft", metavar="ID")
    ap.add_argument("--new", metavar="ID")
    ap.add_argument("--grain", choices=vc.GRAINS, default="county")
    ap.add_argument("--compare-lock", metavar="PATH")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.compare_lock:
        probs = compare_lock(ROOT, Path(a.compare_lock))
        for line in probs:
            print(line)
        print("the variable format matches the sibling's" if not probs else
              f"{len(probs)} difference(s)")
        return 1 if probs else 0
    if a.check:
        probs, warns = check(ROOT, only=a.id)
        for line in probs:
            print(line)
        for line in warns:
            print("warning: " + line)
        n = len(read_entries(ROOT)[0])
        print(f"{len(probs)} problem(s), {len(warns)} warning(s) across {n} entries")
        return 1 if probs else 0
    if a.draft:
        print(draft(ROOT, a.draft))
        return 0
    if a.new:
        print(f"wrote {new_skeleton(ROOT, a.new, a.grain).relative_to(ROOT)}")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
