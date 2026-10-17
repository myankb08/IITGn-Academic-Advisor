"""Write data/metadata.csv: one row per sample in the raw and processed layers."""
import csv
import json
from datetime import datetime, timezone

from src.collect.common import (EVIDENCE, EXTRACTED, PLANS, PROCESSED, ROOT, SOURCES, canonical_json,
                                read_jsonl, rel, sha256_bytes, sha256_file, tool_version)

FIELDS = ["sample_id", "layer", "artifact", "source", "source_doc", "source_page", "source_url",
          "collected_at_utc", "collector", "tool", "tool_version", "content_sha256"]


def mtime_utc(path):
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")


def script_version(module):
    path = ROOT / "src" / "collect" / f"{module}.py"
    return f"sha256:{sha256_file(path)[:12]}"


def source_rows():
    meta = json.load(open(SOURCES / "source_metadata.json"))
    by_path = {s["path"]: s for s in meta["sources"]}
    rows = []
    for f in sorted(SOURCES.iterdir()):
        if f.name.startswith(".") or f.name == "source_metadata.json" or f.is_dir():
            continue
        m = by_path.get(f.name, {})
        digest = sha256_file(f)
        if m.get("sha256") and m["sha256"] != digest:
            raise ValueError(f"sha256 mismatch for {f.name}, raw sources must stay untouched")
        rows.append({"sample_id": f"src:{f.name}", "layer": "raw", "artifact": rel(f), "source": "user_supplied",
                     "source_doc": f.name, "source_page": "", "source_url": m.get("original_url") or "",
                     "collected_at_utc": m.get("local_ingested_at_utc", ""), "collector": "hem436",
                     "tool": "manual download", "tool_version": "", "content_sha256": digest})
    for f in sorted((SOURCES / "ee_mtech_site").glob("*.html")):
        key = f"ee_mtech_site/{f.name}"
        m = by_path.get(key, {})
        digest = sha256_file(f)
        if m.get("sha256") and m["sha256"] != digest:
            raise ValueError(f"sha256 mismatch for {key}, raw sources must stay untouched")
        rows.append({"sample_id": f"src:{key}", "layer": "raw", "artifact": rel(f), "source": "user_supplied_url",
                     "source_doc": key, "source_page": "", "source_url": m.get("url", ""),
                     "collected_at_utc": m.get("collected_at", ""), "collector": "pipeline",
                     "tool": "requests", "tool_version": m.get("capture_tool_version", ""), "content_sha256": digest})
    return rows


def extracted_rows():
    versions = json.load(open(EVIDENCE / "extract_tool_versions.json"))
    when = versions["run_at_utc"]
    rows = []
    for p in read_jsonl(EXTRACTED / "pages.jsonl"):
        rows.append({"sample_id": f"page:{p['file']}#p{p['page']}", "layer": "raw",
                     "artifact": "data/raw/extracted/pages.jsonl", "source": "pdf_extraction",
                     "source_doc": p["file"], "source_page": p["page"], "source_url": "",
                     "collected_at_utc": when, "collector": "pipeline", "tool": "pdfplumber",
                     "tool_version": versions["pdfplumber"], "content_sha256": sha256_bytes(canonical_json(p).encode())})
    ee_pages = EXTRACTED / "ee_pages.jsonl"
    for p in read_jsonl(ee_pages) if ee_pages.exists() else []:
        rows.append({"sample_id": f"eesection:{p['file']}#{p['section']}", "layer": "raw",
                     "artifact": rel(ee_pages), "source": "html_extraction",
                     "source_doc": p["file"], "source_page": f"section {p['section']}", "source_url": "",
                     "collected_at_utc": mtime_utc(ee_pages), "collector": "pipeline", "tool": "html.parser (stdlib)",
                     "tool_version": "", "content_sha256": sha256_bytes(canonical_json(p).encode())})
    for r in read_jsonl(EXTRACTED / "timetable_rows.jsonl"):
        rows.append({"sample_id": f"ttrow:{r['row']}", "layer": "raw",
                     "artifact": "data/raw/extracted/timetable_rows.jsonl", "source": "xlsx_extraction",
                     "source_doc": "Timetable, Sem-I, 2026-27.xlsx", "source_page": "", "source_url": r["course_plan_url"] or "",
                     "collected_at_utc": when, "collector": "pipeline", "tool": "openpyxl",
                     "tool_version": versions["openpyxl"], "content_sha256": sha256_bytes(canonical_json(r).encode())})
    return rows


