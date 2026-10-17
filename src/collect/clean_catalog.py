"""Clean data/raw/catalog_raw.json into data/processed/courses.json.

Every change is written to supporting_files/A_collection/cleaning_changes.csv.
Prerequisites come from course plan text, data/raw/prereq_manual.csv overrides them.
"""
import csv
import json
import re

from src.collect.common import (CODE_RE, EVIDENCE, EXTRACTED, PROCESSED, ROOT, STREAMS,
                                TIMETABLE_XLSX, normalise_code, read_jsonl, record_sha, write_json)

ADV5 = "Adv5_NormsforMTechProgramme.pdf"
ADV17 = "Adv17_Courses and Credit System.pdf"
TYPO_FIXES = {"Algrithms": "Algorithms"}
CATEGORY_RANK = ["compulsory", "stream_core", "basket", "requirement", "open_elective"]
# Placeholder codes for requirements that have no course code in the timetable.
PLACEHOLDERS = {
    "hss": ("REQ-HSS", "HSS course (students admitted before AY 2025-26)"),
    "thesis_units": ("REQ-THESIS", "M.Tech thesis unit"),
    "project_courses": ("REQ-PROJECT", "Postgraduate level project course"),
}
# Credits stated in a rules document rather than the timetable.
RULE_CREDITS = {
    "CS 621": (4, ADV5, "4 credits of Applications of AI courses relevant to the discipline is mandatory"),
    "REQ-THESIS": (4, ADV5, "A student may register for one 4 credit thesis unit or a multiple of it"),
}
DEFAULT_CREDITS = (4, ADV17, "Usually the courses will have 3 lectures per week with approximately 40 lecture hours in a semester, which is defined as a 4 credit course.")
HEADER_RE = re.compile(r"^\W*(?:\d+\.\s*)?(?:background and\s+)?(?:pre-?\s?requisites?|prereqs?|recommended background)\b(.*)$", re.I)
NONE_RE = re.compile(r"\bnone\b|no formal prerequisite|not mandatory|does not set hard prerequisites|no prerequisites?\b", re.I)
QUALIFIER_RE = re.compile(r"^[\s:·\-()]*(?:optional|ug|pg)?[\s:·\-()]*$", re.I)
SUFFIX_RE = re.compile(r"\s*\(([A-Z]{1,3})\)\s*$")
SOFT_RE = re.compile(r"optional|recommended|preferred|not mandatory|background|\bUG\b|or equivalent", re.I)
ALT_SEP_RE = re.compile(r"^\s*(?:/|\bor\b)\s*$", re.I)
_tt = re.search(r"(Sem-[IV]+),\s*(\d{4}-\d{2})", TIMETABLE_XLSX)
TIMETABLE_TERM = f"{_tt.group(2)} {_tt.group(1)}"

changes = []


def log_change(record_id, field, before, after, reason):
    changes.append({"record_id": record_id, "field": field, "before": before, "after": after, "reason": reason})


def find_page(doc, quote):
    flat = " ".join(quote.split())
    for p in read_jsonl(EXTRACTED / "pages.jsonl"):
        if p["file"] == doc and flat in " ".join(p["text"].split()):
            return p["page"]
    raise ValueError(f"quote not found in {doc}: {quote[:60]}")


def clean_title(rec):
    title = rec["title_raw"]
    if title is None:
        return None
    new = title.strip().rstrip(",").strip()
    if new != title:
        log_change(rec["raw_id"], "title", title, new, "stripped trailing whitespace or comma")
    for bad, good in TYPO_FIXES.items():
        if bad in new:
            fixed = new.replace(bad, good)
            log_change(rec["raw_id"], "title", new, fixed, f"typo '{bad}' in source, corrected to '{good}'")
            new = fixed
    return new


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


PLAN_LOGS = ["course_plan_fetch_log.csv", "ee_course_plan_fetch_log.csv"]
PLAN_TEXTS = ["course_plan_text.jsonl", "ee_course_plan_text.jsonl"]
STRUCTURE_PREFIXES = ("Revised CSE", "ee_mtech_site/")
PROGRAMME_ORDER = ["MTech-CSE", "MTech-AI", "MTech-EE"]


def plan_status():
    status = {}
    for name in PLAN_LOGS:
        if not (EVIDENCE / name).exists():
            continue
        with open(EVIDENCE / name) as f:
            for r in csv.DictReader(f):
                prev = status.get(r["code"])
                if prev != "ok":
                    status[r["code"]] = r["outcome"] if r["outcome"] != "failed" else f"failed: {r['detail']}"
    return status


def load_plans():
    plans = {}
    for name in PLAN_TEXTS:
        if (EXTRACTED / name).exists():
            for r in read_jsonl(EXTRACTED / name):
                plans[r["code"]] = r
    return plans


