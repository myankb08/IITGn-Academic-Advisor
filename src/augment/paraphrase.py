"""Second LLM paraphrase of query_text as an augmentation (prompt augment_paraphrase_v1).

Runs on a seeded sample of parents (default 40 per intent, 120 in all, seeds.augmentation), drawn
from the train, val and test splits (programme_holdout is left out); each child follows its parent's
split. The sample ids are written next to the output.
"""
import argparse
import json
import random

from src.augment.common import AUG_DIR, INTERIM, QUERIES, child, read_jsonl, write_jsonl
from src.engine.catalog import load_params
from src.queries.llm_client import CACHE_PATH, LLM, load_prompt, render
from src.queries.paraphrase_llm import load_splits

PROMPT_ID = "augment_paraphrase_v1"
OUT = INTERIM / "aug_paraphrase.jsonl"
SAMPLE_LOG = AUG_DIR / "paraphrase_sample.json"
NUM_PREDICT = 96
SAMPLE_SPLITS = ("train", "val", "test")


def sample_parents(rows, seed, per_intent):
    rng = random.Random(f"{seed}:augment_paraphrase_sample")
    picked = []
    for intent in sorted({r["intent"] for r in rows}):
        pool = sorted((r for r in rows if r["intent"] == intent), key=lambda r: r["query_id"])
        picked += rng.sample(pool, min(per_intent, len(pool)))
    return sorted(picked, key=lambda r: r["query_id"])


def augment(rows, llm, seed, temperature):
    tpl = load_prompt(PROMPT_ID)
    out = []
    for r in rows:
        res = llm.generate(PROMPT_ID, render(tpl, query_text=r["query_text"]),
                           {"seed": seed, "temperature": temperature}, num_predict=NUM_PREDICT)
        out.append(child(r, "paraphrase", "P", query_text=res["response"],
                         para_model=f"{llm.model}@{llm.digest}", para_prompt_id=PROMPT_ID))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queries", default=str(QUERIES))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--cache", default=str(CACHE_PATH))
    ap.add_argument("--per-intent", type=int, default=40)
    args = ap.parse_args()
    params = load_params()
    seed = params["seeds"]["augmentation"]
    splits = load_splits()
    rows = [r for r in read_jsonl(args.queries) if r.get("augmentation") is None
            and (not splits or splits.get(r["query_id"]) in SAMPLE_SPLITS)]
    parents = sample_parents(rows, seed, args.per_intent)
    llm = LLM(params["llm"]["paraphrase_model"], cache_path=args.cache)
    out = augment(parents, llm, seed, params["llm"]["temperature"])
    write_jsonl(args.out, out)
    SAMPLE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SAMPLE_LOG, "w") as f:
        json.dump({"prompt_id": PROMPT_ID, "seed": seed, "per_intent": args.per_intent,
                   "sample_splits": list(SAMPLE_SPLITS) if splits else "no split files",
                   "n_parents": len(parents), "parent_query_ids": [r["query_id"] for r in parents],
                   **llm.stats()}, f, indent=1)
    print(f"paraphrase: {len(out)} children -> {args.out}")


if __name__ == "__main__":
    main()
