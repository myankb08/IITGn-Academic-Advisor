"""Generate synthetic student transcripts that obey the rule engine.

Course loads per semester, thesis/project unit sizes and the grade set are generation
choices for synthetic data, not degree rules. Degree rules come from the catalog.
"""
import argparse
import json
import random
from collections import Counter

from src.engine.catalog import (COURSES_PATH, PROCESSED, ROOT, RULES_PATH, STREAMS, course_level,
                                load_catalog, load_params, requirement_kind, term_label)
from src.engine.rule_engine import offering_check, role_of, validate_transcript

STUDENTS_PATH = PROCESSED / "students.jsonl"
CORRUPTED_PATH = ROOT / "data" / "interim" / "students_corrupted.jsonl"
SUMMARY_PATH = ROOT / "supporting_files" / "B_engine" / "transcripts_summary.json"

COURSE_GRADES = ["A", "A-", "B", "B-", "C", "C-"]
COURSE_GRADE_WEIGHTS = [20, 25, 25, 15, 10, 5]
UNIT_GRADES = ["A", "B", "C"]
PASS_GRADE = "P"
GEN_MAX_CREDITS_PER_SEM = 24
COURSE_SLOTS = {"thesis": {1: 4, 2: 3, 3: 2}, "coursework": {1: 4, 2: 4, 3: 3}}
THESIS_UNITS = {2: [4, 8], 3: [8, 12]}
PROJECT_UNITS = {2: [0, 4], 3: [4, 8]}
TIER = {"compulsory": 0, "ai_applications": 0, "own_core": 1, "own_basket": 2, "other_basket": 3}
UG_BACKGROUND_P = 0.6
# Admit years put every student's upcoming term in 2026-27 (Sem-I after 0 or 2 semesters, Sem-II after 1 or 3).
ADMIT_YEAR = {0: 2026, 1: 2026, 2: 2025, 3: 2025}
INJECT_TYPES = ["DUPLICATE_COURSE", "PREREQ_SAME_OR_LATER_TERM", "UNKNOWN_CODE", "NOT_OFFERED_IN_PARITY",
                "NOT_OFFERED_IN_TERM", "SEMESTER_CREDIT_CAP", "CREDIT_MISMATCH"]