def code_level(code):
    m = re.search(r"\d", code.split()[1]) if " " in code else None
    return int(m.group()) * 100 if m else None


def prereq_block(lines):
    """Return evidence lines for each prerequisite heading, PG-specific headings preferred."""
    blocks = []
    for i, line in enumerate(lines):
        m = HEADER_RE.match(line)
        if not m:
            continue
        block, rest = [line], m.group(1)
        j = i + 1
        while QUALIFIER_RE.match(rest) and j < len(lines):
            block.append(lines[j])
            rest = lines[j] if len(lines[j].strip(" :")) > 1 else ""
            j += 1
        while j < len(lines) and len(lines[j]) < 200 and not HEADER_RE.match(lines[j]) and \
                (CODE_RE.search(lines[j]) or re.search(r"or equivalent", lines[j], re.I)):
            block.append(lines[j])
            j += 1
        blocks.append(block)
    return blocks


def code_groups(line):
    """Codes in a line, alternatives joined by '/' or 'or' grouped together."""
    groups, prev_end = [], None
    for m in CODE_RE.finditer(line):
        code = normalise_code(m.group(0))
        if groups and prev_end is not None and ALT_SEP_RE.match(line[prev_end:m.start()]):
            groups[-1].append(code)
        else:
            groups.append([code])
        prev_end = m.end()
    return groups


def map_titles(text, titles):
    low = text.lower()
    hits = []
    for title, codes in titles.items():
        if len(codes) != 1 or not re.search(rf"\b{re.escape(title)}\b", low):
            continue
        if any(title != t and title in t and re.search(rf"\b{re.escape(t)}\b", low) for t in titles):
            continue
        hits.append(codes[0])
    return hits


def extract_prereqs(code, plans, status, titles):
    """Return (hard codes, prereq_source, evidence, recommended_background) from the course plan.

    A block is soft (recommended background) when its heading or its lines say optional,
    recommended, preferred, not mandatory, background, UG or "or equivalent". UG-level codes
    (below 600) are always recommended background, because M.Tech students come from other
    universities with equivalent courses. Only a PG-level code named in a non-optional
    prerequisite statement is an enforceable prerequisite.
    """
    plan = plans.get(code)
    if plan is None:
        why = status.get(code, "no_url")
        detail = "no course plan link in the Sem-I 2026-27 timetable" if why == "no_url" else f"download {why}"
        return [], "none_stated", f"no course plan available ({detail})", []
    lines = [" ".join(x.split()) for x in plan["text"].splitlines() if x.strip()]
    if len(" ".join(lines)) < 50:
        return [], "none_stated", f"no course plan available ({plan['file']} has no extractable text)", []
    blocks = prereq_block(lines)
    if not blocks:
        return [], "none_stated", f"course plan {plan['file']} has no prerequisite statement", []
    evidence = " || ".join(" | ".join(b) for b in blocks)
    hard, recommended = set(), []
    for b in blocks:
        text = " ".join(b)
        soft_block = bool(SOFT_RE.search(b[0]) or SOFT_RE.search(text))
        if NONE_RE.search(text) and not soft_block:
            continue
        for line in b:
            groups = [[c for c in g if c and c != code] for g in code_groups(line)]
            groups = [g for g in groups if g]
            soft_line = soft_block or SOFT_RE.search(line)
            for g in groups:
                if soft_line or any((code_level(c) or 0) < 600 for c in g):
                    recommended.append({"any_of": sorted(set(g)), "evidence": line, "source_doc": plan["file"]})
                else:
                    hard |= set(g)
            if not soft_line:
                hard |= {c for c in map_titles(line, titles) if c != code and (code_level(c) or 0) >= 600}
    seen, uniq = set(), []
    for r in recommended:
        key = tuple(r["any_of"])
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    return sorted(hard), "course_plan" if hard else "none_stated", evidence, uniq


def load_manual():
    with open(ROOT / "data" / "raw" / "prereq_manual.csv") as f:
        return {r["code"]: r for r in csv.DictReader(f)}


