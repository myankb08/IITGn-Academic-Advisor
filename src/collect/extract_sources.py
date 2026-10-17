"""Extract page text from every source PDF and course rows from the timetable xlsx."""
import openpyxl
import pdfplumber

from src.collect.common import (EVIDENCE, EXTRACTED, SOURCES, TIMETABLE_SHEET, TIMETABLE_XLSX,
                                now_utc, sha256_file, tool_version, write_json, write_jsonl)

COLS = {"course_number_raw": 0, "title": 1, "L": 2, "T": 3, "P": 4, "C": 5, "instructors": 6,
        "plan_cell": 13, "remarks": 15}


def extract_pdfs():
    rows = []
    for pdf in sorted(SOURCES.glob("*.pdf")):
        digest = sha256_file(pdf)
        with pdfplumber.open(pdf) as doc:
            for i, page in enumerate(doc.pages, 1):
                rows.append({"file": pdf.name, "page": i, "text": page.extract_text() or "",
                             "tables": page.extract_tables(), "sha256_file": digest})
    write_jsonl(EXTRACTED / "pages.jsonl", rows)
    return rows


def extract_timetable():
    path = SOURCES / TIMETABLE_XLSX
    ws = openpyxl.load_workbook(path)[TIMETABLE_SHEET]
    rows = []
    for cells in ws.iter_rows(min_row=2):
        number, title = cells[COLS["course_number_raw"]].value, cells[COLS["title"]].value
        if number is None or title is None:
            continue
        link = cells[COLS["plan_cell"]].hyperlink
        rows.append({
            "sheet": TIMETABLE_SHEET,
            "row": cells[0].row,
            "course_number_raw": str(number),
            "title": str(title),
            "L": cells[COLS["L"]].value,
            "T": cells[COLS["T"]].value,
            "P": cells[COLS["P"]].value,
            "C": cells[COLS["C"]].value,
            "instructors": cells[COLS["instructors"]].value,
            "course_plan_url": link.target if link is not None else None,
            "remarks": cells[COLS["remarks"]].value,
        })
    write_jsonl(EXTRACTED / "timetable_rows.jsonl", rows)
    return rows


def main():
    pages = extract_pdfs()
    rows = extract_timetable()
    write_json(EVIDENCE / "extract_tool_versions.json", {
        "run_at_utc": now_utc(),
        "pdfplumber": tool_version("pdfplumber"),
        "pdfminer.six": tool_version("pdfminer.six"),
        "openpyxl": tool_version("openpyxl"),
        "pages": len(pages),
        "pdf_files": len({p["file"] for p in pages}),
        "timetable_rows": len(rows),
    })
    print(f"pages={len(pages)} timetable_rows={len(rows)}")


if __name__ == "__main__":
    main()
