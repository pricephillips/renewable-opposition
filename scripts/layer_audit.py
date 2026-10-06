#!/usr/bin/env python3
"""
layer_audit.py

Checks config/layers.json against the code. A small port of
pricephillips/data-center-map layer_audit.py
(docs/PASSOFF_2026-09-29_tooling_from_data_center_map.md, B1); copied in
spirit, not imported. That module audits a tree of ~100 writers; this one
covers a dozen scripts, so it keeps the two rules and drops the rest.

  Declared writers.  Every file a script writes must be declared, with that
                     script among its writers, and every declared writer must
                     still write the file (a stale declaration is a finding
                     too). A file with two or more writers needs a reason.
  Declared crossings. A script that writes into two layers needs a reason.
  Row ownership.     Where writers share a file by row, each row's owner
                     column must match exactly one writer's prefix.
  Reference files.   A file copied from another repository (layer
                     "reference") has no writer here and names its source
                     under copied_from; every other file has a writer.
  Hand-edited files. A review file a person keeps by hand ("hand_edited":
                     true) has no writer at all.

Write targets come from an AST walk, not a grep, because a script that reads
a path mentions it the same way a script that writes it does. A target is
resolved from module constants (ROOT / "data" / ..., names imported from
common.py, f-strings become *). Output paths must stay module constants for
this to see them (passoff Part C.3); a write the walk cannot resolve is a
finding unless config/layers.json declares it under "dynamic".

Usage
  python scripts/layer_audit.py          report; exit 1 on any finding
"""

from __future__ import annotations

import ast
import csv
import fnmatch
import json
import posixpath
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "layers.json"
SCRIPTS = ("scripts/*.py", "scripts/extractors/*.py")
WRITE_METHODS = {"write_text", "write_bytes"}
# Helpers whose first argument is the file they write, across modules.
SHARED_HELPERS = {"write_csv"}


def _mode_writes(call: ast.Call, pos: int) -> bool:
    mode = None
    if len(call.args) > pos and isinstance(call.args[pos], ast.Constant):
        mode = call.args[pos].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = kw.value.value
    return isinstance(mode, str) and any(c in mode for c in "wax")


class Resolver:
    """Evaluate path expressions to repo-relative posix strings."""

    def __init__(self, module_rel: str, env: dict[str, str]):
        self.module_rel = module_rel
        self.env = dict(env)

    def eval(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            return "".join(v.value if isinstance(v, ast.Constant) else "*" for v in node.values)
        if isinstance(node, ast.Name):
            return self.env.get(node.id)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left, right = self.eval(node.left), self.eval(node.right)
            if left is None or right is None:
                return None
            return posixpath.normpath(posixpath.join(left, right))
        src = ast.unparse(node)
        if "__file__" in src:
            # Path(__file__).resolve().parent.parent and the like.
            path = self.module_rel
            for _ in range(src.count(".parent")):
                path = posixpath.dirname(path) or "."
            return path
        return None

    def assign(self, tree: ast.Module) -> None:
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name):
                value = self.eval(node.value)
                if value is not None:
                    self.env[node.targets[0].id] = value


def _writes_in(tree: ast.AST) -> list[tuple[ast.AST, int]]:
    """(target expression, line) for every write operation under tree."""
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr in WRITE_METHODS:
            out.append((f.value, node.lineno))
        elif isinstance(f, ast.Attribute) and f.attr == "open" and _mode_writes(node, 0):
            out.append((f.value, node.lineno))
        elif isinstance(f, ast.Name) and f.id == "open" and node.args and _mode_writes(node, 1):
            out.append((node.args[0], node.lineno))
    return out


def module_writes(path: Path, common_env: dict[str, str],
                  rel: str | None = None) -> tuple[set[str], list[str]]:
    """(resolved write targets, unresolved write sites) for one module. rel is
    the module's repo-relative path; it defaults to path's place in ROOT."""
    rel = rel or path.relative_to(ROOT).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    res = Resolver(rel, common_env)
    res.assign(tree)

    # Local helpers: functions that write to one of their own parameters.
    helpers: dict[str, int] = {name: 0 for name in SHARED_HELPERS}
    helper_nodes = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        params = [a.arg for a in fn.args.args]
        for target, _ in _writes_in(fn):
            if isinstance(target, ast.Name) and target.id in params:
                helpers[fn.name] = params.index(target.id)
                helper_nodes.add(id(target))

    targets: set[str] = set()
    unresolved: list[str] = []

    def add(expr: ast.AST, line: int) -> None:
        value = res.eval(expr)
        if value is None:
            unresolved.append(f"{rel}:{line}: {ast.unparse(expr)}")
        else:
            targets.add(value)

    for target, line in _writes_in(tree):
        if id(target) not in helper_nodes:
            add(target, line)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in helpers and len(node.args) > helpers[node.func.id]:
            add(node.args[helpers[node.func.id]], node.lineno)
    return targets, unresolved


