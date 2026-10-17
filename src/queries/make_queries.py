"""Build advisory query/answer pairs whose gold answers come from the rule engine.

Needs data/splits/assignment/ from src.split.assign_students: each pair is rendered with a surface template
allowed in its student's split (test: the held-out template of the family; train/val: the others).
"""
import argparse
import json
import math
import random
from collections import Counter

from src.engine.catalog import COURSES_PATH, PROCESSED, ROOT, RULES_PATH, load_catalog, load_params
from src.engine.rule_engine import (basket_label, eligibility, recommend_electives, remaining_requirements,
                                    upcoming_term)
from src.engine.synth_transcripts import STUDENTS_PATH

QUERIES_PATH = PROCESSED / "queries.jsonl"
SUMMARY_PATH = ROOT / "supporting_files" / "B_engine" / "queries_summary.json"

PROFILE = "I'm an {programme} student{stream} ({track} track) and I have completed {n_sem}."

FAMILIES = {
    "remaining_core": {
        "rc_degree_audit": [
            "{profile} What do I still need to finish my degree?",
            "{profile} Can you give me a full audit of my remaining graduation requirements?",
            "{profile} Which requirements are still pending before I can graduate?",
        ],
        "rc_core_courses": [
            "{profile} Which compulsory and core courses have I not taken yet?",
            "{profile} Am I missing any compulsory or stream core course?",
            "{profile} What core coursework and basket credits are still left for my stream?",
        ],
        "rc_credit_gap": [
            "{profile} How many credits am I short of graduating?",
            "{profile} How far am I from the total credit requirement, and where are the gaps?",
            "{profile} Break down how many more credits I need, by category.",
            "{profile} What is my remaining credit gap for coursework and {unit_word}?",
        ],
    },
    "eligibility": {
        "el_can_register": [
            "{profile} Can I register for {course} in {term}?",
            "{profile} Am I eligible to take {course} ({title}) in the upcoming term, {term}?",
            "{profile} Is it possible for me to enrol in {course} next term?",
        ],
        "el_prereq_check": [
            "{profile} Have I met the prerequisites for {course} ({title})?",
            "{profile} Do I satisfy everything needed before taking {course}?",
            "{profile} What is blocking me, if anything, from taking {course}?",
        ],
    },
    "elective_recommendation": {
        "er_next_semester": [
            "{profile} Suggest {k} electives I can take next semester.",
            "{profile} Which {k} electives would you recommend for {term}?",
            "{profile} What are the best {k} elective options for me next term?",
        ],
        "er_basket_fill": [
            "{profile} Which courses should I take to complete my basket requirements?",
            "{profile} Recommend courses that fill my own-basket and other-basket credits.",
            "{profile} I want to close my basket gaps next semester. What should I pick?",
        ],
    },
}

ELIG_TEXT = {
    "PREREQS_MET": "its enforceable prerequisites ({prereqs}) are completed",
    "NO_PREREQS": "no course plan states an enforceable prerequisite for it",
    "OFFERED_IN_TERM": "it is offered in {term} ({source})",
    "PREREQ_UNMET": "prerequisite(s) not yet completed: {unmet}",
    "ALREADY_TAKEN": "you have already passed it",
    "NOT_OFFERED_NEXT_TERM": "it is not offered in {term} ({source})",
    "NOT_OFFERED_IN_PARITY": "it is offered only in {offered_parity} semesters ({source})",
    "NOT_IN_PROGRAMME_CURRICULUM": "it is not part of the {programme} curriculum",
    "NOT_MTECH_COURSE": "it is a UG background course, not an M.Tech course",
    "UNKNOWN_COURSE": "it is not in the CS M.Tech course list",
}
WARN_TEXT = {
    "OFFERING_UNKNOWN": "no timetable for {term} is available yet, so confirm the offering when it is published",
    "MISSING_RECOMMENDED_BACKGROUND": "the course plan recommends background you have not shown ({missing}), so expect to catch up",
    "NOT_COUNTED_BELOW_600_CAP": "you have already used the allowed below-600 courses ({source}), so it will not count toward graduation",
    "OTHER_STREAM_CORE_AS_ELECTIVE": "it is core for another stream, so for you it counts only as an elective",
    "OUTSIDE_PROGRAMME_LIST": "it is not on the {programme} course lists, so it counts only as an elective ({source})",
}
REC_TEXT = {
    "OWN_BASKET_GAP": "fills your {label} ({closes} of {gap} credits still needed)",
    "OTHER_BASKET_GAP": "fills the other-basket requirement ({closes} of {gap} credits still needed)",
    "OWN_BASKET_ELECTIVE": "an extra course from your {label} that counts as an elective",
    "OTHER_BASKET_ELECTIVE": "a course from another stream's basket that counts as an elective",
    "OPEN_ELECTIVE": "an open elective",
}


