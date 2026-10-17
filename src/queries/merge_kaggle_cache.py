"""Merge the Kaggle notebook's LLM cache into data/interim/llm_cache.jsonl.

Only rows with backend "kaggle-transformers" are taken; a row whose (prompt_id, input_hash,
model_digest) key is already in the local cache is skipped, so merging twice changes nothing.
After merging, rerun the LLM steps with LLM_BACKEND=kaggle-transformers: they then read every
answer from the cache without loading a model.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from src.queries.llm_client import CACHE_PATH, ROOT

SRC = ROOT / "data" / "interim" / "kaggle_out"
LOG_DIR = ROOT / "supporting_files" / "D_augmentation"


def read_rows(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def key(row):
    return (row["prompt_id"], row["input_hash"], row["model_digest"])


def merge(src_files, cache_path):
    have = {key(r) for r in read_rows(cache_path)} if Path(cache_path).exists() else set()
    added, skipped, foreign = [], 0, 0
    for path in src_files:
        for r in read_rows(path):
            if (r.get("backend") or {}).get("backend") != "kaggle-transformers":
                foreign += 1
            elif key(r) in have:
                skipped += 1
            else:
                have.add(key(r))
                added.append(r)
    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "a") as f:
        for r in added:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return added, skipped, foreign


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", default=str(SRC), help="folder with the kernel output")
    ap.add_argument("--cache", default=str(CACHE_PATH))
    args = ap.parse_args()
    files = sorted(Path(args.src).rglob("llm_cache.jsonl"))
    if not files:
        raise SystemExit(f"no llm_cache.jsonl under {args.src}")
    added, skipped, foreign = merge(files, args.cache)
    env = next(Path(args.src).rglob("environment.json"), None)
    log = {"source_files": [str(p.resolve().relative_to(ROOT)) if p.resolve().is_relative_to(ROOT) else str(p) for p in files],
           "cache": str(Path(args.cache)), "added": len(added), "already_present": skipped,
           "ignored_other_backend": foreign, "added_per_prompt": dict(Counter(r["prompt_id"] for r in added)),
           "environment": json.loads(env.read_text()) if env else None}
    log_path = LOG_DIR / f"kaggle_merge_{Path(args.src).name}.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log, indent=1))
    print(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
