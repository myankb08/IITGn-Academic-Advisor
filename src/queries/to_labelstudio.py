"""Sample round-1 and round-2 audit items and write Label Studio tasks plus a manifest.

Real run:    .venv/bin/python -m src.queries.to_labelstudio
Fixture run: .venv/bin/python -m src.queries.to_labelstudio --fixture
Real runs draw both rounds from the test split only (data/splits/test.csv from src.split.make_splits),
stratified by intent, so the audited items form the gold test set. Fixture runs use every fixture query.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
ANNOTATORS = ["A1", "A2"]
ROUNDS = {1: "v1", 2: "v2"}
ITEMS_PER_ROUND = 40
SPLIT_ORDER = ["test"]


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def student_summary(s):
    """Short plain-text view of a synthetic student and transcript."""
    if s is None:
        return "(student record not found)"
    head = (f"{s['programme']}, {s['stream']} stream, {s['track']} track, "
            f"admitted {s.get('admit_year', '?')}, {s['semesters_completed']} semester(s) completed.")
    rows = sorted(s.get("transcript", []), key=lambda r: (r.get("semester", 0), r.get("code", "")))
    if not rows:
        return head + " No courses completed yet."
    done = "; ".join(f"{r['code']} (sem {r.get('semester')}, {r.get('credits')} cr, {r.get('grade')})" for r in rows)
    return f"{head} Completed: {done}."


def eligible(q):
    """Original queries with both paraphrase fields filled."""
    return bool(q.get("para_query")) and bool(q.get("para_justification")) and not q.get("parent_query_id")


def allocate(counts, n):
    """Proportional allocation with largest remainders, deterministic tie-break on intent name."""
    total = sum(counts.values())
    raw = {k: n * v / total for k, v in counts.items()}
    alloc = {k: min(int(raw[k]), counts[k]) for k in counts}
    rest = sorted(counts, key=lambda k: (-(raw[k] - int(raw[k])), k))
    i = 0
    while sum(alloc.values()) < n:
        k = rest[i % len(rest)]
        if alloc[k] < counts[k]:
            alloc[k] += 1
        i += 1
    return alloc


def sample_rounds(queries, seed, n_per_round, n_rounds, split_of=None):
    """Stratified by intent, disjoint across rounds. With split_of, only items whose split is in SPLIT_ORDER
    are used (test only), in that order of tiers, each tier shuffled."""
    rng = np.random.default_rng(seed)
    tiers = SPLIT_ORDER if split_of is not None else [None]
    by_intent = {}
    for q in sorted(queries, key=lambda q: q["query_id"]):
        tier = split_of.get(q["query_id"]) if split_of is not None else None
        if tier in tiers:
            by_intent.setdefault(q["intent"], {}).setdefault(tier, []).append(q)
    need = n_per_round * n_rounds
    have = sum(len(t) for v in by_intent.values() for t in v.values())
    if have < need:
        raise SystemExit(f"need {need} eligible queries in splits {tiers}, found {have}")
    pools = {}
    for k, v in sorted(by_intent.items()):
        pools[k] = []
        for tier in tiers:
            items = v.get(tier, [])
            pools[k] += [items[i] for i in rng.permutation(len(items))]
    rounds = []
    for _ in range(n_rounds):
        alloc = allocate({k: len(v) for k, v in pools.items()}, n_per_round)
        picked = []
        for k in sorted(pools):
            picked += pools[k][:alloc[k]]
            pools[k] = pools[k][alloc[k]:]
        order = rng.permutation(len(picked))
        rounds.append([picked[i] for i in order])
    return rounds


def to_task(q, students, rnd, pos):
    item_id = f"R{rnd}-{q['query_id']}"
    return {"data": {
        "item_id": item_id,
        "query_id": q["query_id"],
        "round": rnd,
        "guidelines_version": ROUNDS[rnd],
        "position": pos,
        "student_summary": student_summary(students.get(q["student_id"])),
        "template_query": q["query_text"],
        "para_query": q["para_query"],
        "gold_text": q["gold_text"],
        "para_justification": q["para_justification"],
    }}


def main():
    from src.split.make_splits import load_split_map
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true", help="use tests/fixtures and write under supporting_files")
    args = ap.parse_args()
    params = yaml.safe_load(open(ROOT / "params.yaml"))
    seed = params["seeds"]["annotation_order"]
    if args.fixture:
        qpath = ROOT / "tests/fixtures/fixture_queries.jsonl"
        spath = ROOT / "tests/fixtures/fixture_students.jsonl"
        out_base = ROOT / "supporting_files/C_labelling/fixture_tasks"
    else:
        qpath = ROOT / "data/processed/queries_para.jsonl"
        if not qpath.exists():
            qpath = ROOT / "data/processed/queries.jsonl"
        spath = ROOT / "data/processed/students.jsonl"
        out_base = ROOT / "data/labels"
        if not qpath.exists():
            raise SystemExit(f"{qpath.relative_to(ROOT)} not found; run with --fixture to test")
    split_of = None
    if not args.fixture:
        split_of = load_split_map()
        if not split_of:
            raise SystemExit("no split manifests in data/splits; run .venv/bin/python -m src.split.make_splits first")
    queries = [q for q in load_jsonl(qpath) if eligible(q)]
    students = {s["student_id"]: s for s in load_jsonl(spath)} if spath.exists() else {}
    rounds = sample_rounds(queries, seed, ITEMS_PER_ROUND, len(ROUNDS), split_of)
    for rnd, items in zip(ROUNDS, rounds):
        out = out_base / f"round{rnd}"
        out.mkdir(parents=True, exist_ok=True)
        tasks = [to_task(q, students, rnd, i + 1) for i, q in enumerate(items)]
        with open(out / "tasks.json", "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)
        with open(out / "manifest.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["position", "item_id", "query_id", "intent", "round", "guidelines_version", "annotators", "seed",
                        "split"])
            for t, q in zip(tasks, items):
                d = t["data"]
                w.writerow([d["position"], d["item_id"], q["query_id"], q["intent"], rnd, ROUNDS[rnd], ";".join(ANNOTATORS), seed,
                            (split_of or {}).get(q["query_id"], "")])
        mix, splits = {}, {}
        for q in items:
            mix[q["intent"]] = mix.get(q["intent"], 0) + 1
            s = (split_of or {}).get(q["query_id"], "fixture")
            splits[s] = splits.get(s, 0) + 1
        print(f"round {rnd}: {len(tasks)} items -> {out.relative_to(ROOT)} intents={dict(sorted(mix.items()))} "
              f"splits={dict(sorted(splits.items()))}")


if __name__ == "__main__":
    main()
