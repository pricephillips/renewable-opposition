#!/usr/bin/env python3
"""
precommit_gates.py

Local gates called by the system hooks in .pre-commit-config.yaml. Adapted
from pricephillips/data-center-map scripts/precommit_gates.py
(docs/PASSOFF_2026-09-29_tooling_from_data_center_map.md, A5); copied, not
imported. Each subcommand takes the staged file list from pre-commit and
exits 1 on any finding.

  crlf [--fix] FILE...   A CSV may not introduce CR bytes. Every tracked CSV
                         is LF since the A5b renormalization and every writer
                         passes lineterminator="\\n", so this is a regression
                         guard. A file whose committed (HEAD) version already
                         has CR is left alone; a new CSV must be LF. --fix
                         rewrites the offenders and still exits 1.
  emdash FILE...         U+2014 in deliverables (the four pages, README.md,
                         docs/coverage_audit.md and content/*.md),
                         reported as path:line. Record text in the CSVs is
                         quoted from its source and is out of scope (A6).
  nodecheck FILE...      node --check on .js files and on inline <script>
                         blocks of .html files (scripts/check_inline_js.py).
  private FILE...        Refuses any staged file whose name starts with
                         "local_knowledge": reports from local contacts
                         live outside this public repository
                         ($RO_LOCAL_KNOWLEDGE, see scripts/site_profile.py).
                         .gitignore keeps them out of `git add`; this
                         catches a forced add or a renamed copy.
  tests FILE...          The whole pytest suite, plus --selftest on each
                         touched module that has one. The suite is small
                         enough to run whole on any Python change.

Usage
  python scripts/precommit_gates.py <subcommand> [args]
  python scripts/precommit_gates.py --selftest
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

EMDASH = "—"
# Name prefix of files that must never be committed (private local reports).
PRIVATE_PREFIX = "local_" + "knowledge"

SELFTEST_RE = re.compile(
    r"""add_argument\(\s*["']--selftest|["']--selftest["']\s*(?:in|==)""")


def _rel(path: str) -> str:
    return os.path.relpath(os.path.abspath(path), ROOT).replace(os.sep, "/")


def head_has_cr(rel: str) -> bool:
    """True if the committed version of rel contains CR. A file absent from
    HEAD (new) has no baseline, so it must be LF."""
    r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT,
                       capture_output=True)
    return r.returncode == 0 and b"\r" in r.stdout


def crlf(files: list[str], fix: bool, baseline=head_has_cr) -> int:
    bad = 0
    for f in files:
        rel = _rel(f)
        if not rel.endswith(".csv"):
            continue
        with open(f, "rb") as fh:
            data = fh.read()
        if b"\r" not in data or baseline(rel):
            continue
        bad += 1
        if fix:
            with open(f, "wb") as fh:
                fh.write(data.replace(b"\r\n", b"\n"))
            print(f"fixed CRLF -> LF: {rel}")
        else:
            print(f"{rel}: CRLF line endings")
    return 1 if bad else 0


def emdash(files: list[str]) -> int:
    bad = 0
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh, 1):
                if EMDASH in line:
                    print(f"{_rel(f)}:{i}: em-dash")
                    bad += 1
    return 1 if bad else 0


def private(files: list[str]) -> int:
    bad = [f for f in files if os.path.basename(f).lower().startswith(PRIVATE_PREFIX)]
    for f in bad:
        print(f"{_rel(f)}: local-knowledge files hold reports from local contacts and are never "
              "committed; keep it at $RO_LOCAL_KNOWLEDGE outside the repository and unstage it")
    return 1 if bad else 0


def nodecheck(files: list[str]) -> int:
    import check_inline_js as cij
    bad = 0
    for f in files:
        with open(f, encoding="utf-8") as fh:
            src = fh.read()
        if f.endswith(".html"):
            blocks = cij.inline_blocks(src)
        elif f.endswith(".js"):
            blocks = [(1, src)]
        else:
            continue
        for line, block in blocks:
            ok, err = cij.node_check(block)
            if not ok:
                print(f"{_rel(f)}:{line}: {err.strip().splitlines()[-1] if err.strip() else 'syntax error'}")
                bad += 1
    return 1 if bad else 0


def has_selftest(path: str) -> bool:
    try:
        with open(path, encoding="utf-8") as fh:
            return bool(SELFTEST_RE.search(fh.read()))
    except OSError:
        return False


def selftest_files(files: list[str]) -> int:
    bad = 0
    for f in files:
        if not f.endswith(".py") or not has_selftest(f):
            continue
        r = subprocess.run([sys.executable, f, "--selftest"], cwd=ROOT,
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            bad += 1
            tail = (r.stdout + r.stderr).strip().splitlines()[-20:]
            print(f"FAIL selftest: {_rel(f)}\n  " + "\n  ".join(tail))
    return 1 if bad else 0


def tests(files: list[str]) -> int:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT,
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print("FAIL pytest\n  " + "\n  ".join(
            (r.stdout + r.stderr).strip().splitlines()[-30:]))
    # This module's own selftest is included: it runs in a few seconds.
    selftests_failed = selftest_files(files)
    return 1 if r.returncode != 0 or selftests_failed else 0


def selftest() -> int:
    checks: list[tuple[str, bool]] = []

    def check(name: str, ok: bool) -> None:
        checks.append((name, bool(ok)))

    import contextlib
    import io
    td = tempfile.mkdtemp()

    def w(name: str, data: bytes) -> str:
        p = os.path.join(td, name)
        with open(p, "wb") as fh:
            fh.write(data)
        return p

    quiet = contextlib.redirect_stdout(io.StringIO())
    crlf_csv = w("hand.csv", b"a,b\r\n1,2\r\n")
    lf_csv = w("clean.csv", b"a,b\n1,2\n")
    gen_csv = w("gen.csv", b"a,b\r\n")
    lf_base = lambda rel: False  # noqa: E731
    cr_base = lambda rel: True  # noqa: E731
    with quiet:
        check("a CSV introducing CRLF is reported", crlf([crlf_csv], False, lf_base) == 1)
        check("LF csv is clean", crlf([lf_csv], False, lf_base) == 0)
        check("a CSV already CRLF in HEAD is left alone", crlf([gen_csv], False, cr_base) == 0)
        check("--fix rewrites and still exits 1", crlf([crlf_csv], True, lf_base) == 1)
    with open(crlf_csv, "rb") as fh:
        check("--fix leaves LF only", fh.read() == b"a,b\n1,2\n")

    md = w("deliv.md", ("ok\nhas " + EMDASH + " here\n").encode())
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = emdash([md])
    check("em-dash exits 1 with its line number", rc == 1 and ":2: em-dash" in buf.getvalue())
    with quiet:
        check("clean markdown passes emdash", emdash([w("ok.md", b"plain, text\n")]) == 0)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = private([os.path.join("data", "review", PRIVATE_PREFIX + ".csv"), "data/review/queue.csv"])
    check("a staged local-knowledge file is refused", rc == 1 and "never committed" in buf.getvalue())
    with quiet:
        check("a renamed copy is refused too", private([PRIVATE_PREFIX + "_backup.xlsx"]) == 1)
        check("other files pass the private gate", private(["data/review/queue.csv", "README.md"]) == 0)

    good_html = w("good.html", b"<script>var a = 1;</script>\n")
    bad_html = w("bad.html", b"<p>x</p>\n<script>function ( {</script>\n")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        check("valid inline script passes nodecheck", nodecheck([good_html]) == 0)
        check("broken inline script fails nodecheck", nodecheck([bad_html]) == 1)
    check("nodecheck reports the block's line", "bad.html:2:" in buf.getvalue())

    nost = w("plain.py", b"print('no selftest here')\n")
    good = w("good.py", b"import sys\nif '--selftest' in sys.argv: sys.exit(0)\n")
    badp = w("bad.py", b"import sys\nif '--selftest' in sys.argv: sys.exit(1)\n")
    with quiet:
        check("a module without a selftest is skipped", selftest_files([nost]) == 0)
        check("a passing selftest passes", selftest_files([good]) == 0)
        check("a failing selftest fails", selftest_files([badp]) == 1)

    failed = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {n}")
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--selftest"]:
        return selftest()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_crlf = sub.add_parser("crlf")
    p_crlf.add_argument("--fix", action="store_true")
    p_crlf.add_argument("files", nargs="*")
    for name in ("emdash", "private", "nodecheck", "tests"):
        sub.add_parser(name).add_argument("files", nargs="*")
    args = ap.parse_args(argv)
    if args.cmd == "crlf":
        return crlf(args.files, args.fix)
    if args.cmd == "emdash":
        return emdash(args.files)
    if args.cmd == "private":
        return private(args.files)
    if args.cmd == "nodecheck":
        return nodecheck(args.files)
    return tests(args.files)


if __name__ == "__main__":
    sys.exit(main())
