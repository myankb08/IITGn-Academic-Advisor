"""Turn a reviewed adjudication worksheet into data/labels/round{N}/adjudication.csv.

A row is resolved when the reviewer either writes y in review_ok (the proposal becomes final) or fills the
final_* columns and decided_by themselves (their own call wins). Unresolved rows stop the script.
"""
import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_COLS = ["item_id", "final_decision", "final_category", "final_edit", "decided_by"]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--reviewer", required=True, help="annotator id(s) who reviewed, e.g. A1 or A1+A2")
    args = ap.parse_args()
    base = ROOT / f"data/labels/round{args.round}"
    rows = list(csv.DictReader(open(base / "adjudication_worksheet.csv", encoding="utf-8")))
    out, missing = [], []
    for r in rows:
        if r["final_decision"].strip():
            if not r["decided_by"].strip():
                missing.append(f"{r['item_id']} (final_* filled but decided_by empty)")
                continue
            out.append({k: r[k].strip() for k in OUT_COLS})
        elif r["review_ok"].strip().lower() in ("y", "yes"):
            out.append({"item_id": r["item_id"], "final_decision": r["proposed_decision"],
                        "final_category": r["proposed_category"], "final_edit": r["proposed_edit"],
                        "decided_by": f"{args.reviewer} (reviewed assistant proposal)"})
        else:
            missing.append(r["item_id"])
    if missing:
        raise SystemExit(f"{len(missing)} rows not reviewed yet: {missing}")
    with open(base / "adjudication.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLS)
        w.writeheader()
        w.writerows(out)
    own = sum(not r["decided_by"].endswith("(reviewed assistant proposal)") for r in out)
    print(f"round {args.round}: {len(out)} rows -> {(base / 'adjudication.csv').relative_to(ROOT)} "
          f"({len(out) - own} proposals approved, {own} reviewer's own calls)")


if __name__ == "__main__":
    main()
