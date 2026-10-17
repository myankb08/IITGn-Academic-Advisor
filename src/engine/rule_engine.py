"""Deterministic degree rule engine for the CS discipline M.Tech programmes.

Credit accounting (an interpretation of Adv5 page 2 and the CSE course structure page 1):
each passed course gets one role for the student. Compulsory courses, own stream core and
basket courses of any stream count as discipline-specified. Electives are open electives,
other streams' core courses, HSS courses when HSS is not required, and basket credits beyond
the own-basket and other-basket minimums. Only the first two courses below 600 level count
(besides one UG HSS course); later ones are flagged and not counted.
"""
import functools
import json
import re

from src.engine.catalog import (CSE, STREAMS, TIMETABLE_DOC, course_level, is_pass, load_catalog,
                                requirement_kind, term_label, term_parity)

CSE_DOC = CSE

REPEATABLE = {"thesis", "project", "pe"}
NON_COURSEWORK = {"aarohan", "thesis", "project", "pe"}


@functools.lru_cache(maxsize=1)
def default_catalog():
    return load_catalog()


def _cat(catalog):
    return catalog if catalog is not None else default_catalog()


def _prefix(code):
    m = re.match(r"[A-Z]+", code or "")
    return m.group() if m else ""


def prules(catalog, student):
    """Rules for the student's programme (common rules with the programme's overrides)."""
    return catalog.rules_for(student["programme"])


def role_of(catalog, student, code):
    c = catalog.course(code)
    if c is None:
        return "hss" if _prefix(code) == "HS" else "unknown"
    if c.get("category") == "ug_background":
        return "ug_background"
    kind = requirement_kind(c)
    if kind:
        return kind
    rules = prules(catalog, student)
    if code == rules.ai_applications_course:
        return "ai_applications"
    cat = c.get("category")
    streams = c.get("streams") or []
    progs = c.get("programmes") or []
    in_prog = not progs or student["programme"] in progs
    stream = student.get("stream")
    if cat == "compulsory" and in_prog:
        return "compulsory"
    if cat == "stream_core" and in_prog and stream in streams:
        return "own_core"
    if cat == "basket" and in_prog:
        if stream is None or stream in streams:
            return "own_basket"
        if set(streams) & set(rules.streams(student["programme"])):
            return "other_basket"
    if _prefix(code) == "HS":
        return "hss"
    return "elective"


def hss_required(catalog, student):
    cutoff = prules(catalog, student).get("hss_required_before_admit_year")
    return bool(cutoff) and int(student.get("admit_year") or cutoff) < int(cutoff)


def _passed_entries(catalog, student):
    """Passed transcript entries in order, first pass only for non-repeatable courses."""
    seen, out = set(), []
    mooc_ok = prules(catalog, student).get("mooc_electives_allowed")
    for e in sorted(student.get("transcript", []), key=lambda e: (e["semester"], e["code"])):
        if not is_pass(e.get("grade")):
            continue
        if e.get("mooc"):
            role = "elective" if mooc_ok else "mooc_not_counted"
        else:
            role = role_of(catalog, student, e["code"])
        if role not in REPEATABLE and e["code"] in seen:
            continue
        seen.add(e["code"])
        out.append((e, role))
    return out


def _below_600_split(catalog, entries, rules):
    """Split entries into counted and excess below-600 courses per the programme's cap."""
    cap_courses = rules.get("below_600_max_courses")
    cap_credits = rules.get("below_600_max_credits")
    used_courses, used_credits, hss_ug_used = 0, 0, False
    counted, excess = [], []
    for e, role in entries:
        lvl = None if e.get("mooc") else course_level(catalog.course(e["code"]), e["code"])
        if role in NON_COURSEWORK or role in {"writing"} or lvl is None or lvl >= 600:
            counted.append((e, role))
            continue
        if role == "hss" and not hss_ug_used:
            hss_ug_used = True
            counted.append((e, role))
            continue
        over = (cap_courses is not None and used_courses + 1 > cap_courses) or \
               (cap_credits is not None and used_credits + e["credits"] > cap_credits)
        if over:
            excess.append((e, role))
            continue
        used_courses += 1
        used_credits += e["credits"]
        counted.append((e, role))
    usage = {"cap_courses": cap_courses, "cap_credits": cap_credits, "courses_used": used_courses,
             "credits_used": used_credits, "excess_courses": sorted(e["code"] for e, _ in excess),
             "cap_reached": (cap_courses is not None and used_courses >= cap_courses) or
                            (cap_credits is not None and used_credits >= cap_credits)}
    return counted, usage