def _name(catalog, code):
    c = catalog.course(code)
    return f"{code} ({c['title']})" if c and c.get("title") else code


def _join(items):
    return ", ".join(items) if items else "none"


def _profile(s):
    n = s["semesters_completed"]
    return PROFILE.format(programme=s["programme"], stream=f" in the {s['stream']} stream" if s.get("stream") else "",
                          track=s["track"],
                          n_sem=f"{n} semester{'s' if n != 1 else ''}" if n else "no semesters yet")


def text_remaining(g, catalog, family):
    parts = []
    if family in ("rc_degree_audit", "rc_core_courses"):
        parts.append("Compulsory courses still missing: " + _join([_name(catalog, c) for c in g["compulsory_missing"]]) + ".")
        if g["stream"] and g["own_basket"].get("label", "own").startswith("own"):
            parts.append(f"{g['stream']} stream core still missing: "
                         + _join([_name(catalog, c) for c in g["stream_core_missing"]]) + ".")
    ob, xb = g["own_basket"], g["other_basket"]
    label = ob.get("label", f"own {g['stream']} basket")
    parts.append(f"{label[0].upper() + label[1:]}: {ob['earned']} credits earned, minimum {ob['min']} ({ob['gap']} to go).")
    if xb["min"]:
        parts.append(f"Other baskets ({', '.join(xb['streams'])}): {xb['earned']} credits earned, minimum {xb['min']} "
                     f"({xb['gap']} to go).")
    if family in ("rc_degree_audit", "rc_credit_gap"):
        unit = "thesis" if g["track"] == "thesis" else "project"
        cw, un, tot = g["coursework"], g[unit], g["total"]
        el = g["electives"]
        parts.append(f"Coursework: {cw['earned']} credits earned, minimum {cw['min']} ({cw['gap']} to go). "
                     f"{unit.capitalize()}: {un['earned']} credits earned, minimum {un['min']} ({un['gap']} to go). "
                     f"Electives: {el['earned']} credits earned, minimum {el['min']} ({el['gap']} to go).")
        pending = [k.replace("_", " ") for k, r in sorted(g["requirements"].items()) if r["status"] == "missing"]
        untracked = [k.replace("_", " ") for k, r in sorted(g["requirements"].items()) if r["status"] == "not_trackable"]
        parts.append("Other requirements pending: " + _join(pending) + "."
                     + (f" Not tracked in the catalog: {_join(untracked)}." if untracked else ""))
        parts.append(f"Total: {tot['earned']} of {tot['min']} credits, {tot['gap']} remaining.")
    if g["below_600"]["excess_courses"]:
        parts.append("Below-600 courses over the cap that do not count: " + _join(g["below_600"]["excess_courses"]) + ".")
    reasons = g["reason_codes"]
    structure = (f"compulsory courses, {g['stream']} core, at least {ob['min']} own-basket and {xb['min']} other-basket credits"
                 if xb["min"] else f"at least {ob['min']} credits of {label}")
    why = (f"Justification: checked your transcript against the {g['programme']} {g['track']} track rules "
           f"({structure}, {g['coursework']['min']} coursework credits, {g['total']['min']} total credits); "
           f"open items: {_join([r.lower().replace('_', ' ') for r in reasons])}.")
    return " ".join(parts + [why])


def text_eligibility(g, catalog, student):
    name = _name(catalog, g["course"])
    head = (f"Yes, you can register for {name} in {g['term']}." if g["eligible"]
            else f"No, you cannot register for {name} in {g['term']}.")
    src = g.get("sources", {})
    fill = {"prereqs": ", ".join(g["prerequisites"]), "unmet": ", ".join(g["unmet_prerequisites"]),
            "term": g["term"], "offered_parity": g.get("offered_parity"), "programme": student["programme"],
            "missing": "; ".join(" or ".join(grp) for grp in g.get("missing_recommended", []))}
    why = [ELIG_TEXT[r].format(**fill, source=src.get(r) or "course records") for r in g["reason_codes"] if r in ELIG_TEXT]
    notes = [WARN_TEXT[w].format(**fill, source=src.get(w) or "rules") for w in g["warnings"] if w in WARN_TEXT]
    out = f"{head} Justification: {'; '.join(why)}."
    if notes:
        out += f" Note: {'; '.join(notes)}."
    return out


