#!/usr/bin/env bash
# Unzip a submission into a temp folder and run the README rebuild commands inside code/.
#
#   scripts/check_submission.sh path/to/CS203_A1_Project4_25210087_25210122.zip
#
# Needs python3.10 and network access for pip. Leaves the temp folder for inspection and prints its path.
set -euo pipefail

ZIP="$(cd "$(dirname "${1:?usage: check_submission.sh path/to/submission.zip}")" && pwd)/$(basename "$1")"
NAME="CS203_A1_Project4_25210087_25210122"
TMP="$(mktemp -d)"
echo "checking in $TMP"
unzip -q "$ZIP" -d "$TMP"
cd "$TMP/$NAME"
for p in code/.git code/dvc.yaml code/dvc.lock code/README.md data supporting_files report/report.pdf dvc_remote; do
  [ -e "$p" ] || { echo "missing $p" >&2; exit 1; }
done

cd code
# README "Rebuild the data", with two checks in between: the pulled data must match the data/ copy,
# and dvc repro must leave the pipeline up to date (checked before pytest, which writes test outputs).
python3.10 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
.venv/bin/dvc pull
diff -rq ../data data -x '.gitignore' -x '*.dvc' && echo "data/ matches the pulled data"
.venv/bin/dvc repro
.venv/bin/dvc status | tee "$TMP/dvc_status.txt"
grep -q "up to date" "$TMP/dvc_status.txt" || { echo "dvc status is not clean" >&2; exit 1; }
.venv/bin/pytest -q
echo "submission check passed: $TMP"
