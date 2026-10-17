"""Build data/processed/rules.json from the M.Tech norms, the CSE course structure and the EE M.Tech site.

Each rule carries a verbatim quote; the script finds the page that contains it,
so every number is linked to source_doc and source_page (or source_section for the EE site pages),
and a missing quote fails the run.
"""
from src.collect.build_catalog import EE_ITEM_RE
from src.collect.common import EXTRACTED, PROCESSED, STRUCTURE_PDF, normalise_code, read_jsonl, record_sha, write_json

ADV5 = "Adv5_NormsforMTechProgramme.pdf"
ADV17 = "Adv17_Courses and Credit System.pdf"
ADV24 = "Adv24_Norms For Pass_Fail_Option_And_Substitution_Of_Courses.pdf"
ADV42 = "Adv42_Norms_for_Early_Admit_MTech_programme.pdf"
BOTH = ["MTech-CSE", "MTech-AI"]
TRACKS = ["thesis", "coursework"]
ALL = {"programmes": BOTH, "tracks": TRACKS, "admitted": "all"}
THESIS = {**ALL, "tracks": ["thesis"]}
COURSEWORK = {**ALL, "tracks": ["coursework"]}
FROM_2025 = {**ALL, "admitted": "from AY 2025-26"}
BEFORE_2025 = {**ALL, "admitted": "before AY 2025-26"}
FROM_2023 = {**ALL, "admitted": "from AY 2023-24"}
BEFORE_2023 = {**ALL, "admitted": "before AY 2023-24"}