def _gap(earned, minimum):
    minimum = minimum or 0
    return {"earned": earned, "min": minimum, "gap": max(0, minimum - earned)}


def passed_codes(student, catalog=None):
    catalog = _cat(catalog)
    return sorted({e["code"] for e, _ in _passed_entries(catalog, student)})


def _structure_codes(catalog, student, category, own_stream=True):
    out = []
    for code in catalog.codes:
        c = catalog.course(code)
        if c.get("category") != category:
            continue
        progs = c.get("programmes") or []
        if progs and student["programme"] not in progs:
            continue
        if category == "stream_core" and own_stream and student["stream"] not in (c.get("streams") or []):
            continue
        out.append(code)
    return sorted(out)


def remaining_requirements(student, catalog=None):
    catalog = _cat(catalog)
    rules = prules(catalog, student)
    track = student["track"]
    counted, below = _below_600_split(catalog, _passed_entries(catalog, student), rules)
    credits = {}
    for e, role in counted:
        credits[role] = credits.get(role, 0) + e["credits"]
    passed = {e["code"] for e, _ in counted}

    compulsory = _structure_codes(catalog, student, "compulsory")
    own_core = _structure_codes(catalog, student, "stream_core")
    own_min = rules.get("own_basket_min_credits")
    other_min = rules.get("other_basket_min_credits")
    own_b, other_b = credits.get("own_basket", 0), credits.get("other_basket", 0)
    need_hss = hss_required(catalog, student)

    discipline = sum(credits.get(r, 0) for r in ("compulsory", "own_core", "own_basket", "other_basket"))
    electives = credits.get("elective", 0) + max(0, own_b - own_min) + max(0, other_b - other_min)
    if not need_hss:
        electives += credits.get("hss", 0)
    skip = {"unknown", "ug_background", "mooc_not_counted"}
    coursework = sum(v or 0 for r, v in credits.items() if r not in NON_COURSEWORK | skip)
    total = sum(v or 0 for r, v in credits.items() if r not in {"pe"} | skip)
    cw_min, th_min = rules.get("coursework_min_credits", track), rules.get("thesis_min_credits", track)
    aarohan_in_cw = bool(cw_min and th_min is not None and cw_min + th_min == rules.get("total_min_credits"))
    if aarohan_in_cw:
        coursework += credits.get("aarohan", 0)

    def req_status(kind, minimum, required=True):
        code = catalog.req_code(kind)
        earned = credits.get(kind, 0)
        if not required:
            status = "not_required"
        elif code is None and kind != "hss":
            status = "not_trackable"
        else:
            status = "done" if earned >= (minimum or 0) else "missing"
        return {"code": code, "required": required, "earned": earned, "min": minimum if required else 0,
                "status": status}

    pe_code = catalog.req_code("pe")
    pe_done = sum(1 for e, r in counted if r == "pe")
    pe_min = rules.get("pe_courses_required")
    ai_code = rules.ai_applications_course
    ai_done = ai_code in passed if ai_code else False
    requirements = {
        "writing": req_status("writing", rules.get("writing_credits")),
        "aarohan": req_status("aarohan", rules.get("aarohan_credits")),
        "hss": {"code": None, "required": need_hss, "earned": credits.get("hss", 0),
                "min": rules.get("hss_min_credits") if need_hss else 0,
                "status": "not_required" if not need_hss else
                ("done" if credits.get("hss", 0) >= rules.get("hss_min_credits") else "missing")},
        "physical_education": {"code": pe_code, "required": True, "earned": pe_done, "min": pe_min,
                               "unit": "courses", "status": "not_trackable" if pe_code is None else
                               ("done" if pe_done >= (pe_min or 0) else "missing")},
        "ai_applications": {"code": ai_code, "required": not need_hss,
                            "earned": catalog.course(ai_code)["credits"] if ai_done else 0,
                            "min": rules.get("ai_applications_credits") if not need_hss else 0,
                            "status": "not_required" if need_hss else ("done" if ai_done else
                                                                       ("missing" if ai_code else "not_trackable"))},
    }
    out = {
        "student_id": student["student_id"],
        "programme": student["programme"],
        "stream": student["stream"],
        "track": track,
        "semesters_completed": student["semesters_completed"],
        "compulsory_missing": sorted(c for c in compulsory if c not in passed),
        "stream_core_missing": sorted(c for c in own_core if c not in passed),
        "own_basket": {"stream": student["stream"], "label": basket_label(rules, student), **_gap(own_b, own_min)},
        "other_basket": {"streams": sorted(s for s in rules.streams(student["programme"]) if s != student["stream"]),
                         **_gap(other_b, other_min)},
        "discipline_specified": _gap(discipline, rules.get("discipline_specified_min_credits")),
        "electives": _gap(electives, rules.get("electives_min_credits")),
        "requirements": requirements,
        "coursework": {**_gap(coursework, cw_min), "includes_aarohan": aarohan_in_cw},
        "thesis": _gap(credits.get("thesis", 0), th_min),
        "project": _gap(credits.get("project", 0), rules.get("project_min_credits", track)),
        "total": _gap(total, rules.get("total_min_credits")),
        "below_600": below,
    }
    reasons = []
    if out["compulsory_missing"]:
        reasons.append("MISSING_COMPULSORY")
    if out["stream_core_missing"]:
        reasons.append("MISSING_STREAM_CORE")
    for key, code in (("own_basket", "OWN_BASKET_GAP"), ("other_basket", "OTHER_BASKET_GAP"),
                      ("discipline_specified", "DISCIPLINE_GAP"), ("electives", "ELECTIVES_GAP"),
                      ("coursework", "COURSEWORK_GAP"), ("thesis", "THESIS_GAP"),
                      ("project", "PROJECT_GAP"), ("total", "TOTAL_GAP")):
        if out[key]["gap"] > 0:
            reasons.append(code)
    for key, r in requirements.items():
        if r["status"] == "missing":
            reasons.append(f"{key.upper()}_MISSING")
    if below["excess_courses"]:
        reasons.append("BELOW_600_CAP_EXCEEDED")
    out["reason_codes"] = sorted(reasons)
    return out


