"""Merge the two annotators' error reviews into the test error sheet, with Cohen's kappa and an elective rule check.

Inputs in supporting_files/C_eval/<name>/test/error_review/: A1_export_from_page.json (hem436, shared store of the
review page) and A2_export_from_page.csv (myankb08, CSV copied from the page).
Writes reviewed_category / reviewer_notes (A1) and reviewed_category_a2 / reviewer_notes_a2 into error_sheet.csv,
an elective_check column for elective errors, and error_review/summary.json (counts, agreement, kappa with a
1000-sample bootstrap CI).
elective_check: allowed_different (every recommended course is one the student may take and that counts) or
not_allowed, then the rule engine's priority tier of each course before any pick (0 own-basket gap, 1 other-basket
gap, 2 own basket, 3 other basket, 4 open; or why it is not allowed), model picks against the rule-engine picks.
The rule engine updates the gaps after each pick, so these static tiers do not rank the two lists.
Example: python -m src.eval.error_review --name advisor_v1
"""
import argparse
import json
import re

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import cohen_kappa_score

from src.augment.common import ROOT, read_jsonl
from src.engine.catalog import course_level, load_catalog
from src.engine.rule_engine import (ELECTIVE_CATEGORIES, eligibility, passed_codes, recommend_electives,
                                    remaining_requirements, role_of)

parser = argparse.ArgumentParser()
parser.add_argument("--name", default="advisor_v1", help="evaluated model folder under supporting_files/C_eval")
opt = parser.parse_args()
print(opt)

d = ROOT / "supporting_files/C_eval" / opt.name / "test"
sheet = pd.read_csv(d / "error_sheet.csv", keep_default_na=False)
a1 = json.load(open(d / "error_review/A1_export_from_page.json"))["items"]
a2 = pd.read_csv(d / "error_review/A2_export_from_page.csv", keep_default_na=False).set_index("query_id")
assert set(a1) == set(sheet.query_id) == set(a2.index), "both reviews must cover every error"

# ----------
#  Elective rule check
# ----------
cat = load_catalog()
students = {s["student_id"]: s for s in read_jsonl(ROOT / "data/processed/students.jsonl")
            + read_jsonl(ROOT / "data/processed/students_augmented.jsonl")}
rows = {r["query_id"]: r for r in read_jsonl(ROOT / "data/sft/test.jsonl")}
preds = {p["query_id"]: p["response"] for p in read_jsonl(d / "preds.jsonl")}


def tier(st, code, rem):
    """Rule-engine priority tier of one recommended course, or why it cannot be recommended."""
    c = cat.course(code)
    if c is None:
        return "unknown"
    role, lvl = role_of(cat, st, code), course_level(c, code)
    if c.get("category") not in ELECTIVE_CATEGORIES or role in {"own_core", "compulsory", "ai_applications"}:
        return "not_elective"
    if lvl is not None and lvl < 600 and rem["below_600"]["cap_reached"]:
        return "below_600_cap"
    if code in passed_codes(st, cat) or not eligibility(st, code, catalog=cat)["eligible"]:
        return "not_eligible"
    if role == "own_basket" and rem["own_basket"]["gap"] > 0:
        return "0"
    if role == "other_basket" and rem["other_basket"]["gap"] > 0:
        return "1"
    return {"own_basket": "2", "other_basket": "3"}.get(role, "4")


checks = {}
for q in sheet.query_id[sheet.intent == "elective_recommendation"]:
    st = students[rows[q]["student_id"]]
    rem = remaining_requirements(st, cat)
    m = re.search(r"\{[\s\S]*\}", preds[q])
    pred = [r["course"] for r in json.loads(m.group(0)).get("recommendations", [])] if m else []
    ref = [r["course"] for r in recommend_electives(st, k=3, catalog=cat)["recommendations"]]
    pt, rt = [tier(st, c, rem) for c in pred], [tier(st, c, rem) for c in ref]
    allowed = all(t.isdigit() for t in pt)
    verdict = "allowed_different" if allowed else "not_allowed"
    checks[q] = {"verdict": verdict, "text": f"{verdict}: model " + ", ".join(f"{c} [{t}]" for c, t in zip(pred, pt))
                 + "; rule engine " + ", ".join(f"{c} [{t}]" for c, t in zip(ref, rt))}

# ----------
#  Merge and agreement
# ----------
sheet["reviewed_category"] = sheet.query_id.map(lambda q: a1[q]["cat"])
sheet["reviewer_notes"] = sheet.query_id.map(lambda q: a1[q]["notes"])
sheet["reviewed_category_a2"] = sheet.query_id.map(a2.reviewed_category)
sheet["reviewer_notes_a2"] = sheet.query_id.map(a2.reviewer_notes)
sheet["elective_check"] = sheet.query_id.map(lambda q: checks.get(q, {}).get("text", ""))
sheet.to_csv(d / "error_sheet.csv", index=False)

x, y = sheet.reviewed_category.to_numpy(), sheet.reviewed_category_a2.to_numpy()
rng = np.random.default_rng(yaml.safe_load(open(ROOT / "params_a2.yaml"))["seeds"]["bootstrap"])
boot = [cohen_kappa_score(x[i], y[i]) for i in (rng.integers(0, len(x), len(x)) for _ in range(1000))]
res = {"n": len(x), "a1": sheet.reviewed_category.value_counts().to_dict(),
       "a2": sheet.reviewed_category_a2.value_counts().to_dict(), "agree": int((x == y).sum()),
       "kappa": cohen_kappa_score(x, y), "kappa_ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
       "disagreements (a1 | a2)": pd.Series([f"{a} | {b}" for a, b in zip(x, y) if a != b]).value_counts().to_dict(),
       "elective_check": pd.Series([c["verdict"] for c in checks.values()]).value_counts().to_dict()}
json.dump(res, open(d / "error_review/summary.json", "w"), indent=1)
print(json.dumps(res, indent=1))
