"""Shared paths and helpers for the Part A collection scripts."""
import hashlib
import json
import re
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "data" / "raw" / "sources"
EXTRACTED = ROOT / "data" / "raw" / "extracted"
PLANS = ROOT / "data" / "raw" / "course_plans"
PROCESSED = ROOT / "data" / "processed"
EVIDENCE = ROOT / "supporting_files" / "A_collection"

STRUCTURE_PDF = "Revised CSE MTech Course Structure [2025-26].pdf"
TIMETABLE_XLSX = "Timetable, Sem-I, 2026-27.xlsx"
TIMETABLE_SHEET = "Time table"
PROGRAMMES = ["MTech-CSE", "MTech-AI"]
STREAMS = ["AI/ML", "Systems", "Theory"]

CODE_RE = re.compile(r"\b([A-Z]{2,3})\s*[-:]?\s*(\d{3})(?:\s*-\s*([IVXL]+))?\b")
SECTION_RE = re.compile(r"\s*\(([A-Z]{1,3})\)\s*$")


def load_params():
    with open(ROOT / "params.yaml") as f:
        return yaml.safe_load(f)


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def record_sha(record):
    body = {k: v for k, v in record.items() if k != "record_sha256"}
    return sha256_bytes(canonical_json(body).encode("utf-8"))


def tool_version(pkg):
    return version(pkg)


def normalise_code(raw):
    """'CS610 (E)' -> 'CS 610', 'CS 691-XIV' -> 'CS 691-XIV'. Returns None if no code."""
    if raw is None:
        return None
    text = SECTION_RE.sub("", str(raw).strip())
    m = CODE_RE.match(text)
    if not m:
        return None
    code = f"{m.group(1)} {m.group(2)}"
    return f"{code}-{m.group(3)}" if m.group(3) else code


def code_filename(code):
    return code.replace(" ", "_")


def rel(path):
    return str(Path(path).resolve().relative_to(ROOT))


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