def text_recommend(g, student, catalog):
    if not g["recommendations"]:
        return (f"No eligible elective is available for you in {g['term']}. "
                f"Justification: every remaining elective is already taken, blocked by prerequisites, or not offered then.")
    gaps = {"OWN_BASKET_GAP": g["gaps_before"]["own_basket"], "OTHER_BASKET_GAP": g["gaps_before"]["other_basket"]}
    items = []
    for r in g["recommendations"]:
        gap = gaps.get(r["reason_code"], 0)
        label = basket_label(catalog.rules_for(student["programme"]), student)
        why = REC_TEXT[r["reason_code"]].format(label=label, closes=r["credits_toward_gap"], gap=gap)
        if r.get("warnings"):
            why += " (note: " + ", ".join(w.lower().replace("_", " ") for w in r["warnings"]) + ")"
        items.append(f"{r['rank']}) {r['course']} ({r['title']}): {why}")
        if r["reason_code"] in gaps:
            gaps[r["reason_code"]] = max(0, gap - (r["credits"] or 0))
    return (f"Recommended for {g['term']}: " + "; ".join(items) + ". "
            f"Justification: each course is eligible (no unmet enforceable prerequisite, not ruled out for that term, "
            f"not yet taken) and "
            f"they are ranked own basket first, then other baskets, then open electives.")


NOT_ELIGIBLE_ORDER = ["PREREQ_UNMET", "ALREADY_TAKEN", "NOT_OFFERED_IN_PARITY", "NOT_OFFERED_NEXT_TERM",
                      "NOT_IN_PROGRAMME_CURRICULUM"]
WARNING_ORDER = ["MISSING_RECOMMENDED_BACKGROUND", "NOT_COUNTED_BELOW_600_CAP", "OTHER_STREAM_CORE_AS_ELECTIVE",
                 "OUTSIDE_PROGRAMME_LIST", "OFFERING_UNKNOWN"]


def case_of(g):
    """Bucket of an eligibility answer: main blocking reason, or the first warning, or CLEAN."""
    if not g["eligible"]:
        return next((r for r in NOT_ELIGIBLE_ORDER if r in g["reason_codes"]), g["reason_codes"][0])
    return next((w for w in WARNING_ORDER if w in g["warnings"]), "CLEAN")


def eligibility_buckets(students, catalog):
    buckets = {}
    for s in students:
        for code in catalog.codes:
            if catalog.course(code).get("category") in ("requirement", "ug_background"):
                continue
            g = eligibility(s, code, catalog=catalog)
            buckets.setdefault(case_of(g), []).append((s["student_id"], code))
    return buckets


def eligibility_plan(buckets):
    """Alternate eligible and not-eligible cases; eligible ones alternate CLEAN and a warning."""
    warns = [w for w in WARNING_ORDER if w in buckets]
    ok = []
    for w in warns:
        ok += ["CLEAN", w] if "CLEAN" in buckets else [w]
    ok = ok or ["CLEAN"]
    bad = [r for r in NOT_ELIGIBLE_ORDER if r in buckets]
    return ok, bad


def slot_splits(n, shares, rng):
    """n split labels with counts proportional to shares (largest remainder), in seeded order."""
    raw = {k: n * v for k, v in shares.items()}
    alloc = {k: int(raw[k]) for k in raw}
    for k in sorted(raw, key=lambda k: (-(raw[k] - alloc[k]), k))[:n - sum(alloc.values())]:
        alloc[k] += 1
    labels = [k for k in sorted(alloc) for _ in range(alloc[k])]
    rng.shuffle(labels)
    return labels


def allowed_templates(family, n, split, held):
    """Template indexes a pair in this split may use: test only the held-out one, train/val the others."""
    if not held or split not in ("train", "val", "test"):
        return list(range(n))
    h = int(held[family].rsplit("_t", 1)[1]) - 1
    return [h] if split == "test" else [i for i in range(n) if i != h]


