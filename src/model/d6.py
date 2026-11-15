"""D6 label policy for Assignment 2: a passed course may be registered again to improve the grade.

Academic Advisory 24 (B.1) lets a student repeat a passed compulsory or elective course; the better grade counts and
no new credits are earned. The A1 rule engine blocks such a course with ALREADY_TAKEN. For A2 labels the course is
eligible when its prerequisites and offering allow it, with the warning REPEAT_FOR_GRADE_IMPROVEMENT. The A1 engine
and the frozen A1 files are not changed (docs/DECISIONS.md D6, docs/A2_PLAN.md D14).
"""
from src.engine.rule_engine import eligibility
from src.queries.make_queries import text_eligibility

REPEAT = "REPEAT_FOR_GRADE_IMPROVEMENT"
ADV24 = ("Adv24_Norms For Pass_Fail_Option_And_Substitution_Of_Courses.pdf p1, B.1: a compulsory or elective course "
         "may be repeated to improve the grade; the better grade counts")


def eligibility_d6(student, code, term=None, catalog=None):
    """Rule-engine eligibility, except that a passed course is eligible again (no new credit) when nothing else blocks it."""
    g = eligibility(student, code, term=term, catalog=catalog)
    if "ALREADY_TAKEN" not in g["reason_codes"]:
        return g
    # Same check without this course on the transcript: a course is never its own prerequisite
    rest = {**student, "transcript": [t for t in student.get("transcript", []) if t["code"] != code]}
    g2 = eligibility(rest, code, term=term, catalog=catalog)
    return {**g2, "student_id": g["student_id"], "already_taken": True,
            "warnings": g2["warnings"] + [REPEAT], "sources": {**g2["sources"], REPEAT: ADV24}}


def text_d6(g, catalog, student):
    """A1 eligibility justification, plus one sentence for a repeat."""
    text = text_eligibility(g, catalog, student)
    if REPEAT in g["warnings"]:
        text += (" You have already passed it, so this is a repeat to improve your grade: the better grade counts and it"
                 " earns no new credits (Academic Advisory 24, B.1).")
    return text


if __name__ == "__main__":
    # Self check: a passed course with no other block becomes eligible with the repeat warning
    from src.engine.catalog import load_catalog
    from src.serve.core import make_student
    cat = load_catalog()
    s = make_student("MTech-CSE", "AI/ML", "thesis", 2, ["CS 610", "CS 614"])
    a1, d6 = eligibility(s, "CS 610", catalog=cat), eligibility_d6(s, "CS 610", catalog=cat)
    print("A1:", a1["eligible"], a1["reason_codes"], "| D6:", d6["eligible"], d6["reason_codes"], d6["warnings"])
    print(text_d6(d6, cat, s))
    assert not a1["eligible"] and REPEAT in d6["warnings"] and d6["already_taken"]
