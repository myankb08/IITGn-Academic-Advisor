"""Freeze the gold test set: test-split items that passed the human audit.

    .venv/bin/python -m src.split.freeze_gold

Reads data/labels/audited.jsonl (from src.queries.adjudicate), keeps items whose query is in the test
split and whose final decision is accept or edit (rejects are left out), joins the query record and writes
data/gold/gold_test.jsonl plus its sha256 in data/gold/GOLD_SHA256.txt (also filled into HANDOFF_A2.md).
Stops if no labels exist yet.
"""
import hashlib
import json
from collections import Counter

from src.split.make_splits import EVIDENCE, ROOT, load_split_map, read_jsonl

AUDITED = ROOT / "data" / "labels" / "audited.jsonl"
QUERIES_PARA = ROOT / "data" / "processed" / "queries_para.jsonl"
QUERIES = ROOT / "data" / "processed" / "queries.jsonl"
GOLD = ROOT / "data" / "gold"
FIELDS = ["query_id", "student_id", "template_id", "template_family", "intent", "target_course", "query_text",
          "gold_json", "gold_text", "para_model", "para_prompt_id"]
GOLD_START, GOLD_END = "<!-- GOLD_SHA256 -->", "<!-- /GOLD_SHA256 -->"


def main():
    if not AUDITED.exists() or not AUDITED.read_text().strip():
        raise SystemExit("no human labels yet: data/labels/audited.jsonl is missing or empty. Label rounds 1 and 2 "
                         "in Label Studio, export to data/labels/roundN/, fill adjudication.csv, run "
                         "src.queries.adjudicate, then rerun this script.")
    split_of = load_split_map()
    if not split_of:
        raise SystemExit("no split manifests in data/splits; run src.split.make_splits first")
    qpath = QUERIES_PARA if QUERIES_PARA.exists() else QUERIES
    queries = {q["query_id"]: q for q in read_jsonl(qpath)}
    audited = read_jsonl(AUDITED)
    skipped = Counter()
    rows = []
    for a in sorted(audited, key=lambda a: (a["query_id"], a["round"])):
        if split_of.get(a["query_id"]) != "test":
            skipped[f"not test ({split_of.get(a['query_id'], 'unsplit')})"] += 1
            continue
        if a["final_decision"] not in ("accept", "edit"):
            skipped[f"final_decision {a['final_decision']}"] += 1
            continue
        q = queries[a["query_id"]]
        rows.append({**{k: q.get(k) for k in FIELDS}, "split": "test", "item_id": a["item_id"], "round": a["round"],
                     "guidelines_version": a["guidelines_version"], "para_query": a["para_query"],
                     "para_justification": a["para_justification"], "final_decision": a["final_decision"],
                     "final_category": a["final_category"],
                     "final_edit": a["final_edit"] if a["final_decision"] == "edit" else None,
                     "decided_by": a["decided_by"]})
    if not rows:
        raise SystemExit(f"no accepted or edited test-split items in audited.jsonl (skipped: {dict(skipped)})")
    GOLD.mkdir(parents=True, exist_ok=True)
    out = GOLD / "gold_test.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    (GOLD / "GOLD_SHA256.txt").write_text(f"{digest}  data/gold/gold_test.jsonl\n")
    summary = {"n_gold": len(rows), "sha256": digest, "source": str(qpath.relative_to(ROOT)),
               "by_decision": dict(sorted(Counter(r["final_decision"] for r in rows).items())),
               "by_intent": dict(sorted(Counter(r["intent"] for r in rows).items())),
               "skipped": dict(sorted(skipped.items()))}
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with open(EVIDENCE / "gold_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    handoff = ROOT / "HANDOFF_A2.md"
    if handoff.exists():
        text = handoff.read_text(encoding="utf-8")
        head, sep, rest = text.partition(GOLD_START)
        if sep and GOLD_END in rest:
            tail = rest.split(GOLD_END, 1)[1]
            handoff.write_text(f"{head}{GOLD_START}`{digest}` ({len(rows)} items){GOLD_END}{tail}", encoding="utf-8")
    print(f"gold_test: {len(rows)} items, sha256 {digest}")


if __name__ == "__main__":
    main()