# rule_id, value, unit, applies_to, extra fields, source_doc, verbatim quote
RULES = [
    ("total_min_credits", 82, "credits", ALL, {},
     ADV5, "the total minimum credit requirement for both MTech (Coursework Track) or MTech (Thesis Track) is 82"),
    ("coursework_min_credits.thesis", 32, "credits", THESIS, {"note": "disciplines may specify more than 32"},
     ADV5, "Students in the MTech (Thesis Track) will be required to earn at least 32 credits through coursework, at least 32 credits through thesis units"),
    ("thesis_min_credits.thesis", 32, "credits", THESIS, {"codes": ["REQ-THESIS"]},
     ADV5, "at least 32 credits through thesis units and 2 credits of postgraduate orientation programme Aarohan"),
    ("project_min_credits.thesis", 0, "credits", THESIS, {"codes": ["REQ-PROJECT"]},
     ADV5, "Credits through >=0 >=16 project courses"),
    ("coursework_min_credits.coursework", 48, "credits", COURSEWORK, {},
     ADV5, "Students in the MTech (Coursework Track) will be required to earn at least 48 credits through coursework"),
    ("project_min_credits.coursework", 16, "credits", COURSEWORK, {"codes": ["REQ-PROJECT"]},
     ADV5, "at least 16 credits through project courses and 2 credits of postgraduate orientation programme Aarohan"),
    ("thesis_min_credits.coursework", 0, "credits", COURSEWORK, {"codes": ["REQ-THESIS"]},
     ADV5, "Credits through >=32 0 thesis"),
    ("aarohan_credits", 2, "credits", ALL, {"codes": ["FP 601"]},
     ADV5, "Completing PG Orientation Programme Aarohan (2 Credits) is a mandatory graduation requirement for all MTech students"),
    ("aarohan_fail_extra_hss_credits", 2, "credits", ALL, {"codes": ["REQ-HSS"], "note": "students joining from Semester II 2022-23 onwards"},
     ADV5, "In cases where a student fails to clear Aarohan, they must clear an additional two credits worth of HSS courses for graduation"),
    ("writing_credits", 4, "credits", ALL, {"codes": ["FP 602"]},
     ADV5, "The 4-credit “Writing” course will be required for all students."),
    ("hss_min_credits", 4, "credits", BEFORE_2025, {"codes": ["REQ-HSS"]},
     ADV5, "For students admitted before AY 2025-26, in addition to the Writing course, at least 4 credits will have to be earned through Humanities and Social Sciences (HSS) courses"),
    ("hss_ug_courses_allowed", 1, "courses", BEFORE_2025, {},
     ADV5, "One undergraduate level HSS course may be counted towards this requirement."),
    ("applications_of_ai_credits", 4, "credits", FROM_2025, {"codes": ["CS 621"], "note": "for MTech AI and MTech CSE this is Ethics of AI"},
     ADV5, "For students admitted from AY 2025-26, 4 credits of Applications of AI courses relevant to the discipline is mandatory"),
    ("applications_of_ai_course", "CS 621", "code", FROM_2025, {"codes": ["CS 621"]},
     ADV5, "the 4 credits of course on Applications of AI relevant to the discipline shall be “Ethics of AI”"),
    ("electives_min_credits", 8, "credits", ALL, {},
     ADV5, "Students must take at least 8 credits of electives inside or outside the discipline."),
    ("discipline_specified_min_credits", 16, "credits", ALL,
     {"note": "the CSE structure lists the discipline courses: compulsory, stream core and baskets. It does not say whether CS 610/CS 621 count inside these 16 credits"},
     ADV5, "Students must take at least 16 credits of courses specified by the discipline."),
    ("ug_courses_max", 2, "courses", ALL,
     {"levels": "1XX to 5XX", "note": "besides one UG level HSS course. Sources cap the number of UG courses, not a credit total"},
     ADV5, "Two undergraduate level courses (with course codes 1XX to 5XX) may be counted towards graduation requirements (besides one UG level HSS course)."),
    ("below_600_constraint_applies", True, "flag", ALL, {"see": "ug_courses_max"},
     STRUCTURE_PDF, "For any < 600 level course, the usual constraint on the number of such credits permissible applies."),
    ("physical_education_courses", 2, "courses", ALL, {"codes": ["PE 600"], "credits_each": 0, "grading": "Pass/No Pass", "when": "one each in the first two semesters"},
     ADV5, "must complete two Physical Education (PE) courses, one each in their first two semesters, as part of their graduation requirements"),
    ("pe_credits_each", 0, "credits", ALL, {"codes": ["PE 600"]},
     ADV5, "2 physical education courses of zero credit each."),
    ("compulsory_courses", ["CS 610", "CS 621"], "codes", ALL, {},
     STRUCTURE_PDF, "CS 610 (Algorithms) is a compulsory course for all streams"),
    ("compulsory_cs621", "CS 621", "code", ALL, {"offered": "even"},
     STRUCTURE_PDF, "CS 621 (Ethics of AI) is a compulsory course for all streams (Offered in Even semester)."),
    ("compulsory_cs610_offered", "odd", "semester", ALL, {"codes": ["CS 610"]},
     STRUCTURE_PDF, "(Offered in Odd semester)."),
    ("stream_core_credits", 8, "credits", ALL, {},
     STRUCTURE_PDF, "the core courses (in red below - 8 credits)"),
    ("stream_core.AI/ML", ["ES 678", "ES 667"], "codes", ALL, {"stream": "AI/ML"},
     STRUCTURE_PDF, "ES 678: Machine Learning"),
    ("stream_core.Systems", ["CS 612", "CS 616"], "codes", {**ALL, "programmes": ["MTech-CSE"]}, {"stream": "Systems"},
     STRUCTURE_PDF, "CS 612: Computer Systems"),
    ("stream_core.Theory", ["CS 619", "CS 614"], "codes", {**ALL, "programmes": ["MTech-CSE"]}, {"stream": "Theory"},
     STRUCTURE_PDF, "CS 619: CS Theory Toolkit"),
    ("own_basket_min_credits", 4, "credits", ALL, {},
     STRUCTURE_PDF, "at least 4 credits in the respective baskets (in blue below)"),
    ("other_basket_min_credits", 4, "credits", ALL, {"note": "from any of the other two baskets"},
     STRUCTURE_PDF, "at least 4 credits from any of the other two baskets"),
    ("mtech_ai_stream", "AI/ML", "stream", {**ALL, "programmes": ["MTech-AI"]}, {},
     STRUCTURE_PDF, "MTech in AI is deemed to be in the AI-ML stream only and should follow the corresponding curriculum."),
    ("remaining_credits_sources", ["any CS course (offline)", "any basket course"], "options", ALL, {},
     STRUCTURE_PDF, "Any CS xxx tagged course (offline)"),
    ("online_courses_count", False, "flag", ALL, {},
     STRUCTURE_PDF, "Note that no online courses count here."),
    ("thesis_unit_credits", 4, "credits", THESIS, {"codes": ["REQ-THESIS"], "note": "register for one unit or a multiple of it"},
     ADV5, "A student may register for one 4 credit thesis unit or a multiple of it"),
    ("thesis_first_semester", False, "flag", THESIS, {"note": "normally no thesis registration in the first semester, thesis in the remaining three"},
     ADV5, "It is normally expected that students will not register for the thesis in their first semester"),
    ("thesis_summer_credits", 10, "credits", THESIS, {"note": "about 10 credits of thesis in summer unless waived"},
     ADV5, "register for about 10 credits of thesis in summer unless there is a specific waiver on justifiable grounds"),
    ("thesis_project_grades", ["A", "B", "C", "F"], "grades", FROM_2023, {"passing": ["A", "B", "C"]},
     ADV5, "The thesis units will be graded using A, B, C and F grades, where A, B and C are passing grades and F is a fail grade."),
    ("thesis_f_credits_exit", 20, "credits", FROM_2023, {"note": "exit if F grades in more than 20 thesis credits"},
     ADV5, "If a student accumulates F grades in more than 20 credits of thesis units any time during their MTech programme, the student will have to exit the programme."),
    ("thesis_grades_in_cpi", False, "flag", ALL, {},
     ADV5, "Thesis grades will not be counted towards CPI calculation."),
    ("project_grades", ["A", "B", "C", "F"], "grades", COURSEWORK, {"counts_in_cpi": True},
     ADV5, "The project courses will be graded using only A, B, C and F grades"),
    ("project_credits_in_cpi", True, "flag", COURSEWORK, {},
     ADV5, "the credits earned through project courses will be counted towards CPI calculation."),
    ("credit_expiry_years", 8, "years", FROM_2023, {},
     ADV5, "credits earned older than eight years will be deemed expired"),
    ("extension_request_after_semesters", 7, "semesters", FROM_2023, {},
     ADV5, "After 7 semesters, a request from the student is needed to extend the programme"),
    ("fellowship_min_cpi", 6.0, "cpi", ALL, {},
     ADV5, "In case the CPI of a student falls below 6.0 out of 10, the fellowship provided, if any, by the Institute will be stopped"),
    ("min_cpi_graduation", 6.0, "cpi", BEFORE_2023, {},
     ADV5, "The minimum CPI for graduation is 6.0 out of 10."),
    ("min_cpi_continuation", 5.5, "cpi", BEFORE_2023, {},
     ADV5, "The minimum CPI for continuing in the programme at any point is 5.5 out of 10."),
    ("max_duration_years", 3, "years", BEFORE_2023, {},
     ADV5, "Full-time MTech students will have a maximum of three years to obtain the degree."),
    ("track_change_deadline", "beginning of second semester", "deadline", ALL, {"max_changes": 1},
     ADV5, "Students may request a change of track once during their programme of study, but at the latest, by the beginning of the second semester."),
    ("pass_fail_conversions_max", 2, "courses", ALL, {"note": "converted course is dropped from CPI"},
     ADV24, "Each student will have this option available for a maximum of two courses for conversion during the entire programme."),
    ("pass_fail_earliest", "after first semester", "timing", ALL, {},
     ADV24, "The students in other programmes can use this option any time after their first semester into the programme."),
    ("repeat_best_grade_counts", True, "flag", ALL, {},
     ADV24, "Better of the two grades will be counted towards CPI calculation"),
    ("elective_substitution", True, "flag", ALL, {},
     ADV24, "A student can substitute one elective course by another elective course to improve his/her CPI"),
    ("level_600_is_pg", 600, "level", ALL, {},
     ADV17, "XX:600 PG/PhD level course"),
    ("standard_course_credits", 4, "credits", ALL, {"ltp": [3, 0, 0]},
     ADV17, "Usually the courses will have 3 lectures per week with approximately 40 lecture hours in a semester, which is defined as a 4 credit course."),
    ("course_credit_range", [1, 5], "credits", ALL, {},
     ADV17, "a course may usually have credits in the range of 1-5"),
    ("early_admit_same_curriculum", True, "flag", ALL, {},
     ADV42, "The fees structure, the curriculum as well as other regulations will be same as that of the regular MTech programme at IIT Gandhinagar."),
    ("early_admit_extra_fellowship_cpi", 8.0, "cpi", ALL, {"note": "Early Admit students only"},
     ADV42, "The continuation of additional fellowship beyond the first semester is subject to the student maintaining a CPI 8.0 and above."),
]
EE_HOME = "ee_mtech_site/home.html"
EE = {"programmes": ["MTech-EE"], "tracks": ["thesis"], "admitted": "all"}
EE_STREAM_PAGES = {
    "Power Engineering & Control Systems": "ee_mtech_site/power-engineering-control-systems.html",
    "Signal Processing & Machine Learning": "ee_mtech_site/signal-processing-machine-learning.html",
    "Integrated Circuit Design & Technology": "ee_mtech_site/integrated-circuit-design-technology.html",
}
EE_LIST_QUOTE = ("Students must credit at least 16 credits of courses from this list under the 'Courses Specified by "
                 "the Discipline' basket. The courses in this list can also be considered as Electives.")
