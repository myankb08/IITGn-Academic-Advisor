"""Augmentation tests on the fixture catalog in tests/fixtures (not real course data)."""
import random
from pathlib import Path

import pytest

from src.augment.common import gold_for, resolve_codes
from src.augment.transcript_variants import reorder_student, truncate_student
from src.augment.typos_abbrev import augment_text, format_code
from src.augment.verify import check_child
from src.engine.catalog import load_catalog

FIX = Path(__file__).resolve().parent / "fixtures"
STREAMS = ["Signal Processing & Machine Learning", "AI/ML", "Systems", "Theory"]
TEXTS = [
    "I'm an MTech-AI student in the AI/ML stream (thesis track) and I have completed 2 semesters. "
    "Have I met the prerequisites for FX 667 (Deep Learning)?",
    "I'm an MTech-EE student in the Signal Processing & Machine Learning stream (thesis track) and I have "
    "completed 1 semester. Can I register for FX 613 in 2026-27 Sem-II after FX 610 and FX 691-XIV?",
    "Which electives would you recommend for my remaining requirements next semester?",
]


@pytest.fixture(scope="module")
def cat():
    return load_catalog(FIX / "courses.json", FIX / "rules.json")


def student(transcript, sem=2):
    return {"student_id": "T0001", "programme": "MTech-AI", "stream": "AI/ML", "track": "thesis",
            "admit_year": 2025, "semesters_completed": sem, "seed": 0, "ug_background": [],
            "transcript": [{"code": c, "semester": s, "credits": 4, "grade": "A"} for c, s in transcript]}


def pair(s, query_text, gold, intent="eligibility", target="FX 667", qid="Q1"):
    return {"query_id": qid, "student_id": s["student_id"], "template_id": "el_prereq_check_t1",
            "template_family": "el_prereq_check", "intent": intent, "target_course": target,
            "query_text": query_text, "gold_json": gold, "gold_text": "", "augmentation": None,
            "parent_query_id": None}


@pytest.mark.parametrize("seed", range(200))
def test_typos_never_change_course_codes(seed):
    known = {"FX 667", "FX 613", "FX 610", "FX 691-XIV"}
    prefixes = {"FX"}
    for text in TEXTS:
        out = augment_text(text, random.Random(seed), STREAMS, prefixes)
        assert resolve_codes(out, known) == resolve_codes(text, known)
        for name in ("MTech-AI", "MTech-EE", "AI/ML", "Signal Processing & Machine Learning", "2026-27 Sem-II"):
            if name in text:
                assert name in out


def test_typos_actually_change_text():
    changed = sum(augment_text(TEXTS[2], random.Random(s), STREAMS, {"FX"}) != TEXTS[2] for s in range(50))
    assert changed == 50


def test_code_format_variants_resolve():
    for fmt in ("compact", "lower_hyphen", "lower_space", "compact_lower"):
        assert resolve_codes(format_code("FX 691-XIV", fmt), {"FX 691-XIV"}) == ["FX 691-XIV"]
        assert resolve_codes(format_code("FX 610", fmt), {"FX 610"}) == ["FX 610"]


def test_verify_text_child(cat):
    s = student([("FX 678", 1)])
    students = {s["student_id"]: s}
    parent = pair(s, "Can I take FX 667 next term?", gold_for({"intent": "eligibility", "target_course": "FX 667"}, s, cat))
    ok = {**parent, "query_id": "Q1-T", "augmentation": "typo_abbrev", "parent_query_id": "Q1",
          "query_text": "Can i tkae fx-667 nxt term?"}
    assert check_child(ok, parent, students, cat)[:2] == (True, "ok")
    lost = {**ok, "query_text": "Can I take it next term?"}
    assert check_child(lost, parent, students, cat)[1] == "code_lost"
    added = {**ok, "query_text": "Can I take FX 667 or FX 613 next term?"}
    assert check_child(added, parent, students, cat)[1] == "code_added"


def test_verify_transcript_children(cat):
    s = student([("FX 678", 1), ("FX 610", 1), ("FX 667", 2)], sem=2)
    row = {"intent": "remaining_core", "target_course": None}
    parent = pair(s, "What is left?", gold_for(row, s, cat), intent="remaining_core", target=None)
    r = reorder_student(s, random.Random(0))
    assert r["transcript"] != s["transcript"]
    t = truncate_student(s, 1)
    students = {s["student_id"]: s, r["student_id"]: r, t["student_id"]: t}
    kid_r = {**parent, "query_id": "Q1-R", "augmentation": "transcript_reorder", "parent_query_id": "Q1",
             "student_id": r["student_id"]}
    assert check_child(kid_r, parent, students, cat)[:2] == (True, "ok")
    kid_l = {**parent, "query_id": "Q1-L", "augmentation": "transcript_length", "parent_query_id": "Q1",
             "student_id": t["student_id"], "gold_json": gold_for(row, t, cat)}
    ok, reason, info = check_child(kid_l, parent, students, cat)
    assert (ok, reason) == (True, "ok") and info["gold_changed_vs_parent"]
    stale = {**kid_l, "gold_json": parent["gold_json"]}
    assert check_child(stale, parent, students, cat)[1] == "gold_not_recomputed"


def test_verify_catches_changed_transcript(cat):
    s = student([("FX 678", 1), ("FX 610", 1)])
    bad = {**s, "student_id": "T0001-R", "transcript": s["transcript"][:1]}
    row = {"intent": "remaining_core", "target_course": None}
    parent = pair(s, "What is left?", gold_for(row, s, cat), intent="remaining_core", target=None)
    kid = {**parent, "query_id": "Q1-R", "augmentation": "transcript_reorder", "parent_query_id": "Q1",
           "student_id": bad["student_id"]}
    assert check_child(kid, parent, {s["student_id"]: s, bad["student_id"]: bad}, cat)[1] == "transcript_changed"
