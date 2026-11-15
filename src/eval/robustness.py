"""Robustness on the A1 Part D augmented test data: each augmented child against its parent question.

Reads supporting_files/C_eval/<name>/test/scores.jsonl (from src.eval.evaluate) and data/sft/test.jsonl.
Per augmentation type: n, mean set_f1 of children and of their parents, mean drop, and the share of children whose
exact-match outcome equals the parent's (invariance). Output: supporting_files/C_eval/<name>/test/robustness.json.
Example: python -m src.eval.robustness --name advisor_v3
"""
import argparse
import json

import numpy as np

from src.augment.common import ROOT, read_jsonl

parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True, help="output folder name in supporting_files/C_eval")
opt = parser.parse_args()
print(opt)

d = ROOT / "supporting_files/C_eval" / opt.name / "test"
scores = {s["query_id"]: s for s in read_jsonl(d / "scores.jsonl")}
rows = read_jsonl(ROOT / "data/sft/test.jsonl")
out = {}
for aug in sorted({r["augmentation"] for r in rows if r["augmentation"]}):
    pairs = [(scores[r["query_id"]], scores[r["parent_query_id"]]) for r in rows
             if r["augmentation"] == aug and r["parent_query_id"] in scores]
    c, p = np.array([x["set_f1"] for x, _ in pairs]), np.array([y["set_f1"] for _, y in pairs])
    out[aug] = {"n": len(pairs), "child_set_f1": float(c.mean()), "parent_set_f1": float(p.mean()),
                "mean_drop": float((p - c).mean()),
                "exact_match_invariance": float(np.mean([x["exact_match"] == y["exact_match"] for x, y in pairs]))}
json.dump(out, open(d / "robustness.json", "w"), indent=1)
print(json.dumps(out, indent=1))
