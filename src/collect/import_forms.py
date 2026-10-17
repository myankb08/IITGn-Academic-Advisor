"""Anonymise the Google Form CSV export and fill the consent register.

Real run:    .venv/bin/python -m src.collect.import_forms
Fixture run: .venv/bin/python -m src.collect.import_forms --fixture
The raw CSV is only read. Timestamps and any email column are dropped, rows are reordered by a
content hash so ids do not follow submission order, then ids R001.. are assigned.
"""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORM_VERSION = "v1"
CONSENT_VERSION = "v1"
# exact question titles from docs/GOOGLE_FORM.md -> output field
FIELDS = {
    "Consent": "consent",
    "Programme": "programme",
    "Stream": "stream",
    "Track": "track",
    "Current semester": "semester",
    "Courses completed so far": "courses_completed",
    "Your question for an academic advisor": "question",
    "What kind of question is this?": "question_kind",
}
DROP = {"timestamp", "email address", "email", "username"}
CONSENT_YES = "I agree"
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\s-]?){10,13}(?!\d)")
FREE_TEXT = ["courses_completed", "question"]


def redact(text, counts):
    text, n1 = EMAIL_RE.subn("[email removed]", text)
    text, n2 = PHONE_RE.subn("[phone removed]", text)
    counts["emails_redacted"] += n1
    counts["phones_redacted"] += n2
    return text


def map_header(header):
    """Map CSV columns to fields, by exact title first, then by case-insensitive prefix."""
    mapping, unknown = {}, []
    for col in header:
        key = col.strip()
        if key.lower() in DROP:
            continue
        hit = FIELDS.get(key) or next((v for k, v in FIELDS.items() if key.lower().startswith(k.lower())), None)
        if hit:
            mapping[col] = hit
        else:
            unknown.append(col)
    return mapping, unknown


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true", help="read tests/fixtures, write under supporting_files")
    args = ap.parse_args()
    if args.fixture:
        src = ROOT / "tests/fixtures/fixture_forms_responses_raw.csv"
        out_dir = ROOT / "supporting_files/C_labelling/fixture_forms"
        out_jsonl, out_register = out_dir / "responses_anonymised.jsonl", out_dir / "consent_register.csv"
        log_path = out_dir / "import_log.json"
    else:
        src = ROOT / "data/raw/forms/responses_raw.csv"
        out_jsonl = ROOT / "data/raw/forms/responses_anonymised.jsonl"
        out_register = ROOT / "data/consent_register.csv"
        log_path = ROOT / "supporting_files/C_labelling/forms_import_log.json"
    if not src.exists():
        raise SystemExit(f"{src.relative_to(ROOT)} not found")
    with open(src, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        mapping, unknown = map_header(reader.fieldnames or [])
        rows = [{field: (r.get(col) or "").strip() for col, field in mapping.items()} for r in reader]
    missing = sorted(set(FIELDS.values()) - set(mapping.values()))
    if missing:
        raise SystemExit(f"CSV lacks columns for {missing}; check titles against docs/GOOGLE_FORM.md")
    counts = {"emails_redacted": 0, "phones_redacted": 0}
    for r in rows:
        for k in FREE_TEXT:
            r[k] = redact(r[k], counts)
    rows.sort(key=lambda r: hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest())
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    out_register.parent.mkdir(parents=True, exist_ok=True)
    kept = 0
    with open(out_jsonl, "w", encoding="utf-8") as fj, open(out_register, "w", newline="", encoding="utf-8") as fr:
        reg = csv.writer(fr)
        reg.writerow(["response_id", "consent_given", "consent_statement_version", "form_version", "included_in_dataset", "reason"])
        for i, r in enumerate(rows, start=1):
            rid = f"R{i:03d}"
            consent = r["consent"].lower().startswith(CONSENT_YES.lower())
            usable = consent and bool(r["question"])
            reason = "" if usable else ("no consent" if not consent else "empty question")
            reg.writerow([rid, "yes" if consent else "no", CONSENT_VERSION, FORM_VERSION, "yes" if usable else "no", reason])
            if not usable:
                continue
            rec = {"response_id": rid, "form_version": FORM_VERSION, **{k: v for k, v in r.items() if k != "consent"}}
            fj.write(json.dumps(rec, ensure_ascii=False) + "\n")
            kept += 1
    log = {"source": str(src.relative_to(ROOT)), "rows_read": len(rows), "rows_kept": kept,
           "rows_excluded": len(rows) - kept, "dropped_columns": sorted(c for c in (reader.fieldnames or []) if c.strip().lower() in DROP),
           "unmapped_columns": unknown, **counts}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
