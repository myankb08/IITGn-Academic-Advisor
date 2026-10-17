"""Load courses.json and rules.json and resolve the rule numbers the engine needs.

rules.json is written by the curriculum step and its exact nesting is not fixed by the
data contract, so rule values are looked up by key name. Any rule that is not found falls
back to the value stated in the source documents, with that document and page recorded.
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
COURSES_PATH = PROCESSED / "courses.json"
RULES_PATH = PROCESSED / "rules.json"
PARAMS_PATH = ROOT / "params.yaml"

ADV5 = "Adv5_NormsforMTechProgramme.pdf"
CSE = "Revised CSE MTech Course Structure [2025-26].pdf"
TRACKS = ("thesis", "coursework")
STREAMS = ("AI/ML", "Systems", "Theory")
PASS_FAIL_GRADES = {"F", "U", "NP", "I", "W"}

# name: (key regex, track scoped, fallback value, fallback source_doc, fallback page)
RULE_SPECS = {
    "total_min_credits": (r"^total|^min_?total", False, 82, ADV5, 1),
    "coursework_min_credits": (r"course_?work|credits_through_courses|^courses?_min", True, {"thesis": 32, "coursework": 48}, ADV5, 1),
    "thesis_min_credits": (r"thesis", True, {"thesis": 32, "coursework": 0}, ADV5, 1),
    "project_min_credits": (r"project", True, {"thesis": 0, "coursework": 16}, ADV5, 1),
    "aarohan_credits": (r"aarohan", False, 2, ADV5, 2),
    "writing_credits": (r"writing", False, 4, ADV5, 1),
    "hss_min_credits": (r"(hss|humanit)(?!.*(admit|year))", False, 4, ADV5, 2),
    "ai_applications_credits": (r"ai_?app|applications?_of_ai", False, 4, ADV5, 2),
    "own_basket_min_credits": (r"own_?basket|respective_?basket|basket_?own", False, 4, CSE, 1),
    "other_basket_min_credits": (r"other_?basket|basket_?other", False, 4, CSE, 1),
    "stream_core_credits": (r"(stream_?)?core_?(min_?)?credits", False, 8, CSE, 1),
    "discipline_specified_min_credits": (r"discipline", False, 16, ADV5, 2),
    "electives_min_credits": (r"elective", False, 8, ADV5, 2),
    "below_600_max_courses": (r"(below|under|lt|less_than|sub)_?600.*course|^ug_?(level_?)?courses?_(max|cap|limit)", False, 2, ADV5, 2),
    "below_600_max_credits": (r"(below|under|lt|less_than|sub)_?600.*credit", False, None, None, None),
    "max_credits_per_semester": (r"(max|cap).*(per_?sem|semester)|per_?sem.*(max|cap)", False, None, None, None),
    "mooc_electives_allowed": (r"^mooc", False, False, CSE, 2),
    "pe_courses_required": (r"physical.*(course|count|number|required)$|^pe_courses", False, 2, ADV5, 2),
    "mtech_ai_stream": (r"^mtech_ai_stream$", False, "AI/ML", CSE, 1),
    "hss_required_before_admit_year": (r"hss.*(admit|year)|(admit|year).*hss", False, 2025, ADV5, 2),
}
GENERIC_KEYS = {"min", "max", "value", "credits", "min_credits", "max_credits", "cap", "limit", "number"}
ID_KEYS = ("rule_id", "id", "name", "key", "rule")
SCOPE_KEYS = ("track", "programme", "program")


def load_params(path=PARAMS_PATH):
    with open(path) as f:
        return yaml.safe_load(f)


def _flatten(node, path, out):
    """Collect (path, value, provenance) for numeric leaves and {'value': x} dicts."""
    if isinstance(node, dict):
        if "value" in node and not isinstance(node["value"], (dict, list)):
            prov = {k: node.get(k) for k in ("source_doc", "source_page")}
            out.append((path, node["value"], prov))
            return
        for k, v in node.items():
            _flatten(v, path + [str(k).lower()], out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            seg = []
            if isinstance(v, dict):
                seg = [str(v[k]).lower() for k in SCOPE_KEYS if isinstance(v.get(k), str)]
                ident = next((v[k] for k in ID_KEYS if isinstance(v.get(k), str)), None)
                seg.append(str(ident).lower() if ident else str(i))
            else:
                seg = [str(i)]
            _flatten(v, path + seg, out)
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        out.append((path, node, {}))


def _key_of(path):
    """Last meaningful key, joined with its parent when the last key is generic."""
    if not path:
        return ""
    if path[-1] in GENERIC_KEYS and len(path) > 1:
        return f"{path[-2]}_{path[-1]}"
    return path[-1]


def _lookup(flat, regex, track=None, year=False):
    hits = []
    for path, value, prov in flat:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        if not re.search(regex, _key_of(path)):
            continue
        if not year and value >= 1000:
            continue
        scope = path[:-1] if path[-1] not in GENERIC_KEYS else path[:-2]
        if track:
            other = [t for t in TRACKS if t != track][0]
            if any(other in s for s in scope):
                continue
            rank = 0 if any(track in s for s in scope) else 1
        else:
            if any(t in s for t in TRACKS for s in scope):
                continue
            rank = 0
        hits.append((rank, "/".join(path), value, prov))
    if not hits:
        return None
    hits.sort(key=lambda h: (h[0], h[1]))
    return hits[0]


@dataclass
class RuleSet:
    values: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    ai_applications_course: str = None
    requirement_codes: dict = field(default_factory=dict)
    programme: str = None
    programme_info: dict = field(default_factory=dict)
    overlays: dict = field(default_factory=dict)
    ai_course_by_programme: dict = field(default_factory=dict)

    def get(self, name, track=None):
        v = self.values.get(name)
        if isinstance(v, dict):
            return v.get(track)
        return v

    def for_programme(self, programme):
        """Copy with the programme's override rules applied (rules.json 'overrides')."""
        ov = self.overlays.get(programme, {})
        values, prov = dict(self.values), dict(self.provenance)
        for name, (value, pv) in ov.items():
            if isinstance(value, dict) and isinstance(values.get(name), dict):
                values[name] = {**values[name], **value}
                prov[name] = {**prov[name], **pv}
            else:
                values[name], prov[name] = value, pv
        ai = self.ai_course_by_programme.get(programme, self.ai_applications_course) \
            if programme in self.ai_course_by_programme else self.ai_applications_course
        return RuleSet(values, prov, ai, self.requirement_codes, programme, self.programme_info, {},
                       self.ai_course_by_programme)

    def tracks(self, programme):
        return (self.programme_info.get(programme) or {}).get("tracks") or list(TRACKS)

    def streams(self, programme):
        info = self.programme_info.get(programme)
        return list(info.get("streams") or []) if info is not None else list(STREAMS)

    def to_dict(self):
        return {"programme": self.programme, "values": self.values, "provenance": self.provenance,
                "ai_applications_course": self.ai_applications_course,
                "requirement_codes": self.requirement_codes,
                "overlays": {p: {k: v[0] for k, v in o.items()} for p, o in sorted(self.overlays.items())}}


