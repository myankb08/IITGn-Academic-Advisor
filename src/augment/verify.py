"""Verify augmented children with the rule engine and write data/processed/queries_augmented.jsonl.

Checks per child (gold is compared without student_id, which differs for derived students):
- paraphrase, typo_abbrev: every course code of the parent query still resolves after
  normalisation and no new code appears; the target course is re-read from the child text and
  the rule engine answer for it equals the parent gold.
- transcript_reorder: the engine answer for the reordered student equals the parent gold.
- transcript_length: the truncated student only has entries up to its snapshot, and the stored
  child gold equals a fresh engine run for it (gold may differ from the parent by design).
Children that fail are dropped and listed in supporting_files/D_augmentation/dropped.csv.
"""
import argparse
import csv
import json
import random
import re
from collections import Counter, defaultdict

from src.augment.common import (AUG_DIR, INTERIM, PROCESSED, QUERIES, STUDENTS, STUDENTS_AUG, gold_for,
                                read_jsonl, rel, resolve_codes, strip_ids, write_jsonl)
from src.engine.catalog import load_catalog, load_params

CHILD_FILES = {"paraphrase": INTERIM / "aug_paraphrase.jsonl",
               "typo_abbrev": INTERIM / "aug_typo_abbrev.jsonl",
               "transcript": INTERIM / "aug_transcript.jsonl"}
OUT = PROCESSED / "queries_augmented.jsonl"
AUGS = ["paraphrase", "typo_abbrev", "transcript_reorder", "transcript_length"]
TEXT_AUGS = {"paraphrase", "typo_abbrev"}


NUM_WORDS = {"1": "one", "2": "two", "3": "three", "4": "four"}
PROGRAMME_RE = {"MTech-CSE": r"\bcse\b|computer science",
                "MTech-EE": r"\bee\b|electrical eng",
                "MTech-ICDT": r"\bicdt\b|integrated circuit",
                "MTech-AI": r"m\.?\s*tech[\s-]*(in\s+)?ai\b|\bai\s+m\.?\s*tech|artificial intelligence"}
# a stream counts as kept when every keyword group is present (alternatives inside a group)
STREAM_KEYS = {"ai/ml": [r"\bai\b|artificial intelligence", r"\bml\b|machine learning"],
               "systems": [r"\bsystems?\b"], "theory": [r"\btheor"],
               "power engineering & control systems": [r"power", r"control"],
               "signal processing & machine learning": [r"signal processing|\bsp\b|spml", r"\bml\b|machine learning|spml"]}


def _has_number(text, n):
    return re.search(rf"\b({n}|{NUM_WORDS.get(n, n)})\b", text) is not None


def slot_issues(parent_text, child_text):
    """Facts the parent question states that the child paraphrase lost or turned around (empty list = keeps all).
    Checked: programme, stream, track, semesters completed, the number of electives asked for, the term,
    and that the question is still asked by the student (guidelines v2 R4)."""
    p, c = parent_text, child_text.lower()
    bad = []
    if re.search(r"^\W*(are|have|do|is)\s+you\b|\bare you an?\b", c):
        bad.append("turned_to_student")
    m = re.search(r"MTech-(CSE|AI|EE|ICDT)", p)
    if m and not re.search(PROGRAMME_RE[m.group(0)], c):
        bad.append("programme")
    m = re.search(r"in the (.+?) stream", p)
    if m and not all(re.search(k, c) for k in STREAM_KEYS.get(m.group(1).lower(), [re.escape(m.group(1).lower())])):
        bad.append("stream")
    m = re.search(r"\((thesis|coursework) track\)", p)
    if m:
        other = "coursework" if m.group(1) == "thesis" else "thesis"
        if m.group(1) not in c or re.search(rf"\b({other}|workshop)\b", c):
            bad.append("track")
    m = re.search(r"completed (\d+|no) semesters?", p)
    if m:
        n = m.group(1)
        ok = (re.search(r"\b(no|any|zero|0)\b[^.?]*semester|not (yet )?completed|first semester|just start", c)
              if n == "no" else _has_number(c, n))
        if not ok:
            bad.append("semesters")
    m = re.search(r"\b(\d) electives\b", p)
    if m and not _has_number(c, m.group(1)):
        bad.append("elective_count")
    m = re.search(r"Sem-(I+)\b", p)
    if m:
        second = m.group(1) == "II"
        pat = (r"sem(ester)?[\s-]*(ii|2)\b|second semester|even semester" if second
               else r"sem(ester)?[\s-]*(i|1)\b|first semester|odd semester")
        if not re.search(pat, c):
            bad.append("term")
    return bad


def check_child(kid, parent, students, catalog):
    """(passed, reason, info) for one child."""
    aug = kid["augmentation"]
    info = {}
    if aug == "paraphrase":
        lost = slot_issues(parent["query_text"], kid["query_text"] or "")
        if lost:
            info = {"parent_codes": [], "child_codes": []}
            return False, "slot_lost:" + "+".join(lost), info
    if aug in TEXT_AUGS:
        known = set(catalog.codes)
        want = resolve_codes(parent["query_text"], known)
        got = resolve_codes(kid["query_text"], known)
        info = {"parent_codes": want, "child_codes": got}
        if not (kid["query_text"] or "").strip():
            return False, "empty_text", info
        if set(want) - set(got):
            return False, "code_lost", info
        if set(got) - set(want):
            return False, "code_added", info
        row = dict(kid)
        if kid["intent"] == "eligibility":
            hits = [c for c in got if c == parent["target_course"]]
            if not hits:
                return False, "target_not_resolved", info
            row["target_course"] = hits[0]
        gold = gold_for(row, students[parent["student_id"]], catalog)
        if strip_ids(gold) != strip_ids(parent["gold_json"]):
            return False, "gold_changed", info
        return True, "ok", info
    s = students.get(kid["student_id"])
    if s is None:
        return False, "missing_student", info
    gold = gold_for(kid, s, catalog)
    if aug == "transcript_reorder":
        same_multiset = sorted(map(json.dumps, s["transcript"])) == sorted(
            map(json.dumps, students[parent["student_id"]]["transcript"]))
        if not same_multiset:
            return False, "transcript_changed", info
        if strip_ids(gold) != strip_ids(parent["gold_json"]):
            return False, "gold_changed", info
        return True, "ok", info
    if any(int(e["semester"]) > s["semesters_completed"] for e in s["transcript"]):
        return False, "entry_after_snapshot", info
    if strip_ids(gold) != strip_ids(kid["gold_json"]):
        return False, "gold_not_recomputed", info
    def core(g):
        return {k: v for k, v in strip_ids(g).items() if k != "semesters_completed"}
    info["gold_changed_vs_parent"] = core(gold) != core(parent["gold_json"])
    return True, "ok", info


