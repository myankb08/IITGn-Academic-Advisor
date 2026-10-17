"""LLM paraphrases of each query and a student-friendly rewrite of each gold justification.

Order of work, so labelling can start early: rows are taken split by split (test, val,
programme_holdout, train, from data/splits/*.csv; without split files, by sha256(query_id)),
and each row gets its query paraphrase and its justification rewrite before the next row.
`--only-splits test` limits a run to some splits. The output file is rewritten every few calls,
with null for anything not generated yet. Outputs are kept as the model returns them: errors
are left in for the human audit.
"""
import argparse
import csv
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

from src.engine.catalog import load_params
from src.queries.llm_client import CACHE_PATH, LLM, ROOT, load_prompt, render

QUERIES = ROOT / "data" / "processed" / "queries.jsonl"
SPLITS = ROOT / "data" / "splits"
OUT = ROOT / "data" / "processed" / "queries_para.jsonl"
RUN_LOG = ROOT / "supporting_files" / "C_labelling" / "paraphrase_run.json"
Q_PROMPT = "paraphrase_query_v1"
J_PROMPT = "paraphrase_justification_v1"
Q_TOKENS, J_TOKENS = 96, 160
SPLIT_ORDER = ("test", "val", "programme_holdout", "train")


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def rel(path):
    p = Path(path).resolve()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(path)


def load_splits(split_dir=SPLITS):
    """{query_id: split} from any csv in data/splits with a query_id column (split column or file stem)."""
    out = {}
    for path in sorted(Path(split_dir).glob("*.csv")):
        with open(path) as f:
            for row in csv.DictReader(f):
                if row.get("query_id"):
                    out[row["query_id"]] = (row.get("split") or path.stem).strip().lower()
    return out


def work_order(rows, splits):
    def key(r):
        sp = splits.get(r["query_id"])
        rank = SPLIT_ORDER.index(sp) if sp in SPLIT_ORDER else len(SPLIT_ORDER)
        return (rank, r["query_id"] if splits else hashlib.sha256(r["query_id"].encode()).hexdigest())
    return sorted(rows, key=key)


def build_rows(rows, done_q, done_j, llm):
    out = []
    for r in rows:
        q, j = done_q.get(r["query_id"]), done_j.get(r["query_id"])
        out.append({**r, "para_query": q, "para_justification": j,
                    "para_model": f"{llm.model}@{llm.digest}" if q is not None or j is not None else None,
                    "para_prompt_id": f"{Q_PROMPT}+{J_PROMPT}" if q is not None or j is not None else None})
    return out


def write_rows(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    with open(tmp, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queries", default=str(QUERIES))
    ap.add_argument("--splits", default=str(SPLITS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--run-log", default=str(RUN_LOG))
    ap.add_argument("--cache", default=str(CACHE_PATH))
    ap.add_argument("--only-splits", default=None, help="comma separated, e.g. test or test,val")
    ap.add_argument("--limit", type=int, default=None, help="first N rows of the work order only (smoke runs)")
    ap.add_argument("--write-every", type=int, default=10)
    ap.add_argument("--replay", action="store_true", help="cache only: never call a model, leave misses null")
    args = ap.parse_args()
    params = load_params()
    rows = [r for r in read_jsonl(args.queries) if r.get("augmentation") is None]
    splits = load_splits(args.splits)
    todo = work_order(rows, splits)
    if args.only_splits:
        keep = set(args.only_splits.split(","))
        todo = [r for r in todo if splits.get(r["query_id"]) in keep]
    todo = [] if args.replay else todo[:args.limit]
    llm = LLM(params["llm"]["paraphrase_model"], cache_path=args.cache)
    opts = {"seed": params["seeds"]["paraphrase"], "temperature": params["llm"]["temperature"]}
    q_tpl, j_tpl = load_prompt(Q_PROMPT), load_prompt(J_PROMPT)

    def q_call(r, fn):
        return fn(Q_PROMPT, render(q_tpl, query_text=r["query_text"]), opts, num_predict=Q_TOKENS)

    def j_call(r, fn):
        return fn(J_PROMPT, render(j_tpl, gold_text=r["gold_text"]), opts, num_predict=J_TOKENS)

    t0 = time.time()
    done_q, done_j, timings = {}, {}, {"query": 0.0, "justification": 0.0}
    for r in rows:
        q, j = q_call(r, llm.lookup), j_call(r, llm.lookup)
        if q:
            done_q[r["query_id"]] = q["response"]
        if j:
            done_j[r["query_id"]] = j["response"]
    for n, r in enumerate(todo, 1):
        for kind, call, done in (("query", q_call, done_q), ("justification", j_call, done_j)):
            t1 = time.time()
            done[r["query_id"]] = call(r, llm.generate)["response"]
            timings[kind] += time.time() - t1
        if n % args.write_every == 0 or n == len(todo):
            write_rows(args.out, build_rows(rows, done_q, done_j, llm))
            print(f"{n}/{len(todo)} rows done ({splits.get(r['query_id'], 'no split')}), "
                  f"{time.time() - t0:.0f}s, new calls {llm.calls}", flush=True)
    out = build_rows(rows, done_q, done_j, llm)
    write_rows(args.out, out)
    per_split = {}
    for sp in sorted({splits.get(r["query_id"], "none") for r in out}):
        part = [r for r in out if splits.get(r["query_id"], "none") == sp]
        per_split[sp] = {"rows": len(part), "complete": sum(r["para_query"] is not None and r["para_justification"] is not None
                                                            for r in part)}
    log = {
        "input": rel(args.queries), "output": rel(args.out), "n_pairs": len(out),
        "per_intent": dict(sorted(Counter(r["intent"] for r in out).items())),
        "prompt_ids": [Q_PROMPT, J_PROMPT], "num_predict": {"query": Q_TOKENS, "justification": J_TOKENS},
        "seed": opts["seed"], "temperature": opts["temperature"], "only_splits": args.only_splits,
        "limit": args.limit, "split_files_found": bool(splits), "per_split": per_split,
        "para_query_done": sum(r["para_query"] is not None for r in out),
        "para_justification_done": sum(r["para_justification"] is not None for r in out),
        "empty_para_query": sum(r["para_query"] == "" for r in out),
        "empty_para_justification": sum(r["para_justification"] == "" for r in out),
        "seconds_this_run": {k: round(v, 1) for k, v in timings.items()},
        "wall_seconds": round(time.time() - t0, 1),
        **llm.stats(),
    }
    Path(args.run_log).parent.mkdir(parents=True, exist_ok=True)
    with open(args.run_log, "w") as f:
        json.dump(log, f, indent=1)
    print(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