# Engine rule name -> rule_id in the structured rules.json written by src/collect/build_rules.py.
RULE_IDS = {
    "total_min_credits": "total_min_credits",
    "coursework_min_credits": "coursework_min_credits.{track}",
    "thesis_min_credits": "thesis_min_credits.{track}",
    "project_min_credits": "project_min_credits.{track}",
    "aarohan_credits": "aarohan_credits",
    "writing_credits": "writing_credits",
    "hss_min_credits": "hss_min_credits",
    "ai_applications_credits": "applications_of_ai_credits",
    "own_basket_min_credits": "own_basket_min_credits",
    "other_basket_min_credits": "other_basket_min_credits",
    "stream_core_credits": "stream_core_credits",
    "discipline_specified_min_credits": "discipline_specified_min_credits",
    "electives_min_credits": "electives_min_credits",
    "below_600_max_courses": "ug_courses_max",
    "max_credits_per_semester": "max_credits_per_semester",
    "pe_courses_required": "physical_education_courses",
    "mtech_ai_stream": "mtech_ai_stream",
}
REQ_CODE_KEYS = {"writing": "writing", "aarohan": "aarohan", "physical_education": "pe"}


def _structured(raw, rs):
    """Fill rs from rules.json records keyed by rule_id; return the names it filled."""
    records = raw.get("rules") if isinstance(raw, dict) else None
    if not isinstance(records, dict):
        return set()
    done = set()

    def take(rule_id):
        r = records.get(rule_id)
        if not isinstance(r, dict) or "value" not in r:
            return None
        prov = {"from": "rules.json", "path": f"rules/{rule_id}", "source_doc": r.get("source_doc"),
                "source_page": r.get("source_page")}
        if r.get("not_stated"):
            prov["from"] = "not_stated"
        return r["value"], prov

    for name, rid in RULE_IDS.items():
        if "{track}" in rid:
            hits = {t: take(rid.format(track=t)) for t in TRACKS}
            if all(hits.values()):
                rs.values[name] = {t: h[0] for t, h in hits.items()}
                rs.provenance[name] = {t: h[1] for t, h in hits.items()}
                done.add(name)
            continue
        hit = take(rid)
        if hit:
            rs.values[name], rs.provenance[name] = hit
            done.add(name)
    hss = records.get("hss_min_credits") or {}
    m = re.search(r"before AY (\d{4})", str((hss.get("applies_to") or {}).get("admitted", "")))
    if m:
        rs.values["hss_required_before_admit_year"] = int(m.group(1))
        rs.provenance["hss_required_before_admit_year"] = {
            "from": "rules.json", "path": "rules/hss_min_credits/applies_to/admitted",
            "source_doc": hss.get("source_doc"), "source_page": hss.get("source_page")}
        done.add("hss_required_before_admit_year")
    ai = take("applications_of_ai_course")
    if ai and isinstance(ai[0], str):
        rs.ai_applications_course = ai[0]
    for key, kind in REQ_CODE_KEYS.items():
        code = (raw.get("requirement_codes") or {}).get(key)
        if code:
            rs.requirement_codes[kind] = code
    online = take("online_courses_count")
    if online is not None:
        rs.values["mooc_electives_allowed"] = bool(online[0])
        rs.provenance["mooc_electives_allowed"] = online[1]
        done.add("mooc_electives_allowed")
    rs.overlays = _programme_overlays(records)
    return done