def build(students, catalog, params, split_of=None, held=None):
    """Pairs per intent; each pair slot gets a split (in proportion to the students per split) first, then a
    student of that split and a template allowed there. Eligibility slots come in eligible/not-eligible pairs
    that share a split, so every split stays balanced."""
    rng = random.Random(params["seeds"]["queries"])
    per_intent = math.ceil(params["queries"]["min_pairs"] / 3)
    rows, used = [], {}
    by_id = {s["student_id"]: s for s in students}
    split_of = split_of or {s["student_id"]: "all" for s in students}
    pool = {}
    for s in students:
        pool.setdefault(split_of[s["student_id"]], []).append(s)
    shares = {k: len(v) / len(students) for k, v in sorted(pool.items())}
    buckets = eligibility_buckets(students, catalog)
    ok_cycle, bad_cycle = eligibility_plan(buckets)
    split_buckets = {sp: {case: [x for x in v if split_of[x[0]] == sp] for case, v in buckets.items()} for sp in pool}
    for intent, fams in FAMILIES.items():
        fam_names = sorted(fams)
        labels = slot_splits(math.ceil(per_intent / 2) if intent == "eligibility" else per_intent, shares, rng)
        for i in range(per_intent):
            family = fam_names[(i // 2) % len(fam_names)] if intent == "eligibility" else fam_names[i % len(fam_names)]
            split = labels[i // 2] if intent == "eligibility" else labels[i]
            allowed = allowed_templates(family, len(fams[family]), split, held)
            for attempt in range(400):
                s = rng.choice(pool[split])
                t_idx = rng.choice(allowed)
                target, gold = None, None
                if intent == "eligibility":
                    cycle = ok_cycle if i % 2 == 0 or not bad_cycle else bad_cycle
                    start = (i // 2) % len(cycle)
                    case = next((cycle[(start + j) % len(cycle)] for j in range(len(cycle))
                                 if split_buckets[split].get(cycle[(start + j) % len(cycle)])), None)
                    if case is None:
                        raise SystemExit(f"no eligibility case of this kind for split {split}")
                    sid, target = rng.choice(split_buckets[split][case])
                    s = by_id[sid]
                    gold = eligibility(s, target, catalog=catalog)
                elif intent == "remaining_core":
                    gold = remaining_requirements(s, catalog)
                else:
                    gold = recommend_electives(s, k=3, catalog=catalog)
                    if not gold["recommendations"]:
                        continue
                key = (s["student_id"], family, target)
                if key in used and (attempt < 200 or t_idx in used[key]):
                    continue
                used.setdefault(key, set()).add(t_idx)
                break
            else:
                raise SystemExit(f"could not find a fresh pair for {family} in split {split}")
            fill = {"profile": _profile(s), "course": target, "term": upcoming_term(s), "k": 3,
                    "title": catalog.course(target)["title"] if target else None,
                    "unit_word": "thesis" if s["track"] == "thesis" else "project"}
            if intent == "remaining_core":
                text = text_remaining(gold, catalog, family)
            elif intent == "eligibility":
                text = text_eligibility(gold, catalog, s)
            else:
                text = text_recommend(gold, s, catalog)
            rows.append({"student_id": s["student_id"], "template_id": f"{family}_t{t_idx + 1}",
                         "template_family": family, "intent": intent, "target_course": target,
                         "query_text": fams[family][t_idx].format(**fill), "gold_json": gold,
                         "gold_text": text, "para_query": None, "para_justification": None,
                         "para_model": None, "para_prompt_id": None, "augmentation": None,
                         "parent_query_id": None})
    for n, r in enumerate(rows, 1):
        r["query_id"] = f"Q{n:04d}"
    return [{"query_id": r.pop("query_id"), **r} for r in rows]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--courses", default=str(COURSES_PATH))
    ap.add_argument("--rules", default=str(RULES_PATH))
    ap.add_argument("--students", default=str(STUDENTS_PATH))
    args = ap.parse_args()
    params = load_params()
    catalog = load_catalog(args.courses, args.rules)
    with open(args.students) as f:
        students = [json.loads(line) for line in f if line.strip()]
    from src.split.assign_students import load_assignment
    split_of, held = load_assignment()
    missing = sorted({s["student_id"] for s in students} - set(split_of))
    if missing:
        raise SystemExit(f"{len(missing)} students have no split (e.g. {missing[:3]}); rerun src.split.assign_students")
    rows = build(students, catalog, params, split_of, held)
    QUERIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(QUERIES_PATH, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=False) + "\n")
    elig = [r for r in rows if r["intent"] == "eligibility"]
    summary = {
        "n_pairs": len(rows),
        "per_intent": dict(sorted(Counter(r["intent"] for r in rows).items())),
        "per_family": dict(sorted(Counter(r["template_family"] for r in rows).items())),
        "per_template": dict(sorted(Counter(r["template_id"] for r in rows).items())),
        "eligibility_eligible": sum(r["gold_json"]["eligible"] for r in elig),
        "eligibility_not_eligible": sum(not r["gold_json"]["eligible"] for r in elig),
        "not_eligible_reasons": dict(sorted(Counter(c for r in elig if not r["gold_json"]["eligible"]
                                                    for c in r["gold_json"]["reason_codes"]).items())),
        "eligible_warnings": dict(sorted(Counter(w for r in elig if r["gold_json"]["eligible"]
                                                 for w in r["gold_json"]["warnings"]).items())),
        "eligibility_cases": dict(sorted(Counter(case_of(r["gold_json"]) for r in elig).items())),
        "eligibility_terms": dict(sorted(Counter(r["gold_json"]["term"] for r in elig).items())),
        "recommendation_reasons": dict(sorted(Counter(p["reason_code"] for r in rows
                                                      if r["intent"] == "elective_recommendation"
                                                      for p in r["gold_json"]["recommendations"]).items())),
        "distinct_students": len({r["student_id"] for r in rows}),
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_PATH, "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps(summary["per_intent"]), json.dumps(summary["per_family"]))


if __name__ == "__main__":
    main()
