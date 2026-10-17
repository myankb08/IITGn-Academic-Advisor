"""Rule engine tests on the hand-written fixture in tests/fixtures (not real course data)."""
import json
from pathlib import Path

import pytest

from src.engine.catalog import load_catalog, load_params, resolve_rules, term_label
from src.engine.prereq_graph import build_graph, find_cycles, missing_prereq_codes, topological_order
from src.engine.rule_engine import (eligibility, recommend_electives, remaining_requirements,
                                    upcoming_term, validate_transcript)
from src.engine.synth_transcripts import generate, inject_violations
from src.queries.make_queries import build

FIX = Path(__file__).resolve().parent / "fixtures"
SEM_I = "2026-27 Sem-I"
SEM_II = "2026-27 Sem-II"


@pytest.fixture(scope="module")
def cat():
    return load_catalog(FIX / "courses.json", FIX / "rules.json")


def student(transcript, stream="AI/ML", track="thesis", sem=2, programme="MTech-AI", ug=()):
    return {"student_id": "T0001", "programme": programme, "stream": stream, "track": track,
            "admit_year": {0: 2026, 1: 2026, 2: 2025, 3: 2025}[sem], "semesters_completed": sem, "seed": 0,
            "ug_background": list(ug),
            "transcript": [{"code": c, "semester": s, "credits": cr, "grade": g} for c, s, cr, g in transcript]}


def test_terms():
    assert term_label(2025, 1) == "2025-26 Sem-I"
    assert term_label(2025, 3) == SEM_I
    assert upcoming_term(student([], sem=2)) == SEM_I
    assert upcoming_term(student([], sem=1)) == SEM_II


def test_graph(cat):
    g = build_graph(cat)
    assert g.edges["FX 678", "FX 667"]["type"] == "hard"
    assert g.edges["UG 101", "FX 666"]["type"] == "recommended"
    assert g.nodes["UG 101"]["category"] == "ug_background"
    assert find_cycles(g) == []
    order = topological_order(g)
    assert order.index("FX 678") < order.index("FX 667") < order.index("FX 613")
    assert missing_prereq_codes(g) == []


def test_eligibility_unmet_hard_prereq(cat):
    s = student([("FX 610", 1, 4, "A")])
    out = eligibility(s, "FX 667", catalog=cat)
    assert out["term"] == SEM_I and out["eligible"] is False
    assert out["unmet_prerequisites"] == ["FX 678"]
    assert "PREREQ_UNMET" in out["reason_codes"] and out["sources"]["PREREQ_UNMET"]
    s2 = student([("FX 678", 1, 4, "B")])
    assert eligibility(s2, "FX 667", catalog=cat)["eligible"] is True


def test_eligibility_offering(cat):
    s = student([("FX 612", 1, 4, "A")], stream="Systems", programme="MTech-CSE")
    out = eligibility(s, "FX 616", catalog=cat)
    assert out["reason_codes"] == ["NOT_OFFERED_NEXT_TERM"] and "Timetable" in out["sources"]["NOT_OFFERED_NEXT_TERM"]
    assert "NOT_OFFERED_IN_PARITY" in eligibility(s, "FX 621", catalog=cat)["reason_codes"]
    s1 = student([("FX 612", 1, 4, "A")], stream="Systems", programme="MTech-CSE", sem=1)
    out = eligibility(s1, "FX 616", catalog=cat)
    assert out["eligible"] is True and out["warnings"] == ["OFFERING_UNKNOWN"]
    assert "NOT_OFFERED_IN_PARITY" in eligibility(s1, "FX 610", catalog=cat)["reason_codes"]
    assert eligibility(s1, "FX 621", catalog=cat)["eligible"] is True


def test_eligibility_taken_failed_unknown(cat):
    s = student([("FX 678", 1, 4, "F"), ("FX 610", 1, 4, "A")])
    assert eligibility(s, "FX 667", catalog=cat)["unmet_prerequisites"] == ["FX 678"]
    assert "ALREADY_TAKEN" in eligibility(s, "FX 610", catalog=cat)["reason_codes"]
    assert eligibility(s, "NOPE 1", catalog=cat)["reason_codes"] == ["UNKNOWN_COURSE"]
    assert eligibility(s, "UG 101", catalog=cat)["reason_codes"] == ["NOT_MTECH_COURSE"]


def test_recommended_background_warning(cat):
    out = eligibility(student([]), "FX 666", catalog=cat)
    assert out["eligible"] is True
    assert out["warnings"] == ["MISSING_RECOMMENDED_BACKGROUND"]
    assert out["missing_recommended"] == [["UG 101", "UG 102"]]
    assert eligibility(student([], ug=["UG 102"]), "FX 666", catalog=cat)["warnings"] == []


def test_other_warnings(cat):
    s = student([("FX 431", 1, 4, "A"), ("FX 434", 1, 4, "A")], stream="Systems", programme="MTech-CSE")
    assert "NOT_COUNTED_BELOW_600_CAP" in eligibility(s, "FX 435", catalog=cat)["warnings"]
    assert "OTHER_STREAM_CORE_AS_ELECTIVE" in eligibility(student([]), "FX 612", catalog=cat)["warnings"]


