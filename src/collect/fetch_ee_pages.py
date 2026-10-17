"""Fetch the EE M.Tech Google Site pages and the course plans of the EE courses they list.

Usage: python -m src.collect.fetch_ee_pages [--refresh]
Saved pages are reused unless --refresh is given. The URL was supplied by hem436.
"""
import csv
import json
import re
import sys
import time
from html.parser import HTMLParser

import requests

from src.collect.common import (EVIDENCE, EXTRACTED, ROOT, SOURCES, normalise_code, now_utc, read_jsonl,
                                rel, sha256_bytes, sha256_file, tool_version, write_jsonl)
from src.collect.fetch_course_plans import HEADERS, LOG_FIELDS, SLEEP, fetch_one, to_text

BASE = "https://sites.google.com/iitgn.ac.in/ee-mtech/"
SLUGS = ["home", "power-engineering-control-systems", "signal-processing-machine-learning",
         "integrated-circuit-design-technology"]
SITE_DIR = SOURCES / "ee_mtech_site"
SITE_LOG = EVIDENCE / "ee_site_fetch_log.csv"
PLAN_LOG = EVIDENCE / "ee_course_plan_fetch_log.csv"
SUPPLIED_URL = BASE + "power-engineering-control-systems"
EE_CODE_RE = re.compile(r"^((?:EE|ES)\s*\d{3})\s+(.+)$")


class _Sections(HTMLParser):
    """Split page text into sections at each <h1>, keeping line breaks at block tags."""

    BLOCK = ("p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4")

    def __init__(self):
        super().__init__()
        self.sections, self.skip, self.in_h1 = [["preamble", []]], 0, False
        self.h1 = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "h1":
            self.in_h1, self.h1 = True, []
        if tag in self.BLOCK:
            self.sections[-1][1].append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag == "h1" and self.in_h1:
            self.in_h1 = False
            self.sections.append([" ".join("".join(self.h1).split()), []])

    def handle_data(self, data):
        if self.skip:
            return
        if self.in_h1:
            self.h1.append(data)
        else:
            self.sections[-1][1].append(data)


def page_sections(path):
    p = _Sections()
    p.feed(path.read_text(encoding="utf-8"))
    out = []
    for name, parts in p.sections:
        lines = [ln.strip() for ln in "".join(parts).splitlines()]
        text = "\n".join(ln for ln in lines if ln)
        if text:
            out.append((name, text))
    return out


