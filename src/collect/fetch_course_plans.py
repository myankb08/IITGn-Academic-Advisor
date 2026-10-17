"""Download course plans for CS M.Tech relevant courses and extract their text.

Usage: python -m src.collect.fetch_course_plans [--refresh | --offline]
Files already downloaded are reused unless --refresh is given, so reruns are idempotent.
--offline makes no requests and reuses the previous log for codes without a file.
Plans that need an IITGN login are downloaded by hand into data/raw/course_plans_manual/
as <CODE with space as _>.(pdf|docx|txt|html); they are ingested on every run and take
precedence over a fetched file for the same code.
"""
import csv
import io
import re
import sys
import time
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser

import pdfplumber
import requests

from src.collect.common import (CODE_RE, EVIDENCE, EXTRACTED, PLANS, ROOT, STRUCTURE_PDF, code_filename,
                                normalise_code, now_utc, read_jsonl, rel, sha256_bytes, tool_version,
                                write_jsonl)

LOG = EVIDENCE / "course_plan_fetch_log.csv"
LOG_FIELDS = ["code", "timetable_row", "original_url", "request_url", "method", "http_status",
              "content_type", "outcome", "detail", "file", "sha256", "fetched_at_utc"]
MANUAL = ROOT / "data" / "raw" / "course_plans_manual"
MANUAL_EXTS = {"pdf", "docx", "txt", "html"}
MANUAL_METHOD = "manual download with IITGN login"
HEADERS = {"User-Agent": "Mozilla/5.0 (coursework data collection, IITGN CS203)"}
SLEEP = 0.5
GDOC_RE = re.compile(r"docs\.google\.com/document/(?:u/\d+/)?d/([\w-]+)")
DRIVE_RE = re.compile(r"drive\.google\.com/(?:file/d/([\w-]+)|open\?id=([\w-]+))")


def relevant_codes():
    """Codes named in the CSE structure PDF plus CS 6xx / ES 6xx rows in the timetable."""
    pages = [p for p in read_jsonl(EXTRACTED / "pages.jsonl") if p["file"] == STRUCTURE_PDF]
    codes = set()
    for p in pages:
        for m in CODE_RE.finditer(p["text"]):
            codes.add(normalise_code(m.group(0)))
    for r in read_jsonl(EXTRACTED / "timetable_rows.jsonl"):
        code = normalise_code(r["course_number_raw"])
        if code and re.match(r"(CS|ES) 6\d\d", code):
            codes.add(code)
    return sorted(codes)


def first_url_rows():
    out = {}
    for r in read_jsonl(EXTRACTED / "timetable_rows.jsonl"):
        code = normalise_code(r["course_number_raw"])
        if code and code not in out and r["course_plan_url"]:
            out[code] = r
    return out


def candidate_requests(url):
    m = GDOC_RE.search(url)
    if m:
        return [("gdoc_export_txt", f"https://docs.google.com/document/d/{m.group(1)}/export?format=txt"),
                ("drive_usercontent", f"https://drive.usercontent.google.com/download?id={m.group(1)}&export=download&confirm=t")]
    m = DRIVE_RE.search(url)
    if m:
        fid = m.group(1) or m.group(2)
        return [("drive_usercontent", f"https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t")]
    return [("direct_get", url)]


def sniff_ext(content, content_type):
    if content.startswith(b"%PDF"):
        return "pdf"
    if content.startswith(b"PK"):
        return "docx" if b"word/" in content[:4000] or b"[Content_Types]" in content[:200] else "zip"
    if "text/plain" in content_type:
        return "txt"
    if "html" in content_type:
        return "html"
    return "bin"


def looks_like_login(content):
    head = content.lower()
    return b"accounts.google.com" in head and (b"sign in" in head or b"servicelogin" in head)


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def to_text(path, ext):
    data = path.read_bytes()
    if ext == "pdf":
        with pdfplumber.open(io.BytesIO(data)) as doc:
            return "\n".join(p.extract_text() or "" for p in doc.pages), f"pdfplumber {tool_version('pdfplumber')}"
    if ext == "docx":
        xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")
        xml = re.sub(r"</w:p>", "\n", xml)
        return re.sub(r"<[^>]+>", "", xml), "zipfile+regex (word/document.xml)"
    if ext == "html":
        p = _Text()
        p.feed(data.decode("utf-8", errors="replace"))
        text = re.sub(r"\n\s*\n+", "\n", "".join(p.parts))
        return text, "html.parser (stdlib)"
    if ext == "txt":
        return data.decode("utf-8-sig", errors="replace"), "utf-8 decode"
    return "", "unsupported"


