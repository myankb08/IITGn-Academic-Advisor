#!/usr/bin/env bash
# Assemble CS203_A1_Project4_25210087_25210122/ and zip it.
#
#   scripts/make_submission.sh [output_parent_dir]     (default: the folder that holds the repo)
#
# Layout:
#   code/              git clone of the repo at tag a1-final (with .git, origin set to GitHub)
#   data/              data/ at that tag, pulled from the DVC remote
#   dvc_remote/        copy of the DVC remote, so `dvc pull` inside code/ works offline (code/../dvc_remote)
#   supporting_files/  supporting_files/ at that tag
#   report/report.pdf  from $REPORT (default reports/report.pdf)
# Needs: the tag pushed to the local repo, `dvc push` done, the report PDF present.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="CS203_A1_Project4_25210087_25210122"
TAG="${TAG:-a1-final}"
REPORT="${REPORT:-$REPO/reports/report.pdf}"
GITHUB_URL="https://github.com/hem436/CS203_Project.git"
OUT_PARENT="$(cd "${1:-$REPO/..}" && pwd)"
OUT="$OUT_PARENT/$NAME"
REMOTE="$REPO/../dvc_remote"
DVC="$REPO/.venv/bin/dvc"

[ -e "$OUT" ] && { echo "$OUT already exists, remove it first" >&2; exit 1; }
[ -e "$OUT.zip" ] && { echo "$OUT.zip already exists, remove it first" >&2; exit 1; }
[ -f "$REPORT" ] || { echo "report not found: $REPORT" >&2; exit 1; }
[ -d "$REMOTE" ] || { echo "DVC remote not found: $REMOTE (run dvc push first)" >&2; exit 1; }
git -C "$REPO" rev-parse -q --verify "refs/tags/$TAG" >/dev/null || { echo "tag $TAG not found" >&2; exit 1; }

mkdir -p "$OUT/report"
git clone --quiet --branch "$TAG" "$REPO" "$OUT/code"
git -C "$OUT/code" remote set-url origin "$GITHUB_URL"
cp -r "$REMOTE" "$OUT/dvc_remote"

# Pull the data of this tag from the copied remote, copy it out, then return code/ to a clean clone.
(cd "$OUT/code" && "$DVC" pull --quiet)
cp -r "$OUT/code/data" "$OUT/data"
cp -r "$OUT/code/supporting_files" "$OUT/supporting_files"
git -C "$OUT/code" clean -fdqX
cp "$REPORT" "$OUT/report/report.pdf"

(cd "$OUT_PARENT" && zip -qr "$NAME.zip" "$NAME")
echo "wrote $OUT and $OUT.zip ($(du -sh "$OUT.zip" | cut -f1))"