def plan_rows():
    log = {}
    for name in ("course_plan_fetch_log.csv", "ee_course_plan_fetch_log.csv"):
        if not (EVIDENCE / name).exists():
            continue
        with open(EVIDENCE / name) as f:
            for r in csv.DictReader(f):
                if r["outcome"] == "ok":
                    log[r["file"]] = r
    rows = []
    for f in sorted(PLANS.iterdir()):
        r = log.get(rel(f), {})
        rows.append({"sample_id": f"plan:{f.name}", "layer": "raw", "artifact": rel(f), "source": "course_plan_download",
                     "source_doc": f.name, "source_page": "", "source_url": r.get("original_url", ""),
                     "collected_at_utc": r.get("fetched_at_utc", ""), "collector": "pipeline", "tool": "requests",
                     "tool_version": tool_version("requests"), "content_sha256": sha256_file(f)})
    manual = ROOT / "data" / "raw" / "course_plans_manual"
    for f in sorted(manual.iterdir()) if manual.exists() else []:
        if f.suffix.lower() not in (".pdf", ".docx", ".txt", ".html"):
            continue
        r = log.get(rel(f), {})
        rows.append({"sample_id": f"plan_manual:{f.name}", "layer": "raw", "artifact": rel(f),
                     "source": "course_plan_manual_download", "source_doc": f.name, "source_page": "",
                     "source_url": r.get("original_url", ""), "collected_at_utc": r.get("fetched_at_utc", ""),
                     "collector": "hem436", "tool": "manual download with IITGN login", "tool_version": "",
                     "content_sha256": sha256_file(f)})
    texts = [(t, "course_plan_text.jsonl") for t in read_jsonl(EXTRACTED / "course_plan_text.jsonl")]
    if (EXTRACTED / "ee_course_plan_text.jsonl").exists():
        texts += [(t, "ee_course_plan_text.jsonl") for t in read_jsonl(EXTRACTED / "ee_course_plan_text.jsonl")]
    for t, name in texts:
        rows.append({"sample_id": f"plantext:{t['code']}", "layer": "raw",
                     "artifact": f"data/raw/extracted/{name}", "source": "course_plan_text_extraction",
                     "source_doc": t["file"], "source_page": "", "source_url": t["source_url"],
                     "collected_at_utc": mtime_utc(EXTRACTED / name),
                     "collector": t.get("collector", "pipeline"),
                     "tool": t["extractor"], "tool_version": "", "content_sha256": sha256_bytes(canonical_json(t).encode())})
    return rows


def catalog_rows():
    rows = []
    raw_path = ROOT / "data" / "raw" / "catalog_raw.json"
    for r in json.load(open(raw_path)):
        rows.append({"sample_id": f"catraw:{r['raw_id']}", "layer": "raw", "artifact": rel(raw_path),
                     "source": "build_catalog", "source_doc": r["source_doc"],
                     "source_page": r["source_page"] if r["source_page"] is not None
                     else (f"section {r['source_section']}" if r.get("source_section") else ""),
                     "source_url": r.get("course_plan_url") or "", "collected_at_utc": mtime_utc(raw_path),
                     "collector": "pipeline", "tool": "src.collect.build_catalog",
                     "tool_version": script_version("build_catalog"), "content_sha256": sha256_bytes(canonical_json(r).encode())})
    manual = ROOT / "data" / "raw" / "prereq_manual.csv"
    with open(manual) as f:
        for r in csv.DictReader(f):
            rows.append({"sample_id": f"prereq_manual:{r['code']}", "layer": "raw", "artifact": rel(manual),
                         "source": "manual_decision", "source_doc": "", "source_page": "", "source_url": "",
                         "collected_at_utc": r["decided_at"], "collector": "pipeline", "tool": "manual review",
                         "tool_version": "", "content_sha256": sha256_bytes(canonical_json(r).encode())})
    courses_path = PROCESSED / "courses.json"
    for c in json.load(open(courses_path)):
        rows.append({"sample_id": f"course:{c['code']}", "layer": "processed", "artifact": rel(courses_path),
                     "source": "clean_catalog", "source_doc": c["source_doc"],
                     "source_page": c["source_page"] if c["source_page"] is not None else f"row {c['source_row']}",
                     "source_url": c["source_url"] or "", "collected_at_utc": mtime_utc(courses_path),
                     "collector": "pipeline", "tool": "src.collect.clean_catalog",
                     "tool_version": script_version("clean_catalog"), "content_sha256": c["record_sha256"]})
    rules_path = PROCESSED / "rules.json"
    for r in json.load(open(rules_path))["rules"].values():
        if r.get("not_stated"):
            continue
        rows.append({"sample_id": f"rule:{r['rule_id']}", "layer": "processed", "artifact": rel(rules_path),
                     "source": "build_rules", "source_doc": r["source_doc"],
                     "source_page": r["source_page"] if r["source_page"] is not None else f"section {r['source_section']}",
                     "source_url": "", "collected_at_utc": mtime_utc(rules_path), "collector": "pipeline",
                     "tool": "src.collect.build_rules", "tool_version": script_version("build_rules"),
                     "content_sha256": r["record_sha256"]})
    return rows


def main():
    rows = source_rows() + extracted_rows() + plan_rows() + catalog_rows()
    with open(ROOT / "data" / "metadata.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    counts = {}
    for r in rows:
        key = r["sample_id"].split(":")[0]
        counts[key] = counts.get(key, 0) + 1
    print(f"metadata rows={len(rows)} {counts}")


if __name__ == "__main__":
    main()
