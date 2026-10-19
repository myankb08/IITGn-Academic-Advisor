#!/usr/bin/env bash
# Force a full rerun of every DVC stage and check the outputs are byte-identical to before.
# Writes supporting_files/F_reproducibility/repro_check.txt. Run from anywhere: scripts/repro_check.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT=supporting_files/F_reproducibility/repro_check.txt
FILES=(data/processed/courses.json data/processed/rules.json data/processed/students.jsonl
       data/processed/queries.jsonl data/processed/queries_para.jsonl data/processed/queries_augmented.jsonl
       data/splits/train.csv data/splits/val.csv data/splits/test.csv data/splits/programme_holdout.csv
       data/splits/shifted_forms.csv data/labels/audited.jsonl data/gold/gold_test.jsonl
       data/interim/base_model_answers.jsonl data/raw/forms/responses_anonymised.jsonl)
before=$(mktemp); meta_before=$(mktemp)
sha256sum "${FILES[@]}" > "$before"
cp data/metadata.csv "$meta_before"
.venv/bin/dvc repro --force --quiet
{
  echo "# Reproducibility check at commit $(git rev-parse --short HEAD), $(date '+%Y-%m-%d %H:%M %Z')"
  echo "# sha256 of key outputs recorded, then 'dvc repro --force' (every stage rerun), then sha256sum -c"
  echo
  sha256sum -c "$before" 2>&1 || true
  echo
  .venv/bin/python - "$meta_before" <<'EOF'
import csv, sys
strip = lambda p: [{k: v for k, v in r.items() if k != "collected_at_utc"} for r in csv.DictReader(open(p))]
a, b = strip(sys.argv[1]), strip("data/metadata.csv")
print(f"data/metadata.csv: {len(b)} rows; identical apart from collected_at_utc (run time): {a == b}")
EOF
  echo
  echo "# dvc status after the run:"
  .venv/bin/dvc status 2>&1 | grep -v WARNING
} > "$OUT"
rm -f "$before" "$meta_before"
cat "$OUT"