def basket_label(rules, student):
    """How the programme's sources name the own-stream course list."""
    if not rules.get("stream_core_credits") and not rules.get("other_basket_min_credits"):
        where = f" ({student['stream']})" if student.get("stream") else ""
        return f"courses specified by the discipline{where}"
    return f"own {student['stream']} basket"


def upcoming_term(student):
    """The term the student registers for next: programme semester semesters_completed + 1."""
    return term_label(student["admit_year"], int(student.get("semesters_completed", 0)) + 1)


def student_terms(student):
    return {sem: term_label(student["admit_year"], sem) for sem in range(1, 9)}


def background_codes(student):
    """Codes the student has from UG or equivalent; they satisfy prerequisites, never earn credit."""
    return set(student.get("ug_background") or [])


def offering_check(catalog, code, term):
    """(blocking reason or None, warning or None, evidence) for taking code in term."""
    c = catalog.course(code)
    parity = term_parity(term)
    if c.get("offered_parity") in ("odd", "even") and c["offered_parity"] != parity:
        return "NOT_OFFERED_IN_PARITY", None, c.get("offering_evidence")
    placeholder = c.get("category") == "requirement" and not c.get("offered_terms")
    if term in catalog.known_terms and not placeholder:
        if term not in (c.get("offered_terms") or []):
            return "NOT_OFFERED_NEXT_TERM", None, f"{TIMETABLE_DOC}: {code} is not listed for {term}"
        return None, None, c.get("offering_evidence")
    if c.get("offered_parity") or placeholder:
        return None, None, c.get("offering_evidence")
    return None, "OFFERING_UNKNOWN", f"no timetable for {term} in data/raw/sources and no stated semester"


def _missing_recommended(catalog, student, c, have):
    return [g["any_of"] for g in (c.get("recommended_background") or [])
            if not set(g["any_of"]) & have]


def _cite_rule(rules, name):
    p = rules.provenance.get(name) or {}
    if not p.get("source_doc"):
        return "rules.json"
    where = f"p{p['source_page']}" if p.get("source_page") else f"[{p.get('source_section')}]"
    return f"{p['source_doc']} {where}"


