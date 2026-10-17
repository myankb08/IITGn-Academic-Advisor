"""Refresh the frozen-files table in HANDOFF_A2.md (path, rows, sha256) from the files on disk.

    .venv/bin/python -m src.split.handoff

Rewrites only the block between the FROZEN_FILES markers; a file that does not exist yet is listed as pending.
"""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HANDOFF = ROOT / "HANDOFF_A2.md"
START, END = "<!-- FROZEN_FILES_START -->", "<!-- FROZEN_FILES_END -->"
FILES = [
    "params.yaml",
    "dvc.lock",
    "data/processed/courses.json",
    "data/processed/rules.json",
    "data/processed/prereq_graph.json",
    "data/processed/students.jsonl",
    "data/processed/students_augmented.jsonl",
    "data/processed/queries.jsonl",
    "data/processed/queries_para.jsonl",
    "data/processed/queries_augmented.jsonl",
    "data/splits/train.csv",
    "data/splits/val.csv",
    "data/splits/test.csv",
    "data/splits/programme_holdout.csv",
    "data/splits/shifted_forms.csv",
    "data/labels/audited.jsonl",
    "data/gold/gold_test.jsonl",
    "data/metadata.csv",
]


def rows(path):
    if path.suffix == ".jsonl":
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    if path.suffix == ".csv":
        return max(0, sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()) - 1)
    return ""


def table():
    lines = ["| file | rows | sha256 |", "|---|---|---|"]
    for name in FILES:
        p = ROOT / name
        if p.exists():
            lines.append(f"| `{name}` | {rows(p)} | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |")
        else:
            lines.append(f"| `{name}` | pending | not created yet |")
    return "\n".join(lines)


def main():
    text = HANDOFF.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise SystemExit(f"markers {START} / {END} not found in HANDOFF_A2.md")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    HANDOFF.write_text(f"{head}{START}\n{table()}\n{END}{tail}", encoding="utf-8")
    print(f"updated {HANDOFF.relative_to(ROOT)} ({len(FILES)} files)")


if __name__ == "__main__":
    main()
