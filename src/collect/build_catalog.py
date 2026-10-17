"""Build data/raw/catalog_raw.json: course records exactly as found in the sources (CSE PDF, Adv5, EE site, timetable).

Defects (duplicates, typos, float credits, section suffixes) are kept on purpose.
clean_catalog.py fixes them and logs every change.
"""
import re

from src.collect.common import (CODE_RE, EXTRACTED, ROOT, STRUCTURE_PDF, TIMETABLE_XLSX, normalise_code,
                                read_jsonl, write_json)

ADV5 = "Adv5_NormsforMTechProgramme.pdf"
BASKET_HEADINGS = {"AI/ML Basket": "AI/ML", "Systems Basket": "Systems", "Theory Basket": "Theory"}
ITEM_RE = re.compile(r"^\d+\.\s+([A-Z]{2,3}\s*\d{3}(?:-[IVXL]+)?)\s*:?\s*(.*)$")
EE_STREAMS = {
    "power-engineering-control-systems": "Power Engineering & Control Systems",
    "signal-processing-machine-learning": "Signal Processing & Machine Learning",
    "integrated-circuit-design-technology": "Integrated Circuit Design & Technology",
}
EE_ITEM_RE = re.compile(r"^((?:EE|ES)\s*\d{3})\s+(.+)$")
COMPULSORY_RE = re.compile(r"^\d+\.\s+([A-Z]{2,3}\s*\d{3})\s*\(([^)]*)\)\s*is a compulsory course")
REQUIREMENTS = [
    # key, regex matched against Adv5 page text, timetable code that implements it (or None)
    ("writing", r"The 4-credit “Writing” course will be required for all students\.", "FP 602"),
    ("aarohan", r"Completing PG Orientation Programme Aarohan \(2 Credits\) is a mandatory", "FP 601"),
    ("physical_education", r"must\s+complete two Physical Education \(PE\) courses", "PE 600"),
    ("hss", r"at least\s+4 credits will have to be earned through Humanities and Social Sciences \(HSS\)", None),
    ("thesis_units", r"A\s+student may register for one 4 credit thesis unit or a multiple of it", None),
    ("project_courses", r"required to earn at least 16 credits\s+through postgraduate level project courses", None),
]


def structure_records(pages):
    recs = []
    basket = None
    for p in pages:
        lines = [x.strip() for x in p["text"].splitlines()]
        for i, line in enumerate(lines):
            m = COMPULSORY_RE.match(line)
            if m:
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                offered = re.search(r"Offered in (\w+) semester", line + " " + nxt)
                recs.append({"role": "compulsory", "stream": None, "code_raw": m.group(1), "title_raw": m.group(2),
                             "offered_raw": offered.group(1) if offered else None, "line": f"{line} {nxt}".strip(),
                             "source_page": p["page"]})
                continue
            if line in BASKET_HEADINGS:
                basket = BASKET_HEADINGS[line]
                continue
            m = ITEM_RE.match(line)
            if m and basket:
                recs.append({"role": "basket", "stream": basket, "code_raw": m.group(1), "title_raw": m.group(2),
                             "offered_raw": None, "line": line, "source_page": p["page"]})
        for table in p["tables"]:
            for row in table:
                for cell, stream in zip(row, ["AI/ML", "Systems", "Theory"]):
                    if not cell or not cell.startswith("Core:"):
                        continue
                    items = []
                    for line in cell.splitlines()[1:]:
                        if CODE_RE.match(line):
                            items.append(line)
                        elif items:
                            items[-1] += " " + line
                    for item in items:
                        code, _, title = item.partition(":")
                        recs.append({"role": "stream_core", "stream": stream, "code_raw": code.strip(),
                                     "title_raw": title.strip(), "offered_raw": None, "line": item,
                                     "source_page": p["page"]})
    out = []
    for n, r in enumerate(recs, 1):
        out.append({"raw_id": f"struct-{n:03d}", "source_doc": STRUCTURE_PDF, "source_row": None, **r})
    return out


def requirement_records(pages):
    out = []
    for key, pattern, code in REQUIREMENTS:
        hits = [p for p in pages if re.search(pattern, p["text"])]
        if not hits:
            raise ValueError(f"requirement text not found in {ADV5}: {key}")
        m = re.search(pattern, hits[0]["text"])
        out.append({"raw_id": f"req-{key}", "role": "requirement", "requirement": key, "stream": None,
                    "code_raw": code, "title_raw": None, "offered_raw": None,
                    "line": " ".join(m.group(0).split()), "source_doc": ADV5,
                    "source_page": hits[0]["page"], "source_row": None})
    return out


def timetable_records(rows, wanted):
    out = []
    for r in rows:
        code = normalise_code(r["course_number_raw"])
        if code not in wanted:
            continue
        out.append({"raw_id": f"tt-r{r['row']}", "role": "timetable_offering", "stream": None,
                    "code_raw": r["course_number_raw"], "title_raw": r["title"],
                    "L": r["L"], "T": r["T"], "P": r["P"], "C": r["C"],
                    "course_plan_url": r["course_plan_url"], "remarks": r["remarks"],
                    "source_doc": TIMETABLE_XLSX, "source_page": None, "source_row": r["row"]})
    return out


def ee_records(sections):
    out = []
    for slug, stream in EE_STREAMS.items():
        doc = f"ee_mtech_site/{slug}.html"
        secs = [p for p in sections if p["file"] == doc and p["section"] == "Curriculum"]
        if not secs:
            raise ValueError(f"no Curriculum section in {doc}, run fetch_ee_pages first")
        n = 0
        for line in secs[0]["text"].splitlines():
            m = EE_ITEM_RE.match(line)
            if not m:
                continue
            n += 1
            out.append({"raw_id": f"ee-{slug.split('-')[0]}-{n:02d}", "role": "basket", "stream": stream,
                        "code_raw": m.group(1), "title_raw": m.group(2), "offered_raw": None, "line": line,
                        "programmes": ["MTech-EE"], "source_doc": doc, "source_page": None,
                        "source_section": "Curriculum", "source_row": None})
    return out


def build():
    pages = read_jsonl(EXTRACTED / "pages.jsonl")
    rows = read_jsonl(EXTRACTED / "timetable_rows.jsonl")
    struct = structure_records([p for p in pages if p["file"] == STRUCTURE_PDF])
    reqs = requirement_records([p for p in pages if p["file"] == ADV5])
    ee = ee_records(read_jsonl(EXTRACTED / "ee_pages.jsonl"))
    for r in struct:
        r.setdefault("programmes", ["MTech-CSE", "MTech-AI"])
    for r in reqs:
        r.setdefault("programmes", ["MTech-CSE", "MTech-AI", "MTech-EE"])
    wanted = {normalise_code(r["code_raw"]) for r in struct + reqs + ee if r["code_raw"]}
    wanted |= {c for c in (normalise_code(r["course_number_raw"]) for r in rows)
               if c and re.match(r"(CS|ES|EE) 6\d\d", c)}
    tt = timetable_records(rows, wanted)
    for r in tt:
        r.setdefault("programmes", None)
    records = struct + reqs + ee + tt
    for r in records:
        r.setdefault("source_section", None)
    return records


def main():
    records = build()
    write_json(ROOT / "data" / "raw" / "catalog_raw.json", records)
    by_role = {}
    for r in records:
        by_role[r["role"]] = by_role.get(r["role"], 0) + 1
    print(f"catalog_raw records={len(records)} {by_role}")


if __name__ == "__main__":
    main()