def eligibility(student, course_code, term=None, catalog=None):
    """Can the student register for course_code in term (default: the student's upcoming term)."""
    catalog = _cat(catalog)
    term = term or upcoming_term(student)
    c = catalog.course(course_code)
    base = {"student_id": student["student_id"], "course": course_code, "term": term,
            "semester_parity": term_parity(term)}
    if c is None or not catalog.is_mtech(course_code):
        reason = "UNKNOWN_COURSE" if c is None else "NOT_MTECH_COURSE"
        return {**base, "title": c.get("title") if c else None, "eligible": False, "already_taken": False,
                "prerequisites": [], "unmet_prerequisites": [], "missing_recommended": [],
                "offered_parity": None, "offered_terms": [], "role": None, "reason_codes": [reason],
                "warnings": [], "sources": {reason: "data/processed/courses.json"}}
    passed = set(passed_codes(student, catalog))
    have = passed | background_codes(student)
    role = role_of(catalog, student, course_code)
    prereqs = sorted(set(c.get("prerequisites") or []))
    unmet = sorted(p for p in prereqs if p not in have)
    taken = course_code in passed and role not in REPEATABLE
    block, warn, off_ev = offering_check(catalog, course_code, term)
    reasons, warnings, sources = [], [], {}
    if taken:
        reasons.append("ALREADY_TAKEN")
        sources["ALREADY_TAKEN"] = "student transcript (passed grade)"
    if unmet:
        reasons.append("PREREQ_UNMET")
        sources["PREREQ_UNMET"] = c.get("prereq_evidence")
    if block:
        reasons.append(block)
        sources[block] = off_ev
    if warn:
        warnings.append(warn)
        sources[warn] = off_ev
    missing_rec = _missing_recommended(catalog, student, c, have)
    if missing_rec:
        warnings.append("MISSING_RECOMMENDED_BACKGROUND")
        docs = sorted({g.get("source_doc") or "" for g in c["recommended_background"]})
        sources["MISSING_RECOMMENDED_BACKGROUND"] = f"course plan {', '.join(docs)}: " + " | ".join(
            g["evidence"] for g in c["recommended_background"] if g["any_of"] in missing_rec)
    if c.get("category") == "stream_core" and role == "elective":
        warnings.append("OTHER_STREAM_CORE_AS_ELECTIVE")
        sources["OTHER_STREAM_CORE_AS_ELECTIVE"] = f"{CSE_DOC} p1 (core of {', '.join(c.get('streams') or [])} only)"
    rules = prules(catalog, student)
    progs = c.get("programmes") or []
    if progs and student["programme"] not in progs and c.get("category") != "requirement":
        warnings.append("OUTSIDE_PROGRAMME_LIST")
        sources["OUTSIDE_PROGRAMME_LIST"] = (f"{c.get('source_doc')}: listed for {', '.join(progs)}; electives may be "
                                             f"inside or outside the discipline ({_cite_rule(rules, 'electives_min_credits')})")
    lvl = course_level(c, course_code)
    if lvl is not None and lvl < 600 and role not in NON_COURSEWORK and role != "hss":
        _, below = _below_600_split(catalog, _passed_entries(catalog, student), rules)
        cr = c.get("credits") or 0
        if (below["cap_courses"] is not None and below["courses_used"] + 1 > below["cap_courses"]) or \
                (below["cap_credits"] is not None and below["credits_used"] + cr > below["cap_credits"]):
            warnings.append("NOT_COUNTED_BELOW_600_CAP")
            cap = "below_600_max_courses" if below["cap_courses"] is not None else "below_600_max_credits"
            sources["NOT_COUNTED_BELOW_600_CAP"] = _cite_rule(rules, cap)
    eligible = not reasons
    if eligible:
        reasons.append("PREREQS_MET" if prereqs else "NO_PREREQS")
        if not warn:
            reasons.append("OFFERED_IN_TERM")
            sources["OFFERED_IN_TERM"] = off_ev
    return {**base, "title": c.get("title"), "eligible": eligible, "already_taken": taken,
            "prerequisites": prereqs, "unmet_prerequisites": unmet, "missing_recommended": missing_rec,
            "offered_parity": c.get("offered_parity"), "offered_terms": sorted(c.get("offered_terms") or []),
            "role": role, "reason_codes": sorted(reasons), "warnings": sorted(warnings),
            "sources": dict(sorted(sources.items()))}


