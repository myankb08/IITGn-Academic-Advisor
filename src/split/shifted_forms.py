"""Write the shifted evaluation split from the real Google Forms queries.

    .venv/bin/python -m src.split.shifted_forms

Reads data/raw/forms/responses_anonymised.jsonl (consenting rows only, made by src.collect.import_forms)
and writes data/splits/shifted_forms.csv with the manifest columns plus question_kind and form_version.
These are real student questions without a template, so template_family is "real_form" and template_id is empty.
If the forms file is absent the stage stops with a message and writes nothing.
"""
import csv
import json
from collections import Counter

from src.split.make_splits import COLUMNS, EVIDENCE, FORMS, ROOT, SPLITS, read_jsonl


def main():
    if not FORMS.exists():
        raise SystemExit(f"pending: {FORMS.relative_to(ROOT)} not present; run src.collect.import_forms "
                         "after data/raw/forms/responses_raw.csv is added")
    rows = read_jsonl(FORMS)
    SPLITS.mkdir(parents=True, exist_ok=True)
    out = SPLITS / "shifted_forms.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS + ["question_kind", "form_version"])
        w.writeheader()
        for r in sorted(rows, key=lambda r: r["response_id"]):
            w.writerow({"query_id": r["response_id"], "student_id": "", "template_family": "real_form",
                        "template_id": "", "programme": r.get("programme"), "split": "shifted",
                        "question_kind": r.get("question_kind"), "form_version": r.get("form_version")})
    summary = {"n_rows": len(rows),
               "by_programme": dict(sorted(Counter(str(r.get("programme")) for r in rows).items())),
               "by_question_kind": dict(sorted(Counter(str(r.get("question_kind")) for r in rows).items()))}
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with open(EVIDENCE / "shifted_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print(f"shifted_forms: {len(rows)} rows -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