def fetch_pages(refresh, session):
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    prev = {}
    if SITE_LOG.exists():
        with open(SITE_LOG) as f:
            prev = {r["slug"]: r for r in csv.DictReader(f)}
    rows = []
    for slug in SLUGS:
        path = SITE_DIR / f"{slug}.html"
        if path.exists() and not refresh and slug in prev and prev[slug]["outcome"] == "ok":
            rows.append(prev[slug])
            continue
        url = BASE + slug
        entry = {"slug": slug, "url": url, "fetched_at_utc": now_utc()}
        try:
            resp = session.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException as exc:
            rows.append({**entry, "http_status": "", "outcome": "failed", "detail": type(exc).__name__})
            continue
        time.sleep(SLEEP)
        if resp.status_code != 200:
            rows.append({**entry, "http_status": resp.status_code, "outcome": "failed", "detail": "non-200 status"})
            continue
        path.write_bytes(resp.content)
        rows.append({**entry, "http_status": resp.status_code, "final_url": resp.url, "outcome": "ok",
                     "detail": f"{len(resp.content)} bytes", "file": rel(path), "sha256": sha256_bytes(resp.content)})
    fields = ["slug", "url", "final_url", "http_status", "outcome", "detail", "file", "sha256", "fetched_at_utc"]
    with open(SITE_LOG, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    return rows


def update_source_metadata(rows):
    path = SOURCES / "source_metadata.json"
    meta = json.load(open(path))
    keep = [s for s in meta["sources"] if not s["path"].startswith("ee_mtech_site/")]
    for r in rows:
        if r["outcome"] != "ok":
            continue
        keep.append({
            "path": f"ee_mtech_site/{r['slug']}.html",
            "source_id": f"ee_mtech_site_{r['slug']}",
            "title": f"EE M.Tech site, {r['slug']} page",
            "url": r["url"],
            "final_url": r.get("final_url") or r["url"],
            "supplied_url": SUPPLIED_URL,
            "provided_by": "user",
            "url_supplied_by": "hem436",
            "collected_at": r["fetched_at_utc"],
            "collector": "pipeline",
            "capture_tool": "requests",
            "capture_tool_version": tool_version("requests"),
            "sha256": sha256_file(ROOT / r["file"]),
            "representation": "original_http_body",
        })
    meta["sources"] = keep
    with open(path, "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        f.write("\n")


def extract_pages():
    rows = []
    for slug in SLUGS:
        path = SITE_DIR / f"{slug}.html"
        if not path.exists():
            continue
        for section, text in page_sections(path):
            rows.append({"file": f"ee_mtech_site/{slug}.html", "section": section, "text": text})
    write_jsonl(EXTRACTED / "ee_pages.jsonl", rows)
    return rows


def ee_codes(pages):
    codes = set()
    for p in pages:
        if p["section"] != "Curriculum" or p["file"].endswith("home.html"):
            continue
        for line in p["text"].splitlines():
            m = EE_CODE_RE.match(line)
            if m:
                codes.add(normalise_code(m.group(1)))
    return codes


def fetch_plans(pages, refresh, session):
    """Fetch plans for EE-prefixed courses; ES courses are already handled by fetch_course_plans."""
    rows = read_jsonl(EXTRACTED / "timetable_rows.jsonl")
    url_rows = {}
    wanted = {c for c in ee_codes(pages) if c.startswith("EE ")}
    for r in rows:
        code = normalise_code(r["course_number_raw"])
        if code and re.match(r"EE 6\d\d", code):
            wanted.add(code)
        if code in wanted and code not in url_rows and r["course_plan_url"]:
            url_rows[code] = r
    prev = {}
    if PLAN_LOG.exists():
        with open(PLAN_LOG) as f:
            for r in csv.DictReader(f):
                prev.setdefault(r["code"], []).append(r)
    log, texts = [], []
    for code in sorted(wanted):
        row = url_rows.get(code)
        if row is None:
            log.append({"code": code, "outcome": "no_url",
                        "detail": "not in Sem-I timetable or no course plan hyperlink", "fetched_at_utc": now_utc()})
            continue
        old_ok = [r for r in prev.get(code, []) if r["outcome"] == "ok"]
        if old_ok and not refresh and (ROOT / old_ok[-1]["file"]).exists():
            log.extend(prev[code])
            path = ROOT / old_ok[-1]["file"]
        else:
            entries, path = fetch_one(code, row, session)
            log.extend(entries)
            if path is None:
                continue
        text, extractor = to_text(path, path.suffix.lstrip("."))
        texts.append({"code": code, "file": path.name, "format": path.suffix.lstrip("."),
                      "source_url": row["course_plan_url"], "text": text, "extractor": extractor,
                      "sha256_file": sha256_file(path)})
    with open(PLAN_LOG, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        w.writeheader()
        for r in log:
            w.writerow({k: r.get(k, "") for k in LOG_FIELDS})
    write_jsonl(EXTRACTED / "ee_course_plan_text.jsonl", texts)
    return wanted, url_rows, texts


def main():
    refresh = "--refresh" in sys.argv
    session = requests.Session()
    site = fetch_pages(refresh, session)
    update_source_metadata(site)
    pages = extract_pages()
    wanted, url_rows, texts = fetch_plans(pages, refresh, session)
    ok = sum(r["outcome"] == "ok" for r in site)
    print(f"site_pages={ok}/{len(SLUGS)} sections={len(pages)} ee_site_codes={len(ee_codes(pages))} "
          f"ee_plan_codes={len(wanted)} with_url={len(url_rows)} plans_fetched={len(texts)}")


if __name__ == "__main__":
    main()
