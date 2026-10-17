#!/usr/bin/env bash
# Local LLM steps in priority order, then the non-LLM steps that depend on them.
# Every LLM call is cached in data/interim/llm_cache.jsonl, so the queue can be stopped and rerun.
# Backend: LLM_BACKEND (default llamacpp here, see supporting_files/D_augmentation/llm_backend.md).
set -euo pipefail
cd "$(dirname "$0")/.."
export LLM_BACKEND="${LLM_BACKEND:-llamacpp}"
PY=.venv/bin/python
LOG=supporting_files/D_augmentation/local_queue.log
mkdir -p "$(dirname "$LOG")"
run() { echo "$(date +%FT%T) start $*" >> "$LOG"; "$PY" -m "$@"; echo "$(date +%FT%T) done $*" >> "$LOG"; }
run src.queries.paraphrase_llm --phase all
run src.active.base_model_answers
run src.augment.paraphrase
run src.augment.typos_abbrev
run src.augment.transcript_variants
run src.augment.verify
run src.active.disagreement
run src.active.al_vs_random