def _programme_overlays(records):
    """Programme-specific rules: 'overrides' names the common rule_id they replace.

    Rules prefixed '<prefix>.' without 'overrides' replace the common rule of the same name.
    """
    reverse = {}
    for name, rid in RULE_IDS.items():
        for t in TRACKS:
            reverse[rid.format(track=t)] = (name, t if "{track}" in rid else None)
    reverse["online_courses_count"] = ("mooc_electives_allowed", None)
    out = {}
    for rid, r in sorted(records.items()):
        progs = (r.get("applies_to") or {}).get("programmes") or []
        if "." not in rid or not (r.get("overrides") or rid.split(".", 1)[0] in {"ee"}):
            continue
        target = r.get("overrides") or rid.split(".", 1)[1]
        stripped = rid.split(".", 1)[1]
        hit = reverse.get(target) or reverse.get(stripped) or (("mooc_electives_allowed", None)
                                                              if stripped == "mooc_electives_allowed" else None)
        if not hit or r.get("value") is None:
            continue
        name, track = hit
        prov = {"from": "rules.json", "path": f"rules/{rid}", "source_doc": r.get("source_doc"),
                "source_page": r.get("source_page"), "source_section": r.get("source_section")}
        for prog in progs:
            ov = out.setdefault(prog, {})
            if name == "below_600_max_courses" and r.get("unit") == "credits":
                ov["below_600_max_credits"] = (r["value"], prov)
                ov["below_600_max_courses"] = (None, {**prov, "note": "replaced by a credit cap"})
            elif track:
                ov[name] = ({track: r["value"]}, {track: prov})
            else:
                ov[name] = (r["value"], prov)
            if name == "discipline_specified_min_credits":
                note = {**prov, "note": "the discipline list of the student's stream is the own basket"}
                ov["own_basket_min_credits"] = (r["value"], note)
                ov.setdefault("other_basket_min_credits", (0, {**prov, "note": "no other-basket rule for this programme"}))
                ov.setdefault("stream_core_credits", (0, {**prov, "note": "no stream core for this programme"}))
    return out


def resolve_rules(raw, courses):
    flat = []
    _flatten(raw or {}, [], flat)
    rs = RuleSet()
    progs = raw.get("programmes") if isinstance(raw, dict) else None
    if isinstance(progs, dict):
        rs.programme_info = {p: v for p, v in progs.items() if isinstance(v, dict)}
        rs.ai_course_by_programme = dict(raw.get("applications_of_ai_by_programme") or {})
    done = _structured(raw, rs)
    for name, (regex, scoped, fallback, doc, page) in RULE_SPECS.items():
        if name in done:
            continue
        if scoped:
            vals, provs = {}, {}
            for t in TRACKS:
                hit = _lookup(flat, regex, t)
                if hit:
                    vals[t] = int(hit[2]) if float(hit[2]).is_integer() else hit[2]
                    provs[t] = {"from": "rules.json", "path": hit[1], **hit[3]}
                else:
                    vals[t] = fallback[t]
                    provs[t] = {"from": "fallback", "source_doc": doc, "source_page": page}
            rs.values[name], rs.provenance[name] = vals, provs
            continue
        hit = _lookup(flat, regex, year=name.endswith("_year"))
        if hit:
            v = hit[2]
            rs.values[name] = int(v) if float(v).is_integer() else v
            rs.provenance[name] = {"from": "rules.json", "path": hit[1], **hit[3]}
        else:
            rs.values[name] = fallback
            rs.provenance[name] = {"from": "fallback" if doc else "not_stated", "source_doc": doc, "source_page": page}
    if rs.ai_applications_course is None:
        rs.ai_applications_course = _find_ai_course(raw, courses)
    return rs


