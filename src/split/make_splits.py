"""Write the split manifests from the student assignment and check the split invariants.

    .venv/bin/python -m src.split.make_splits

The assignment comes from src.split.assign_students (data/splits/assignment/): students are split
by programme (params.yaml `splits`), every MTech-ICDT student is in programme_holdout, and make_queries has
already rendered every pair with a template allowed in its split. So no pair is dropped here; the script
fails if a pair breaks a rule (test pair without the held-out template, train/val pair with it, student in two splits).
Augmented children (parent_query_id set) take the split of their root parent.
"""
import csv
import json
from collections import Counter
from pathlib import Path

import yaml

from src.split.assign_students import HOLDOUT_PROGRAMME, load_assignment

ROOT = Path(__file__).resolve().parents[2]
QUERIES = ROOT / "data" / "processed" / "queries.jsonl"
AUGMENTED = ROOT / "data" / "processed" / "queries_augmented.jsonl"
STUDENTS = ROOT / "data" / "processed" / "students.jsonl"
FORMS = ROOT / "data" / "raw" / "forms" / "responses_anonymised.jsonl"
SPLITS = ROOT / "data" / "splits"
EVIDENCE = ROOT / "supporting_files" / "E_splits"
COLUMNS = ["query_id", "student_id", "template_family", "template_id", "programme", "split"]
SPLIT_NAMES = ["train", "val", "test", "programme_holdout"]


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_split_map(folder=SPLITS):
    """query_id -> split from the train/val/test/programme_holdout manifests, or {} if none exist."""
    out = {}
    for s in SPLIT_NAMES:
        path = Path(folder) / f"{s}.csv"
        if path.exists():
            with open(path, newline="", encoding="utf-8") as f:
                out.update({r["query_id"]: r["split"] for r in csv.DictReader(f)})
    return out


def assign_rows(queries, programme_of, split_of, held):
    """Manifest rows plus the pairs that break a split rule (expected empty)."""
    rows, broken = [], []
    for q in sorted(queries, key=lambda q: q["query_id"]):
        split = split_of[q["student_id"]]
        is_held = held[q["template_family"]] == q["template_id"]
        row = {"query_id": q["query_id"], "student_id": q["student_id"], "template_family": q["template_family"],
               "template_id": q["template_id"], "programme": programme_of[q["student_id"]], "split": split}
        if split == "test" and not is_held:
            broken.append({**row, "reason": "test pair without the held-out template"})
        elif split in ("train", "val") and is_held:
            broken.append({**row, "reason": "train/val pair with a held-out template"})
        rows.append(row)
    return rows, broken


def add_children(rows, children):
    """Children inherit the split of their root parent; a child whose parent is unknown is listed as lost."""
    kept = {r["query_id"]: r for r in rows}
    parent = {c["query_id"]: c["parent_query_id"] for c in children}
    out, lost = [], []
    for c in sorted(children, key=lambda c: c["query_id"]):
        root, seen = c["parent_query_id"], set()
        while root in parent and root not in seen:
            seen.add(root)
            root = parent[root]
        base = kept.get(root)
        row = {"query_id": c["query_id"], "student_id": c.get("student_id") or (base or {}).get("student_id"),
               "template_family": c.get("template_family"), "template_id": c.get("template_id"),
               "programme": (base or {}).get("programme"), "split": (base or {}).get("split")}
        if base is None:
            lost.append({**row, "reason": "parent not in queries.jsonl", "parent_query_id": root})
        elif (str(row["student_id"]).split("-")[0], row["template_family"]) != (base["student_id"],
                                                                                base["template_family"]):
            lost.append({**row, "reason": "stale child: parent pair changed since augment ran", "parent_query_id": root})
        else:
            out.append(row)
    return out, lost


def overlap_checks(rows):
    by_split = {s: [r for r in rows if r["split"] == s] for s in SPLIT_NAMES}
    students = {s: {r["student_id"] for r in v} for s, v in by_split.items()}
    templates = {s: {r["template_id"] for r in v} for s, v in by_split.items()}
    checks = {}
    for i, a in enumerate(SPLIT_NAMES):
        for b in SPLIT_NAMES[i + 1:]:
            checks[f"students_{a}_x_{b}"] = len(students[a] & students[b])
    checks["templates_trainval_x_test"] = len((templates["train"] | templates["val"]) & templates["test"])
    checks["holdout_programme_in_train_val_test"] = sum(r["programme"] == HOLDOUT_PROGRAMME for s in ("train", "val", "test")
                                                        for r in by_split[s])
    checks["duplicate_query_ids"] = sum(n - 1 for n in Counter(r["query_id"] for r in rows).values() if n > 1)
    return checks


