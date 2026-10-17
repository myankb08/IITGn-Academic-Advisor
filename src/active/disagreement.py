"""Informativeness score: disagreement between the base model answer and the rule engine gold.

For each pool pair with base answer A (parsed JSON) and gold G:

    if A is not valid JSON or lacks the keys of its intent:  score = 3   (the maximum)
    else score = (1 - Jaccard(codes(A), codes(G)))
               + 1[eligibility intent and A.eligible != G.eligible]
               + 1[remaining_core intent and A.total.gap != G.total.gap]
               + 1[A names any course code that is not in courses.json]

codes() is the course code set the intent is about: compulsory_missing + stream_core_missing for
remaining_core, unmet_prerequisites for eligibility, recommended courses for
elective_recommendation. Jaccard of two empty sets is 1. Each term is at most 1, so a valid answer
scores at most 3 and an invalid one always ties with the worst valid one.

Failure types (a pair can have several): invalid_json, hallucinated_code, wrong_eligibility,
wrong_remaining (missing-course set or total gap differs from gold) and ineligible_recommendation
(a recommended course the rule engine says the student cannot take next term, or already passed).
"""
import argparse
import json
import re
from collections import Counter

from src.augment.common import INTERIM, QUERIES, ROOT, STUDENTS, read_jsonl, rel, write_jsonl
from src.engine.catalog import load_catalog
from src.engine.rule_engine import eligibility

ANSWERS = INTERIM / "base_model_answers.jsonl"
OUT = INTERIM / "al_scores.jsonl"
SUMMARY = ROOT / "supporting_files" / "D_active_learning" / "scores_summary.json"
STRICT_CODE_RE = re.compile(r"\b([A-Z]{2,3})\s?-?(\d{3})(?:-([IVXL]+))?\b")
FAILURE_TYPES = ["invalid_json", "hallucinated_code", "wrong_eligibility", "wrong_remaining", "ineligible_recommendation"]
REQUIRED = {"remaining_core": ("compulsory_missing", "stream_core_missing", "total"),
            "eligibility": ("eligible",), "elective_recommendation": ("recommendations",)}
MAX_SCORE = 3.0


def norm(code):
    m = STRICT_CODE_RE.search(str(code or ""))
    if not m:
        return None
    return f"{m.group(1)} {m.group(2)}" + (f"-{m.group(3)}" if m.group(3) else "")


def code_set(obj, intent):
    if intent == "remaining_core":
        items = list(obj.get("compulsory_missing") or []) + list(obj.get("stream_core_missing") or [])
    elif intent == "eligibility":
        items = list(obj.get("unmet_prerequisites") or [])
    else:
        items = [(x.get("course") if isinstance(x, dict) else x) for x in (obj.get("recommendations") or [])]
    return {c for c in map(norm, items) if c}


def all_codes(obj):
    return {norm(m.group(0)) for m in STRICT_CODE_RE.finditer(json.dumps(obj))}


def jaccard(a, b):
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def valid(obj, intent):
    if not isinstance(obj, dict) or any(k not in obj for k in REQUIRED[intent]):
        return False
    try:
        code_set(obj, intent)
        if intent == "remaining_core":
            int(obj["total"]["gap"])
    except (TypeError, KeyError, ValueError, AttributeError):
        return False
    return True


def score(answer, row, student, catalog):
    """(score, failure types, details) for one base-model answer."""
    intent, gold, obj = row["intent"], row["gold_json"], answer.get("parsed")
    if not valid(obj, intent):
        return MAX_SCORE, ["invalid_json"], {}
    pred, ref = code_set(obj, intent), code_set(gold, intent)
    j = jaccard(pred, ref)
    s, fails = 1.0 - j, []
    halluc = sorted(c for c in all_codes(obj) if c not in catalog.courses)
    if halluc:
        s += 1
        fails.append("hallucinated_code")
    if intent == "eligibility" and bool(obj["eligible"]) != bool(gold["eligible"]):
        s += 1
        fails.append("wrong_eligibility")
    if intent == "remaining_core":
        gap_wrong = int(obj["total"]["gap"]) != int(gold["total"]["gap"])
        s += gap_wrong
        if gap_wrong or pred != ref:
            fails.append("wrong_remaining")
    bad_recs = []
    if intent == "elective_recommendation":
        for c in sorted(pred - set(halluc)):
            e = eligibility(student, c, catalog=catalog)
            if not e["eligible"]:
                bad_recs.append(c)
        if bad_recs:
            fails.append("ineligible_recommendation")
    return round(s, 4), fails, {"jaccard": round(j, 4), "pred_codes": sorted(pred), "gold_codes": sorted(ref),
                                "hallucinated": halluc, "ineligible_recs": bad_recs}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--answers", default=str(ANSWERS))
    ap.add_argument("--queries", default=str(QUERIES))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    catalog = load_catalog()
    rows = {r["query_id"]: r for r in read_jsonl(args.queries)}
    students = {s["student_id"]: s for s in read_jsonl(STUDENTS)}
    out = []
    for a in read_jsonl(args.answers):
        r = rows[a["query_id"]]
        sc, fails, det = score(a, r, students[r["student_id"]], catalog)
        out.append({"query_id": a["query_id"], "intent": r["intent"], "programme": students[r["student_id"]]["programme"],
                    "score": sc, "failures": fails, "failed": bool(fails), **det})
    write_jsonl(args.out, out)
    summary = {"n": len(out), "failed": sum(o["failed"] for o in out),
               "failure_types": {t: sum(t in o["failures"] for o in out) for t in FAILURE_TYPES},
               "failed_by_intent": dict(Counter(o["intent"] for o in out if o["failed"])),
               "mean_score": round(sum(o["score"] for o in out) / len(out), 4) if out else None,
               "score_histogram": dict(sorted(Counter(round(o["score"], 1) for o in out).items())),
               "output": rel(args.out)}
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY, "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
