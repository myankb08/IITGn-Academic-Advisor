"""Build supporting_files/B_validation/before_after.md from the raw and processed results.

    .venv/bin/python -m src.validate.before_after

For each check run on the raw catalog it lists the raw failures, the cleaning_changes.csv rows
(by line number) that touched the failing records, and the failures left after cleaning.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "supporting_files" / "B_validation"
CHANGES = ROOT / "supporting_files" / "A_collection" / "cleaning_changes.csv"
FIELDS = {"V01": None, "V02": {"code", "record"}, "V03": {"credits"}, "V05": {"code", "title", "record"},
          "V06": {"record"}, "V07": {"record"}, "V08": {"title"}, "V09": {"title"}, "V10": {"record", "title"},
          "V15": {"credits"}}


def failing_ids(failures):
    ids = set()
    for f in failures:
        for k in ("id", "duplicate_of"):
            if f.get(k):
                ids.add(str(f[k]))
        ids.update(str(x) for x in f.get("ids") or [])
    return ids


def main():
    raw = pd.read_csv(OUT / "raw" / "results.csv")
    proc = pd.read_csv(OUT / "processed" / "results.csv").set_index("check_id")
    raw_fail = json.loads((OUT / "raw" / "failures.json").read_text())
    changes = pd.read_csv(CHANGES, dtype=str).fillna("")
    changes["line"] = changes.index + 2
    lines = ["# Before and after cleaning", "",
             "Built by `src/validate/before_after.py` from `raw/results.csv`, `processed/results.csv` and "
             "`supporting_files/A_collection/cleaning_changes.csv` (line numbers count the header as line 1). "
             "Raw checks run on `data/raw/catalog_raw.json`, after checks on `data/processed/courses.json`.", "",
             "| check | description | failures on raw | fix applied (cleaning_changes.csv lines) | status after | failures after |",
             "|---|---|---|---|---|---|"]
    for r in raw.itertuples():
        ids = failing_ids(raw_fail.get(r.check_id, []))
        fields = FIELDS.get(r.check_id)
        # a dropped record (field "record") also resolves every failure on it
        hit = changes[changes.record_id.isin(ids)
                      & (changes.field.isin(list(fields) + ["record"]) if fields else True)]
        if len(hit):
            kinds = ", ".join(sorted(set(hit.field)))
            nums = ", ".join(str(n) for n in hit.line.tolist()[:12]) + (" ..." if len(hit) > 12 else "")
            fix = f"{len(hit)} rows ({kinds}): {nums}"
        else:
            fix = "none logged" if r.n_failures else "-"
        after = proc.loc[r.check_id] if r.check_id in proc.index else None
        lines.append(f"| {r.check_id} | {r.description} | {r.n_failures} ({r.status}) | {fix} | "
                     f"{after.status if after is not None else 'n/a'} | {after.n_failures if after is not None else 'n/a'} |")
    lines += ["", "V01 checks a different schema in each layer (raw extraction format vs the processed contract), "
              "so its two columns are not a before/after pair of the same rule.", ""]
    (OUT / "before_after.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
