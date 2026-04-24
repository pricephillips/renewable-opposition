from __future__ import annotations
import csv, json
from pathlib import Path

ROOT = Path('.')
SEED = ROOT / 'data' / 'seed'
PROCESSED = ROOT / 'data' / 'processed'
PROCESSED.mkdir(parents=True, exist_ok=True)

FILES = {
    'restrictions_seed.csv': 'restrictions.json',
    'contested_projects_seed.csv': 'contested_projects.json',
    'cases_seed.csv': 'cases.json',
}

REQUIRED = {
    'restrictions_seed.csv': ['state','technology','restriction_type','severity_score','description'],
    'contested_projects_seed.csv': ['state','project_name','technology','severity_score','description'],
    'cases_seed.csv': ['state','project_name','technology','court_level','severity_score','description'],
}

INT_FIELDS = {'severity_score'}


def clean(v: str):
    v = (v or '').strip()
    return v if v else None


def normalize_row(row: dict[str, str]) -> dict:
    out = {}
    for k, v in row.items():
        key = k.strip()
        val = clean(v)
        if key in INT_FIELDS and val is not None:
            try:
                val = int(val)
            except ValueError:
                pass
        out[key] = val
    return out


def validate(rows: list[dict], required: list[str], filename: str):
    errors = []
    for i, row in enumerate(rows, start=2):
        missing = [f for f in required if row.get(f) in (None, '')]
        if missing:
            errors.append(f'{filename}: row {i} missing required fields: {", ".join(missing)}')
    if errors:
        raise SystemExit('\n'.join(errors))


def convert(seed_name: str, out_name: str):
    src = SEED / seed_name
    dst = PROCESSED / out_name
    if not src.exists():
        print(f'Skipping missing {src}')
        return
    with src.open(newline='', encoding='utf-8-sig') as f:
        rows = [normalize_row(r) for r in csv.DictReader(f)]
    validate(rows, REQUIRED[seed_name], seed_name)
    with dst.open('w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f'Wrote {dst} ({len(rows)} records)')


if __name__ == '__main__':
    for seed_name, out_name in FILES.items():
        convert(seed_name, out_name)
