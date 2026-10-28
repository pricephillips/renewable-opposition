"""
variable_core.py

The shared core of the variable registry (spec 033): how a variable manifest
entry is read, how its rows are keyed and filtered, how a state value is
copied onto counties, how a value is transformed or encoded, and how its
quality bounds are checked.

This file is copied byte for byte into renewable-opposition
(scripts/variable_core.py) and pinned in both repositories by
variable_format.lock, so the two pipelines read one manifest format with
their own copies (Price's decision, 2026-10-28: no shared package). Keep it
standard library only, with no repository paths and no import from either
repository. Anything repository-specific (where manifests live, which
features already exist, how the model consumes a column) belongs in that
repository's variable_registry.py.

Changing anything here changes the format: bump the lock in both
repositories in the same week (specs/033-variable-registry/research.md, R2).

Usage
  python variable_core.py --selftest
"""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass, field

FORMAT_VERSION = 1

GRAINS = ("county", "state")
AUDIENCES = ("internal", "client", "public")
SOURCE_TYPES = ("csv_url", "arcgis", "socrata", "pudl", "custom", "none")
UNITS = ("count", "share", "percent", "usd", "mw", "per_sqmi", "index",
         "category", "none")
FORMATS = ("int", "dec1", "dec2", "pct0", "pct1", "usd0", "text")
TRANSFORMS = ("identity", "log1p", "log10")
LEAKAGE_CLASSES = ("none", "neighbor_outcome", "pre_outcome")
REFRESH_DAYS = {"monthly": 30, "quarterly": 91, "annual": 365}

ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,40}$")

# 50 states, D.C. and Puerto Rico, 2-digit FIPS to postal abbreviation.
STATE_FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO",
    "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI",
    "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
    "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY", "72": "PR",
}
STATE_ABBRS = frozenset(STATE_FIPS.values())


class ManifestError(ValueError):
    """An entry that cannot be read at all."""


class DuplicateKeyError(ValueError):
    """A key that repeats after `where` in a manifest entry's file."""


@dataclass
class Column:
    col: str                 # column in the data file
    name: str                # feature name
    label: str
    unit: str = "none"
    format: str = "dec2"
    transform: str = "identity"
    tier: int = 3            # a legacy column keeps its raw value until use
    leakage_class: str = "none"
    levels: list | None = None
    qc: dict = field(default_factory=dict)


@dataclass
class Entry:
    id: str
    file: str
    key: str
    grain: str
    audience: str
    columns: list
    format_version: int = FORMAT_VERSION
    enabled: bool = True
    where: dict = field(default_factory=dict)
    refresh: str | None = None
    source: dict = field(default_factory=dict)
    definition: str = ""
    legacy: bool = False     # read from the older feature_plugins.json
    origin: str = ""         # where the entry was read from, for messages
    notes: list = field(default_factory=list)   # columns skipped while reading


# --------------------------------------------------------------------------
# reading entries
# --------------------------------------------------------------------------

def _column(col: str, meta: dict) -> Column:
    if not isinstance(meta, dict):
        raise ManifestError(f"column {col!r} is not an object")
    levels = meta.get("levels")
    qc = meta.get("qc") or {}
    if not isinstance(qc, dict):
        raise ManifestError(f"column {col!r}: qc is not an object")
    try:
        tier = int(meta.get("tier", 3))
    except (TypeError, ValueError):
        raise ManifestError(f"column {col!r}: tier {meta.get('tier')!r} is not a whole number")
    return Column(
        col=col,
        name=str(meta.get("name", f"plg_{col}")),
        label=str(meta.get("label", col)),
        unit=str(meta.get("unit", "none")),
        format=str(meta.get("format", "dec2")),
        transform=str(meta.get("transform", "identity")),
        tier=tier,
        leakage_class=str(meta.get("leakage_class", "none")),
        levels=[str(x) for x in levels] if isinstance(levels, list) else None,
        qc=dict(qc),
    )


def _legacy_column(col: str, meta: dict) -> Column:
    """A feature_plugins.json column exactly as the old plugin block read it:
    name, label, transform, tier and leakage class as written (no type
    coercion, so the catalog keeps a null label as null), and nothing it
    never read (unit, levels and qc stay at their defaults)."""
    if not isinstance(meta, dict):
        raise ManifestError(f"column {col!r} is not an object")
    return Column(col=col, name=meta.get("name", f"plg_{col}"),
                  label=meta.get("label", col),
                  transform=meta.get("transform", "identity"),
                  tier=meta.get("tier", 3),
                  leakage_class=meta.get("leakage_class", "none"))