def common_env() -> dict[str, str]:
    res = Resolver("scripts/common.py", {})
    res.assign(ast.parse((ROOT / "scripts" / "common.py").read_text(encoding="utf-8")))
    return res.env


def _file_entry(files: dict, target: str) -> str | None:
    for pattern in files:
        if target == pattern or fnmatch.fnmatch(target, pattern):
            return pattern
    return None


def audit(config: dict, writes: dict[str, set[str]], unresolved: dict[str, list[str]],
          read_rows=None) -> list[str]:
    findings: list[str] = []
    files = config["files"]
    dynamic = config.get("dynamic", {})

    # Which declared file each module writes.
    found: dict[str, set[str]] = {pattern: set() for pattern in files}
    for module, targets in sorted(writes.items()):
        for target in sorted(targets):
            pattern = _file_entry(files, target)
            if pattern is None:
                findings.append(f"undeclared file: {module} writes {target}")
                continue
            found[pattern].add(module)
            if module not in files[pattern]["writers"]:
                findings.append(f"undeclared writer: {module} writes {pattern}")
    for module, sites in sorted(unresolved.items()):
        declared = dynamic.get(module)
        if not declared:
            findings += [f"unresolved write (declare it under dynamic): {s}" for s in sites]
            continue
        for pattern in declared["files"]:
            found.setdefault(pattern, set()).add(module)

    for pattern, entry in files.items():
        writers = entry["writers"]
        if entry["layer"] == "reference":
            if writers or not entry.get("copied_from"):
                findings.append(f"{pattern}: a reference file has no writer here and names copied_from")
        elif entry.get("hand_edited"):
            if writers or entry["layer"] != "review":
                findings.append(f"{pattern}: a hand-edited file is a review file with no writer")
        elif not writers:
            findings.append(f"{pattern}: no writer declared")
        for module in writers:
            if module not in found.get(pattern, set()):
                findings.append(f"stale declaration: {module} no longer writes {pattern}")
        if len(writers) > 1 and not entry.get("reason"):
            findings.append(f"{pattern}: {len(writers)} writers and no reason")

    layers_by_module: dict[str, set[str]] = {}
    for pattern, entry in files.items():
        for module in entry["writers"]:
            layers_by_module.setdefault(module, set()).add(entry["layer"])
    crossings = config.get("crossings", {})
    for module, layers in sorted(layers_by_module.items()):
        if len(layers) > 1 and module not in crossings:
            findings.append(f"undeclared crossing: {module} writes layers {sorted(layers)}")
    for module in crossings:
        if len(layers_by_module.get(module, ())) < 2:
            findings.append(f"stale crossing: {module} writes one layer")

    read_rows = read_rows or _read_rows
    for pattern, entry in files.items():
        owners = entry.get("row_owner")
        if not owners:
            continue
        column, prefixes = owners["column"], owners["prefixes"]
        if set(prefixes) != set(entry["writers"]):
            findings.append(f"{pattern}: row_owner prefixes must name exactly its writers")
        for i, row in enumerate(read_rows(pattern), start=2):
            value = row.get(column, "")
            hits = [m for m, pre in prefixes.items() if any(value.startswith(p) for p in pre)]
            if len(hits) != 1:
                findings.append(f"{pattern} row {i}: {column}={value!r} matches "
                                f"{len(hits)} writers")
    return findings


def _read_rows(rel: str) -> list[dict]:
    path = ROOT / rel
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def scan() -> tuple[dict[str, set[str]], dict[str, list[str]]]:
    env = common_env()
    writes, unresolved = {}, {}
    for pattern in SCRIPTS:
        for path in sorted(ROOT.glob(pattern)):
            rel = path.relative_to(ROOT).as_posix()
            targets, sites = module_writes(path, env)
            if targets:
                writes[rel] = targets
            if sites:
                unresolved[rel] = sites
    return writes, unresolved


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    exempt = set(config.get("exempt", {}))
    writes, unresolved = scan()
    writes = {m: t for m, t in writes.items() if m not in exempt}
    unresolved = {m: s for m, s in unresolved.items() if m not in exempt}
    findings = audit(config, writes, unresolved)
    shared = sum(1 for e in config["files"].values() if len(e["writers"]) > 1)
    print(f"layer audit: {len(config['files'])} declared files, {len(writes)} writing "
          f"modules, {shared} shared files (declared), {len(findings)} finding(s)")
    for f in findings:
        print(f"  {f}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