ELECTIVE_CATEGORIES = {"basket", "open_elective", "stream_core"}


def recommend_electives(student, k=3, term=None, catalog=None):
    catalog = _cat(catalog)
    term = term or upcoming_term(student)
    rem = remaining_requirements(student, catalog)
    gaps = {"own": rem["own_basket"]["gap"], "other": rem["other_basket"]["gap"],
            "elective": rem["electives"]["gap"]}
    cap_reached = rem["below_600"]["cap_reached"]
    pool = []
    for code in catalog.codes:
        c = catalog.course(code)
        role = role_of(catalog, student, code)
        if c.get("category") not in ELECTIVE_CATEGORIES or role in {"own_core", "compulsory", "ai_applications"}:
            continue
        lvl = course_level(c, code)
        below = lvl is not None and lvl < 600
        if below and cap_reached:
            continue
        el = eligibility(student, code, term, catalog)
        if el["eligible"]:
            pool.append((code, c, role, below, el["warnings"]))
    picks = []
    while pool and len(picks) < k:
        scored = []
        for code, c, role, below, warns in pool:
            cr = c.get("credits") or 0
            if role == "own_basket" and gaps["own"] > 0:
                tier, reason, closes = 0, "OWN_BASKET_GAP", min(cr, gaps["own"])
            elif role == "other_basket" and gaps["other"] > 0:
                tier, reason, closes = 1, "OTHER_BASKET_GAP", min(cr, gaps["other"])
            elif role == "own_basket":
                tier, reason, closes = 2, "OWN_BASKET_ELECTIVE", min(cr, gaps["elective"])
            elif role == "other_basket":
                tier, reason, closes = 3, "OTHER_BASKET_ELECTIVE", min(cr, gaps["elective"])
            else:
                tier, reason, closes = 4, "OPEN_ELECTIVE", min(cr, gaps["elective"])
            scored.append(((tier, -closes, len(warns), below, code), code, c, role, reason, closes, below, warns))
        scored.sort(key=lambda s: s[0])
        _, code, c, role, reason, closes, below, warns = scored[0]
        picks.append({"rank": len(picks) + 1, "course": code, "title": c.get("title"),
                      "credits": c.get("credits"), "role": role, "reason_code": reason,
                      "credits_toward_gap": closes, "below_600": below, "warnings": warns,
                      "prerequisites": sorted(set(c.get("prerequisites") or []))})
        key = {"OWN_BASKET_GAP": "own", "OTHER_BASKET_GAP": "other"}.get(reason, "elective")
        gaps[key] = max(0, gaps[key] - (c.get("credits") or 0))
        pool = [p for p in pool if p[0] != code]
    return {"student_id": student["student_id"], "term": term, "semester_parity": term_parity(term), "k": k,
            "gaps_before": {"own_basket": rem["own_basket"]["gap"], "other_basket": rem["other_basket"]["gap"],
                            "electives": rem["electives"]["gap"]},
            "recommendations": picks, "eligible_pool_size": len(pool) + len(picks)}


