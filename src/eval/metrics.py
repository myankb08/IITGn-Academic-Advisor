"""Per-row scores of one raw model answer against the rule engine, measured before any rule-engine check.

Reuses the A1 failure definitions (src/active/disagreement.py): code_set, all_codes and valid.
- set_f1: remaining_core and elective_recommendation use the F1 of the course set; eligibility uses the F1 of the
  unmet-prerequisite set when the yes/no is right, else 0. This is the selection and gate metric.
- exact_match: the whole answer equals the rule engine (sets, eligible flag, total credit gap).
- invented_codes: course codes in the raw output that are not in courses.json.
- violations: answers that break a rule: an ineligible or already passed recommendation, a passed course listed as
  missing, or eligible = true with unmet prerequisites listed.
"""
import json

from src.active.base_model_answers import parse_json
from src.active.disagreement import STRICT_CODE_RE, all_codes, code_set, norm, valid
from src.engine.rule_engine import eligibility, passed_codes


def prf(pred, gold):
    """Set precision, recall, F1; two empty sets count as perfect."""
    if not pred and not gold:
        return 1.0, 1.0, 1.0
    tp = len(pred & gold)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def score_row(text, row, student, catalog):
    """Score dict for one raw answer text."""
    intent, gold = row["intent"], row["gold_json"]
    obj = parse_json(text)
    invented = sorted({norm(m.group(0)) for m in STRICT_CODE_RE.finditer(text or "")} - set(catalog.courses))
    out = {"valid_json": valid(obj, intent), "invented_codes": len(invented), "invented": invented,
           "answer_chars": len(text or "")}
    if not out["valid_json"]:
        return {**out, "precision": 0.0, "recall": 0.0, "set_f1": 0.0, "exact_match": 0, "violations": 0,
                "eligible_correct": 0 if intent == "eligibility" else None, "pred_codes": [], "gold_codes": []}

    pred, ref = code_set(obj, intent), code_set(gold, intent)
    p, r, f1 = prf(pred, ref)
    passed = set(passed_codes(student, catalog))
    violations = 0
    if intent == "remaining_core":
        exact = pred == ref and _int(obj["total"].get("gap")) == gold["total"]["gap"]
        violations = int(bool(pred & passed))
    elif intent == "eligibility":
        right = bool(obj["eligible"]) == bool(gold["eligible"])
        f1, exact = (f1 if right else 0.0), right and pred == ref
        violations = int(bool(obj["eligible"]) and bool(pred))
        out["eligible_correct"] = int(right)
    else:
        exact = pred == ref
        bad = [c for c in pred - set(invented) if c in passed or not eligibility(student, c, catalog=catalog)["eligible"]]
        violations = int(bool(bad))
    return {**out, "precision": p, "recall": r, "set_f1": f1, "exact_match": int(exact), "violations": violations,
            "pred_codes": sorted(pred), "gold_codes": sorted(ref)}


def _int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def summarise(scores):
    """Mean of each numeric score over rows."""
    keys = ["set_f1", "precision", "recall", "exact_match", "valid_json", "violations", "invented_codes"]
    out = {k: sum(float(s[k]) for s in scores) / len(scores) for k in keys}
    out["invented_rate"] = sum(s["invented_codes"] > 0 for s in scores) / len(scores)
    elig = [s["eligible_correct"] for s in scores if s.get("eligible_correct") is not None]
    out["eligibility_acc"] = sum(elig) / len(elig) if elig else None
    out["n"] = len(scores)
    return out


if __name__ == "__main__":
    # Self check: the rule-engine target must score perfectly on every val row
    from src.augment.common import ROOT, read_jsonl
    from src.engine.catalog import load_catalog
    catalog = load_catalog()
    students = {s["student_id"]: s for s in read_jsonl(ROOT / "data/processed/students.jsonl")
                + read_jsonl(ROOT / "data/processed/students_augmented.jsonl")}
    rows = read_jsonl(ROOT / "data/sft/val.jsonl")
    s = summarise([score_row(r["target"], r, students[r["student_id"]], catalog) for r in rows])
    print(json.dumps(s, indent=1))
    assert s["exact_match"] == 1.0 and s["violations"] == 0 and s["invented_codes"] == 0
