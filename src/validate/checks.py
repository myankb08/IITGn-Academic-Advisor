"""Named validation checks for Part B (Pandera dataframe checks plus graph and engine checks).

Each check is a function `fn(bundle) -> row` registered with an id, a one-line description and
the requirement it covers. A row has check_id, description, requirement, target, status
(pass | fail | warn | skip), passed, n_failures, examples, note.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx
import pandas as pd
import pandera.pandas as pa
from rapidfuzz import fuzz

from src.collect.common import normalise_code, record_sha

ROOT = Path(__file__).resolve().parents[2]

CODE_RE = re.compile(r"^(?:[A-Z]{2,3} \d{3}(?:-[IVXL]+)?|REQ-[A-Z]+)$")
CATEGORIES = {"compulsory", "stream_core", "basket", "open_elective", "requirement", "ug_background"}
PREREQ_SOURCES = {"course_plan", "manual", "none_stated"}
OFFERED = {"odd", "even", "both", None}
PROGRAMMES = {"MTech-CSE", "MTech-AI"}
STREAMS = {"AI/ML", "Systems", "Theory"}
TRACKS = {"thesis", "coursework"}
RAW_ROLES = {"compulsory", "stream_core", "basket", "requirement", "timetable_offering"}
INTENTS = {"remaining_core", "eligibility", "elective_recommendation"}
AUGMENTATIONS = {None, "paraphrase", "typo_abbrev", "transcript_reorder", "transcript_length"}
DECISIONS = {"accept", "edit", "reject"}
ERROR_CATEGORIES = {"none", "hallucinated_course", "wrong_fact_or_policy", "meaning_drift",
                    "incomplete_justification", "fluency", "ambiguous_query"}
GRADES = {"A", "A-", "B", "B-", "C", "C-", "P", "F", "U", "NP", "I", "W"}
CREDIT_MIN, CREDIT_MAX = 1, 16
TITLE_TYPO_RATIO = 85       # structure vs timetable title: below 100 and at least this is a typo
NEAR_DUP_RATIO = 92         # token_sort_ratio between titles of different codes
EXAMPLES = 8
PREREQ_TYPES = {"PREREQ_MISSING", "PREREQ_SAME_OR_LATER_TERM"}
CAP_TYPES = {"SEMESTER_CREDIT_CAP", "BELOW_600_CAP"}
LEAK_PATTERNS = [
    (re.compile(r"\b[A-Z]{3,}(?:_[A-Z0-9]+)+\b"), "engine reason code"),
    (re.compile(r"gold_?(json|text|answer)", re.I), "gold field name"),
    (re.compile(r"\b(answer|justification)\s*:", re.I), "answer marker"),
    (re.compile(r"[{}]"), "JSON brace"),
    (re.compile(r"\b(eligible|gap)\s*[:=]\s*(true|false|\d)", re.I), "gold value"),
]


@dataclass
class Bundle:
    """Everything a stage can check. Missing parts are None and dependent checks skip."""
    stage: str
    raw_catalog: list = None
    courses: list = None
    rules: dict = None
    timetable_rows: list = None
    students: list = None
    queries: list = None
    splits: dict = None
    labels: list = None
    catalog: object = None          # engine Catalog used for transcripts
    ref_catalog: object = None      # engine Catalog used to recompute gold answers
    paths: dict = field(default_factory=dict)


CHECKS = []


def check(check_id, description, requirement, stages):
    def deco(fn):
        CHECKS.append({"check_id": check_id, "description": description, "requirement": requirement,
                       "stages": set(stages), "fn": fn})
        return fn
    return deco


def result(meta, target, failures, warn=False, note="", skip=None):
    if skip:
        status, failures = "skip", []
    elif failures:
        status = "warn" if warn else "fail"
    else:
        status = "pass"
    return {"check_id": meta["check_id"], "description": meta["description"],
            "requirement": meta["requirement"], "target": target, "status": status,
            "passed": status != "fail", "n_failures": len(failures),
            "examples": failures[:EXAMPLES], "all_failures": failures, "note": skip or note}


def run_check(meta, b):
    return meta["fn"](meta, b)


# ---------- helpers ----------

def courses_df(courses):
    """DataFrame of course records that keeps int credits as int (pandas would turn int+None into float)."""
    df = pd.DataFrame(courses)
    if "credits" in df.columns:
        df["credits"] = pd.Series([c.get("credits") for c in courses], dtype=object, index=df.index)
    return df


def course_frame(b):
    """Uniform frame over raw or processed course records."""
    if b.stage == "raw":
        rows = []
        for r in b.raw_catalog:
            rows.append({"record_id": r["raw_id"], "code": r.get("code_raw"), "title": r.get("title_raw"),
                         "credits": r.get("C"), "kind": r.get("role"), "stream": r.get("stream"),
                         "group": r.get("source_doc"), "L": r.get("L"), "T": r.get("T"), "P": r.get("P")})
        return pd.DataFrame(rows)
    rows = []
    for c in b.courses:
        rows.append({"record_id": c.get("code"), "code": c.get("code"), "title": c.get("title"),
                     "credits": c.get("credits"), "kind": c.get("category"), "stream": None,
                     "group": "courses.json", "level": c.get("level")})
    return courses_df(rows)


def zero_credit_codes(rules):
    """Codes that rules.json states carry 0 credits (e.g. PE 600)."""
    out = set()
    for r in (rules or {}).get("rules", {}).values():
        if r.get("unit") == "credits" and r.get("value") == 0 and r.get("codes"):
            if not re.search(r"(thesis|project)_min", r.get("rule_id", "")):
                out.update(r["codes"])
    return out


def rule_value(rules, rule_id):
    r = (rules or {}).get("rules", {}).get(rule_id)
    return None if r is None else r.get("value")


def timetable_by_code(rows):
    out = {}
    for r in rows or []:
        code = normalise_code(r.get("course_number_raw"))
        if code:
            out.setdefault(code, []).append(r)
    return out


def timetable_by_row(rows):
    return {r["row"]: r for r in rows or []}


def norm_title(t):
    return re.sub(r"\s+", " ", str(t or "")).strip().strip(",;:").strip()


def pandera_failures(schema, df, id_col):
    try:
        schema.validate(df, lazy=True)
        return []
    except pa.errors.SchemaErrors as e:
        fc = e.failure_cases
        out, seen = [], set()
        for _, r in fc.iterrows():
            idx = r["index"]
            if r["schema_context"] == "DataFrameSchema":
                if (idx, str(r["check"])) in seen:
                    continue
                seen.add((idx, str(r["check"])))
                r = r.copy()
                r["column"] = None
            rid = df.loc[idx, id_col] if idx is not None and pd.notna(idx) and idx in df.index else None
            out.append({"id": None if rid is None else str(rid), "column": r["column"],
                        "check": str(r["check"]), "value": str(r["failure_case"])[:120]})
        return out


def prereq_graph(courses):
    g = nx.DiGraph()
    for c in courses:
        g.add_node(c["code"])
    for c in courses:
        for p in c.get("prerequisites") or []:
            g.add_edge(p, c["code"])
    return g


def engine():
    from src.engine import rule_engine
    return rule_engine


# ---------- schema and format ----------

def _is_str_list(v, allowed=None):
    return isinstance(v, list) and all(isinstance(x, str) and (allowed is None or x in allowed) for x in v)


def _is_ltp(v):
    return v is None or (isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v))


RAW_SCHEMA = pa.DataFrameSchema({
    "raw_id": pa.Column(str, unique=True),
    "role": pa.Column(str, pa.Check.isin(RAW_ROLES)),
    "source_doc": pa.Column(str),
    "source_page": pa.Column(float, nullable=True, coerce=True),
    "source_row": pa.Column(float, nullable=True, coerce=True),
}, strict=False)

def _is_background(v):
    return isinstance(v, list) and all(isinstance(x, dict) and _is_str_list(x.get("any_of")) for x in v)


def _is_credit(v):
    return v is None or (isinstance(v, int) and not isinstance(v, bool))


def course_schema(programmes, streams):
    return pa.DataFrameSchema({
        "code": pa.Column(str),
        "title": pa.Column(object, nullable=True),
        "credits": pa.Column(object, pa.Check(lambda s: s.map(_is_credit)), nullable=True),
        "credits_source": pa.Column(str),
        "ltp": pa.Column(object, pa.Check(lambda s: s.map(_is_ltp)), nullable=True),
        "level": pa.Column(float, nullable=True, coerce=True),
        "prerequisites": pa.Column(object, pa.Check(lambda s: s.map(_is_str_list))),
        "prereq_source": pa.Column(str, pa.Check.isin(PREREQ_SOURCES)),
        "prereq_evidence": pa.Column(str),
        "category": pa.Column(str, pa.Check.isin(CATEGORIES)),
        "streams": pa.Column(object, pa.Check(lambda s: s.map(lambda v: _is_str_list(v, streams)))),
        "programmes": pa.Column(object, pa.Check(lambda s: s.map(lambda v: _is_str_list(v, programmes)))),
        "source_doc": pa.Column(str),
        "source_page": pa.Column(float, nullable=True, coerce=True),
        "source_row": pa.Column(float, nullable=True, coerce=True),
        "source_url": pa.Column(object, nullable=True),
        "other_sources": pa.Column(object, pa.Check(lambda s: s.map(lambda v: isinstance(v, list))), required=False),
        "recommended_background": pa.Column(object, pa.Check(lambda s: s.map(_is_background)), required=False),
        "offered": pa.Column(object, pa.Check(lambda s: s.map(lambda v: v in OFFERED)), nullable=True, required=False),
        "offered_parity": pa.Column(object, pa.Check(lambda s: s.map(lambda v: v in OFFERED)), nullable=True, required=False),
        "offered_terms": pa.Column(object, pa.Check(lambda s: s.map(_is_str_list)), required=False),
        "record_sha256": pa.Column(str, pa.Check.str_matches(r"^[0-9a-f]{64}$")),
    }, checks=[
        pa.Check(lambda df: df.category.eq("ug_background") | df.title.notna(), name="title_required"),
        pa.Check(lambda df: df.category.eq("ug_background") | df.credits.notna(), name="credits_required"),
    ], strict=False)


def student_schema(programmes, streams):
    return pa.DataFrameSchema({
        "student_id": pa.Column(str, pa.Check.str_matches(r"^S\d{4}$"), unique=True),
        "programme": pa.Column(str, pa.Check.isin(set(programmes))),
        "stream": pa.Column(object, nullable=True),
        "track": pa.Column(str, pa.Check.isin(TRACKS)),
        "admit_year": pa.Column(int, pa.Check.in_range(2015, 2030)),
        "semesters_completed": pa.Column(int, pa.Check.in_range(0, 8)),
        "seed": pa.Column(int),
        "transcript": pa.Column(object, pa.Check(lambda s: s.map(lambda v: isinstance(v, list)))),
    }, checks=[pa.Check(lambda df: ~((df.programme == "MTech-AI") & (df.stream != "AI/ML")),
                        name="mtech_ai_is_aiml_stream"),
               pa.Check(lambda df: pd.Series([_stream_ok(programmes, p, st) for p, st in zip(df.programme, df.stream)],
                                             index=df.index), name="stream_belongs_to_programme")], strict=False)


def _stream_ok(programmes, prog, stream):
    allowed = programmes.get(prog) or []
    if stream is None or stream != stream:
        return not allowed
    return stream in allowed


def programmes_of(rules):
    return set((rules or {}).get("programmes") or PROGRAMMES)


def programme_streams(rules):
    """{programme: [streams]}; an empty list means the programme has no streams (e.g. MTech-ICDT)."""
    progs = (rules or {}).get("programmes") or {p: {"streams": sorted(STREAMS)} for p in PROGRAMMES}
    return {p: list(v.get("streams") or []) for p, v in progs.items()}


def streams_of(rules):
    progs = (rules or {}).get("programmes") or {}
    return {s for p in progs.values() for s in p.get("streams", [])} or STREAMS


TRANSCRIPT_SCHEMA = pa.DataFrameSchema({
    "student_id": pa.Column(str),
    "code": pa.Column(str, pa.Check.str_matches(CODE_RE.pattern)),
    "semester": pa.Column(int, pa.Check.in_range(1, 8)),
    "credits": pa.Column(int, pa.Check.in_range(0, CREDIT_MAX)),
    "grade": pa.Column(str, pa.Check.isin(GRADES)),
}, strict=False)

QUERY_SCHEMA = pa.DataFrameSchema({
    "query_id": pa.Column(str, pa.Check.str_matches(r"^Q\d{4,}"), unique=True),
    "student_id": pa.Column(str),
    "template_id": pa.Column(str),
    "template_family": pa.Column(str),
    "intent": pa.Column(str, pa.Check.isin(INTENTS)),
    "target_course": pa.Column(object, nullable=True),
    "query_text": pa.Column(str, pa.Check.str_length(min_value=10)),
    "gold_json": pa.Column(object, pa.Check(lambda s: s.map(lambda v: isinstance(v, dict)))),
    "gold_text": pa.Column(str, pa.Check.str_length(min_value=10)),
    "augmentation": pa.Column(object, pa.Check(lambda s: s.map(lambda v: v in AUGMENTATIONS)), nullable=True),
    "parent_query_id": pa.Column(object, nullable=True),
}, checks=[pa.Check(lambda df: (df.intent == "eligibility") == df.target_course.notna(),
                    name="target_course_iff_eligibility"),
           pa.Check(lambda df: pd.Series([i.startswith(f) for i, f in zip(df.template_id, df.template_family)],
                                         index=df.index), name="template_id_in_family")], strict=False)


@check("V01", "Records match the data contract schema and types (Pandera)", "general: schema and types",
       ["raw", "processed", "corrupted"])
def v01_schema(meta, b):
    if b.stage == "raw":
        df = pd.DataFrame(b.raw_catalog)
        return result(meta, "catalog_raw.json", pandera_failures(RAW_SCHEMA, df, "raw_id"))
    schema = course_schema(programmes_of(b.rules), streams_of(b.rules))
    df = courses_df(b.courses)
    fails = pandera_failures(schema, df, "code")
    missing = [{"id": c.get("code"), "column": k, "check": "field present", "value": "missing"}
               for c in b.courses for k, col in schema.columns.items() if col.required and k not in c]
    if not {"offered", "offered_parity"} & set(df.columns):
        missing.append({"id": None, "column": "offered|offered_parity", "check": "field present", "value": "missing"})
    return result(meta, "courses.json", missing + fails)


@check("V02", "Course codes match '<PREFIX> <NNN>[-<ROMAN>]' or 'REQ-*'", "general: code format regex",
       ["raw", "processed", "corrupted"])
def v02_code_format(meta, b):
    df = course_frame(b)
    bad = [{"id": r.record_id, "code": r.code} for r in df.itertuples()
           if not isinstance(r.code, str) or not CODE_RE.match(r.code)]
    if b.courses is not None and b.stage != "raw":
        bad += [{"id": c["code"], "prerequisite": p} for c in b.courses for p in c.get("prerequisites") or []
                if not CODE_RE.match(str(p))]
    return result(meta, "catalog_raw.json" if b.stage == "raw" else "courses.json", bad)


@check("V03", f"Credits are integers in {CREDIT_MIN}..{CREDIT_MAX} (0 only where rules.json states 0; ug_background excluded)",
       "general: value ranges (credits)", ["raw", "processed", "corrupted"])
def v03_credit_range(meta, b):
    df = course_frame(b)
    zero_ok = zero_credit_codes(b.rules)
    bad = []
    for r in df.itertuples():
        v = r.credits
        if r.kind == "ug_background" or v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        if isinstance(v, bool) or not isinstance(v, int):
            bad.append({"id": r.record_id, "code": r.code, "credits": v, "problem": f"type {type(v).__name__}, not int"})
            continue
        if v == 0 and normalise_code(r.code) in zero_ok:
            continue
        if not CREDIT_MIN <= v <= CREDIT_MAX:
            bad.append({"id": r.record_id, "code": r.code, "credits": v, "problem": "out of range"})
    return result(meta, "catalog_raw.json" if b.stage == "raw" else "courses.json", bad,
                  note=f"zero-credit codes allowed by rules.json: {sorted(zero_ok)}")


@check("V04", "level is first digit of the course number * 100, null only for REQ-* placeholders",
       "general: value ranges (level)", ["processed", "corrupted"])
def v04_level(meta, b):
    bad = []
    for c in b.courses:
        code, lvl = c.get("code", ""), c.get("level")
        m = re.match(r"^[A-Z]{2,3} (\d)\d\d", code)
        want = int(m.group(1)) * 100 if m else None
        if lvl != want or (lvl is not None and lvl not in range(100, 1000, 100)):
            bad.append({"id": code, "level": lvl, "expected": want})
    return result(meta, "courses.json", bad)


@check("V05", "Required fields are not null or empty", "general: missing values", ["raw", "processed", "corrupted"])
def v05_missing(meta, b):
    bad = []
    if b.stage == "raw":
        for r in b.raw_catalog:
            for k in ("raw_id", "role", "source_doc", "code_raw", "title_raw"):
                if r.get(k) in (None, ""):
                    bad.append({"id": r.get("raw_id"), "field": k})
            if r.get("role") == "timetable_offering" and r.get("C") is None:
                bad.append({"id": r.get("raw_id"), "field": "C"})
        return result(meta, "catalog_raw.json", bad)
    for c in b.courses:
        keys = ("code", "credits_source", "category", "source_doc", "prereq_source", "prereq_evidence", "record_sha256")
        if c.get("category") != "ug_background":
            keys += ("title", "credits")
        for k in keys:
            if c.get(k) in (None, "", []):
                bad.append({"id": c.get("code"), "field": k})
        if c.get("source_page") is None and c.get("source_row") is None and not c.get("source_section") \
                and c.get("category") != "ug_background":
            bad.append({"id": c.get("code"), "field": "source_page|source_row"})
    for s in b.students or []:
        for k in ("student_id", "programme", "track", "admit_year"):
            if s.get(k) in (None, ""):
                bad.append({"id": s.get("student_id"), "field": k})
    for q in b.queries or []:
        for k in ("query_id", "student_id", "template_id", "intent", "query_text", "gold_json", "gold_text"):
            if q.get(k) in (None, "", {}):
                bad.append({"id": q.get("query_id"), "field": k})
    return result(meta, "courses.json, students.jsonl, queries.jsonl", bad)


@check("V06", "No course code appears twice (raw: within one source document)", "spec: no course code appears twice",
       ["raw", "processed", "corrupted"])
def v06_unique_code(meta, b):
    df = course_frame(b)
    df = df[df.code.notna()]
    if b.stage == "raw":
        df = df.assign(code=df.code.map(lambda c: normalise_code(c) or c))
    bad = []
    for (grp, code), sub in df.groupby(["group", "code"]):
        if len(sub) > 1:
            bad.append({"code": code, "source": grp, "ids": sorted(sub.record_id)})
    return result(meta, "catalog_raw.json" if b.stage == "raw" else "courses.json", bad)


@check("V07", "No exact duplicate records (all content fields equal, provenance ignored)",
       "general: exact duplicates", ["raw", "processed", "corrupted"])
def v07_exact_dup(meta, b):
    if b.stage == "raw":
        recs = [(r["raw_id"], {k: v for k, v in r.items() if k not in ("raw_id", "source_row", "line", "source_page")})
                for r in b.raw_catalog]
    else:
        drop = {"record_sha256", "source_row", "source_page", "other_sources", "source_doc"}
        recs = [(c.get("code"), {k: v for k, v in c.items() if k not in drop}) for c in b.courses]
    seen, bad = {}, []
    for rid, body in recs:
        key = json.dumps(body, sort_keys=True)
        if key in seen:
            bad.append({"id": rid, "duplicate_of": seen[key]})
        else:
            seen[key] = rid
    return result(meta, "catalog_raw.json" if b.stage == "raw" else "courses.json", bad)


@check("V08", "Course titles agree with the timetable title for the same code (catches typos like 'Algrithms')",
       "general: spelling / title consistency against timetable", ["raw", "processed", "corrupted"])
def v08_title_vs_timetable(meta, b):
    if not b.timetable_rows:
        return result(meta, "titles", [], skip="timetable_rows.jsonl missing")
    tt = timetable_by_code(b.timetable_rows)
    df = course_frame(b)
    if b.stage == "raw":
        df = df[df.kind != "timetable_offering"]
    bad = []
    for r in df.itertuples():
        code = normalise_code(r.code) if isinstance(r.code, str) else None
        if not code or code not in tt or not r.title:
            continue
        mine = norm_title(r.title)
        others = sorted({norm_title(x["title"]) for x in tt[code]})
        if any(mine.casefold() == o.casefold() for o in others):
            continue
        best = max(others, key=lambda o: fuzz.ratio(mine.casefold(), o.casefold()))
        ratio = round(fuzz.ratio(mine.casefold(), best.casefold()), 1)
        bad.append({"id": r.record_id, "code": code, "title": r.title, "timetable_title": best, "ratio": ratio,
                    "kind": "typo" if ratio >= TITLE_TYPO_RATIO else "different wording or abbreviation"})
    return result(meta, "titles vs timetable_rows.jsonl", bad,
                  note=f"typo when rapidfuzz ratio >= {TITLE_TYPO_RATIO} and < 100 (case-insensitive)")


@check("V09", "Titles have no leading/trailing whitespace, double spaces or trailing punctuation",
       "general: text hygiene", ["raw", "processed", "corrupted"])
def v09_title_hygiene(meta, b):
    df = course_frame(b)
    bad = [{"id": r.record_id, "title": r.title} for r in df.itertuples()
           if isinstance(r.title, str) and (r.title != r.title.strip() or "  " in r.title or r.title.rstrip()[-1:] in ",;:")]
    return result(meta, "titles", bad)


@check("V10", f"No two different codes have near-duplicate titles (rapidfuzz token_sort_ratio >= {NEAR_DUP_RATIO})",
       "general: near-duplicate titles (warning, needs human review)", ["raw", "processed", "corrupted"])
def v10_near_dup_titles(meta, b):
    df = course_frame(b).dropna(subset=["code", "title"])
    df = df.assign(code=df.code.map(lambda c: normalise_code(c) or c))
    titles = df.drop_duplicates(["code", "title"])[["code", "title"]].values.tolist()
    bad, seen = [], set()
    for i, (c1, t1) in enumerate(titles):
        for c2, t2 in titles[i + 1:]:
            if c1 == c2 or (c1, c2) in seen:
                continue
            ratio = fuzz.token_sort_ratio(norm_title(t1).casefold(), norm_title(t2).casefold())
            if ratio >= NEAR_DUP_RATIO:
                seen.add((c1, c2))
                bad.append({"codes": [c1, c2], "titles": [t1, t2], "ratio": round(ratio, 1)})
    return result(meta, "titles", bad, warn=True,
                  note="warning only: cross-listed UG/PG or special-topics versions can share a title")


# ---------- graph ----------

@check("V11", "Every prerequisite code exists in courses.json", "spec: every prerequisite code exists",
       ["processed", "corrupted"])
def v11_prereq_exists(meta, b):
    codes = {c["code"] for c in b.courses}
    bad = [{"id": c["code"], "unknown_prerequisite": p} for c in b.courses
           for p in c.get("prerequisites") or [] if p not in codes]
    bad += [{"id": c["code"], "unknown_background_code": p} for c in b.courses
            for grp in c.get("recommended_background") or [] for p in grp.get("any_of") or [] if p not in codes]
    return result(meta, "courses.json prerequisites and recommended_background", bad)


@check("V12", "The prerequisite graph has no cycles (and no self loops)", "spec: prerequisite graph is acyclic",
       ["processed", "corrupted"])
def v12_acyclic(meta, b):
    g = prereq_graph(b.courses)
    cycles = [sorted(c) for c in nx.simple_cycles(g)]
    return result(meta, "courses.json prerequisites", [{"cycle": c} for c in cycles],
                  note=f"{g.number_of_nodes()} nodes, {g.number_of_edges()} edges")


# ---------- handbook credit arithmetic ----------

def effective_rule(rules, base_id, programme):
    """Value of base_id for a programme, honouring rules that declare `overrides: base_id`."""
    for rid, r in (rules or {}).get("rules", {}).items():
        named = r.get("overrides") == base_id or (not r.get("overrides") and rid != base_id
                                                  and rid.split(".", 1)[-1] == base_id)
        if named and programme in (r.get("applies_to") or {}).get("programmes", []):
            return r.get("value")
    base = (rules or {}).get("rules", {}).get(base_id)
    if base is None:
        return None
    progs = (base.get("applies_to") or {}).get("programmes")
    return base.get("value") if not progs or programme in progs else None


@check("V13", "Credit totals agree with the handbook: every total is 82, per-track minimums fit in it, splits sum to it",
       "spec: credit totals match the handbook", ["processed", "corrupted"])
def v13_credit_totals(meta, b):
    r = b.rules
    bad, sums = [], {}
    for rid, rec in (r or {}).get("rules", {}).items():
        if rid.split(".")[-1] == "total_min_credits" or rec.get("overrides") == "total_min_credits":
            if rec.get("value") != 82:
                bad.append({"rule": rid, "value": rec.get("value"), "expected": 82})
        if rid.split(".")[-1] == "credit_split" and isinstance(rec.get("value"), list):
            prog = ((rec.get("applies_to") or {}).get("programmes") or [None])[0]
            total = effective_rule(r, "total_min_credits", prog)
            if sum(rec["value"]) != total:
                bad.append({"rule": rid, "problem": "credit split does not sum to total", "split": rec["value"], "total": total})
    for prog, spec in sorted((r or {}).get("programmes", {}).items()):
        total = effective_rule(r, "total_min_credits", prog)
        for t in spec.get("tracks", []):
            parts = {k: effective_rule(r, f"{k}_min_credits.{t}", prog) for k in ("coursework", "thesis", "project")}
            if any(v is None for v in parts.values()) or total is None:
                bad.append({"programme": prog, "track": t, "problem": "missing minimum", "parts": parts, "total": total})
                continue
            s = sum(parts.values())
            sums[f"{prog}/{t}"] = s
            if s > total:
                bad.append({"programme": prog, "track": t, "problem": "track minimums exceed total", "sum": s, "total": total})
            comp = [effective_rule(r, k, prog) for k in ("writing_credits", "applications_of_ai_credits",
                                                         "electives_min_credits", "discipline_specified_min_credits")]
            if None not in comp and sum(comp) > parts["coursework"]:
                bad.append({"programme": prog, "track": t, "problem": "coursework components exceed coursework minimum",
                            "components": sum(comp), "coursework_min": parts["coursework"]})
    expected = {"coursework_min_credits.thesis": 32, "thesis_min_credits.thesis": 32,
                "coursework_min_credits.coursework": 48, "project_min_credits.coursework": 16,
                "aarohan_credits": 2, "writing_credits": 4, "own_basket_min_credits": 4,
                "other_basket_min_credits": 4, "discipline_specified_min_credits": 16,
                "electives_min_credits": 8, "stream_core_credits": 8}
    for k, v in expected.items():
        if rule_value(r, k) != v:
            bad.append({"rule": k, "value": rule_value(r, k), "expected": v, "source": "Adv5 p1-2 / CSE structure p1"})
    return result(meta, "rules.json", bad,
                  note="coursework+thesis+project minimums: " + json.dumps(sums)
                       + "; credits above these minimums up to 82 are free choice (Adv5 p1 states minimums only)")


@check("V14", "Structure courses agree with rules: compulsory and core lists, core = 8 credits, baskets can meet minimums, rule codes exist",
       "spec: compulsory credits, basket minimums", ["processed", "corrupted"])
def v14_structure(meta, b):
    r, bad = b.rules, []
    by = {}
    for c in b.courses:
        by.setdefault(c["code"], c)
    comp = rule_value(r, "compulsory_courses") or []
    actual_comp = sorted(c for c, x in by.items() if x.get("category") == "compulsory")
    if sorted(comp) != actual_comp:
        bad.append({"problem": "compulsory list differs", "rules": sorted(comp), "courses": actual_comp})
    for code in comp:
        if code in by and not by[code].get("credits"):
            bad.append({"problem": "compulsory course has no credits", "code": code})
    core_min = rule_value(r, "stream_core_credits")
    own_min = rule_value(r, "own_basket_min_credits") or 0
    other_min = rule_value(r, "other_basket_min_credits") or 0
    core_streams = sorted(k.split(".", 1)[1] for k in (r or {}).get("rules", {}) if k.startswith("stream_core."))
    for stream in core_streams:
        listed = rule_value(r, f"stream_core.{stream}") or []
        actual = sorted(c for c, x in by.items() if x.get("category") == "stream_core" and stream in (x.get("streams") or []))
        if sorted(listed) != actual:
            bad.append({"stream": stream, "problem": "stream core list differs", "rules": sorted(listed), "courses": actual})
        cr = sum((by.get(c) or {}).get("credits") or 0 for c in listed)
        if core_min is not None and cr != core_min:
            bad.append({"stream": stream, "problem": "core credits != stream_core_credits", "credits": cr, "rule": core_min})
        basket = [x for x in by.values() if x.get("category") == "basket"]
        own = sum(x.get("credits") or 0 for x in basket if stream in (x.get("streams") or []))
        other = sum(x.get("credits") or 0 for x in basket if stream not in (x.get("streams") or []))
        if own < own_min:
            bad.append({"stream": stream, "problem": "basket cannot meet own-basket minimum", "credits": own})
        if other < other_min:
            bad.append({"stream": stream, "problem": "other baskets cannot meet minimum", "credits": other})
        disc = sum((by.get(c) or {}).get("credits") or 0 for c in comp) + cr + own_min + other_min
        if disc < (rule_value(r, "discipline_specified_min_credits") or 0):
            bad.append({"stream": stream, "problem": "discipline courses cannot reach discipline minimum", "credits": disc})
    placeholders = set((r or {}).get("placeholder_codes") or {})
    refs = set()
    for rid, rec in (r or {}).get("rules", {}).items():
        vals = list(rec.get("codes") or [])
        if rec.get("unit") in ("codes", "code"):
            vals += rec["value"] if isinstance(rec.get("value"), list) else [rec.get("value")]
        refs.update((rid, v) for v in vals if isinstance(v, str))
    for kind, code in ((r or {}).get("requirement_codes") or {}).items():
        refs.add((f"requirement_codes.{kind}", code))
    for rid, code in sorted(refs):
        if code not in by and code not in placeholders:
            bad.append({"problem": "code named in rules.json missing from courses.json", "rule": rid, "code": code})
    return result(meta, "courses.json vs rules.json", bad, note=f"streams with core lists: {core_streams}")


@check("V15", "Course credits and L-T-P agree with the timetable row where both exist",
       "spec: course credits agree with timetable L-T-P-C", ["raw", "processed", "corrupted"])
def v15_timetable_ltpc(meta, b):
    if not b.timetable_rows:
        return result(meta, "timetable", [], skip="timetable_rows.jsonl missing")
    rows = timetable_by_row(b.timetable_rows)
    bad = []
    if b.stage == "raw":
        for r in b.raw_catalog:
            if r.get("role") != "timetable_offering":
                continue
            t = rows.get(r.get("source_row"))
            if t and (r.get("C") != t["C"] or [r.get("L"), r.get("T"), r.get("P")] != [t["L"], t["T"], t["P"]]):
                bad.append({"id": r["raw_id"], "raw": [r.get("L"), r.get("T"), r.get("P"), r.get("C")],
                            "timetable": [t["L"], t["T"], t["P"], t["C"]]})
        return result(meta, "catalog_raw.json vs timetable_rows.jsonl", bad)
    for c in b.courses:
        refs = [c.get("source_row")] if c.get("source_doc", "").startswith("Timetable") else []
        refs += [o.get("source_row") for o in c.get("other_sources") or [] if str(o.get("source_doc", "")).startswith("Timetable")]
        for row in [x for x in refs if x is not None]:
            t = rows.get(row)
            if t is None:
                bad.append({"id": c["code"], "row": row, "problem": "timetable row not found"})
                continue
            if normalise_code(t["course_number_raw"]) != c["code"]:
                bad.append({"id": c["code"], "row": row, "problem": "row has another code", "row_code": t["course_number_raw"]})
                continue
            if c.get("category") == "ug_background":
                continue
            if t["C"] is not None and c.get("credits") != t["C"]:
                bad.append({"id": c["code"], "row": row, "credits": c.get("credits"), "timetable_C": t["C"]})
            if c.get("ltp") is not None and [float(x) for x in c["ltp"]] != [t["L"], t["T"], t["P"]]:
                bad.append({"id": c["code"], "row": row, "ltp": c["ltp"], "timetable_LTP": [t["L"], t["T"], t["P"]]})
    return result(meta, "courses.json vs timetable_rows.jsonl", bad)


@check("V16", "Every rule has a value or not_stated, plus source_doc and source_page; course record hashes match",
       "general: provenance integrity", ["processed", "corrupted"])
def v16_provenance(meta, b):
    bad = []
    for rid, r in (b.rules or {}).get("rules", {}).items():
        if r.get("value") is None and not r.get("not_stated"):
            bad.append({"id": rid, "problem": "null value without not_stated"})
        if not r.get("not_stated") and (not r.get("source_doc") or (r.get("source_page") is None and not r.get("source_section"))):
            bad.append({"id": rid, "problem": "missing source_doc and source_page/source_section"})
        if r.get("record_sha256") and r["record_sha256"] != record_sha(r):
            bad.append({"id": rid, "problem": "record_sha256 mismatch"})
    for c in b.courses:
        if c.get("record_sha256") != record_sha(c):
            bad.append({"id": c.get("code"), "problem": "record_sha256 mismatch"})
    return result(meta, "rules.json, courses.json", bad)


# ---------- transcripts ----------

def _violations(b):
    if b.students is None or b.catalog is None:
        return None
    eng = engine()
    return [(s, eng.validate_transcript(s, b.catalog)) for s in b.students]


def _viol_rows(b, types, include):
    out = []
    for s, v in _violations(b):
        hits = [x for x in v["violations"] if (x["type"] in types) == include]
        if hits:
            out.append({"id": s["student_id"], "injected": s.get("injected_violation"),
                        "violations": [f"{x['type']} {x['code'] or ''} s{x['semester']}: {x['detail']}" for x in hits][:4]})
    return out


@check("V17", "Students and transcript entries match the schema (Pandera)", "general: schema and types (students)",
       ["processed", "corrupted"])
def v17_student_schema(meta, b):
    if b.students is None:
        return result(meta, "students.jsonl", [], skip="students.jsonl missing")
    fails = pandera_failures(student_schema(programme_streams(b.rules), streams_of(b.rules)),
                             pd.DataFrame(b.students), "student_id")
    entries = pd.DataFrame([{"student_id": s["student_id"], **e} for s in b.students for e in s["transcript"]])
    if len(entries):
        fails += pandera_failures(TRANSCRIPT_SCHEMA, entries, "student_id")
    return result(meta, "students.jsonl", fails)


@check("V18", "Synthetic transcripts have no prerequisite violations (engine validate_transcript)",
       "spec: transcripts pass the rule engine (prerequisites)", ["processed", "corrupted"])
def v18_transcript_prereq(meta, b):
    if _violations(b) is None:
        return result(meta, "students.jsonl", [], skip="students or catalog missing")
    return result(meta, "students.jsonl", _viol_rows(b, PREREQ_TYPES, True))


@check("V19", "Transcripts respect credit caps: below-600 course cap and per-semester cap if stated",
       "spec: credit caps respected, below-600 cap", ["processed", "corrupted"])
def v19_transcript_caps(meta, b):
    if _violations(b) is None:
        return result(meta, "students.jsonl", [], skip="students or catalog missing")
    cap = b.catalog.rules.get("max_credits_per_semester")
    note = "per-semester cap not stated in sources (rules.json not_stated), only below-600 cap is enforced" \
        if cap is None else f"per-semester cap {cap}"
    return result(meta, "students.jsonl", _viol_rows(b, CAP_TYPES, True), note=note)


@check("V20", "Transcripts have no other engine violations (unknown code, duplicate pass, credit mismatch, parity, term range)",
       "spec: transcripts pass the rule engine", ["processed", "corrupted"])
def v20_transcript_other(meta, b):
    if _violations(b) is None:
        return result(meta, "students.jsonl", [], skip="students or catalog missing")
    return result(meta, "students.jsonl", _viol_rows(b, PREREQ_TYPES | CAP_TYPES, False))


# ---------- queries and labels ----------

@check("V21", "Queries match the schema; intent, augmentation and template fields valid (Pandera)",
       "general: label validity (intent) and schema", ["processed", "corrupted"])
def v21_query_schema(meta, b):
    if b.queries is None:
        return result(meta, "queries.jsonl", [], skip="queries.jsonl missing")
    df = pd.DataFrame(b.queries)
    fails = pandera_failures(QUERY_SCHEMA, df, "query_id")
    sids = {s["student_id"] for s in b.students or []}
    codes = {c["code"] for c in b.courses or []}
    for q in b.queries:
        if sids and q["student_id"] not in sids:
            fails.append({"id": q["query_id"], "problem": "unknown student_id", "value": q["student_id"]})
        if q.get("target_course") and codes and q["target_course"] not in codes:
            fails.append({"id": q["query_id"], "problem": "unknown target_course", "value": q["target_course"]})
    return result(meta, "queries.jsonl", fails)


def recompute_gold(q, student, catalog):
    eng = engine()
    g = q["gold_json"]
    if q["intent"] == "remaining_core":
        return eng.remaining_requirements(student, catalog)
    if q["intent"] == "eligibility":
        return eng.eligibility(student, q["target_course"], g.get("term"), catalog=catalog)
    return eng.recommend_electives(student, g.get("k", 3), g.get("term"), catalog=catalog)


def _diff_keys(a, b):
    if not isinstance(a, dict) or not isinstance(b, dict):
        return ["<root>"]
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


@check("V22", "Stored gold_json equals the rule engine output recomputed from the student",
       "spec: gold answers recomputed by the engine equal stored gold_json", ["processed", "corrupted"])
def v22_gold_recompute(meta, b):
    if b.queries is None or b.students is None or b.ref_catalog is None:
        return result(meta, "queries.jsonl", [], skip="queries, students or catalog missing")
    students = {s["student_id"]: s for s in b.students}
    bad, skipped = [], 0
    for q in b.queries:
        s = students.get(q["student_id"])
        if s is None or q.get("augmentation") == "transcript_length":
            skipped += 1
            continue
        fresh = json.loads(json.dumps(recompute_gold(q, s, b.ref_catalog)))
        if fresh != q["gold_json"]:
            bad.append({"id": q["query_id"], "intent": q["intent"], "keys_differ": _diff_keys(fresh, q["gold_json"])})
    return result(meta, "queries.jsonl", bad, note=f"{len(b.queries) - skipped} recomputed, {skipped} skipped "
                                                   "(missing student or transcript_length augmentation)")


@check("V23", "Query text (and paraphrase) does not leak gold answer markers or the gold text",
       "spec: query text contains no leaked gold answer marker", ["processed", "corrupted"])
def v23_leak(meta, b):
    if b.queries is None:
        return result(meta, "queries.jsonl", [], skip="queries.jsonl missing")
    bad = []
    for q in b.queries:
        for fld in ("query_text", "para_query"):
            text = q.get(fld)
            if not text:
                continue
            for rx, why in LEAK_PATTERNS:
                m = rx.search(text)
                if m:
                    bad.append({"id": q["query_id"], "field": fld, "marker": why, "match": m.group()})
            gt = norm_title(q.get("gold_text", ""))[:40]
            if len(gt) >= 20 and gt in text:
                bad.append({"id": q["query_id"], "field": fld, "marker": "gold_text copied"})
    return result(meta, "queries.jsonl", bad)


@check("V24", "Audited labels use allowed decisions and error categories, and edits carry text",
       "general: label validity (decisions, error categories)", ["processed", "corrupted"])
def v24_labels(meta, b):
    if not b.labels:
        return result(meta, "audited.jsonl", [], skip="no data/labels/audited.jsonl yet (labels come from humans)")
    bad = []
    for r in b.labels:
        for who in ("A1", "A2"):
            a = r.get(who) or {}
            if a.get("decision") not in DECISIONS:
                bad.append({"id": r.get("item_id"), "field": f"{who}.decision", "value": a.get("decision")})
            if a.get("error_category") not in ERROR_CATEGORIES:
                bad.append({"id": r.get("item_id"), "field": f"{who}.error_category", "value": a.get("error_category")})
        if r.get("final_decision") not in DECISIONS:
            bad.append({"id": r.get("item_id"), "field": "final_decision", "value": r.get("final_decision")})
        if r.get("final_category") not in ERROR_CATEGORIES:
            bad.append({"id": r.get("item_id"), "field": "final_category", "value": r.get("final_category")})
        if r.get("final_decision") == "edit" and not (r.get("final_edit") or "").strip():
            bad.append({"id": r.get("item_id"), "field": "final_edit", "value": "empty for an edit"})
        if r.get("final_decision") == "accept" and r.get("final_category") not in ("none", None):
            bad.append({"id": r.get("item_id"), "field": "final_category", "value": "accept with an error category"})
    return result(meta, "audited.jsonl", bad)


@check("V25", "No student or template in both train and test; held-out programmes and students not in train",
       "spec: no student or template in both train and test", ["processed", "corrupted"])
def v25_split_leak(meta, b):
    if not b.splits:
        return result(meta, "data/splits/*.csv", [], skip="no split manifests in data/splits yet (Part C)")
    df = pd.concat(b.splits.values(), ignore_index=True)
    need = {"query_id", "student_id", "template_family", "programme", "split"}
    if not need <= set(df.columns):
        return result(meta, "splits", [{"problem": "missing columns", "columns": sorted(need - set(df.columns))}])
    bad = []
    tcol = "template_id" if "template_id" in df.columns else "template_family"
    held = sorted(x for x in df.split.unique() if x not in ("train", "val"))
    tr = df[df.split == "train"]
    for name in held:
        te = df[df.split == name]
        # real form questions share programmes with train by nature, so "shifted" is checked on ids and text only
        cols = ("student_id", tcol) if name == "test" else ("query_id",) if name == "shifted" else ("student_id", "programme")
        for col in cols:
            for v in sorted(set(tr[col].dropna()) & set(te[col].dropna())):
                bad.append({"split": name, "column": col, "value": v})
    if "shifted" in held and b.queries:
        forms = ROOT / "data" / "raw" / "forms" / "responses_anonymised.jsonl"
        if forms.exists():
            norm = lambda t: " ".join(str(t).lower().split())  # noqa: E731
            train_ids = set(tr.query_id)
            train_text = {norm(q.get("query_text")) for q in b.queries if q["query_id"] in train_ids}
            for line in forms.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    if norm(r.get("question")) in train_text:
                        bad.append({"split": "shifted", "column": "question", "value": r.get("response_id"),
                                    "problem": "form question text equals a train query_text"})
    fam = sorted(set(tr.template_family) & set(df.loc[df.split == "test", "template_family"]))
    dups = df.query_id[df.query_id.duplicated()].tolist()
    bad += [{"column": "query_id", "value": q, "problem": "in more than one split row"} for q in dups]
    return result(meta, "splits", bad, note=f"{len(df)} rows; train vs test on student_id and {tcol}, train vs other held-out splits "
                                            f"({[h for h in held if h != 'test']}) on student_id and programme; "
                                            f"template families shared by train and test (by design): {len(fam)}")


def applicable(stage):
    return [c for c in CHECKS if stage in c["stages"]]
