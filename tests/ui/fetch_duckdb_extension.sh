#!/usr/bin/env bash
# Fetch the one DuckDB-WASM extension the SQL console loads at run time
# (Parquet), pinned by version and SHA-256, into tests/ui/.cache/ so the
# offline UI tests can serve it (fixtures.js maps extensions.duckdb.org
# there). Browsers in production fetch it from extensions.duckdb.org, which
# sends access-control-allow-origin: *. The version follows the DuckDB core
# inside @duckdb/duckdb-wasm in package.json (1.29.0 ships DuckDB v1.1.1).
set -euo pipefail
cd "$(dirname "$0")"
PATH_IN_REPO="v1.1.1/wasm_eh/parquet.duckdb_extension.wasm"
SHA256="e24fb2953c6a80e32d17fa3921f90f1f05ccbfa40f382e77702c1e6af9b79479"
OUT=".cache/duckdb-extensions/$PATH_IN_REPO"
if [ -f "$OUT" ] && echo "$SHA256  $OUT" | sha256sum -c --quiet - 2>/dev/null; then
  exit 0
fi
mkdir -p "$(dirname "$OUT")"
curl -sSfL -o "$OUT.part" "https://extensions.duckdb.org/$PATH_IN_REPO"
echo "$SHA256  $OUT.part" | sha256sum -c --quiet -
mv "$OUT.part" "$OUT"
echo "fetched $OUT"
