"""Checks for the Assignment 2 data and scoring code (needs data/sft from src.model.build_sft and src.retrain.make_pool)."""
import hashlib

import pytest

from src.augment.common import ROOT, read_jsonl
from src.engine.catalog import load_catalog
from src.eval.metrics import score_row, summarise
from src.retrain.make_pool import relabel

SFT = ROOT / "data" / "sft"
pytestmark = pytest.mark.skipif(not (SFT / "shifted.jsonl").exists(), reason="data/sft not built")


def students():
    return {s["student_id"]: s for s in read_jsonl(ROOT / "data/processed/students.jsonl")
            + read_jsonl(ROOT / "data/processed/students_augmented.jsonl")}


def test_gold_checksum_unchanged():
    assert hashlib.sha256((ROOT / "data/gold/gold_test.jsonl").read_bytes()).hexdigest() == \
        "cd2e08dcb56f5716b06981e096c3c93fd417abab1989b5d22d45befeafbc383f"


def test_rule_engine_target_scores_perfectly():
    catalog, st = load_catalog(), students()
    rows = read_jsonl(SFT / "val.jsonl")
    s = summarise([score_row(r["target"], r, st[r["student_id"]], catalog) for r in rows])
    assert s["exact_match"] == 1.0 and s["violations"] == 0 and s["invented_codes"] == 0


def test_relabel_with_v1_reproduces_a1_gold():
    catalog, st = load_catalog(), students()
    for r in read_jsonl(SFT / "programme_holdout.jsonl"):
        if r["label_policy"] == "d6_repeat":
            continue  # D6 relabelled rows differ from A1 on purpose; checked in test_d6_labels
        g = relabel(r, st[r["student_id"]], catalog, d6=False)[0]
        g["student_id"] = r["gold_json"].get("student_id", g.get("student_id"))
        assert g == r["gold_json"], r["query_id"]


def test_pool_is_disjoint_from_evaluation_data():
    pool = read_jsonl(SFT / "pool.jsonl")
    evaluation = {r["student_id"] for s in ["val", "test", "gold", "shifted"] for r in read_jsonl(SFT / f"{s}.jsonl")}
    assert all(r["query_id"].startswith("P") and r["student_id"].startswith("P") for r in pool)
    assert not {r["student_id"] for r in pool} & evaluation


def test_d6_labels():
    """D6 rows: an A1 ALREADY_TAKEN label became eligible-for-repeat or kept another blocking reason; gold_a1 is unchanged."""
    from src.model.d6 import REPEAT
    for split in ["train", "val", "test", "gold"]:
        for r in read_jsonl(SFT / f"{split}.jsonl"):
            g = r["gold_json"]
            assert "ALREADY_TAKEN" not in g.get("reason_codes", []), r["query_id"]
            if r["label_policy"] == "d6_repeat":
                assert g["already_taken"] and REPEAT in g["warnings"]
    a1 = read_jsonl(SFT / "gold_a1.jsonl")
    assert sum("ALREADY_TAKEN" in r["gold_json"]["reason_codes"] for r in a1 if r["intent"] == "eligibility") == 6