# rule_id, value, unit, applies_to, extra fields, source_doc, source_section, verbatim quote
EE_RULES = [
    ("ee.total_min_credits", 82, "credits", EE, {"overrides": "total_min_credits"},
     EE_HOME, "Curriculum", "Total Credits 82"),
    ("ee.coursework_min_credits", 42, "credits", EE, {"overrides": "coursework_min_credits.thesis"},
     EE_HOME, "Curriculum", "Coursework Credits 42"),
    ("ee.thesis_min_credits", 40, "credits", EE, {"overrides": "thesis_min_credits.thesis", "codes": ["REQ-THESIS"]},
     EE_HOME, "Curriculum", "Thesis Credits 40"),
    ("ee.thesis_units", 10, "units of 4 credits", EE, {"codes": ["REQ-THESIS"]},
     EE_HOME, "Curriculum", "10 x 4 Credit Thesis Units"),
    ("ee.credit_split", [42, 40], "credits", EE, {"note": "coursework, thesis"},
     EE_HOME, "Curriculum", "42 credits through coursework and 40 credits through thesis credits."),
    ("ee.aarohan_credits", 2, "credits", EE, {"codes": ["FP 601"]},
     EE_HOME, "Curriculum", "Aarohan - 2 Credits"),
    ("ee.writing_credits", 4, "credits", EE, {"codes": ["FP 602"]},
     EE_HOME, "Curriculum", "Writing - 4 Credits"),
    ("ee.applications_of_ai_credits", 4, "credits", EE, {"note": "the EE site does not name the course"},
     EE_HOME, "Curriculum", "4 credits of Applications of AI courses relevant to the discipline"),
    ("ee.electives_min_credits", 8, "credits", EE, {},
     EE_HOME, "Curriculum", "Electives - At least 8 Credits"),
    ("ee.discipline_specified_min_credits", 16, "credits", EE, {"see": "ee.discipline_list.<stream>"},
     EE_HOME, "Curriculum", "Courses specified by the Discipline - At least 16 Credits"),
    ("ee.physical_education_courses", 2, "courses", EE, {"codes": ["PE 600"], "credits_each": 0, "grading": "Pass/Fail"},
     EE_HOME, "Curriculum", "Physical Education - 2 Courses (Zero credit each)"),
    ("ee.fellowship_after_aarohan", True, "flag", EE, {},
     EE_HOME, "Curriculum", "Fellowship (if eligible) will be usually released only after completion of Aarohan."),
    ("ee.ug_elective_credits_max", 8, "credits", EE, {"overrides": "ug_courses_max", "levels": "5XX or below", "group": "electives"},
     EE_HOME, "Curriculum", "A maximum of 8 Credits from the Electives group can be at the undergraduate level (Course Code 5XX or below)."),
    ("ee.other_courses_min_level", 600, "level", EE, {},
     EE_HOME, "Curriculum", "All other courses MUST be at the postgraduate level (Course Code 6XX or above)."),
    ("ee.mooc_electives_allowed", True, "flag", EE, {"note": "pre-approved MOOCs only, electives group only, within approved credit limits"},
     EE_HOME, "Curriculum", "Pre-approved MOOCs, subject to approved credit limits, can be considered for courses from the Electives group."),
    ("ee.sub_specialisations", ["Power Engineering & Control Systems", "Signal Processing & Machine Learning"], "streams",
     {**EE, "admitted": "from AY 2025-26"}, {"degree": "MTech (Electrical Engineering), no specialization on the degree"},
     EE_HOME, "A. Electrical Engineering", "The following sub-specializations are offered for MTech in Electrical Engineering, for students admitted from 2025-26."),
    ("ee.icdt_degree", "MTech (Integrated Circuit Design & Technology)", "degree", EE,
     {"note": "the site lists ICDT as a separate degree; it is modelled here as an MTech-EE stream as instructed"},
     EE_HOME, "B. Integrated Circuit Design & Technology", "The degree offered is MTech (Integrated Circuit Design & Technology)"),
]
NOT_STATED = {
    "max_credits_per_semester": "no maximum credits per semester is stated in Adv5, Adv17, Adv24, Adv42, the CSE structure or the EE M.Tech site",
}
CSE_AI_ONLY = {"applications_of_ai_course"}
ALL_PROGRAMMES = ["MTech-CSE", "MTech-AI", "MTech-EE"]


