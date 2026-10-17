"""Rule-based typo, abbreviation and course-code-format augmentation of query_text.

Per parent query (rng seeded with seeds.augmentation and the query_id):
- abbreviations from ABBREVIATIONS below, each applied with probability 0.6;
- one or two typos in words of 4+ letters: a keyboard-adjacent substitution or a dropped letter,
  never the first letter;
- every course code rewritten in one format variant from CODE_FORMATS.
Course codes, programme names, stream names, terms, track words and numbers are protected: typos
and abbreviations never touch them, and course codes only change format, never content.
"""
import argparse
import random
import re

from src.augment.common import (INTERIM, LOOSE_CODE_RE, QUERIES, STUDENTS, child, known_streams, overlaps,
                                protected_spans, read_jsonl, write_jsonl)
from src.engine.catalog import load_catalog, load_params

OUT = INTERIM / "aug_typo_abbrev.jsonl"

# documented abbreviation dictionary: phrase (case-insensitive, whole words) -> abbreviation
ABBREVIATIONS = {
    "machine learning": "ML",
    "artificial intelligence": "AI",
    "prerequisites": "pre-reqs",
    "prerequisite": "pre-req",
    "requirements": "reqs",
    "requirement": "req",
    "semesters": "sems",
    "semester": "sem",
    "electives": "elecs",
    "elective": "elec",
    "algorithms": "algos",
    "algorithm": "algo",
    "credits": "creds",
    "courses": "crs",
    "information": "info",
    "recommend": "rec",
    "graduation": "grad",
    "programme": "prog",
    "please": "pls",
    "you": "u",
}

KEYBOARD = ["qwertyuiop", "asdfghjkl", "zxcvbnm"]
CODE_FORMATS = ["compact", "lower_hyphen", "lower_space", "compact_lower"]


def _adjacent():
    adj = {}
    for r, row in enumerate(KEYBOARD):
        for c, ch in enumerate(row):
            near = set()
            for rr in (r - 1, r, r + 1):
                if 0 <= rr < len(KEYBOARD):
                    for cc in (c - 1, c, c + 1):
                        if 0 <= cc < len(KEYBOARD[rr]) and (rr, cc) != (r, c):
                            near.add(KEYBOARD[rr][cc])
            adj[ch] = sorted(near)
    return adj


ADJACENT = _adjacent()


def format_code(code_text, fmt):
    m = LOOSE_CODE_RE.fullmatch(code_text.strip())
    pre, num, suf = m.group(1).upper(), m.group(2), m.group(3)
    base = {"compact": f"{pre}{num}", "lower_hyphen": f"{pre.lower()}-{num}",
            "lower_space": f"{pre.lower()} {num}", "compact_lower": f"{pre.lower()}{num}"}[fmt]
    if suf:
        base += f"-{suf.upper() if fmt == 'compact' else suf.lower()}"
    return base


def vary_codes(text, fmt, known_prefixes):
    def sub(m):
        return format_code(m.group(0), fmt) if m.group(1).upper() in known_prefixes and m.group(1).isupper() else m.group(0)
    return LOOSE_CODE_RE.sub(sub, text)


def abbreviate(text, rng, streams, p=0.6):
    for phrase, short in ABBREVIATIONS.items():
        spans = protected_spans(text, streams)
        hits = [m for m in re.finditer(rf"\b{re.escape(phrase)}\b", text, re.I) if not overlaps(m.span(), spans)]
        for m in reversed(hits):
            if rng.random() < p:
                text = text[:m.start()] + short + text[m.end():]
    return text


def typo_word(word, rng):
    i = rng.randrange(1, len(word))
    if rng.random() < 0.5 and word[i].lower() in ADJACENT:
        rep = rng.choice(ADJACENT[word[i].lower()])
        rep = rep.upper() if word[i].isupper() else rep
        return word[:i] + rep + word[i + 1:]
    return word[:i] + word[i + 1:]


def add_typos(text, rng, streams, n):
    spans = protected_spans(text, streams)
    words = [m for m in re.finditer(r"[A-Za-z]{4,}", text) if not overlaps(m.span(), spans)]
    for m in sorted(rng.sample(words, min(n, len(words))), key=lambda m: -m.start()):
        text = text[:m.start()] + typo_word(m.group(0), rng) + text[m.end():]
    return text


def augment_text(text, rng, streams, known_prefixes):
    text = abbreviate(text, rng, streams)
    text = add_typos(text, rng, streams, rng.choice([1, 2]))
    return vary_codes(text, rng.choice(CODE_FORMATS), known_prefixes)


def augment(rows, catalog, seed, students=()):
    streams = known_streams(catalog, students)
    prefixes = {c.split()[0] for c in catalog.codes}
    out = []
    for r in rows:
        rng = random.Random(f"{seed}:{r['query_id']}:typo_abbrev")
        out.append(child(r, "typo_abbrev", "T", query_text=augment_text(r["query_text"], rng, streams, prefixes)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queries", default=str(QUERIES))
    ap.add_argument("--students", default=str(STUDENTS))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    params = load_params()
    rows = [r for r in read_jsonl(args.queries) if r.get("augmentation") is None]
    out = augment(rows, load_catalog(), params["seeds"]["augmentation"], read_jsonl(args.students))
    write_jsonl(args.out, out)
    print(f"typo_abbrev: {len(out)} children -> {args.out}")


if __name__ == "__main__":
    main()