def _pick(rng, weights):
    keys = sorted(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


def _streams_available(catalog, programme):
    """Streams of the programme that have courses in the catalog; [None] when it has no streams."""
    declared = catalog.rules_for(programme).streams(programme)
    if not declared:
        return [None]
    found = {s for code in catalog.codes for s in (catalog.course(code).get("streams") or [])}
    return [s for s in declared if s in found] or declared


def _candidates(catalog, student, passed_before, taken, term):
    out = []
    have = passed_before | set(student.get("ug_background") or [])
    for code in catalog.codes:
        c = catalog.course(code)
        if c.get("category") in ("requirement", "ug_background") or requirement_kind(c) or code in taken:
            continue
        progs = c.get("programmes") or []
        if progs and student["programme"] not in progs:
            continue
        if offering_check(catalog, code, term)[0]:
            continue
        if any(p not in have for p in (c.get("prerequisites") or [])):
            continue
        if not c.get("credits"):
            continue
        out.append(code)
    return out


def generate_student(catalog, idx, base_seed, params):
    seed = base_seed * 100000 + idx
    rng = random.Random(seed)
    tcfg = params["transcripts"]
    programme = _pick(rng, tcfg["programmes"])
    rules = catalog.rules_for(programme)
    stream = rng.choice(_streams_available(catalog, programme))
    track = _pick(rng, {t: w for t, w in tcfg["tracks"].items() if t in rules.tracks(programme)})
    sc = rng.randint(0, 3)
    ug = sorted(c for c in catalog.ug_codes if rng.random() < UG_BACKGROUND_P)
    student = {"student_id": f"S{idx:04d}", "programme": programme, "stream": stream, "track": track,
               "admit_year": ADMIT_YEAR[sc], "semesters_completed": sc, "ug_background": ug,
               "transcript": [], "seed": seed}
    rule_cap = rules.get("max_credits_per_semester")
    cap = min(GEN_MAX_CREDITS_PER_SEM, rule_cap) if rule_cap else GEN_MAX_CREDITS_PER_SEM
    below_cap = rules.get("below_600_max_courses")
    below_credit_cap = rules.get("below_600_max_credits")
    own_min = rules.get("own_basket_min_credits") or 0
    other_min = rules.get("other_basket_min_credits") or 0
    writing = catalog.req_code("writing")
    w_ok = [s for s in (1, 2) if writing and not offering_check(
        catalog, writing, term_label(student["admit_year"], s))[0]]
    writing_sem = rng.choice(w_ok) if w_ok else None
    pe = catalog.req_code("pe")
    passed, below_used, below_credits = set(), 0, 0
    basket = Counter()
    for sem in range(1, sc + 1):
        term = term_label(student["admit_year"], sem)
        entries, load = [], 0

        def add(code, credits, grade):
            nonlocal load
            entries.append({"code": code, "semester": sem, "credits": credits, "grade": grade})
            load += credits

        aarohan = catalog.req_code("aarohan")
        if sem == 1 and aarohan:
            add(aarohan, catalog.course(aarohan)["credits"], PASS_GRADE)
        if pe and sem <= 2:
            add(pe, catalog.course(pe)["credits"] or 0, PASS_GRADE)
        slots = max(1, COURSE_SLOTS[track][min(sem, 3)] + rng.choice([-1, 0, 0, 1]))
        if writing and sem == writing_sem:
            add(writing, catalog.course(writing)["credits"], rng.choices(COURSE_GRADES, COURSE_GRADE_WEIGHTS)[0])
            slots -= 1
        units = THESIS_UNITS if track == "thesis" else PROJECT_UNITS
        unit_code = catalog.req_code("thesis" if track == "thesis" else "project")
        unit_credits = rng.choice(units[sem]) if sem in units and unit_code else 0
        cands = _candidates(catalog, student, passed, passed, term)
        scored = []
        for code in cands:
            role = role_of(catalog, student, code)
            tier = TIER.get(role, 4)
            if role == "own_basket" and basket["own_basket"] >= own_min:
                tier = 4
            if role == "other_basket" and basket["other_basket"] >= other_min:
                tier = 4
            scored.append((tier + rng.random() * 2.0, code, role))
        scored.sort()
        for _, code, role in scored:
            if slots <= 0:
                break
            c = catalog.course(code)
            cr = c["credits"]
            if load + cr + unit_credits > cap:
                continue
            lvl = course_level(c, code)
            if lvl is not None and lvl < 600:
                if below_cap is not None and below_used + 1 > below_cap:
                    continue
                if below_credit_cap is not None and below_credits + cr > below_credit_cap:
                    continue
                below_used += 1
                below_credits += cr
            add(code, cr, rng.choices(COURSE_GRADES, COURSE_GRADE_WEIGHTS)[0])
            basket[role] += cr
            slots -= 1
        if unit_credits:
            add(unit_code, unit_credits, rng.choice(UNIT_GRADES))
        student["transcript"].extend(sorted(entries, key=lambda e: e["code"]))
        passed |= {e["code"] for e in entries}
    return student


def inject_violations(students, n, catalog, seed):
    """Corrupt n students with one violation each, cycling through INJECT_TYPES."""
    rng = random.Random(seed)
    pool = [s for s in students if s["semesters_completed"] >= 2 and any(
        catalog.is_mtech(e["code"]) and not requirement_kind(catalog.course(e["code"])) for e in s["transcript"])]
    known = set(catalog.known_terms)
    chosen = sorted(rng.sample(pool, min(n, len(pool))), key=lambda s: s["student_id"])
    cap = catalog.rules.get("max_credits_per_semester")
    types = [t for t in INJECT_TYPES if cap is not None or t != "SEMESTER_CREDIT_CAP"]
    out = []
    for i, s in enumerate(chosen):
        s = json.loads(json.dumps(s))
        kind = types[i % len(types)]
        tr = s["transcript"]
        regular = [e for e in tr if catalog.course(e["code"]) and not requirement_kind(catalog.course(e["code"]))]
        if kind == "PREREQ_SAME_OR_LATER_TERM":
            dep = [e for e in regular if catalog.course(e["code"]).get("prerequisites")]
            if dep:
                e = dep[0]
                pre = catalog.course(e["code"])["prerequisites"][0]
                for x in tr:
                    if x["code"] == pre:
                        x["semester"] = e["semester"]
            else:
                kind = "UNKNOWN_CODE"
        if kind == "DUPLICATE_COURSE" and regular:
            e = dict(regular[0])
            e["semester"] = s["semesters_completed"]
            tr.append(e)
        elif kind == "UNKNOWN_CODE":
            tr.append({"code": "ZZ 999", "semester": 1, "credits": 4, "grade": "B"})
        elif kind == "NOT_OFFERED_IN_PARITY":
            fixed = [e for e in regular if catalog.course(e["code"]).get("offered_parity") in ("odd", "even")]
            if fixed:
                e = fixed[0]
                e["semester"] = e["semester"] + 1 if e["semester"] + 1 <= s["semesters_completed"] else e["semester"] - 1
            else:
                tr.append({"code": "ZZ 998", "semester": 1, "credits": 4, "grade": "B"})
                kind = "UNKNOWN_CODE"
        elif kind == "NOT_OFFERED_IN_TERM":
            sems = [k for k in range(1, s["semesters_completed"] + 1) if term_label(s["admit_year"], k) in known]
            have = {e["code"] for e in tr}
            absent = [c for c in catalog.codes if catalog.course(c).get("credits") and c not in have
                      and catalog.course(c).get("category") in ("basket", "open_elective", "stream_core")
                      and not catalog.course(c).get("prerequisites")
                      and offering_check(catalog, c, term_label(s["admit_year"], sems[0]))[0] == "NOT_OFFERED_NEXT_TERM"] if sems else []
            if absent:
                tr.append({"code": absent[0], "semester": sems[0], "credits": catalog.course(absent[0])["credits"], "grade": "B"})
            else:
                tr.append({"code": "ZZ 997", "semester": 1, "credits": 4, "grade": "B"})
                kind = "UNKNOWN_CODE"
        elif kind == "SEMESTER_CREDIT_CAP":
            sem1 = sum(e["credits"] for e in tr if e["semester"] == 1)
            have = {e["code"] for e in tr}
            filler = [c for c in catalog.codes if c not in have and catalog.course(c).get("credits")
                      and catalog.is_mtech(c) and not requirement_kind(catalog.course(c))]
            j = 0
            while sem1 <= cap and j < len(filler):
                tr.append({"code": filler[j], "semester": 1, "credits": catalog.course(filler[j])["credits"] or 4, "grade": "B"})
                sem1 += catalog.course(filler[j])["credits"] or 4
                j += 1
        elif kind == "CREDIT_MISMATCH" and regular:
            regular[0]["credits"] = regular[0]["credits"] + 1
        s["transcript"] = sorted(tr, key=lambda e: (e["semester"], e["code"]))
        s["injected_violation"] = kind
        out.append(s)
    return out


def write_jsonl(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def generate(catalog, params, n=None):
    n = n or params["transcripts"]["n_students"]
    seed = params["seeds"]["transcripts"]
    return [generate_student(catalog, i, seed, params) for i in range(1, n + 1)]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--courses", default=str(COURSES_PATH))
    ap.add_argument("--rules", default=str(RULES_PATH))
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--inject-violations", type=int, default=0,
                    help="write N corrupted students to data/interim for Part B tests")
    args = ap.parse_args()
    params = load_params()
    catalog = load_catalog(args.courses, args.rules)
    students = generate(catalog, params, args.n)
    checks = [validate_transcript(s, catalog) for s in students]
    bad = [c for c in checks if not c["valid"]]
    if bad:
        raise SystemExit(f"generator produced {len(bad)} invalid transcripts, first: {bad[0]}")
    if args.inject_violations:
        corrupted = inject_violations(students, args.inject_violations, catalog, params["seeds"]["transcripts"])
        write_jsonl(corrupted, CORRUPTED_PATH)
        found = [validate_transcript(s, catalog) for s in corrupted]
        caught = sum(1 for s, v in zip(corrupted, found) if s["injected_violation"] in v["violation_types"])
        print(f"corrupted={len(corrupted)} detected={caught} -> {CORRUPTED_PATH.relative_to(ROOT)}")
        return
    write_jsonl(students, STUDENTS_PATH)
    summary = {
        "n_students": len(students),
        "programmes": dict(sorted(Counter(s["programme"] for s in students).items())),
        "streams": dict(sorted(Counter(str(s["stream"]) for s in students).items())),
        "programme_tracks": dict(sorted(Counter(f"{s['programme']}/{s['track']}" for s in students).items())),
        "tracks": dict(sorted(Counter(s["track"] for s in students).items())),
        "semesters_completed": dict(sorted(Counter(str(s["semesters_completed"]) for s in students).items())),
        "upcoming_terms": dict(sorted(Counter(term_label(s["admit_year"], s["semesters_completed"] + 1)
                                              for s in students).items())),
        "ug_background_codes": dict(sorted(Counter(c for s in students for c in s["ug_background"]).items())),
        "transcript_entries": sum(len(s["transcript"]) for s in students),
        "violations": sum(c["n_violations"] for c in checks),
        "rules_used": {prog: catalog.rules_for(prog).to_dict() for prog in sorted(params["transcripts"]["programmes"])},
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_PATH, "w") as f:
        json.dump(summary, f, indent=1)
    print(f"students={len(students)} entries={summary['transcript_entries']} violations={summary['violations']}")


if __name__ == "__main__":
    main()
