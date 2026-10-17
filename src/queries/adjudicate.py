"""Merge A1/A2 exports with the human adjudication CSV into data/labels/audited.jsonl.

Real run:    .venv/bin/python -m src.queries.adjudicate
Fixture run: .venv/bin/python -m src.queries.adjudicate --fixture
Items where A1 and A2 agree on decision and category (and on edit text when decision = edit)
are taken as agreed. Every other item needs a row in adjudication.csv; a row there always wins.
"""
import argparse
import csv
import json
from pathlib import Path

from src.queries.ls_export import CATEGORIES, DECISIONS, read_export

ROOT = Path(__file__).resolve().parents[2]
ROUNDS = {1: "v1", 2: "v2"}
ADJ_COLS = ["item_id", "final_decision", "final_category", "final_edit", "decided_by"]


def round_paths(rnd, fixture):
    if fixture:
        base = ROOT / "tests/fixtures"
        return (base / f"fixture_round{rnd}_export_A1.json", base / f"fixture_round{rnd}_export_A2.json",
                base / f"fixture_round{rnd}_adjudication.csv")
    base = ROOT / f"data/labels/round{rnd}"
    return base / "export_A1.json", base / "export_A2.json", base / "adjudication.csv"


def read_adjudication(path):
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = set(ADJ_COLS) - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"{path.relative_to(ROOT)} lacks columns {sorted(missing)}")
        rows = {r["item_id"].strip(): {k: (r[k] or "").strip() for k in ADJ_COLS} for r in reader if r["item_id"].strip()}
    for r in rows.values():
        if r["final_decision"] not in DECISIONS or r["final_category"] not in CATEGORIES:
            raise SystemExit(f"bad label in adjudication row {r}")
        if r["final_decision"] == "edit" and not r["final_edit"]:
            raise SystemExit(f"adjudication row {r['item_id']} is edit without final_edit")
        if not r["decided_by"]:
            raise SystemExit(f"adjudication row {r['item_id']} has no decided_by")
    return rows


def agreed(a, b):
    if a["decision"] != b["decision"] or a["error_category"] != b["error_category"]:
        return False
    return a["decision"] != "edit" or a["edit_text"] == b["edit_text"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true", help="read fixtures from tests/fixtures, write under supporting_files")
    args = ap.parse_args()
    out_path = ROOT / ("supporting_files/C_labelling/fixture_audited.jsonl" if args.fixture else "data/labels/audited.jsonl")
    log_path = ROOT / "supporting_files/C_labelling" / ("fixture_adjudication_log.json" if args.fixture else "adjudication_log.json")
    records, log, unresolved = [], {}, []
    for rnd, gver in ROUNDS.items():
        p1, p2, padj = round_paths(rnd, args.fixture)
        if not (p1.exists() and p2.exists()):
            log[f"round{rnd}"] = "skipped, exports not found"
            continue
        r1, w1 = read_export(p1, "A1")
        r2, w2 = read_export(p2, "A2")
        adj = read_adjudication(padj)
        stats = {"agreed": 0, "adjudicated": 0, "unresolved": 0, "warnings": w1 + w2,
                 "unused_adjudication_rows": sorted(set(adj) - (set(r1) & set(r2)))}
        for item_id in sorted(set(r1) & set(r2)):
            a, b = r1[item_id], r2[item_id]
            if item_id in adj:
                f = adj[item_id]
                final = (f["final_decision"], f["final_category"], f["final_edit"] or None, f["decided_by"])
                stats["adjudicated"] += 1
            elif agreed(a, b):
                final = (a["decision"], a["error_category"], a["edit_text"] or None, "agreement")
                stats["agreed"] += 1
            else:
                unresolved.append(item_id)
                stats["unresolved"] += 1
                continue
            d = a["data"]
            records.append({
                "item_id": item_id, "query_id": a["query_id"], "round": rnd, "guidelines_version": gver,
                "para_query": d.get("para_query"), "para_justification": d.get("para_justification"),
                "A1": {k: a[k] for k in ["decision", "error_category", "edit_text"]},
                "A2": {k: b[k] for k in ["decision", "error_category", "edit_text"]},
                "final_decision": final[0], "final_category": final[1], "final_edit": final[2], "decided_by": final[3],
            })
        log[f"round{rnd}"] = stats
    log["unresolved_items"] = unresolved
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
    if unresolved:
        raise SystemExit(f"{len(unresolved)} items need a row in adjudication.csv: {unresolved}; see {log_path.relative_to(ROOT)}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(records)} audited items -> {out_path.relative_to(ROOT)}")
    print(json.dumps({k: v for k, v in log.items() if k != "unresolved_items"}, indent=2))


if __name__ == "__main__":
    main()