def merge(code, recs):
    struct = [r for r in recs if r["source_doc"].startswith(STRUCTURE_PREFIXES)]
    reqs = [r for r in recs if r["role"] == "requirement"]
    tt = [r for r in recs if r["role"] == "timetable_offering"]
    roles = {r["role"] for r in recs}
    category = "open_elective"
    for c in CATEGORY_RANK:
        if c in roles:
            category = c
            break
    if category == "compulsory":
        streams = list(STREAMS)
    else:
        streams = sorted({r["stream"] for r in struct if r["stream"]},
                         key=lambda x: (STREAMS.index(x) if x in STREAMS else len(STREAMS), x))
    titles = {r["raw_id"]: clean_title(r) for r in recs if r["title_raw"] is not None}
    title = None
    if tt:
        title = titles[tt[0]["raw_id"]]
    elif struct:
        title = titles[struct[0]["raw_id"]]
    elif reqs:
        title = titles[reqs[0]["raw_id"]]
    for r in struct:
        if titles[r["raw_id"]] != title:
            log_change(r["raw_id"], "title", titles[r["raw_id"]], title,
                       f"title taken from timetable row {tt[0]['source_row']} (official course name)" if tt else
                       f"title taken from the first structure listing ({struct[0]['source_doc']})")
    credits, credits_source, ltp = None, None, None
    if tt:
        cs = {to_float(r["C"]) for r in tt}
        if len(cs) > 1:
            raise ValueError(f"conflicting credits for {code}: {cs}")
        c = cs.pop()
        credits, credits_source = int(c), "timetable"
        for r in tt:
            if isinstance(r["C"], float):
                log_change(r["raw_id"], "credits", r["C"], credits, "float credit in xlsx converted to int")
        ltp_vals = [to_float(tt[0][k]) for k in ("L", "T", "P")]
        ltp = ltp_vals if all(v is not None for v in ltp_vals) else None
    elif code in RULE_CREDITS:
        credits, doc, quote = RULE_CREDITS[code]
        credits_source = f"rules_doc: {doc} p{find_page(doc, quote)}"
    else:
        credits, doc, quote = DEFAULT_CREDITS
        credits_source = f"default: {doc} p{find_page(doc, quote)} (standard 3-0-0 course = 4 credits)"
    offered_parity, evidence = None, []
    for r in struct:
        if r.get("offered_raw"):
            offered_parity = r["offered_raw"].lower()
            evidence.append(f"{r['source_doc']} p{r['source_page']}: {r['line']}")
    offered_terms = [TIMETABLE_TERM] if tt else []
    if tt:
        evidence.append(f"{TIMETABLE_XLSX} row {tt[0]['source_row']}: listed in {TIMETABLE_TERM}")
    primary = (struct or reqs or tt)[0]
    others = [r for r in recs if r is not primary]
    seen, dedup = set(), []
    for r in others:
        key = (r["source_doc"], r["source_page"], r["source_row"])
        if key in seen or key == (primary["source_doc"], primary["source_page"], primary["source_row"]):
            log_change(r["raw_id"], "record", r["raw_id"], primary["raw_id"],
                       "duplicate listing in the same source merged into one course record")
            continue
        seen.add(key)
        dedup.append({"source_doc": r["source_doc"], "source_page": r["source_page"], "source_row": r["source_row"],
                      "source_section": r.get("source_section")})
    url = next((r["course_plan_url"] for r in tt if r.get("course_plan_url")), None)
    level = int(code.split()[1][0]) * 100 if not code.startswith("REQ-") else None
    progs = {p for r in recs for p in (r.get("programmes") or [])}
    programmes = [p for p in PROGRAMME_ORDER if p in progs] + sorted(progs - set(PROGRAMME_ORDER))
    return {"code": code, "title": title, "credits": credits, "credits_source": credits_source, "ltp": ltp,
            "level": level, "category": category, "streams": streams, "programmes": programmes,
            "offered_parity": offered_parity, "offered_terms": offered_terms,
            "offering_evidence": " || ".join(evidence) or None, "source_doc": primary["source_doc"],
            "source_page": primary["source_page"], "source_section": primary.get("source_section"),
            "source_row": primary["source_row"], "source_url": url, "other_sources": dedup}


def ug_background_records(courses, plans):
    """Codes referenced by prerequisites or recommended background that are not M.Tech catalog courses."""
    known = {c["code"] for c in courses}
    tt_titles = {}
    for r in read_jsonl(EXTRACTED / "timetable_rows.jsonl"):
        code = normalise_code(r["course_number_raw"])
        if code and code not in tt_titles:
            tt_titles[code] = (r["title"], r["row"])
    refs = {}
    for c in courses:
        for p in c["prerequisites"]:
            refs.setdefault(p, []).append((c["code"], c["prereq_evidence"], None))
        for rb in c["recommended_background"]:
            for p in rb["any_of"]:
                refs.setdefault(p, []).append((c["code"], rb["evidence"], rb["source_doc"]))
    out = []
    for code in sorted(set(refs) - known):
        by, line, doc = refs[code][0]
        title, row = tt_titles.get(code, (None, None))
        plan = plans.get(by, {})
        rec = {"code": code, "title": title, "credits": None,
               "credits_source": "not counted: UG background course, not part of the M.Tech catalog",
               "ltp": None, "level": int(code.split()[1][0]) * 100, "category": "ug_background",
               "streams": [], "programmes": [], "prerequisites": [], "prereq_source": "none_stated",
               "prereq_evidence": "UG background course, prerequisites not tracked",
               "recommended_background": [], "offered_parity": None, "offered_terms": [],
               "offering_evidence": None, "source_doc": doc or plan.get("file"), "source_page": None,
               "source_section": None, "source_row": None, "source_url": plan.get("source_url"),
               "other_sources": [{"source_doc": TIMETABLE_XLSX, "source_page": None, "source_row": row,
                                  "source_section": None}] if row else []}
        log_change(code, "record", None, "added",
                   f"referenced by {', '.join(sorted({b for b, _, _ in refs[code]}))} ('{line}'), "
                   f"added as ug_background so every referenced code exists"
                   + (f"; title from timetable row {row}" if title else "; no title in any source"))
        out.append(rec)
    return out


