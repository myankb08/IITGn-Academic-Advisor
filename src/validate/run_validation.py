"""Run every applicable validation check for one stage and write results.csv, results.md, failures.json.

    .venv/bin/python -m src.validate.run_validation --stage processed
    .venv/bin/python -m src.validate.run_validation --stage raw --report-only
    .venv/bin/python -m src.validate.run_validation --stage corrupted --report-only

Exits non-zero when any check fails, unless --report-only. In the corrupted stage it also writes
faults_caught.json/.md, which says for every injected fault whether its target check caught it.
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from src.validate.checks import ROOT, Bundle, applicable, run_check

RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
CORRUPTED = ROOT / "data" / "interim" / "corrupted"
SPLITS = ROOT / "data" / "splits"
LABELS = ROOT / "data" / "labels"
OUT = ROOT / "supporting_files" / "B_validation"


def read_json(path):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else None


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return None
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def read_splits(folder):
    files = sorted(Path(folder).glob("*.csv"))
    return {f.stem: pd.read_csv(f) for f in files} or None


def read_labels(folder):
    rows = []
    for f in sorted(Path(folder).rglob("audited.jsonl")):
        rows += read_jsonl(f) or []
    return rows or None


def load_bundle(stage):
    from src.engine.catalog import load_catalog
    timetable = read_jsonl(RAW / "extracted" / "timetable_rows.jsonl")
    if stage == "raw":
        return Bundle(stage, raw_catalog=read_json(RAW / "catalog_raw.json"),
                      rules=read_json(PROCESSED / "rules.json"), timetable_rows=timetable,
                      paths={"catalog_raw": "data/raw/catalog_raw.json"})
    ref = load_catalog(PROCESSED / "courses.json", PROCESSED / "rules.json")
    if stage == "processed":
        return Bundle(stage, courses=read_json(PROCESSED / "courses.json"), rules=read_json(PROCESSED / "rules.json"),
                      timetable_rows=timetable, students=read_jsonl(PROCESSED / "students.jsonl"),
                      queries=read_jsonl(PROCESSED / "queries.jsonl"), splits=read_splits(SPLITS),
                      labels=read_labels(LABELS), catalog=ref, ref_catalog=ref,
                      paths={"data": "data/processed", "splits": "data/splits", "labels": "data/labels"})
    if not (CORRUPTED / "faults.json").exists():
        sys.exit("data/interim/corrupted/faults.json missing, run: .venv/bin/python -m src.validate.corrupt")
    bad = load_catalog(CORRUPTED / "courses.json", CORRUPTED / "rules.json")
    return Bundle(stage, courses=read_json(CORRUPTED / "courses.json"), rules=read_json(CORRUPTED / "rules.json"),
                  timetable_rows=timetable, students=read_jsonl(CORRUPTED / "students.jsonl"),
                  queries=read_jsonl(CORRUPTED / "queries.jsonl"), splits=read_splits(CORRUPTED / "splits"),
                  labels=read_labels(CORRUPTED / "labels"), catalog=bad, ref_catalog=ref,
                  paths={"data": "data/interim/corrupted", "gold_reference": "data/processed"})


def run(stage):
    b = load_bundle(stage)
    return [run_check(meta, b) for meta in applicable(stage)]


def fault_coverage(rows):
    faults = read_json(CORRUPTED / "faults.json")["faults"]
    by_id = {r["check_id"]: r for r in rows}
    out = []
    for f in faults:
        r = by_id.get(f["check_id"])
        blob = json.dumps(r["all_failures"]) if r else ""
        caught = bool(r) and r["status"] == "fail" and all(tok in blob for tok in f["match"])
        out.append({**f, "check_status": r["status"] if r else "missing", "caught": caught})
    return out


def md_table(df, cols):
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df[cols].iterrows():
        lines.append("| " + " | ".join(str(r[c]).replace("|", "/").replace("\n", " ") for c in cols) + " |")
    return "\n".join(lines)


def write(rows, stage, out):
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([{k: v for k, v in r.items() if k != "all_failures"} for r in rows])
    df["examples"] = df["examples"].map(lambda e: json.dumps(e, ensure_ascii=False))
    df.to_csv(out / "results.csv", index=False)
    with open(out / "failures.json", "w") as f:
        json.dump({r["check_id"]: r["all_failures"] for r in rows if r["all_failures"]}, f, indent=1, ensure_ascii=False)
    counts = df.status.value_counts().to_dict()
    text = [f"# Validation results: {stage}", "",
            f"Checks run: {len(df)}. " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) + ".", "",
            md_table(df, ["check_id", "description", "requirement", "target", "status", "n_failures", "note"]), ""]
    if stage == "corrupted":
        cov = fault_coverage(rows)
        with open(out / "faults_caught.json", "w") as f:
            json.dump(cov, f, indent=1)
        cdf = pd.DataFrame(cov)
        text += ["## Injected faults", "",
                 f"Caught {int(cdf.caught.sum())} of {len(cdf)} injected faults.", "",
                 md_table(cdf, ["fault_id", "description", "check_id", "check_status", "caught"]), ""]
    text += ["Failure examples (first 8 per check) are in results.csv, all failures in failures.json.", ""]
    (out / "results.md").write_text("\n".join(text))
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=["raw", "processed", "corrupted"], required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    out = Path(args.out) if args.out else OUT / args.stage
    if not out.is_absolute():
        out = ROOT / out
    rows = run(args.stage)
    df = write(rows, args.stage, out)
    for r in rows:
        print(f"{r['check_id']} {r['status']:<4} {r['n_failures']:>4}  {r['description']}")
    print(f"results in {out.relative_to(ROOT)}")
    failed = int((df.status == "fail").sum())
    if args.stage == "corrupted":
        cov = fault_coverage(rows)
        print(f"injected faults caught: {sum(c['caught'] for c in cov)}/{len(cov)}")
    if failed and not args.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
