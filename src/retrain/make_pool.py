"""Shifted data and the pre-labelled retraining pool for Part E (docs/A2_PLAN.md D6, D7).

1. Applies data/a2/curriculum_update.json to courses.json -> data/a2/courses_v2.json (a simulated update).
2. Labels programme_holdout again under the v2 catalog and the D6 policy -> data/sft/shifted.jsonl. Its
   rows keep their A1 query text; only the rule-engine answers change where the update affects them.
3. New students (seed seeds.retrain_pool, 60% MTech-ICDT) and pairs from the A1 generators under v2, labelled by
   the rule engine (the simulated annotator) -> data/a2/students_pool.jsonl, data/sft/pool.jsonl.
   Student and query ids start with P, so the pool never overlaps any evaluation split.
4. The 19 Google Forms questions as unlabelled traffic -> data/sft/forms.jsonl (no gold_json).
"""
import copy
import json
from collections import Counter

import yaml

from src.augment.common import ROOT, read_jsonl, write_jsonl
from src.engine.catalog import RULES_PATH, load_catalog, load_params
from src.engine.rule_engine import eligibility, recommend_electives, remaining_requirements, validate_transcript
from src.engine.synth_transcripts import generate
from src.model.build_sft import apply_d6, load_template, make_row
from src.model.d6 import eligibility_d6, text_d6
from src.queries.make_queries import build, text_eligibility, text_recommend, text_remaining
from src.queries.llm_client import render

A2 = ROOT / "data" / "a2"
SFT = ROOT / "data" / "sft"
INTENT_OF_KIND = {"Remaining requirements": "remaining_core", "Eligibility for a course": "eligibility",
                  "Elective advice": "elective_recommendation", "Other": "remaining_core"}


def apply_update(courses, upd):
    """Copy of the course list with the update applied."""
    out = copy.deepcopy(courses)
    by_code = {c["code"]: c for c in out}
    for code, pre in upd["set_prerequisites"].items():
        by_code[code].update(prerequisites=pre, prereq_source="curriculum_update_v2")
    for code, terms in upd["set_offered_terms"].items():
        by_code[code].update(offered_terms=terms, offered_parity=None)
    for new in upd["new_courses"]:
        rec = copy.deepcopy(by_code[new["copy_fields_from"]])
        rec.update({k: v for k, v in new.items() if k != "copy_fields_from"}, source_doc="curriculum_update_v2",
                   prereq_source="curriculum_update_v2", offering_evidence="curriculum_update_v2", other_sources=[])
        out.append(rec)
    return out


def relabel(q, s, catalog, d6=True):
    """gold_json and gold_text of one A1 pair recomputed with another catalog (D6 policy unless d6=False)."""
    if q["intent"] == "remaining_core":
        g = remaining_requirements(s, catalog)
        return g, text_remaining(g, catalog, q["template_family"])
    if q["intent"] == "eligibility":
        if d6:
            g = eligibility_d6(s, q["target_course"], term=q["gold_json"]["term"], catalog=catalog)
            return g, text_d6(g, catalog, s)
        g = eligibility(s, q["target_course"], term=q["gold_json"]["term"], catalog=catalog)
        return g, text_eligibility(g, catalog, s)
    g = recommend_electives(s, k=3, term=q["gold_json"]["term"], catalog=catalog)
    return g, text_recommend(g, s, catalog)


