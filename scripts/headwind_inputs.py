"""Plug-in inputs for the Renewable Headwind Model.

config/headwind_inputs.json lists county or state data files the model reads
without a code change. Each entry becomes the variable in_<id> in every
request's county snapshot (scripts/headwind_history.py). A dated file is
time-matched: a request made in year Y reads the latest row from year
Y - lag_years or earlier (lag_years defaults to 1), so nothing from the
request's own year enters. A file with no year column is a static value.

Every configured input is loaded and added to the history, and the model's
report gives each one's lift on its own over the core model
(scripts/headwind_model.py, input_lift). An input reaches the fit only when
the registration (config/headwind_model_registration.json) lists in_<id>
under variables, so adding a data file never changes the model by itself.
Register an input once its lift passes the promotion rule.

The wanted list in the same file is the shared scouts' brief: the inputs the
model lacks. This script only reads it (--wanted prints it).

Usage: python scripts/headwind_inputs.py [--selftest | --check | --wanted]
"""
from __future__ import annotations

import bisect
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, read_csv  # noqa: E402

CONFIG_PATH = ROOT / "config" / "headwind_inputs.json"
INPUT_DIR = ROOT / "data" / "reference" / "headwind_inputs"
REGISTRATION_PATH = ROOT / "config" / "headwind_model_registration.json"
REQUIRED = ("id", "file", "key", "value_column", "label", "source_url", "license", "added", "registry_id")
KEYS = ("county_fips", "state")
TRANSFORMS = ("identity", "log1p")


def config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def name_of(entry: dict) -> str:
    return f"in_{entry['id']}"


def problems(cfg: dict, input_dir: Path = INPUT_DIR) -> list[str]:
    """Every way the config is malformed; an empty list means it is usable."""
    out, seen = [], set()
    for e in cfg.get("inputs", []):
        eid = e.get("id", "?")
        out += [f"{eid}: missing {k}" for k in REQUIRED if not e.get(k)]
        if eid in seen:
            out.append(f"{eid}: duplicate id")
        seen.add(eid)
        if e.get("key") not in KEYS:
            out.append(f"{eid}: key must be one of {KEYS}")
        if e.get("transform", "identity") not in TRANSFORMS:
            out.append(f"{eid}: transform must be one of {TRANSFORMS}")
        if int(e.get("lag_years", 1)) < 1:
            out.append(f"{eid}: lag_years must be 1 or more, so the request's own year never enters")
        f = input_dir / str(e.get("file", ""))
        if ".." in str(e.get("file", "")) or not f.is_file():
            out.append(f"{eid}: file not found under data/reference/headwind_inputs/")
            continue
        rows = read_csv(f)
        cols = set(rows[0]) if rows else set()
        for c in (e.get("key"), e.get("value_column"), e.get("year_column")):
            if c and c not in cols:
                out.append(f"{eid}: column {c} not in {e['file']}")
    for w in cfg.get("wanted", []):
        out += [f"wanted {w.get('id', '?')}: missing {k}" for k in ("id", "need", "why", "grain", "years") if not w.get(k)]
    return out


def registered(reg: dict | None = None) -> set[str]:
    reg = reg if reg is not None else json.loads(REGISTRATION_PATH.read_text(encoding="utf-8"))
    return {k for k in reg.get("variables", {}) if k.startswith("in_")}


def active(cfg: dict | None = None, reg: dict | None = None) -> list[dict]:
    """The inputs the registration lets into the fit, in config order."""
    cfg = cfg if cfg is not None else config()
    names = registered(reg)
    return [e for e in cfg.get("inputs", []) if name_of(e) in names]


def names(cfg: dict | None = None, reg: dict | None = None) -> list[str]:
    return [name_of(e) for e in active(cfg, reg)]


def _num(v) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


class Input:
    """One loaded input: value for a key as of a request year."""

    def __init__(self, entry: dict, rows: list[dict]):
        self.entry, self.lag = entry, int(entry.get("lag_years", 1))
        self.log = entry.get("transform", "identity") == "log1p"
        ycol, key, val = entry.get("year_column"), entry["key"], entry["value_column"]
        by: dict[str, list[tuple[int, float]]] = {}
        for r in rows:
            v = _num(r.get(val))
            k = (r.get(key) or "").strip()
            if v is None or not k:
                continue
            if key == "county_fips":
                k = k.zfill(5)
            y = _num(r.get(ycol)) if ycol else -10**6
            if y is None:
                continue
            by.setdefault(k, []).append((int(y), v))
        self.series = {k: sorted(v) for k, v in by.items()}
        self.years = {k: [y for y, _ in v] for k, v in self.series.items()}

    def value(self, fips: str, state: str, year: int) -> float | None:
        k = fips if self.entry["key"] == "county_fips" else state
        s = self.series.get(k)
        if not s:
            return None
        i = bisect.bisect_right(self.years[k], year - self.lag) - 1
        if i < 0:
            return None
        v = s[i][1]
        return math.log1p(max(v, 0.0)) if self.log else v