def counts(rows, key):
    out = {}
    for s in SPLIT_NAMES:
        out[s] = dict(sorted(Counter(r[key] for r in rows if r["split"] == s).items()))
    return out


def main():
    params = yaml.safe_load(open(ROOT / "params.yaml"))
    students = read_jsonl(STUDENTS)
    programme_of = {s["student_id"]: s["programme"] for s in students}
    split_of, held = load_assignment()
    queries = [q for q in read_jsonl(QUERIES) if not q.get("parent_query_id")]
    rows, broken = assign_rows(queries, programme_of, split_of, held)
    if broken:
        raise SystemExit(f"{len(broken)} pairs break the template rule, e.g. {broken[:3]}; rerun assign_students "
                         "then make_queries")
    intent_of = {q["query_id"]: q["intent"] for q in queries}
    children, lost = [], []
    if AUGMENTED.exists():
        aug = [c for c in read_jsonl(AUGMENTED) if c.get("parent_query_id")]
        children, lost = add_children(rows, aug)
        intent_of.update({c["query_id"]: c.get("intent") for c in aug})
    all_rows = rows + children
    SPLITS.mkdir(parents=True, exist_ok=True)
    for s in SPLIT_NAMES:
        with open(SPLITS / f"{s}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            w.writerows(r for r in all_rows if r["split"] == s)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with open(EVIDENCE / "dropped_rows.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS + ["reason", "parent_query_id"])
        w.writeheader()
        w.writerows(lost)
    for r in all_rows:
        r["intent"] = intent_of.get(r["query_id"])
    checks = overlap_checks(all_rows)
    summary = {
        "seed": params["seeds"]["splits"],
        "fractions": params["splits"],
        "holdout_programme": HOLDOUT_PROGRAMME,
        "held_out_templates": held,
        "n_queries_in": len(queries),
        "n_children_in": len(children) + len(lost),
        "rows_per_split": {s: sum(r["split"] == s for r in all_rows) for s in SPLIT_NAMES},
        "original_rows_per_split": {s: sum(r["split"] == s for r in rows) for s in SPLIT_NAMES},
        "child_rows_per_split": {s: sum(r["split"] == s for r in children) for s in SPLIT_NAMES},
        "students_per_split": {s: len({r["student_id"] for r in all_rows if r["split"] == s}) for s in SPLIT_NAMES},
        "student_assignment": {s: dict(sorted(Counter(programme_of[sid] for sid, v in split_of.items()
                                                      if v == s).items())) for s in SPLIT_NAMES},
        "students_with_pairs": {s: len({r["student_id"] for r in rows if r["split"] == s}) for s in SPLIT_NAMES},
        "rows_by_programme": counts(all_rows, "programme"),
        "rows_by_intent": counts(all_rows, "intent"),
        "rows_by_template_family": counts(all_rows, "template_family"),
        "original_rows_by_intent": counts(rows, "intent"),
        "original_rows_by_programme": counts(rows, "programme"),
        "original_rows_by_programme_intent": {s: dict(sorted(Counter(f"{r['programme']}/{r['intent']}" for r in rows
                                                                     if r["split"] == s).items())) for s in SPLIT_NAMES},
        "eligibility_by_split": {s: {"eligible": sum(1 for q in queries if q["intent"] == "eligibility"
                                                     and split_of[q["student_id"]] == s and q["gold_json"]["eligible"]),
                                     "not_eligible": sum(1 for q in queries if q["intent"] == "eligibility"
                                                         and split_of[q["student_id"]] == s
                                                         and not q["gold_json"]["eligible"])} for s in SPLIT_NAMES},
        "n_dropped_pairs": 0,
        "n_dropped_children": len(lost),
        "dropped": dict(sorted(Counter(r["reason"] for r in lost).items())),
        "overlap_checks": checks,
        "all_overlaps_zero": all(v == 0 for v in checks.values()),
        "shifted_forms": "present: run src.split.shifted_forms" if FORMS.exists()
        else f"pending: {FORMS.relative_to(ROOT)} not present yet",
    }
    with open(EVIDENCE / "split_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps({"rows": summary["original_rows_per_split"], "children": summary["child_rows_per_split"],
                      "dropped_pairs": 0, "dropped_children": len(lost), "overlaps_zero": summary["all_overlaps_zero"]}))
    if not summary["all_overlaps_zero"]:
        raise SystemExit(f"overlap check failed: {checks}")


if __name__ == "__main__":
    main()