if __name__ == "__main__":
    params = load_params()
    a2 = yaml.safe_load(open(ROOT / "params_a2.yaml"))
    upd = json.load(open(A2 / "curriculum_update.json"))
    courses = json.load(open(ROOT / "data/processed/courses.json"))
    json.dump(apply_update(courses, upd), open(A2 / "courses_v2.json", "w"), indent=1)
    v2 = load_catalog(A2 / "courses_v2.json", RULES_PATH)
    tpl, schemas = load_template("advisor_retrieval_v1")

    # ----------
    #  Shifted: programme_holdout under v2
    # ----------
    students = {s["student_id"]: s for s in read_jsonl(ROOT / "data/processed/students.jsonl")
                + read_jsonl(ROOT / "data/processed/students_augmented.jsonl")}
    rows, changed = [], 0
    for r in read_jsonl(SFT / "programme_holdout.jsonl"):
        q = {**r, "gold_json": r["gold_json"]}
        g, text = relabel(q, students[r["student_id"]], v2)
        if "student_id" in r["gold_json"]:
            g["student_id"] = r["gold_json"]["student_id"]  # A1 keeps the parent id for transcript_reorder children
        changed += g != r["gold_json"]
        new = make_row({**q, "gold_json": g, "gold_text": text}, r["query"], "shifted", students[r["student_id"]],
                       v2, tpl, schemas)
        rows.append({**new, "catalog_version": "v2", "label_changed_by_update": g != r["gold_json"],
                     "label_policy": "d6_repeat" if "REPEAT_FOR_GRADE_IMPROVEMENT" in g.get("warnings", []) else "a1"})
    write_jsonl(SFT / "shifted.jsonl", rows)
    print(f"shifted: {len(rows)} rows, answers changed by the update: {changed}")

    # ----------
    #  Retraining pool: new students and pairs under v2
    # ----------
    pp = {**params, "seeds": {**params["seeds"], "transcripts": a2["seeds"]["retrain_pool"],
                              "queries": a2["seeds"]["retrain_pool"]},
          "transcripts": {**params["transcripts"], "programmes": {"MTech-ICDT": 0.6, "MTech-CSE": 0.15,
                                                                  "MTech-AI": 0.1, "MTech-EE": 0.15}},
          "queries": {"min_pairs": 300}}
    pool_students = generate(v2, pp, n=120)
    for s in pool_students:
        s["student_id"] = "P" + s["student_id"]
    bad = [s["student_id"] for s in pool_students if not validate_transcript(s, v2)["valid"]]
    assert not bad, f"invalid pool transcripts: {bad[:5]}"
    pairs = build(pool_students, v2, pp)
    by_id = {s["student_id"]: s for s in pool_students}
    pool = [{**make_row(apply_d6({**q, "query_id": "P" + q["query_id"]}, by_id[q["student_id"]], v2), q["query_text"], "pool",
                        by_id[q["student_id"]], v2, tpl, schemas), "catalog_version": "v2"} for q in pairs]
    write_jsonl(A2 / "students_pool.jsonl", pool_students)
    write_jsonl(SFT / "pool.jsonl", pool)
    print(f"pool: {len(pool_students)} students, {len(pool)} pairs,",
          dict(Counter(r["programme"] for r in pool)), dict(Counter(r["intent"] for r in pool)))

    # ----------
    #  Google Forms questions: unlabelled traffic
    # ----------
    forms = []
    for f in read_jsonl(ROOT / "data/raw/forms/responses_anonymised.jsonl"):
        intent = INTENT_OF_KIND[f["question_kind"]]
        sem = max(int(f["semester"] or 1) - 1, 0)
        student = (f"{f['programme']}, {f['stream']} stream, {f['track'].lower()} track, {sem} semester(s) completed. "
                   f"Completed (as written by the student): {f['courses_completed'] or 'not given'}.")
        forms.append({"query_id": f["response_id"], "split": "forms", "intent": intent, "programme": f["programme"],
                      "template_family": "real_form", "question_kind": f["question_kind"], "provenance": f["provenance"],
                      "query": f["question"], "student": student, "n_courses": None, "augmentation": None,
                      "prompt": render(tpl, programme=f["programme"], track=f["track"].lower(), rules="see the course list",
                                       catalog="\n".join(f"{c['code']} | {c['title']}" for c in json.load(open(A2 / "courses_v2.json"))
                                                         if f["programme"] in (c.get("programmes") or [])),
                                       student=student, term="2026-27 Sem-II", query=f["question"], schema=schemas[intent])})
    write_jsonl(SFT / "forms.jsonl", forms)
    print(f"forms: {len(forms)} unlabelled rows")
