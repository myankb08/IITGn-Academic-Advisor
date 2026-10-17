#!/usr/bin/env bash
# Run one stage of the LLM steps on a Kaggle T4 and merge the results into the local cache.
#   STAGE=smoke  10 rows end to end, merged into data/interim/kaggle_smoke_cache.jsonl
#   STAGE=test   paraphrases for the test split
#   STAGE=rest   all other paraphrases, base-model answers (train pool), augmentation paraphrases
# COLLECT_ONLY=1 skips building and pushing and only waits for, downloads and merges a pushed kernel.
# MACHINE=NvidiaTeslaP100 overrides the GPU type in kernel-metadata.json.
# Token: read from the repo-root file .secrets into the environment only. Never echo it.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
STAGE="${STAGE:-smoke}"
KAGGLE=.venv/bin/kaggle
PY=.venv/bin/python

[ -f "$ROOT/.secrets" ] || { echo "no .secrets file, stopping"; exit 1; }
export KAGGLE_API_TOKEN="$(cat "$ROOT/.secrets")" KAGGLE_USERNAME=hemant436 KAGGLE_KEY=unused
DATASET="$KAGGLE_USERNAME/course-advisory-llm-inputs"
KERNEL="$KAGGLE_USERNAME/course-advisory-llm-$STAGE"
BUILD=data/interim/kaggle_build/$STAGE
OUT=data/interim/kaggle_out/$STAGE
if [ "$STAGE" = smoke ]; then CACHE=data/interim/kaggle_smoke_cache.jsonl; else CACHE=data/interim/llm_cache.jsonl; fi

case "$STAGE" in
  smoke) STEPS='[["paraphrase","src.queries.paraphrase_llm","--limit","10","--write-every","5"],
                 ["base_model_answers","src.active.base_model_answers","--limit","10"],
                 ["augment_paraphrase","src.augment.paraphrase","--per-intent","1"]]' ;;
  test)  STEPS='[["paraphrase","src.queries.paraphrase_llm","--only-splits","test","--write-every","20"]]' ;;
  rest)  STEPS='[["timing_check","src.queries.paraphrase_llm","--only-splits","train","--limit","16","--write-every","16","--also-backends","llamacpp"],
                 ["paraphrase","src.queries.paraphrase_llm","--write-every","64","--also-backends","llamacpp"],
                 ["base_model_answers","src.active.base_model_answers"],
                 ["augment_paraphrase","src.augment.paraphrase"]]' ;;
  *) echo "unknown STAGE $STAGE"; exit 1 ;;
esac

if [ "${COLLECT_ONLY:-0}" != 1 ]; then
rm -rf "$BUILD" && mkdir -p "$BUILD/dataset" "$BUILD/kernel" "$BUILD/extra/data/interim"
echo "{\"stage\": \"$STAGE\", \"env\": {\"LLM_BATCH\": \"${LLM_BATCH:-16}\"}, \"steps\": $STEPS}" > "$BUILD/extra/run_config.json"
# the local cache rides along so finished calls (Kaggle or local llama.cpp) are not repeated (not for smoke)
if [ "$STAGE" != smoke ] && [ -f data/interim/llm_cache.jsonl ]; then
  cp data/interim/llm_cache.jsonl "$BUILD/extra/data/interim/llm_cache.jsonl"
fi
FILES=(params.yaml data/processed/queries.jsonl data/processed/students.jsonl data/processed/courses.json
       data/processed/rules.json prompts/pipeline src/__init__.py src/engine src/queries src/augment src/active)
for f in data/splits/train.csv data/splits/val.csv data/splits/test.csv data/splits/programme_holdout.csv; do
  [ -f "$f" ] && FILES+=("$f")
done
tar --exclude='__pycache__' -czf "$BUILD/dataset/repo_inputs.tar.gz" "${FILES[@]}" -C "$BUILD/extra" .
sed "s#KAGGLE_USERNAME#$KAGGLE_USERNAME#g" kaggle/dataset/dataset-metadata.json > "$BUILD/dataset/dataset-metadata.json"
sed -e "s#KAGGLE_USERNAME#$KAGGLE_USERNAME#g" -e "s#course-advisory-llm-runs#course-advisory-llm-$STAGE#g" \
  -e "s#NvidiaTeslaT4#${MACHINE:-NvidiaTeslaT4}#g" kaggle/kernel/kernel-metadata.json > "$BUILD/kernel/kernel-metadata.json"
cp notebooks/kaggle_llm_runs.ipynb "$BUILD/kernel/"

if $KAGGLE datasets status "$DATASET" >/dev/null 2>&1; then
  $KAGGLE datasets version -p "$BUILD/dataset" -m "$STAGE inputs $(date -u +%FT%TZ)"
else
  $KAGGLE datasets create -p "$BUILD/dataset"
fi
for _ in $(seq 1 60); do
  [ "$($KAGGLE datasets status "$DATASET" 2>/dev/null)" = "ready" ] && break
  sleep 10
done

$KAGGLE kernels push -p "$BUILD/kernel"
fi
while true; do
  sleep 60
  STATUS=$($KAGGLE kernels status "$KERNEL" 2>&1 || true)
  echo "$(date +%T) $STATUS"
  case "$STATUS" in
    *COMPLETE*|*complete*) break ;;
    *ERROR*|*error*|*CANCEL*|*cancel*) echo "kernel failed"; mkdir -p "$OUT"; $KAGGLE kernels output "$KERNEL" -p "$OUT" || true; exit 1 ;;
  esac
done

rm -rf "$OUT" && mkdir -p "$OUT"
$KAGGLE kernels output "$KERNEL" -p "$OUT"
$PY -m src.queries.merge_kaggle_cache --src "$OUT" --cache "$CACHE"