def verify(parents, children, students, catalog):
    by_id = {r["query_id"]: r for r in parents}
    kept, dropped, stats = [], [], defaultdict(Counter)
    for kid in children:
        parent = by_id[kid["parent_query_id"]]
        ok, reason, info = check_child(kid, parent, students, catalog)
        st = stats[kid["augmentation"]]
        st["n"] += 1
        st[reason] += 1
        if info.get("gold_changed_vs_parent"):
            st["gold_changed_vs_parent"] += 1
        if ok:
            kept.append(kid)
        else:
            dropped.append({"query_id": kid["query_id"], "augmentation": kid["augmentation"], "reason": reason,
                            "parent_codes": ";".join(info.get("parent_codes", [])),
                            "child_codes": ";".join(info.get("child_codes", [])),
                            "child_text": kid["query_text"]})
    return kept, dropped, stats


def summary_rows(stats):
    rows = []
    for aug in AUGS:
        st = stats.get(aug, Counter())
        n = st["n"]
        rows.append({"augmentation": aug, "n_children": n, "n_pass": st["ok"], "n_fail": n - st["ok"],
                     "invariance_rate": round(st["ok"] / n, 4) if n else None,
                     "check": "gold recomputed correctly" if aug == "transcript_length" else "gold unchanged",
                     "gold_changed_vs_parent": st["gold_changed_vs_parent"] if aug == "transcript_length" else 0,
                     "fail_reasons": ";".join(f"{k}={v}" for k, v in sorted(st.items()) if k not in ("n", "ok", "gold_changed_vs_parent"))})
    return rows


def _student_line(s):
    t = ", ".join(f"{e['code']} (s{e['semester']}, {e['grade']})" for e in s["transcript"]) or "empty"
    return f"`{s['student_id']}` semesters_completed={s['semesters_completed']}; transcript: {t}"


def write_samples(aug, kids, parents, students, seed, n=10):
    by_id = {r["query_id"]: r for r in parents}
    rng = random.Random(f"{seed}:samples:{aug}")
    pick = sorted(rng.sample(kids, min(n, len(kids))), key=lambda k: k["query_id"])
    lines = [f"# Samples: {aug}", "", f"{len(pick)} of {len(kids)} verified children, picked with seed {seed}. "
             "For human spot checks: does the child ask the same thing (text augmentations) or is the new "
             "gold right for the new state (transcript_length)?", ""]
    for k in pick:
        p = by_id[k["parent_query_id"]]
        lines += [f"## {k['query_id']} ({k['intent']})", "", f"- before: {p['query_text']}", f"- after: {k['query_text']}"]
        if aug.startswith("transcript"):
            lines += [f"- student before: {_student_line(students[p['student_id']])}",
                      f"- student after: {_student_line(students[k['student_id']])}"]
        if aug == "transcript_length":
            lines += [f"- gold before: {p['gold_text']}", f"- gold after: {k['gold_text']}"]
        lines.append("")
    path = AUG_DIR / f"samples_{aug}.md"
    path.write_text("\n".join(lines))
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queries", default=str(QUERIES))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    params = load_params()
    catalog = load_catalog()
    parents = [r for r in read_jsonl(args.queries) if r.get("augmentation") is None]
    students = {s["student_id"]: s for s in read_jsonl(STUDENTS)}
    if STUDENTS_AUG.exists():
        students.update({s["student_id"]: s for s in read_jsonl(STUDENTS_AUG)})
    children, missing = [], []
    for name, path in CHILD_FILES.items():
        if path.exists():
            children += read_jsonl(path)
        else:
            missing.append(rel(path))
    kept, dropped, stats = verify(parents, children, students, catalog)
    drift = sum(strip_ids(gold_for(r, students[r["student_id"]], catalog)) != strip_ids(r["gold_json"]) for r in parents)
    AUG_DIR.mkdir(parents=True, exist_ok=True)
    rows = summary_rows(stats)
    with open(AUG_DIR / "invariance.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(AUG_DIR / "dropped.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["query_id", "augmentation", "reason", "parent_codes", "child_codes", "child_text"])
        w.writeheader()
        w.writerows(dropped)
    for aug in AUGS:
        kids = [k for k in kept if k["augmentation"] == aug]
        if kids:
            write_samples(aug, kids, parents, students, params["seeds"]["augmentation"])
    write_jsonl(args.out, parents + kept)
    report = {"parents": len(parents), "children_in": len(children), "kept": len(kept), "dropped": len(dropped),
              "parent_gold_drift_vs_engine": drift, "missing_child_files": missing,
              "per_augmentation": {r["augmentation"]: r for r in rows}, "output": rel(args.out)}
    with open(AUG_DIR / "verify_report.json", "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