def parse_entry(d: dict, origin: str = "") -> Entry:
    """A format-1 manifest entry with its defaults applied. Raises
    ManifestError only when the entry cannot be read; whether it is valid is
    for the schema and the registry's checker to say."""
    if not isinstance(d, dict):
        raise ManifestError(f"{origin}: not a JSON object")
    for k in ("id", "file", "key", "grain", "audience", "columns"):
        if k not in d:
            raise ManifestError(f"{origin}: missing {k!r}")
    cols = d["columns"]
    if not isinstance(cols, dict) or not cols:
        raise ManifestError(f"{origin}: 'columns' must be a non-empty object")
    for k in ("where", "source"):
        if d.get(k) is not None and not isinstance(d.get(k), dict):
            raise ManifestError(f"{origin}: {k!r} must be an object")
    try:
        fv = int(d.get("format_version", FORMAT_VERSION))
    except (TypeError, ValueError):
        raise ManifestError(f"{origin}: format_version must be a whole number")
    return Entry(
        id=str(d["id"]), file=str(d["file"]), key=str(d["key"]),
        grain=str(d["grain"]), audience=str(d["audience"]),
        columns=[_column(c, m) for c, m in cols.items()],
        format_version=fv,
        enabled=bool(d.get("enabled", True)),
        where={str(k): str(v) for k, v in (d.get("where") or {}).items()},
        refresh=d.get("refresh"),
        source=dict(d.get("source") or {}),
        definition=str(d.get("definition", "")),
        origin=origin,
    )


def legacy_id(file: str) -> str:
    """The id a legacy plugin entry is known by: its file's name."""
    base = file.replace("\\", "/").rsplit("/", 1)[-1]
    return base.rsplit(".", 1)[0]


def legacy_entries(cfg: dict, origin: str = "feature_plugins.json") -> list:
    """The enabled entries of the older plugin registry, read as they always
    were: county grain, internal audience, no fetch, no quality bounds. A
    disabled plugin is left out before anything in it is read, as before. A
    plugin or column that cannot be read is skipped with a note in
    entry.notes (or a placeholder entry), never taking the others with it."""
    out = []
    plugins = (cfg or {}).get("plugins", []) if isinstance(cfg, dict) else []
    for i, pl in enumerate(plugins if isinstance(plugins, list) else []):
        where = f"{origin}#plugins[{i}]"
        if isinstance(pl, dict) and not pl.get("enabled", True):
            continue
        if not isinstance(pl, dict) or not isinstance(pl.get("file"), str):
            out.append(Entry(id=f"plugin_{i}", file="", key="fips", grain="county",
                             audience="internal", columns=[], legacy=True, origin=where,
                             notes=[f"{where}: not a plugin with a file, skipped"]))
            continue
        cols, notes = [], []
        raw = pl.get("columns", {}) or {}
        for c, m in (raw.items() if isinstance(raw, dict) else []):
            try:
                cols.append(_legacy_column(c, m))
            except ManifestError as exc:
                notes.append(f"{pl['file']}: {exc}, skipped")
        out.append(Entry(
            id=legacy_id(pl["file"]), file=pl["file"], key=pl.get("key", "fips"),
            grain="county", audience="internal", columns=cols,
            source={"title": str(pl.get("source", ""))} if pl.get("source") else {},
            legacy=True, origin=where, notes=notes,
        ))
    return out


# --------------------------------------------------------------------------
# keys and rows
# --------------------------------------------------------------------------

def norm_key(value, grain: str, legacy: bool = False):
    """A county key as 5-digit FIPS, a state key as its postal abbreviation,
    or None when the value is not one. A legacy plugin keeps its old rule
    exactly (str(value).zfill(5), nothing else), so its output never moves."""
    if legacy:
        return str("" if value is None else value).zfill(5)
    s = str("" if value is None else value).strip()
    if grain == "county":
        if s.endswith(".0"):
            s = s[:-2]
        s = s.zfill(5)
        return s if len(s) == 5 and s.isdigit() else None
    if grain == "state":
        if s.upper() in STATE_ABBRS:
            return s.upper()
        if s.endswith(".0"):
            s = s[:-2]
        if s.isdigit():
            return STATE_FIPS.get(s.zfill(2))
        return None
    raise ManifestError(f"unknown grain {grain!r}")


