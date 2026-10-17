"""Assign every synthetic student to a split and pick the test-only template of each family.

    .venv/bin/python -m src.split.assign_students

Runs before make_queries, which renders each pair with a template allowed in its student's split, so no
pair is ever dropped. Students are cut per programme by params.yaml `splits` (by student count, at least one
student in val and test); every MTech-ICDT student goes to programme_holdout. Seed: seeds.splits.
Writes data/splits/assignment/students.csv (student_id, programme, split) and
data/splits/assignment/templates.csv (template_family, template_id, n_templates, test_only).
"""
import csv
import json
from pathlib import Path

import numpy as np
import yaml

from src.queries.make_queries import FAMILIES

ROOT = Path(__file__).resolve().parents[2]
STUDENTS = ROOT / "data" / "processed" / "students.jsonl"
ASSIGN_DIR = ROOT / "data" / "splits" / "assignment"
STUDENTS_CSV = ASSIGN_DIR / "students.csv"
TEMPLATES_CSV = ASSIGN_DIR / "templates.csv"
HOLDOUT_PROGRAMME = "MTech-ICDT"


def template_ids(family, fams=FAMILIES):
    for intent in fams.values():
        if family in intent:
            return [f"{family}_t{i + 1}" for i in range(len(intent[family]))]
    raise KeyError(family)


def held_out_templates(rng, fams=FAMILIES):
    """One template id per family, in sorted family order."""
    families = sorted(f for intent in fams.values() for f in intent)
    return {f: template_ids(f, fams)[int(rng.integers(len(template_ids(f, fams))))] for f in families}


def assign(programme_of, fracs, rng):
    by_prog = {}
    for sid in sorted(programme_of):
        by_prog.setdefault(programme_of[sid], []).append(sid)
    split_of = {}
    for prog in sorted(by_prog):
        members = by_prog[prog]
        if prog == HOLDOUT_PROGRAMME:
            split_of.update({sid: "programme_holdout" for sid in members})
            continue
        order = [members[i] for i in rng.permutation(len(members))]
        n = len(order)
        n_val, n_test = max(1, round(n * fracs["val"])), max(1, round(n * fracs["test"]))
        n_train = n - n_val - n_test
        for i, sid in enumerate(order):
            split_of[sid] = "train" if i < n_train else "val" if i < n_train + n_val else "test"
    return split_of


def load_assignment():
    """(student_id -> split, family -> test-only template id); raises if assign_students has not run."""
    if not STUDENTS_CSV.exists() or not TEMPLATES_CSV.exists():
        raise SystemExit("data/splits/assignment/ missing; run .venv/bin/python -m src.split.assign_students first")
    with open(STUDENTS_CSV, newline="", encoding="utf-8") as f:
        split_of = {r["student_id"]: r["split"] for r in csv.DictReader(f)}
    with open(TEMPLATES_CSV, newline="", encoding="utf-8") as f:
        held = {r["template_family"]: r["template_id"] for r in csv.DictReader(f)}
    return split_of, held


def main():
    params = yaml.safe_load(open(ROOT / "params.yaml"))
    rng = np.random.default_rng(params["seeds"]["splits"])
    with open(STUDENTS, encoding="utf-8") as f:
        programme_of = {s["student_id"]: s["programme"] for s in map(json.loads, filter(str.strip, f))}
    held = held_out_templates(rng)
    split_of = assign(programme_of, params["splits"], rng)
    ASSIGN_DIR.mkdir(parents=True, exist_ok=True)
    with open(STUDENTS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["student_id", "programme", "split"])
        w.writerows([sid, programme_of[sid], split_of[sid]] for sid in sorted(split_of))
    with open(TEMPLATES_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["template_family", "template_id", "n_templates", "test_only"])
        w.writerows([fam, tid, len(template_ids(fam)), True] for fam, tid in held.items())
    counts = {}
    for sid, s in split_of.items():
        counts.setdefault(s, {}).setdefault(programme_of[sid], 0)
        counts[s][programme_of[sid]] += 1
    print(json.dumps({s: dict(sorted(v.items())) for s, v in sorted(counts.items())}))


if __name__ == "__main__":
    main()