def validate_transcript(student, catalog=None):
    catalog = _cat(catalog)
    rules = prules(catalog, student)
    tr = sorted(student.get("transcript", []), key=lambda e: (e["semester"], e["code"]))
    terms = student_terms(student)
    background = background_codes(student)
    viol = []

    def add(kind, e, detail):
        viol.append({"type": kind, "code": e["code"] if e else None,
                     "semester": e["semester"] if e else None, "detail": detail})

    allowed = rules.streams(student["programme"])
    if student.get("programme") == "MTech-AI":
        allowed = [rules.values.get("mtech_ai_stream") or "AI/ML"]
    if (allowed and student.get("stream") not in allowed) or (not allowed and student.get("stream") is not None):
        viol.append({"type": "PROGRAMME_STREAM_MISMATCH", "code": None, "semester": None,
                     "detail": f"{student['programme']} streams are {allowed or 'none'}"})
    track_ok = rules.tracks(student["programme"])
    if student.get("track") not in track_ok:
        viol.append({"type": "PROGRAMME_TRACK_MISMATCH", "code": None, "semester": None,
                     "detail": f"{student['programme']} tracks are {track_ok}"})
    for code in sorted(background - set(catalog.ug_codes)):
        viol.append({"type": "UNKNOWN_BACKGROUND_CODE", "code": code, "semester": None,
                     "detail": "ug_background code is not a ug_background node in courses.json"})
    first_pass = {}
    for e in tr:
        if is_pass(e.get("grade")) and e["code"] not in first_pass:
            first_pass[e["code"]] = e["semester"]
    seen_pass = {}
    for e in tr:
        c = catalog.course(e["code"])
        sem = e["semester"]
        if not 1 <= sem <= max(1, int(student.get("semesters_completed", 0))):
            add("SEMESTER_OUT_OF_RANGE", e, f"semester {sem} outside 1..{student.get('semesters_completed')}")
        if e.get("mooc"):
            if not rules.get("mooc_electives_allowed"):
                add("MOOC_NOT_COUNTED", e, f"online courses do not count for {student['programme']} "
                                          f"({_cite_rule(rules, 'mooc_electives_allowed')})")
            continue
        if c is None:
            add("UNKNOWN_CODE", e, "code not in courses.json")
            continue
        if not catalog.is_mtech(e["code"]):
            add("NOT_MTECH_COURSE", e, "ug_background course cannot appear in an M.Tech transcript")
            continue
        role = role_of(catalog, student, e["code"])
        if role not in REPEATABLE:
            if e["code"] in seen_pass:
                add("DUPLICATE_COURSE", e, f"already passed in semester {seen_pass[e['code']]}")
            elif is_pass(e.get("grade")):
                seen_pass[e["code"]] = sem
            if c.get("credits") is not None and e["credits"] != c["credits"]:
                add("CREDIT_MISMATCH", e, f"transcript {e['credits']} vs catalog {c['credits']}")
        for p in sorted(set(c.get("prerequisites") or [])):
            if p in background:
                continue
            if p not in first_pass:
                add("PREREQ_MISSING", e, f"prerequisite {p} never passed")
            elif first_pass[p] >= sem:
                add("PREREQ_SAME_OR_LATER_TERM", e, f"prerequisite {p} passed in semester {first_pass[p]}")
        block, _, ev = offering_check(catalog, e["code"], terms[sem] if sem in terms else term_label(student["admit_year"], sem))
        if block == "NOT_OFFERED_IN_PARITY" and c.get("category") != "requirement":
            add("NOT_OFFERED_IN_PARITY", e, ev)
        elif block == "NOT_OFFERED_NEXT_TERM" and c.get("category") != "requirement":
            add("NOT_OFFERED_IN_TERM", e, ev)
    cap = rules.get("max_credits_per_semester")
    if cap is not None:
        per_sem = {}
        for e in tr:
            per_sem[e["semester"]] = per_sem.get(e["semester"], 0) + e["credits"]
        for sem in sorted(per_sem):
            if per_sem[sem] > cap:
                viol.append({"type": "SEMESTER_CREDIT_CAP", "code": None, "semester": sem,
                             "detail": f"{per_sem[sem]} credits > cap {cap}"})
    _, below = _below_600_split(catalog, _passed_entries(catalog, student), rules)
    if below["excess_courses"]:
        viol.append({"type": "BELOW_600_CAP", "code": None, "semester": None,
                     "detail": f"below-600 courses over cap: {', '.join(below['excess_courses'])}"})
    viol.sort(key=lambda v: (v["semester"] if v["semester"] is not None else 99, v["code"] or "", v["type"]))
    return {"student_id": student["student_id"], "valid": not viol, "n_violations": len(viol),
            "violation_types": sorted({v["type"] for v in viol}), "violations": viol}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Run the rule engine on one student from students.jsonl")
    ap.add_argument("student_id")
    ap.add_argument("--course", default=None)
    args = ap.parse_args()
    from src.engine.synth_transcripts import STUDENTS_PATH
    with open(STUDENTS_PATH) as f:
        students = {s["student_id"]: s for s in map(json.loads, f)}
    s = students[args.student_id]
    out = {"remaining": remaining_requirements(s), "recommend": recommend_electives(s),
           "validate": validate_transcript(s)}
    if args.course:
        out["eligibility"] = eligibility(s, args.course)
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
