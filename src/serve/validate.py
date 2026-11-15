"""Offline validation of the served model on the bundled gold test set (CPU, int8).

Scores every gold row (or a fixed subset: the first N rows by item_id) with the Part C metrics and compares
the result with the reported values in MODEL_DIR/reported_gold.json (written at release time from a full run).
A metric passes when |measured - reported| <= tolerance (stated in that file). Exit code 1 on any mismatch.
Example: docker run --network none <image> validate
"""
import argparse
import json
import os
import platform
import sys
import time

from src.augment.common import ROOT, read_jsonl
from src.eval.metrics import score_row, summarise
from src.serve import core

KEYS = ["set_f1", "exact_match", "valid_json", "violations", "invented_rate"]


def run(subset=None):
    """Measured metrics (dict) on the gold set or its first `subset` rows."""
    rows = sorted(read_jsonl(ROOT / "data/sft/gold.jsonl"), key=lambda r: r["item_id"])[:subset]
    students = {s["student_id"]: s for s in read_jsonl(ROOT / "data/processed/students.jsonl")
                + read_jsonl(ROOT / "data/processed/students_augmented.jsonl")}
    t0, scores = time.time(), []
    for i, r in enumerate(rows, 1):
        text, conf = core.generate(r["prompt"])
        scores.append({"item_id": r["item_id"], "confidence": conf, "response": text,
                       **score_row(text, r, students[r["student_id"]], core.catalog)})
        print(f"[{i}/{len(rows)}] {r['item_id']} set_f1={scores[-1]['set_f1']:.2f} ({time.time() - t0:.0f}s)", flush=True)
    return {"n": len(rows), "subset": subset, "summary": summarise(scores), "seconds": round(time.time() - t0, 1),
            "sec_per_item": round((time.time() - t0) / len(rows), 2), "rows": scores}


def compare(measured, reported):
    """Rows of (metric, measured, reported, tolerance, passed)."""
    ref = reported["subset" if measured["subset"] else "full"]["summary"]
    tol = reported["tolerance"]
    return [{"metric": k, "measured": round(measured["summary"][k], 4), "reported": round(ref[k], 4), "tolerance": tol,
             "passed": abs(measured["summary"][k] - ref[k]) <= tol} for k in KEYS]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", type=int, default=None, help="only the first N gold rows by item_id (UI uses 5)")
    parser.add_argument("--out", default=os.environ.get("OUT_DIR", str(ROOT / "logs")) + "/validation.json", help="output JSON")
    parser.add_argument("--write_reported", action="store_true", help="release step: save this run as the reported values")
    parser.add_argument("--reported_out", default=None, help="where --write_reported writes (default MODEL_DIR/reported_gold.json)")
    opt = parser.parse_args()
    print(opt)

    core.load()
    m = run(opt.subset)
    info = {"model": core.INFO, "commit": core.COMMIT, "machine": platform.machine(), "cpu_count": os.cpu_count(),
            "python": platform.python_version()}
    path = core.MODEL_DIR / "reported_gold.json"
    if opt.write_reported:
        out_path = opt.reported_out or path
        rep = json.load(open(out_path)) if os.path.exists(out_path) else {"tolerance": 0.02}
        rep["subset" if opt.subset else "full"] = {"n": m["n"], "summary": m["summary"], **info}
        json.dump(rep, open(out_path, "w"), indent=1)
    result = {**info, "measured": {k: v for k, v in m.items() if k != "rows"}, "rows": m["rows"]}
    if path.exists():
        result["comparison"] = compare(m, json.load(open(path)))
    os.makedirs(os.path.dirname(opt.out), exist_ok=True)
    json.dump(result, open(opt.out, "w"), indent=1)

    print(json.dumps({k: round(v, 4) for k, v in m["summary"].items() if isinstance(v, float)}, indent=1))
    for c in result.get("comparison", []):
        print(f"{c['metric']:14s} measured {c['measured']:.4f}  reported {c['reported']:.4f}  tol {c['tolerance']}  {'PASS' if c['passed'] else 'FAIL'}")
    print(f"saved {opt.out}; {m['n']} items in {m['seconds']}s")
    sys.exit(0 if all(c["passed"] for c in result.get("comparison", [])) else 1)
