"""Error sheet for test errors: every row the model gets wrong on the test split (base pairs first, then children).

Each error gets an automatic category from its scores (rule-based, listed below) and a suggested fix per category.
The columns reviewed_category and reviewer_notes are left empty for the two annotators to confirm or correct;
the report uses the reviewed categories. Output: supporting_files/C_eval/<name>/test/error_sheet.csv.
Categories: invalid_output, invented_code, wrong_eligibility, rule_violation, missing_courses, extra_courses,
wrong_courses, wrong_credit_total.
Example: python -m src.eval.error_sheet --name advisor_v3
"""
import argparse
import json

import pandas as pd

from src.active.base_model_answers import parse_json
from src.augment.common import ROOT, read_jsonl

FIX = {"invalid_output": "constrained JSON decoding or a schema retry before the rule check",
       "invented_code": "restrict decoding to catalog codes; reject unknown codes in the rule check (already shown to users)",
       "wrong_eligibility": "add the target course's prerequisite and offering lines to the prompt; more eligible/not pairs",
       "rule_violation": "post-filter recommendations with the rule engine; add negative examples to training",
       "missing_courses": "list the programme's core courses explicitly in the prompt; more remaining_core pairs per stream",
       "extra_courses": "give the passed-course set in the prompt as codes; train on longer transcripts",
       "wrong_courses": "more elective pairs per stream and term; rank by rule-engine order",
       "wrong_credit_total": "let the rule engine compute credit totals; the model only explains them"}


def category(s, row, pred):
    """Rule-based first guess of the error type."""
    if not s["valid_json"]:
        return "invalid_output"
    if s["invented_codes"]:
        return "invented_code"
    if s.get("eligible_correct") == 0:
        return "wrong_eligibility"
    if s["violations"]:
        return "rule_violation"
    if row["intent"] == "remaining_core" and s["set_f1"] == 1:
        return "wrong_credit_total"
    if s["recall"] < 1 and s["precision"] == 1:
        return "missing_courses"
    if s["precision"] < 1 and s["recall"] == 1:
        return "extra_courses"
    return "wrong_courses"


parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True, help="output folder name in supporting_files/C_eval")
opt = parser.parse_args()
print(opt)

d = ROOT / "supporting_files/C_eval" / opt.name / "test"
scores = {s["query_id"]: s for s in read_jsonl(d / "scores.jsonl")}
preds = {p["query_id"]: p["response"] for p in read_jsonl(d / "preds.jsonl")}
out = []
for r in sorted(read_jsonl(ROOT / "data/sft/test.jsonl"), key=lambda r: (bool(r["augmentation"]), r["query_id"])):
    s = scores[r["query_id"]]
    if s["exact_match"]:
        continue
    cat = category(s, r, parse_json(preds[r["query_id"]]))
    out.append({"query_id": r["query_id"], "intent": r["intent"], "programme": r["programme"],
                "template_family": r["template_family"], "augmentation": r["augmentation"] or "none",
                "n_courses": r["n_courses"], "query": r["query"], "pred_codes": " ".join(s["pred_codes"]),
                "gold_codes": " ".join(s["gold_codes"]), "invented": " ".join(s["invented"]), "set_f1": round(s["set_f1"], 3),
                "auto_category": cat, "suggested_fix": FIX[cat], "reviewed_category": "", "reviewer_notes": "",
                "raw_answer": preds[r["query_id"]][:400]})
df = pd.DataFrame(out)
df.to_csv(d / "error_sheet.csv", index=False)
print(f"{len(df)} errors of {len(scores)} test rows")
print(df.groupby(["auto_category", "intent"]).size().to_string())
json.dump(df.auto_category.value_counts().to_dict(), open(d / "error_categories.json", "w"), indent=1)