def fetch_one(code, row, session):
    """Try each candidate url in order; return log rows and the saved path (or None)."""
    logs = []
    for method, url in candidate_requests(row["course_plan_url"]):
        entry = {"code": code, "timetable_row": row["row"], "original_url": row["course_plan_url"],
                 "request_url": url, "method": method, "fetched_at_utc": now_utc()}
        try:
            resp = session.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        except requests.RequestException as exc:
            logs.append({**entry, "http_status": "", "outcome": "failed", "detail": type(exc).__name__})
            time.sleep(SLEEP)
            continue
        ctype = resp.headers.get("Content-Type", "")
        entry.update({"http_status": resp.status_code, "content_type": ctype})
        time.sleep(SLEEP)
        if resp.status_code != 200:
            logs.append({**entry, "outcome": "failed", "detail": "non-200 status (likely not public)"})
            continue
        if method != "direct_get" and ("html" in ctype or looks_like_login(resp.content)):
            why = "Google sign-in page, file not public" if looks_like_login(resp.content) else "html returned instead of file"
            logs.append({**entry, "outcome": "failed", "detail": why})
            continue
        ext = sniff_ext(resp.content, ctype)
        path = PLANS / f"{code_filename(code)}.{ext}"
        path.write_bytes(resp.content)
        logs.append({**entry, "outcome": "ok", "detail": f"{len(resp.content)} bytes",
                     "file": rel(path), "sha256": sha256_bytes(resp.content)})
        return logs, path
    return logs, None


def load_previous_log():
    if not LOG.exists():
        return {}
    prev = {}
    with open(LOG) as f:
        for r in csv.DictReader(f):
            prev.setdefault(r["code"], []).append(r)
    return prev


def manual_plans(urls):
    """Log rows and text rows for hand-downloaded plans in data/raw/course_plans_manual."""
    logs, texts = [], []
    if not MANUAL.exists():
        return logs, texts
    for path in sorted(MANUAL.iterdir()):
        ext = path.suffix.lstrip(".").lower()
        code = normalise_code(path.stem.replace("_", " "))
        if ext not in MANUAL_EXTS or code is None:
            continue
        data = path.read_bytes()
        when = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
        url = (urls.get(code) or {}).get("course_plan_url", "")
        row = (urls.get(code) or {}).get("row", "")
        logs.append({"code": code, "timetable_row": row, "original_url": url, "request_url": "",
                     "method": MANUAL_METHOD, "http_status": "", "content_type": "", "outcome": "ok",
                     "detail": f"collector hem436, {len(data)} bytes", "file": rel(path),
                     "sha256": sha256_bytes(data), "fetched_at_utc": when})
        text, extractor = to_text(path, ext)
        texts.append({"code": code, "file": path.name, "format": ext, "source_url": url, "text": text,
                      "extractor": extractor, "sha256_file": sha256_bytes(data), "collector": "hem436",
                      "method": MANUAL_METHOD})
    return logs, texts


def main():
    refresh = "--refresh" in sys.argv
    offline = "--offline" in sys.argv
    PLANS.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    prev = load_previous_log()
    urls = first_url_rows()
    session = requests.Session()
    log_rows, texts = [], []
    for code in relevant_codes():
        row = urls.get(code)
        if row is None:
            log_rows.append({"code": code, "outcome": "no_url",
                             "detail": "not in Sem-I timetable or no course plan hyperlink",
                             "fetched_at_utc": now_utc()})
            continue
        prev_auto = [r for r in prev.get(code, []) if r.get("method") != MANUAL_METHOD]
        old_ok = [r for r in prev_auto if r["outcome"] == "ok"]
        if old_ok and not refresh and (ROOT / old_ok[-1]["file"]).exists():
            log_rows.extend(prev_auto)
            path = ROOT / old_ok[-1]["file"]
        elif offline:
            log_rows.extend(prev_auto)
            continue
        else:
            logs, path = fetch_one(code, row, session)
            log_rows.extend(logs)
            if path is None:
                continue
        ext = path.suffix.lstrip(".")
        text, extractor = to_text(path, ext)
        texts.append({"code": code, "file": path.name, "format": ext, "source_url": row["course_plan_url"],
                      "text": text, "extractor": extractor, "sha256_file": sha256_bytes(path.read_bytes()),
                      "collector": "pipeline", "method": "download"})
    m_logs, m_texts = manual_plans(urls)
    log_rows.extend(m_logs)
    manual_codes = {t["code"] for t in m_texts}
    texts = sorted([t for t in texts if t["code"] not in manual_codes] + m_texts, key=lambda t: t["code"])
    with open(LOG, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        w.writeheader()
        for r in log_rows:
            w.writerow({k: r.get(k, "") for k in LOG_FIELDS})
    write_jsonl(EXTRACTED / "course_plan_text.jsonl", texts)
    codes = relevant_codes()
    print(f"relevant_codes={len(codes)} with_url={sum(c in urls for c in codes)} plans={len(texts)} "
          f"manual={len(m_texts)}")


if __name__ == "__main__":
    main()