def _find_ai_course(raw, courses):
    """The Applications of AI course for CSE/AI is 'Ethics of AI' (Adv5 page 2)."""
    codes = {c["code"] for c in courses}
    text = json.dumps(raw or {})
    for m in re.finditer(r'"([A-Z]{2,3} \d{3}[^"]*)"', text):
        window = text[max(0, m.start() - 200):m.start()].lower()
        if m.group(1) in codes and re.search(r"ai_?app|applications?[ _]of[ _]ai|ethics", window):
            return m.group(1)
    for c in sorted(courses, key=lambda c: c["code"]):
        if "ethics of ai" in c.get("title", "").lower():
            return c["code"]
    return None


REQ_PATTERNS = {
    "aarohan": r"aarohan",
    "writing": r"writing",
    "thesis": r"thesis",
    "project": r"project",
    "pe": r"physical education|^pe\b|req-pe",
    "hss": r"\bhss\b|humanities",
}


def requirement_kind(course):
    """Kind of a requirement pseudo-course (writing, aarohan, thesis, project, pe, hss) or None."""
    if course is None:
        return None
    text = f"{course.get('code', '')} {course.get('title', '')}".lower()
    if course.get("category") != "requirement" and not course.get("code", "").startswith("REQ"):
        return None
    for kind, rx in REQ_PATTERNS.items():
        if re.search(rx, text):
            return kind
    return "other"


@dataclass
class Catalog:
    courses: dict
    rules: RuleSet
    raw_rules: dict
    source: str
    _by_prog: dict

    def rules_for(self, programme):
        if programme not in self._by_prog:
            self._by_prog[programme] = self.rules.for_programme(programme)
        return self._by_prog[programme]

    @property
    def codes(self):
        return sorted(self.courses)

    def course(self, code):
        return self.courses.get(code)

    @property
    def known_terms(self):
        """Terms for which a full offering list (timetable) is available."""
        return sorted({t for c in self.courses.values() for t in (c.get("offered_terms") or [])})

    def is_mtech(self, code):
        c = self.courses.get(code)
        return c is not None and c.get("category") != "ug_background"

    @property
    def ug_codes(self):
        return sorted(c for c, rec in self.courses.items() if rec.get("category") == "ug_background")

    def req_code(self, kind):
        code = self.rules.requirement_codes.get(kind)
        if code in self.courses:
            return code
        hits = sorted(c for c, rec in self.courses.items() if requirement_kind(rec) == kind)
        return hits[0] if hits else None


def load_catalog(courses_path=COURSES_PATH, rules_path=RULES_PATH):
    with open(courses_path) as f:
        courses = json.load(f)
    raw_rules = {}
    if Path(rules_path).exists():
        with open(rules_path) as f:
            raw_rules = json.load(f)
    by_code = {}
    for c in courses:
        by_code.setdefault(c["code"], c)
    rules = resolve_rules(raw_rules, list(by_code.values()))
    return Catalog(by_code, rules, raw_rules, str(courses_path), {})


def course_level(course, code=None):
    if course and course.get("level") is not None:
        return int(course["level"])
    m = re.search(r"\d", code or (course or {}).get("code", ""))
    return int(m.group()) * 100 if m else None


TIMETABLE_DOC = "Timetable, Sem-I, 2026-27.xlsx"


def term_label(admit_year, semester):
    """'2026-27 Sem-I' for the given 1-based programme semester of a student admitted in admit_year."""
    year = int(admit_year) + (int(semester) - 1) // 2
    return f"{year}-{(year + 1) % 100:02d} Sem-{'I' if int(semester) % 2 == 1 else 'II'}"


def term_parity(term):
    return "even" if term.endswith("Sem-II") else "odd"


def is_pass(grade):
    return grade is None or str(grade).upper() not in PASS_FAIL_GRADES


def parity_of(semester):
    return "odd" if int(semester) % 2 == 1 else "even"