def select_rows(rows, entry: Entry) -> dict:
    """key -> row for an entry's file rows, after `where`. A legacy entry keeps
    the old rule (the last row with a key wins). A format-1 entry raises
    DuplicateKeyError naming the keys that repeat, and drops rows whose key
    does not parse (the checker reports them)."""
    out = {}
    repeated = set()
    for r in rows:
        if any(str(r.get(c, "")).strip() != v for c, v in entry.where.items()):
            continue
        k = norm_key(r.get(entry.key), entry.grain, legacy=entry.legacy)
        if k is None:
            continue
        if k in out and not entry.legacy:
            repeated.add(k)
        out[k] = r
    if repeated:
        shown = ", ".join(sorted(repeated)[:5])
        raise DuplicateKeyError(f"{len(repeated)} key(s) repeat after 'where': {shown}")
    return out


def unparsed_keys(rows, entry: Entry) -> list:
    """Key values (after `where`) that norm_key cannot read."""
    bad = []
    for r in rows:
        if any(str(r.get(c, "")).strip() != v for c, v in entry.where.items()):
            continue
        if norm_key(r.get(entry.key), entry.grain, legacy=entry.legacy) is None:
            bad.append(str(r.get(entry.key)))
    return bad


def broadcast(state_values: dict, county_states: dict) -> dict:
    """fips -> value for every county whose state has a value. A county whose
    state is missing is left out, never filled."""
    return {f: state_values[s] for f, s in county_states.items() if s in state_values}


# --------------------------------------------------------------------------
# values
# --------------------------------------------------------------------------

def to_number(v):
    """float, or None for blank, text or NaN (county_features.fnum)."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


def apply_transform(x, transform: str):
    """The model transforms, exactly as county_features.py has applied them to
    plugin columns: log1p floors negatives at zero, log10 is blank at or
    below zero, and anything else (identity, or a name it does not know)
    leaves the value as it is. None stays None. The schema refuses an
    unknown transform in a format-1 entry; the checker reports it."""
    if x is None:
        return None
    if transform == "log1p":
        return round(math.log1p(max(float(x or 0), 0.0)), 6)
    if transform == "log10":
        return round(math.log10(x), 6) if x > 0 else None
    return x


def encode_level(value, levels):
    """A category value's position in `levels` (0, 1, 2 ...) as a float, or
    None when blank or not listed."""
    s = str("" if value is None else value).strip()
    if not s or not levels or s not in levels:
        return None
    return float(levels.index(s))


def model_value(raw, column: Column):
    """What the model reads for one raw cell: a category column through its
    levels (None without levels), any other through to_number and the
    column's transform."""
    if column.unit == "category":
        return encode_level(raw, column.levels) if column.levels else None
    return apply_transform(to_number(raw), column.transform)


def effective_tier(tier, grain: str) -> int:
    """A state value has no variation within a state: tier 2 at least.
    Raises ValueError for a tier that is not a whole number."""
    return max(int(tier), 2) if grain == "state" else int(tier)


# --------------------------------------------------------------------------
# quality bounds
# --------------------------------------------------------------------------

def qc_problems(name: str, values: list, qc: dict, grain: str, unit: str = "none",
                levels=None) -> list:
    """One line per bound a column's raw values break. `values` holds one raw
    cell per key (after `where`)."""
    probs = []
    n = len(values)
    if unit == "category":
        if levels:
            bad = sorted({str(v).strip() for v in values
                          if str(v).strip() and str(v).strip() not in levels})
            if bad:
                probs.append(f"{name}: value(s) not in levels: {', '.join(bad[:5])}")
        nums = []
    else:
        nums = [to_number(v) for v in values]
        text = [v for v, x in zip(values, nums, strict=True) if x is None and str(v).strip()]
        if text:
            probs.append(f"{name}: {len(text)} non-numeric value(s), "
                         f"for example {str(text[0])[:30]!r}")
    present = [x for x in nums if x is not None] if unit != "category" else \
        [v for v in values if str(v).strip()]
    if "min" in qc:
        lo = [x for x in nums if x is not None and x < qc["min"]]
        if lo:
            probs.append(f"{name}: {len(lo)} row(s) below min {qc['min']}")
    if "max" in qc:
        hi = [x for x in nums if x is not None and x > qc["max"]]
        if hi:
            probs.append(f"{name}: {len(hi)} row(s) above max {qc['max']}")
    if qc.get("integer"):
        frac = [x for x in nums if x is not None and not float(x).is_integer()]
        if frac:
            probs.append(f"{name}: {len(frac)} row(s) not whole numbers")
    if "max_null_share" in qc and n:
        share = 1 - len(present) / n
        if share > qc["max_null_share"]:
            probs.append(f"{name}: {share:.1%} blank, above max_null_share "
                         f"{qc['max_null_share']}")
    floor_key = "min_counties" if grain == "county" else "min_states"
    if floor_key in qc and len(present) < qc[floor_key]:
        probs.append(f"{name}: {len(present)} with a value, below {floor_key} {qc[floor_key]}")
    return probs