def page_of(pages, doc, quote):
    flat = " ".join(quote.split())
    for p in pages:
        if p["file"] == doc and flat in " ".join(p["text"].split()):
            return p["page"]
    raise ValueError(f"quote not found in {doc}: {quote}")


def check_section(sections, doc, section, quote):
    flat = " ".join(quote.split())
    for p in sections:
        if p["file"] == doc and p["section"] == section and flat in " ".join(p["text"].split()):
            return section
    raise ValueError(f"quote not found in {doc} [{section}]: {quote}")


def ee_stream_codes(sections, doc):
    text = next(p["text"] for p in sections if p["file"] == doc and p["section"] == "Curriculum")
    codes = []
    for line in text.splitlines():
        m = EE_ITEM_RE.match(line)
        if m:
            code = normalise_code(m.group(1))
            if code not in codes:
                codes.append(code)
    return codes


def add(rules, entry):
    if entry["rule_id"] in rules:
        raise ValueError(f"duplicate rule id {entry['rule_id']}")
    entry["record_sha256"] = record_sha(entry)
    rules[entry["rule_id"]] = entry


def build():
    pages = read_jsonl(EXTRACTED / "pages.jsonl")
    sections = read_jsonl(EXTRACTED / "ee_pages.jsonl")
    rules = {}
    for rule_id, value, unit, applies, extra, doc, quote in RULES:
        applies = dict(applies)
        if doc != STRUCTURE_PDF and rule_id not in CSE_AI_ONLY:
            applies["programmes"] = list(ALL_PROGRAMMES)
        add(rules, {"rule_id": rule_id, "value": value, "unit": unit, "applies_to": applies, **extra,
                    "source_doc": doc, "source_page": page_of(pages, doc, quote), "source_section": None,
                    "quote": quote})
    for rule_id, value, unit, applies, extra, doc, section, quote in EE_RULES:
        add(rules, {"rule_id": rule_id, "value": value, "unit": unit, "applies_to": applies, **extra,
                    "source_doc": doc, "source_page": None,
                    "source_section": check_section(sections, doc, section, quote), "quote": quote})
    for stream, doc in EE_STREAM_PAGES.items():
        extra = {"stream": stream, "min_credits": 16, "also_count_as_electives": True}
        if "integrated" in doc:
            extra["note"] = "the page marks this list '*To be updated soon'"
        add(rules, {"rule_id": f"ee.discipline_list.{stream}", "value": ee_stream_codes(sections, doc),
                    "unit": "codes", "applies_to": EE, **extra, "source_doc": doc, "source_page": None,
                    "source_section": check_section(sections, doc, "Curriculum", EE_LIST_QUOTE), "quote": EE_LIST_QUOTE})
    for rule_id, why in NOT_STATED.items():
        rules[rule_id] = {"rule_id": rule_id, "value": None, "unit": "credits",
                          "applies_to": {**ALL, "programmes": list(ALL_PROGRAMMES)}, "not_stated": True, "note": why,
                          "source_doc": None, "source_page": None, "source_section": None, "quote": None}
    return {
        "programmes": {
            "MTech-CSE": {"streams": ["AI/ML", "Systems", "Theory"], "tracks": TRACKS},
            "MTech-AI": {"streams": ["AI/ML"], "tracks": TRACKS},
            "MTech-EE": {"streams": list(EE_STREAM_PAGES), "tracks": ["thesis"],
                         "note": "the EE site describes only the thesis structure (42 coursework + 40 thesis); "
                                 "no EE coursework track is described, so none is modelled"},
        },
        "precedence": "a rule with 'overrides' replaces the named common rule for its programmes",
        "placeholder_codes": {
            "REQ-HSS": "HSS course, no single timetable code (HS xxx courses qualify)",
            "REQ-THESIS": "M.Tech thesis unit, no code in the Sem-I 2026-27 timetable",
            "REQ-PROJECT": "PG project course, no code in the Sem-I 2026-27 timetable",
        },
        "requirement_codes": {"writing": "FP 602", "aarohan": "FP 601", "physical_education": "PE 600",
                              "applications_of_ai": "CS 621"},
        "applications_of_ai_by_programme": {"MTech-CSE": "CS 621", "MTech-AI": "CS 621", "MTech-EE": None},
        "rules": rules,
    }


def main():
    out = build()
    write_json(PROCESSED / "rules.json", out)
    n = sum(1 for r in out["rules"].values() if not r.get("not_stated"))
    print(f"rules extracted={n} not_stated={len(NOT_STATED)}")


if __name__ == "__main__":
    main()
