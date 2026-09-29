#!/bin/bash
# SessionStart hook: tools every session on this repo expects. Adapted from
# pricephillips/data-center-map .claude/hooks/session-start.sh
# (docs/PASSOFF_2026-09-29_tooling_from_data_center_map.md, A9).
#
# Everywhere (cloud and local): ast-grep and the DuckDB CLI. Installed only
# when missing, through uv, and never fatal: a machine without uv gets a
# notice, not a failed start.
#
# Cloud sessions only: the Python packages at the versions pinned in
# requirements/ci.txt, plus the checkers, so pre-commit, pytest, ruff, Vale,
# actionlint and zizmor run the same way CI does. Playwright's Chromium is
# already in the image at /opt/pw-browsers: never run `playwright install`;
# run the smoke test with SMOKE_CHROMIUM pointing at that binary. Local
# machines are left alone; see .pre-commit-config.yaml for local setup.
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 0
export PATH="$HOME/.local/bin:$PATH"

have() { command -v "$1" >/dev/null 2>&1; }

tool() {  # tool <command> <uv package>
  have "$1" && return 0
  if have uv; then
    uv tool install -q "$2" >/dev/null 2>&1 || echo "session-start: could not install $2" >&2
  else
    echo "session-start: $1 missing and uv not found; install $2 by hand" >&2
  fi
}

tool ast-grep ast-grep-cli
tool duckdb duckdb-cli

if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ] && have uv; then
  uv pip install --system -q -c requirements/ci.txt -r requirements.txt \
    pytest ruff daff vale >/dev/null 2>&1 \
    || echo "session-start: python package install failed" >&2
  tool pre-commit pre-commit
  tool actionlint actionlint-py
  tool shellcheck shellcheck-py
  tool zizmor zizmor
fi

exit 0
