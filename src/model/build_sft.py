"""Prompts and targets for every split, the input of training, prediction and evaluation.

Writes data/sft/<split>.jsonl for train, val, test, programme_holdout and gold. Each row has the slice fields,
the retrieval prompt (advisor_retrieval_v1), the student fields for the no-context prompts, and the target: the
A1 schema projection of gold_json plus the rule-engine gold_text as justification. Gold rows use audited_query
with the five "workshop" errata fixed (docs/A2_PLAN.md D5); the gold file itself is not changed.
Train rows also get the paraphrase of each base pair (query_id suffix -para), used only by the base_aug mix.
Labels follow the D6 policy (src/model/d6.py): a passed course is eligible again for grade improvement. Rows whose
label changed carry label_policy = "d6_repeat". gold_a1.jsonl keeps the original A1 gold labels for comparison.
"""
import hashlib
import json
import re

import pandas as pd

from src.active.base_model_answers import catalog_context, rules_line
from src.augment.common import ROOT, read_jsonl, write_jsonl
from src.engine.catalog import load_catalog
from src.engine.rule_engine import upcoming_term
from src.model.d6 import eligibility_d6, text_d6
from src.queries.llm_client import load_prompt, render
from src.queries.to_labelstudio import student_summary

OUT = ROOT / "data" / "sft"
PROCESSED = ROOT / "data" / "processed"
GOLD = ROOT / "data" / "gold" / "gold_test.jsonl"
GOLD_SHA = "cd2e08dcb56f5716b06981e096c3c93fd417abab1989b5d22d45befeafbc383f"
ERRATA = {"R1-Q0447", "R1-Q0597", "R2-Q0207", "R2-Q0348", "R2-Q0376"}


def load_template(prompt_id):
    """(main template, {intent: schema text}) from a prompt file with '=== schema: <intent> ===' blocks."""
    parts = re.split(r"^=== schema: (\w+) ===\n", load_prompt(prompt_id), flags=re.M)
    return parts[0].rstrip() + "\n", {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def target(intent, gold, text):
    """A1 schema projection of gold_json plus the justification, as the model should print it."""
    if intent == "remaining_core":
        ans = {"compulsory_missing": gold["compulsory_missing"], "stream_core_missing": gold["stream_core_missing"],
               "total": {k: gold["total"][k] for k in ("earned", "min", "gap")}}
    elif intent == "eligibility":
        ans = {"eligible": gold["eligible"], "unmet_prerequisites": gold["unmet_prerequisites"],
               "reason_codes": gold["reason_codes"]}
    else:
        ans = {"recommendations": [{"rank": r["rank"], "course": r["course"]} for r in gold["recommendations"]]}
    return json.dumps({**ans, "justification": text}, ensure_ascii=False)


def apply_d6(q, student, catalog):
    """The pair with its eligibility label recomputed under D6 when the A1 label is ALREADY_TAKEN."""
    if q["intent"] != "eligibility" or "ALREADY_TAKEN" not in q["gold_json"]["reason_codes"]:
        return q
    g = eligibility_d6(student, q["target_course"], term=q["gold_json"]["term"], catalog=catalog)
    g["student_id"] = q["gold_json"].get("student_id", g["student_id"])
    return {**q, "gold_json": g, "gold_text": text_d6(g, catalog, student), "label_policy": "d6_repeat"}


def make_row(q, query, split, student, catalog, tpl, schemas):
    """One row: slice fields, prompt fields, retrieval prompt, target and gold_json."""
    fields = dict(programme=student["programme"], track=student["track"], rules=rules_line(catalog, student),
                  student=student_summary(student), term=upcoming_term(student), query=query)
    return {
        "query_id": q["query_id"], "split": split, "intent": q["intent"], "template_family": q["template_family"],
        "student_id": student["student_id"], "n_courses": len(student.get("transcript", [])),
        "semesters_completed": student["semesters_completed"], "target_course": q.get("target_course"),
        "augmentation": q.get("augmentation"), "parent_query_id": q.get("parent_query_id"), **fields,
        "prompt": render(tpl, catalog=catalog_context(catalog, student["programme"], q.get("target_course")),
                         schema=schemas[q["intent"]], **fields),
        "target": target(q["intent"], q["gold_json"], q["gold_text"]), "gold_json": q["gold_json"],
        "label_policy": q.get("label_policy", "a1"),
    }


if __name__ == "__main__":
    catalog = load_catalog()
    tpl, schemas = load_template("advisor_retrieval_v1")
    students = {s["student_id"]: s for s in read_jsonl(PROCESSED / "students.jsonl")
                + read_jsonl(PROCESSED / "students_augmented.jsonl")}
    pairs = {q["query_id"]: q for q in read_jsonl(PROCESSED / "queries_para.jsonl")}
    pairs.update({q["query_id"]: q for q in read_jsonl(PROCESSED / "queries_augmented.jsonl") if q.get("parent_query_id")})
    OUT.mkdir(parents=True, exist_ok=True)

    for split in ["train", "val", "test", "programme_holdout"]:
        rows = []
        for qid in pd.read_csv(ROOT / "data" / "splits" / f"{split}.csv").query_id:
            q = apply_d6(pairs[qid], students[pairs[qid]["student_id"]], catalog)
            rows.append(make_row(q, q["query_text"], split, students[q["student_id"]], catalog, tpl, schemas))
            if split == "train" and not q.get("parent_query_id") and q.get("para_query"):
                para = make_row(q, q["para_query"], split, students[q["student_id"]], catalog, tpl, schemas)
                rows.append({**para, "query_id": f"{qid}-para", "augmentation": "a1_paraphrase", "parent_query_id": qid})
        write_jsonl(OUT / f"{split}.jsonl", rows)
        print(f"{split}: {len(rows)} rows, D6 relabelled: {sum(r['label_policy'] == 'd6_repeat' for r in rows)}")

    # Gold: checksum first, then audited text with the errata fix
    assert hashlib.sha256(GOLD.read_bytes()).hexdigest() == GOLD_SHA, "gold checksum changed"
    rows, rows_a1 = [], []
    for g in read_jsonl(GOLD):
        query = g["audited_query"].replace("workshop", "coursework") if g["item_id"] in ERRATA else g["audited_query"]
        extra = {"item_id": g["item_id"], "errata_fixed": g["item_id"] in ERRATA}
        st = students[g["student_id"]]
        rows.append({**make_row(apply_d6(g, st, catalog), query, "gold", st, catalog, tpl, schemas), **extra})
        rows_a1.append({**make_row(g, query, "gold_a1", st, catalog, tpl, schemas), **extra})
    write_jsonl(OUT / "gold.jsonl", rows)
    write_jsonl(OUT / "gold_a1.jsonl", rows_a1)
    print(f"gold: {len(rows)} rows, errata fixed: {sum(r['errata_fixed'] for r in rows)}, "
          f"D6 relabelled: {sum(r['label_policy'] == 'd6_repeat' for r in rows)} (original labels in gold_a1.jsonl)")