# --------------------------------------------------------------------------
# selftest
# --------------------------------------------------------------------------

def selftest() -> int:
    fails = []

    def check(name, ok):
        print(("PASS " if ok else "FAIL ") + name)
        if not ok:
            fails.append(name)

    e = parse_entry({"id": "demo_var", "file": "data/features/demo.csv", "key": "fips",
                     "grain": "county", "audience": "client",
                     "columns": {"a": {"name": "plg_a", "label": "A", "unit": "share",
                                       "format": "pct0", "qc": {"max": 1}}}})
    check("defaults apply", e.enabled and e.columns[0].transform == "identity"
          and e.columns[0].tier == 3 and e.columns[0].leakage_class == "none")
    try:
        parse_entry({"id": "x"}, "f.json")
        check("a missing field is a ManifestError", False)
    except ManifestError as exc:
        check("a missing field is a ManifestError", "missing" in str(exc))

    leg = legacy_entries({"plugins": [{"file": "data/features/grid_generation.csv",
                                        "key": "fips", "enabled": True, "source": "PUDL",
                                        "columns": {"gen_capacity_mw": {
                                            "name": "plg_gen_capacity", "label": "cap",
                                            "tier": 1, "transform": "log1p",
                                            "leakage_class": "none"}}}]})
    check("a legacy entry reads with county grain, internal audience",
          leg[0].id == "grid_generation" and leg[0].grain == "county"
          and leg[0].audience == "internal" and leg[0].legacy
          and leg[0].columns[0].name == "plg_gen_capacity" and leg[0].columns[0].tier == 1)
    check("a legacy column with no name is plg_<col>",
          legacy_entries({"plugins": [{"file": "f.csv", "columns": {"x": {}}}]})[0]
          .columns[0].name == "plg_x")
    odd = legacy_entries({"plugins": [
        {"file": "off.csv", "enabled": False, "columns": {"a": "oops"}},
        {"file": "a.csv", "columns": {"bad": "oops", "ok": {"label": None, "tier": "x",
                                                           "unit": "category"}}},
        "not a plugin"]})
    check("a disabled plugin is not read at all", [e.file for e in odd] == ["a.csv", ""])
    check("an unreadable legacy column is skipped with a note, the rest kept",
          [c.col for c in odd[0].columns] == ["ok"] and "skipped" in odd[0].notes[0])
    check("a legacy column keeps its raw label and tier and ignores unit",
          odd[0].columns[0].label is None and odd[0].columns[0].tier == "x"
          and odd[0].columns[0].unit == "none")
    check("a plugin that is not an object becomes a noted placeholder",
          odd[1].notes and not odd[1].columns)
    try:
        parse_entry({"id": "x_y", "file": "f", "key": "k", "grain": "county",
                     "audience": "internal", "where": "x", "columns": {"a": {}}})
        check("a where that is not an object is a ManifestError", False)
    except ManifestError:
        check("a where that is not an object is a ManifestError", True)
    try:
        parse_entry({"id": "x_y", "file": "f", "key": "k", "grain": "county",
                     "audience": "internal", "columns": {"a": {"tier": "high"}}})
        check("a tier that is not a number is a ManifestError", False)
    except ManifestError:
        check("a tier that is not a number is a ManifestError", True)

    check("county keys pad and drop .0", norm_key("1001", "county") == "01001"
          and norm_key("19001.0", "county") == "19001" and norm_key(" 19001 ", "county") == "19001")
    check("a bad county key is None", norm_key("abc", "county") is None
          and norm_key("123456", "county") is None)
    check("legacy county keys keep zfill only", norm_key(" 1001", "county", legacy=True) == " 1001".zfill(5))
    check("state keys from abbreviation or FIPS", norm_key("va", "state") == "VA"
          and norm_key("51", "state") == "VA" and norm_key(6, "state") == "CA")
    check("a bad state key is None", norm_key("ZZ", "state") is None
          and norm_key("03", "state") is None)

    st = Entry(id="inv", file="f.csv", key="state", grain="state", audience="internal",
               columns=[Column("status", "st_status", "status", unit="category")],
               where={"kind": "sut"})
    rows = [{"state": "VA", "kind": "sut", "status": "in_force"},
            {"state": "VA", "kind": "property", "status": "none"},
            {"state": "TX", "kind": "sut", "status": "none"}]
    got = select_rows(rows, st)
    check("where keeps only matching rows", set(got) == {"VA", "TX"}
          and got["VA"]["status"] == "in_force")
    st.where = {}
    try:
        select_rows(rows, st)
        check("a key repeating after where raises", False)
    except DuplicateKeyError as exc:
        check("a key repeating after where raises", "VA" in str(exc))
    leg_rows = [{"fips": "19001", "v": "1"}, {"fips": "19001", "v": "2"}]
    lg = Entry(id="l", file="f.csv", key="fips", grain="county", audience="internal",
               columns=[], legacy=True)
    check("a legacy entry keeps last-row-wins", select_rows(leg_rows, lg)["19001"]["v"] == "2")
    check("unparsed keys are listed",
          unparsed_keys([{"state": "ZZ"}, {"state": "VA"}],
                        Entry(id="s", file="f", key="state", grain="state",
                              audience="internal", columns=[])) == ["ZZ"])

    b = broadcast({"VA": 3.0}, {"51001": "VA", "51003": "VA", "48001": "TX"})
    check("broadcast fills the state's counties only", b == {"51001": 3.0, "51003": 3.0})

    check("log1p matches county_features (floors negatives)", apply_transform(-5, "log1p") == 0.0
          and apply_transform(0, "log1p") == 0.0
          and apply_transform(math.e - 1, "log1p") == round(math.log1p(math.e - 1), 6))
    check("log10 is blank at or below zero", apply_transform(0, "log10") is None
          and apply_transform(100, "log10") == 2.0)
    check("an unknown transform leaves the value, as the old plugin block did",
          apply_transform(4.0, "sqrt") == 4.0)
    check("None stays None", apply_transform(None, "log1p") is None)
    check("to_number reads NaN as None", to_number("nan") is None and to_number("") is None
          and to_number("1.5") == 1.5)
    lv = ["none", "partial", "full"]
    check("levels encode by position", encode_level("full", lv) == 2.0
          and encode_level(" none ", lv) == 0.0 and encode_level("other", lv) is None)
    cat = Column("c", "c", "c", unit="category", levels=lv)
    check("model_value encodes a category with levels", model_value("partial", cat) == 1.0)
    check("model_value skips a category without levels",
          model_value("partial", Column("c", "c", "c", unit="category")) is None)
    check("model_value transforms a number",
          model_value("100", Column("n", "n", "n", transform="log10")) == 2.0)
    check("state grain is tier 2 at least", effective_tier(1, "state") == 2
          and effective_tier(3, "state") == 3 and effective_tier(1, "county") == 1)

    q = qc_problems("plg_a", ["0.5", "1.2", "", "x"], {"min": 0, "max": 1,
                                                      "max_null_share": 0.2,
                                                      "min_counties": 3}, "county", "share")
    check("qc names the row above max", any("1 row(s) above max 1" in p for p in q))
    check("qc names non-numeric values", any("non-numeric" in p for p in q))
    check("qc names too many blanks", any("max_null_share" in p for p in q))
    check("qc names too few counties", any("min_counties 3" in p for p in q))
    check("qc is quiet on good data", qc_problems("a", ["0", "1"], {"min": 0, "max": 1},
                                                  "county") == [])
    check("qc flags a category value outside levels",
          qc_problems("c", ["none", "odd"], {}, "state", "category", lv)
          == ["c: value(s) not in levels: odd"])
    check("qc uses min_states for state grain",
          qc_problems("s", ["1"], {"min_states": 2}, "state")
          == ["s: 1 with a value, below min_states 2"])

    print(f"\n{'FAIL' if fails else 'PASS'}: {len(fails)} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(selftest())
    ap.print_help()
