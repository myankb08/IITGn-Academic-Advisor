"""Disagreement score tests on the fixture catalog (not real course data)."""
from pathlib import Path

import pytest

from src.active.al_vs_random import al_pick, metrics
from src.active.base_model_answers import parse_json
from src.active.disagreement import MAX_SCORE, score
from src.engine.catalog import load_catalog

FIX = Path(__file__).resolve().parent / "fixtures"
S = {"student_id": "T1", "programme": "MTech-AI", "stream": "AI/ML", "track": "thesis", "admit_year": 2025,
     "semesters_completed": 2, "seed": 0, "ug_background": [], "transcript": []}


@pytest.fixture(scope="module")
def cat():
    return load_catalog(FIX / "courses.json", FIX / "rules.json")


def test_scores(cat):
    row = {"intent": "eligibility", "gold_json": {"eligible": False, "unmet_prerequisites": ["FX 678"]}}
    same = {"parsed": {"eligible": False, "unmet_prerequisites": ["FX 678"], "reason_codes": []}}
    assert score(same, row, S, cat)[:2] == (0.0, [])
    wrong = {"parsed": {"eligible": True, "unmet_prerequisites": ["XY 999"]}}
    sc, fails, _ = score(wrong, row, S, cat)
    assert sc == 3.0 and set(fails) == {"wrong_eligibility", "hallucinated_code"}
    assert score({"parsed": None}, row, S, cat) == (MAX_SCORE, ["invalid_json"], {})


def test_parse_json():
    assert parse_json('```json\n{"eligible": true}\n```') == {"eligible": True}
    assert parse_json("not json") is None


def test_al_pick_orders_by_score():
    pool = [{"score": s, "failed": s > 0, "failures": ["x"] if s else [], "programme": "P", "intent": "i"}
            for s in (0, 3, 1, 0, 2)]
    assert [p["score"] for p in al_pick(pool, 3, 11)] == [3, 2, 1]
    assert metrics(al_pick(pool, 3, 11), pool)["failures_captured"] == 1.0