def load(cfg: dict | None = None, reg: dict | None = None, input_dir: Path = INPUT_DIR,
         every: bool = False) -> dict[str, Input]:
    """The registered inputs, or with every=True all configured ones (the
    history carries them all so the report can measure each one's lift)."""
    cfg = cfg if cfg is not None else config()
    entries = cfg.get("inputs", []) if every else active(cfg, reg)
    return {name_of(e): Input(e, read_csv(input_dir / e["file"])) for e in entries}


def configured(cfg: dict | None = None) -> list[str]:
    cfg = cfg if cfg is not None else config()
    return [name_of(e) for e in cfg.get("inputs", [])]


def apply(rows: list[dict], loaded: dict[str, Input]) -> list[dict]:
    """Add each loaded input to each row, as of the row's year."""
    for r in rows:
        for name, inp in loaded.items():
            v = inp.value(r["county_fips"], r.get("state", ""), int(r["year"]))
            r[name] = "" if v is None else round(v, 4)
    return rows


# ── Self-test ───────────────────────────────────────────────────────────────

def _selftest() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        with tempfile.NamedTemporaryFile("w", suffix=".csv", dir=d, delete=False, encoding="utf-8") as fh:
            fh.write("county_fips,year,farm_share\n1001,2007,0.5\n01001,2012,0.4\n01001,2017,0.3\n02001,2012,x\n")
        entry = {"id": "demo", "file": Path(fh.name).name, "key": "county_fips", "year_column": "year",
                 "value_column": "farm_share", "label": "farm share", "source_url": "https://example.org",
                 "license": "public domain", "added": "2026-11-20", "registry_id": "demo"}
        cfg = {"inputs": [entry], "wanted": []}
        assert problems(cfg, root) == [], problems(cfg, root)
        bad = {"inputs": [dict(entry, lag_years=0, key="zip"), dict(entry)], "wanted": [{"id": "w"}]}
        p = problems(bad, root)
        assert any("lag_years" in x for x in p) and any("key must" in x for x in p)
        assert any("duplicate" in x for x in p) and any("wanted w" in x for x in p), p
        reg = {"variables": {"in_demo": "demo"}}
        assert names(cfg, {"variables": {}}) == [], "an unregistered input stays out of the fit"
        assert list(load(cfg, {"variables": {}}, root, every=True)) == ["in_demo"], "but is loaded for its lift"
        loaded = load(cfg, reg, root)
        inp = loaded["in_demo"]
        assert inp.value("01001", "AL", 2012) == 0.5, "the request's own year never enters"
        assert inp.value("01001", "AL", 2013) == 0.4
        assert inp.value("01001", "AL", 2030) == 0.3
        assert inp.value("01001", "AL", 2007) is None, "nothing before the first row"
        assert inp.value("02001", "AK", 2020) is None, "a non-numeric value is skipped"
        rows = apply([{"county_fips": "01001", "state": "AL", "year": "2018"}], loaded)
        assert rows[0]["in_demo"] == 0.3
        st = Input(dict(entry, key="state", year_column=None, transform="log1p"),
                   [{"state": "AL", "farm_share": "9"}])
        assert abs(st.value("01001", "AL", 2010) - math.log1p(9)) < 1e-9, "a static state value"
    cfg = config()
    assert problems(cfg) == [], problems(cfg)
    print("headwind_inputs selftest: ok")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()
    cfg = config()
    if "--wanted" in sys.argv:
        for w in cfg.get("wanted", []):
            print(f"- {w['id']}: {w['need']} ({w['grain']}; {w['years']})")
        return 0
    p = problems(cfg)
    for line in p:
        print(f"headwind_inputs: {line}")
    on = names(cfg)
    print(f"headwind_inputs: {len(cfg.get('inputs', []))} inputs configured, {len(on)} registered for the fit, "
          f"{len(cfg.get('wanted', []))} wanted")
    return 1 if p else 0


if __name__ == "__main__":
    sys.exit(main())
