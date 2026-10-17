"""Transcript augmentations that create derived students in data/processed/students_augmented.jsonl.

- transcript_reorder: the same transcript entries in a seeded shuffled order. The student state is
  unchanged, so the gold answer must be identical (verify.py checks this).
- transcript_length: the student moved back to an earlier snapshot (k < semesters_completed, only
  entries of semesters 1..k kept). This is a new state, so the query text (profile, term) and the
  gold answer are recomputed with the rule engine and the pair is a new derived pair.
"""
import argparse
import random

from src.augment.common import (INTERIM, QUERIES, STUDENTS, STUDENTS_AUG, child, gold_for, read_jsonl,
                                write_jsonl)
from src.engine.catalog import load_catalog, load_params
from src.engine.rule_engine import upcoming_term
from src.queries.make_queries import FAMILIES, _profile, text_eligibility, text_recommend, text_remaining

OUT = INTERIM / "aug_transcript.jsonl"


def reorder_student(s, rng):
    t = list(s["transcript"])
    if len(t) > 1:
        original = list(t)
        for _ in range(5):
            rng.shuffle(t)
            if t != original:
                break
    return {**s, "student_id": f"{s['student_id']}-R", "transcript": t,
            "derived_from": s["student_id"], "derivation": "transcript_reorder"}


def truncate_student(s, k):
    return {**s, "student_id": f"{s['student_id']}-L{k}", "semesters_completed": k,
            "transcript": [e for e in s["transcript"] if int(e["semester"]) <= k],
            "derived_from": s["student_id"], "derivation": "transcript_length"}


def render_query(row, student, catalog):
    family = row["template_family"]
    t_idx = int(row["template_id"].rsplit("_t", 1)[1]) - 1
    target = row.get("target_course")
    fill = {"profile": _profile(student), "course": target, "term": upcoming_term(student), "k": 3,
            "title": catalog.course(target)["title"] if target and catalog.course(target) else None,
            "unit_word": "thesis" if student["track"] == "thesis" else "project"}
    return FAMILIES[row["intent"]][family][t_idx].format(**fill)


def gold_text_for(row, gold, student, catalog):
    if row["intent"] == "remaining_core":
        return text_remaining(gold, catalog, row["template_family"])
    if row["intent"] == "eligibility":
        return text_eligibility(gold, catalog, student)
    return text_recommend(gold, student, catalog)


def augment(rows, students, catalog, seed):
    by_id = {s["student_id"]: s for s in students}
    kids, derived = [], {}
    for r in rows:
        s = by_id[r["student_id"]]
        rng = random.Random(f"{seed}:{r['query_id']}:transcript")
        if len(s["transcript"]) > 1:
            rs = derived.setdefault(f"{s['student_id']}-R", reorder_student(s, random.Random(f"{seed}:{s['student_id']}:reorder")))
            kids.append(child(r, "transcript_reorder", "R", student_id=rs["student_id"]))
        if s["semesters_completed"] >= 1:
            k = rng.randrange(0, s["semesters_completed"])
            ts = derived.setdefault(f"{s['student_id']}-L{k}", truncate_student(s, k))
            gold = gold_for(r, ts, catalog)
            if r["intent"] == "elective_recommendation" and not gold["recommendations"]:
                continue
            kids.append(child(r, "transcript_length", "L", student_id=ts["student_id"],
                              query_text=render_query(r, ts, catalog), gold_json=gold,
                              gold_text=gold_text_for(r, gold, ts, catalog)))
    return kids, list(derived.values())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queries", default=str(QUERIES))
    ap.add_argument("--students", default=str(STUDENTS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--students-out", default=str(STUDENTS_AUG))
    args = ap.parse_args()
    params = load_params()
    catalog = load_catalog()
    rows = [r for r in read_jsonl(args.queries) if r.get("augmentation") is None]
    kids, derived = augment(rows, read_jsonl(args.students), catalog, params["seeds"]["augmentation"])
    write_jsonl(args.out, kids)
    write_jsonl(args.students_out, sorted(derived, key=lambda s: s["student_id"]))
    n_r = sum(k["augmentation"] == "transcript_reorder" for k in kids)
    print(f"transcript_reorder: {n_r}, transcript_length: {len(kids) - n_r}, derived students: {len(derived)}")


if __name__ == "__main__":
    main()