def main():
    changes.clear()
    raw = json.load(open(ROOT / "data" / "raw" / "catalog_raw.json"))
    groups = {}
    for r in raw:
        if r["role"] == "requirement" and r["code_raw"] is None:
            code, title = PLACEHOLDERS[r["requirement"]]
            log_change(r["raw_id"], "code", None, code, "requirement without a course code in the timetable, placeholder code assigned")
            r = {**r, "title_raw": title}
        else:
            code = normalise_code(r["code_raw"])
            if code != r["code_raw"]:
                suffix = SUFFIX_RE.search(r["code_raw"])
                if suffix and r["role"] == "timetable_offering" and code == "FP 602":
                    log_change(r["raw_id"], "record", r["code_raw"], "dropped",
                               f"Writing variant for another PG programme ({r['title_raw']}), M.Tech uses FP 602 row")
                    continue
                log_change(r["raw_id"], "code", r["code_raw"], code,
                           "section suffix stripped" if suffix else "code spacing normalised")
        groups.setdefault(code, []).append(r)
    for code, recs in groups.items():
        tt = [r for r in recs if r["role"] == "timetable_offering"]
        for r in tt[1:]:
            log_change(r["raw_id"], "record", r["raw_id"], tt[0]["raw_id"],
                       "same course listed again in the timetable under another discipline, merged")
    courses = [merge(code, recs) for code, recs in sorted(groups.items())]
    titles = {}
    for c in courses:
        if c["title"] and not c["code"].startswith("REQ-"):
            titles.setdefault(c["title"].lower(), []).append(c["code"])
    plans = load_plans()
    status, manual = plan_status(), load_manual()
    for c in courses:
        if c["category"] == "requirement":
            c["prerequisites"], c["prereq_source"], c["recommended_background"] = [], "none_stated", []
            c["prereq_evidence"] = "requirement entry, prerequisites not applicable"
        else:
            (c["prerequisites"], c["prereq_source"], c["prereq_evidence"],
             c["recommended_background"]) = extract_prereqs(c["code"], plans, status, titles)
        if c["code"] in manual:
            m = manual[c["code"]]
            before = c["prerequisites"]
            c["prerequisites"] = [x.strip() for x in m["prerequisites"].split(";") if x.strip()]
            c["prereq_source"] = "manual"
            c["prereq_evidence"] = f"{m['reason']} [plan text: {m['evidence']}]"
            log_change(c["code"], "prerequisites", ";".join(before), ";".join(c["prerequisites"]),
                       "manual decision from data/raw/prereq_manual.csv")
    courses = sorted(courses + ug_background_records(courses, plans), key=lambda c: c["code"])
    for c in courses:
        c["record_sha256"] = record_sha(c)
    order = ["code", "title", "credits", "credits_source", "ltp", "level", "prerequisites", "prereq_source",
             "prereq_evidence", "recommended_background", "category", "streams", "programmes", "offered_parity",
             "offered_terms", "offering_evidence", "source_doc", "source_page", "source_section", "source_row", "source_url",
             "other_sources", "record_sha256"]
    courses = [{k: c[k] for k in order} for c in courses]
    write_json(PROCESSED / "courses.json", courses)
    with open(EVIDENCE / "cleaning_changes.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["record_id", "field", "before", "after", "reason"])
        w.writeheader()
        w.writerows(changes)
    with_pre = sum(bool(c["prerequisites"]) for c in courses)
    with_rec = sum(bool(c["recommended_background"]) for c in courses)
    ug = sum(c["category"] == "ug_background" for c in courses)
    print(f"raw={len(raw)} processed={len(courses)} with_prereqs={with_pre} with_recommended={with_rec} "
          f"ug_background={ug} changes={len(changes)}")


if __name__ == "__main__":
    main()
