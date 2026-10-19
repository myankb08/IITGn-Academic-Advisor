#!/usr/bin/env bash
# Build reports/report.pdf (pdflatex twice for references).
set -euo pipefail
cd "$(dirname "$0")"
for i in 1 2; do
  pdflatex -interaction=nonstopmode -halt-on-error report.tex > /dev/null || { tail -n 30 report.log; exit 1; }
done
echo "built $(pwd)/report.pdf"
