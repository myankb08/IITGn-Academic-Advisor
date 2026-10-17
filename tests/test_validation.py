"""Part B validation suite: processed data must pass every check, injected faults must be caught."""
import pytest

from src.validate import corrupt
from src.validate.checks import applicable
from src.validate.run_validation import CORRUPTED, fault_coverage, load_bundle, run_check

PROCESSED_CHECKS = applicable("processed")


@pytest.fixture(scope="module")
def processed():
    return load_bundle("processed")


@pytest.mark.parametrize("meta", PROCESSED_CHECKS, ids=[m["check_id"] for m in PROCESSED_CHECKS])
def test_processed(meta, processed):
    row = run_check(meta, processed)
    if row["status"] == "skip":
        pytest.skip(row["note"])
    assert row["status"] != "fail", f"{row['check_id']} {row['description']}: {row['n_failures']} failures, e.g. {row['examples'][:3]}"


@pytest.fixture(scope="module")
def corrupted_rows():
    corrupt.main()
    b = load_bundle("corrupted")
    return [run_check(m, b) for m in applicable("corrupted")]


def test_every_injected_fault_is_caught(corrupted_rows):
    cov = fault_coverage(corrupted_rows)
    assert len(cov) >= 7
    missed = [c for c in cov if not c["caught"]]
    assert not missed, missed


def test_corruption_is_seeded(corrupted_rows):
    first = (CORRUPTED / "faults.json").read_text()
    corrupt.main()
    assert (CORRUPTED / "faults.json").read_text() == first