def test_remaining_core(cat):
    s = student([("FX 610", 1, 4, "A"), ("FX 678", 1, 4, "A"), ("FX 666", 1, 4, "B"),
                 ("REQ-AAROHAN", 1, 2, "P"), ("REQ-THESIS", 2, 8, "A")])
    out = remaining_requirements(s, catalog=cat)
    assert out["compulsory_missing"] == ["FX 621"]
    assert out["stream_core_missing"] == ["FX 667"]
    assert out["own_basket"]["gap"] == 0 and out["other_basket"]["gap"] == 4
    assert out["requirements"]["writing"]["status"] == "missing"
    assert out["requirements"]["aarohan"]["status"] == "done"
    assert out["coursework"] == {"earned": 12, "min": 32, "gap": 20, "includes_aarohan": False}
    assert out["thesis"]["gap"] == 24
    assert out["total"] == {"earned": 22, "min": 82, "gap": 60}
    json.dumps(out)


def test_below_600_cap(cat):
    s = student([("FX 431", 1, 4, "A"), ("FX 434", 1, 4, "A"), ("FX 435", 2, 4, "A")],
                stream="Systems", programme="MTech-CSE")
    out = remaining_requirements(s, catalog=cat)
    assert out["below_600"]["excess_courses"] == ["FX 435"]
    assert out["coursework"]["earned"] == 8
    assert "BELOW_600_CAP" in validate_transcript(s, catalog=cat)["violation_types"]


def test_recommendation_stable_and_ranked(cat):
    s = student([("FX 610", 1, 4, "A"), ("FX 678", 1, 4, "A")], programme="MTech-CSE")
    a = recommend_electives(s, k=3, catalog=cat)
    b = recommend_electives(json.loads(json.dumps(s)), k=3, catalog=cat)
    assert a == b
    recs = a["recommendations"]
    assert recs[0]["course"] == "FX 666" and recs[0]["reason_code"] == "OWN_BASKET_GAP"
    assert recs[1]["reason_code"] == "OTHER_BASKET_GAP"
    taken = {e["code"] for e in s["transcript"]}
    assert not taken & {r["course"] for r in recs}
    assert all(eligibility(s, r["course"], a["term"], catalog=cat)["eligible"] for r in recs)


def test_validate_detects_violations(cat):
    s = student([("FX 678", 1, 4, "A"), ("FX 667", 1, 4, "A"), ("FX 678", 2, 4, "B"),
                 ("ZZ 999", 2, 4, "A"), ("FX 610", 2, 4, "A"), ("FX 613", 2, 5, "A")])
    types = validate_transcript(s, catalog=cat)["violation_types"]
    for t in ("PREREQ_SAME_OR_LATER_TERM", "DUPLICATE_COURSE", "UNKNOWN_CODE",
              "NOT_OFFERED_IN_PARITY", "CREDIT_MISMATCH"):
        assert t in types
    s1 = student([("FX 616", 1, 4, "A")], stream="Systems", sem=1)
    types = validate_transcript(s1, catalog=cat)["violation_types"]
    assert "NOT_OFFERED_IN_TERM" in types and "PROGRAMME_STREAM_MISMATCH" in types


def test_semester_cap(cat):
    rows = [(c, 1, 4, "A") for c in ("FX 610", "FX 678", "FX 666", "FX 612", "FX 615", "FX 619", "FX 620")]
    assert "SEMESTER_CREDIT_CAP" in validate_transcript(student(rows, sem=1), catalog=cat)["violation_types"]


def test_generator_valid_and_deterministic(cat):
    params = load_params()
    a = generate(cat, params, 60)
    assert a == generate(cat, params, 60)
    assert all(validate_transcript(s, cat)["valid"] for s in a)
    assert all(set(s["ug_background"]) <= {"UG 101", "UG 102"} for s in a)
    bad = inject_violations(a, 14, cat, params["seeds"]["transcripts"])
    assert all(s["injected_violation"] in validate_transcript(s, cat)["violation_types"] for s in bad)


def test_queries_balanced(cat):
    params = load_params()
    rows = build(generate(cat, params), cat, params)
    assert len(rows) >= params["queries"]["min_pairs"]
    intents = [r["intent"] for r in rows]
    assert {i: intents.count(i) for i in set(intents)} == {"remaining_core": 134, "eligibility": 134,
                                                         "elective_recommendation": 134}
    assert len({r["template_family"] for r in rows}) >= 6
    elig = [r["gold_json"] for r in rows if r["intent"] == "eligibility"]
    assert 0.4 < sum(g["eligible"] for g in elig) / len(elig) < 0.6
    not_ok = {c for g in elig if not g["eligible"] for c in g["reason_codes"]}
    assert {"PREREQ_UNMET", "ALREADY_TAKEN", "NOT_OFFERED_NEXT_TERM", "NOT_OFFERED_IN_PARITY"} <= not_ok
    assert any(g["eligible"] and g["warnings"] for g in elig)


def test_structured_rules_track_scoping(cat):
    rec = lambda v, tracks: {"value": v, "applies_to": {"tracks": tracks}, "source_doc": "fixture", "source_page": 1}
    raw = {"rules": {"coursework_min_credits.thesis": rec(32, ["thesis"]),
                     "coursework_min_credits.coursework": rec(48, ["coursework"]),
                     "thesis_min_credits.thesis": rec(32, ["thesis"]),
                     "thesis_min_credits.coursework": rec(0, ["coursework"]),
                     "applications_of_ai_course": rec("FX 621", ["thesis", "coursework"])},
           "requirement_codes": {"writing": "REQ-WRITING"}}
    rs = resolve_rules(raw, list(cat.courses.values()))
    assert rs.get("coursework_min_credits", "thesis") == 32
    assert rs.get("coursework_min_credits", "coursework") == 48
    assert rs.get("thesis_min_credits", "coursework") == 0
    assert rs.ai_applications_course == "FX 621"
    assert rs.requirement_codes == {"writing": "REQ-WRITING"}
