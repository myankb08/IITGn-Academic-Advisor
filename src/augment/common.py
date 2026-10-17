"""Shared helpers for augmentation: io, protected spans and course code resolution."""
import json
import re
from pathlib import Path

from src.engine.rule_engine import eligibility, recommend_electives, remaining_requirements

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
INTERIM = ROOT / "data" / "interim"
QUERIES = PROCESSED / "queries.jsonl"
STUDENTS = PROCESSED / "students.jsonl"
STUDENTS_AUG = PROCESSED / "students_augmented.jsonl"
AUG_DIR = ROOT / "supporting_files" / "D_augmentation"

# any spelling of a course code: "CS 610", "CS610", "cs-610", "Cs 691-xiv"
LOOSE_CODE_RE = re.compile(r"\b([A-Za-z]{2,3})\s*[-:]?\s*(\d{3})(?:\s*-\s*([IVXLivxl]+)\b)?(?![\d])")
PROGRAMME_RE = re.compile(r"\bM\.?\s?Tech[- ]?[A-Za-z]+\b")
TERM_RE = re.compile(r"\b\d{4}-\d{2}\s+Sem-I{1,2}\b")
NUMBER_RE = re.compile(r"\b\d+\b")
TRACK_WORDS = ("thesis", "coursework")


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def rel(path):
    p = Path(path).resolve()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(path)


def resolve_codes(text, known=None):
    """Course codes in text after normalisation to '<PREFIX> <NUMBER>[-<SUFFIX>]'.

    Without `known` only upper-case prefixes count. With `known`, any case counts when the prefix
    is one used by a known code; a prefix+number that is not a known code is still returned (so
    hallucinated codes stay visible), and a suffix is only kept when the suffixed code is known.
    """
    prefixes = {k.split()[0] for k in known} if known else None
    out = []
    for m in LOOSE_CODE_RE.finditer(text or ""):
        pre = m.group(1)
        if (prefixes is None and not pre.isupper()) or (prefixes is not None and pre.upper() not in prefixes):
            continue
        code = f"{pre.upper()} {m.group(2)}"
        if m.group(3):
            full = f"{code}-{m.group(3).upper()}"
            code = full if known is None or full in known else code
        if code not in out:
            out.append(code)
    return out


def protected_spans(text, streams=()):
    """Character spans that augmentation must never change: codes, programmes, streams, terms, tracks, numbers."""
    spans = [m.span() for rx in (LOOSE_CODE_RE, PROGRAMME_RE, TERM_RE, NUMBER_RE) for m in rx.finditer(text)]
    for name in list(streams) + list(TRACK_WORDS):
        spans += [m.span() for m in re.finditer(re.escape(name), text)]
    return sorted(spans)


def overlaps(span, spans):
    return any(span[0] < b and a < span[1] for a, b in spans)


def gold_for(row, student, catalog):
    """Rule engine answer for the row's intent and target course, for this student state."""
    if row["intent"] == "eligibility":
        return eligibility(student, row["target_course"], catalog=catalog)
    if row["intent"] == "remaining_core":
        return remaining_requirements(student, catalog)
    return recommend_electives(student, k=3, catalog=catalog)


def strip_ids(gold):
    """Gold without the student_id field, which differs for derived students by construction."""
    return {k: v for k, v in gold.items() if k != "student_id"}


def child(parent, aug, suffix, **changes):
    return {**parent, "query_id": f"{parent['query_id']}-{suffix}", "para_query": None,
            "para_justification": None, "para_model": None, "para_prompt_id": None,
            "augmentation": aug, "parent_query_id": parent["query_id"], **changes}


def known_streams(catalog, students=()):
    """Stream names from courses.json and the students file, longest first."""
    names = {s for c in catalog.courses.values() for s in (c.get("streams") or [])}
    names |= {s["stream"] for s in students if s.get("stream")}
    return sorted(names, key=len, reverse=True)
