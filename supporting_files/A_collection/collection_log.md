# Part A collection log

Run date: 2026-10-17. Python 3.10 in `.venv`. Tools: pdfplumber 0.11.10 (pdfminer.six 20260107), openpyxl 3.1.5, requests 2.34.2.
Scope: M.Tech CSE (streams AI/ML, Systems, Theory) and M.Tech AI (AI/ML stream only).
The full pipeline was run twice. Apart from timestamps in the fetch log (failed links are retried), every output file had the same sha256 on both runs.

## 1. Extraction (`extract_sources`)

- 9 PDFs, 16 pages written to `data/raw/extracted/pages.jsonl` (text plus pdfplumber tables per page).
- 346 course rows from sheet "Time table" written to `data/raw/extracted/timetable_rows.jsonl`. Section heading rows (no title) are skipped. The plan URL is the hyperlink target of the "Link To Course Plan" cell, not the cell text.
- The "Preferred Knowledge Equivalent to" column is empty for every row, so it gives no prerequisite information.
- Source sha256 values match `source_metadata.json` for all 10 files present. `source_metadata.json` also lists six `collected_sources/*` files (HTML pages and two PDFs) that are not on disk. They are not used and not in `metadata.csv`.
- Tool versions: `extract_tool_versions.json`.

## 2. Course plans (`fetch_course_plans`)

Relevant codes: every code named in the CSE structure PDF plus every CS 6xx and ES 6xx row in the timetable, 50 codes.

| outcome | codes |
|---|---|
| downloaded | 15 |
| link present, download failed | 12 |
| no link in the Sem-I timetable | 23 |

- All 12 failures are Google Docs or Drive files that need an IITGN login: the export URL returns 401 and the Drive download returns a Google sign-in page. These were not bypassed.
- 15 files saved: 5 Google Docs exported as text, 2 Drive PDFs, 8 public course web pages (HTML).
- `ES_662.html` is a SharePoint page that renders with JavaScript, so it has no readable text. It is treated as "no course plan available".
- Course codes not offered in Sem-I 2026-27 (for example CS 616, CS 618, CS 621, the Theory basket) have no link at all.
- Per-request log with URL, status, timestamp and sha256: `course_plan_fetch_log.csv`.

## 3. Catalog (`build_catalog`, `clean_catalog`)

`data/raw/catalog_raw.json` has 77 records: 2 compulsory, 6 stream core and 25 basket listings from the structure PDF, 6 requirement statements from Adv5, and 38 timetable rows. Defects are kept as found: CS 618 listed twice in the AI/ML basket, "Advanced Algrithms", float credits such as 4.0, the `FP 602 (MA)`, `(CG)`, `(CH)` variants, trailing commas and spaces in titles, and courses listed twice in the timetable (CS 329, ES 621, ES 666).

`data/processed/courses.json` has 56 courses: 2 compulsory, 6 stream core, 24 basket, 18 open electives (CS 6xx and ES 6xx in the timetable that are not in any basket), 6 requirement entries.

53 changes, all in `cleaning_changes.csv`:

- 35 float credits converted to int.
- 4 duplicate listings merged (CS 618 in the structure PDF, three courses repeated in the timetable).
- 3 Writing variants for other PG programmes dropped (`FP 602 (MA)`, `(CG)`, `(CH)`); M.Tech uses the plain `FP 602` row.
- 3 placeholder codes assigned to requirements without a timetable code: `REQ-HSS`, `REQ-THESIS`, `REQ-PROJECT`.
- 4 titles stripped of trailing commas or spaces, 1 typo fixed ("Algrithms"), 2 short titles replaced by the timetable title ("NLP", "Computational neuroscience").
- 1 manual prerequisite decision (CS 613).

Credits: 32 from the timetable C column, 2 from a rules document (CS 621 from Adv5 p2, thesis unit from Adv5 p3), 22 default 4 credits citing Adv17 p1 (standard 3-0-0 course). The default covers courses not in the Sem-I timetable and the HSS and project placeholders.

Offered: 32 courses `odd` (in the Sem-I timetable, or CS 610 by the structure PDF), CS 621 `even` (structure PDF), 23 `null` because no source says when they run.

Observation, not changed: ES 417 "5G and Beyond" is in the Systems basket, but the timetable offers "5G and Beyond" as ES 668. This may be a renumbering, but no source says so, so both stay as separate courses.

## 4. Prerequisites

No course ends up with an enforceable prerequisite. This is what the sources say, not a gap in the code:

| result | courses |
|---|---|
| no course plan available (no link, login required, or no text) | 36 |
| plan found, no prerequisite statement | 9 |
| plan says none or not mandatory (ES 616, ES 657, ES 666 PG, ES 668) | 4 |
| manual decision (CS 613) | 1 |
| requirement entries, not applicable | 6 |

- ES 666 lists UG prerequisites (ES 112, MA 101, MA 102) and "PG: None". M.Tech students are PG, so the PG line is used.
- CS 613 lists "Prerequisite (Optional)" with UG courses "or equivalent". These are recommended background, so `data/raw/prereq_manual.csv` stores an empty list with the reason. This decision was made by the pipeline assistant and should be checked by hem436.
- CS 619 mentions "max flow min cut prereq." inside a topic list. The extractor only reads lines that start with a prerequisite heading, so this is ignored.

## 5. Rules (`build_rules`)

`data/processed/rules.json` has 56 rules with a value, each with `source_doc`, `source_page` and a verbatim quote that the script checks against the page text. One entry is marked `not_stated`: maximum credits per semester (none of the sources gives it). The cap on courses below 600 level is stated as a count (at most two UG courses with codes 1XX to 5XX, besides one UG HSS course), not as credits.

Sources used: Adv5 (credits, tracks, Writing, HSS, Applications of AI, electives, discipline courses, UG cap, PE, thesis and project grading, CPI rules), the CSE structure PDF (compulsory courses, stream cores, baskets, M.Tech AI stream), Adv24 (pass/fail and substitution), Adv17 (course levels, standard credits), Adv42 (early admit follows the regular curriculum).

## 6. Metadata (`build_metadata`)

`data/metadata.csv` has 592 rows: 10 source files, 16 PDF pages, 346 timetable rows, 15 course plan files, 15 plan text rows, 77 raw catalog records, 1 manual decision, 56 processed courses, 56 rules.

## 7. EE M.Tech site (`fetch_ee_pages`, follow-up run on 2026-10-17)

- Source URL supplied by hem436. 4 pages fetched with HTTP 200 (home and the three specialisation pages) and saved untouched in `data/raw/sources/ee_mtech_site/`. Log: `ee_site_fetch_log.csv`. Entries were added to `source_metadata.json`.
- 21 `<h1>` sections extracted to `data/raw/extracted/ee_pages.jsonl`.
- Courses listed under "Courses Specified by the Discipline": Power Engineering & Control Systems 11, Signal Processing & Machine Learning 23, Integrated Circuit Design & Technology 14. That is 48 listings and 47 unique codes, because ES 654 appears in two lists. The ICDT list is marked "*To be updated soon".
- Raw defects kept as found: a non-breaking space in "Fundamentals of  Wireless Localization", and titles that differ from the timetable ("Dynamic Behaviour of Electric Machinery" vs "Machines" for EE 648, "Analog CMOS IC Design" vs "CMOS Analog IC Design" for EE 651, "Physics of Transistors" with non-breaking spaces in the timetable, "Optimization Methods For Machine Learning" vs CSE "Optimization for ML" for ES 645).
- `catalog_raw.json` now has 136 records: 48 EE basket listings plus 11 more timetable rows (EE 617, 639, 644, 648, 651, 659, 662, 663, 664, 671, EE 691-VII).
- EE course plans (EE-prefixed codes from the site plus EE 6xx rows in the timetable): 25 codes. 14 have no link, 11 have links, and 7 of those returned files. Only EE 639, EE 663 and EE 664 have readable text. EE 644, EE 651, EE 659 and EE 691-VII are SharePoint shells with no text. EE 617, EE 648, EE 662 and EE 671 need a login. Log: `ee_course_plan_fetch_log.csv`. ES courses on the EE lists are covered by the CSE fetch.
- Prerequisite statement found: EE 663 says "Prerequisites: Basic UG coursework on Communication Systems (EE341) and Signals and Systems (ES244). All necessary mathematical concepts will be covered as part of the course." (the PDF text has no spaces between words). EE 639 and EE 664 have no prerequisite statement.
- Rules: 20 new `ee.` rules, so `rules.json` has 76 rules with values. EE credits are 42 coursework + 40 thesis (10 x 4-credit units) = 82. Other EE rules: Aarohan 2, Writing 4, Applications of AI 4 (course not named), electives at least 8, discipline list at least 16, PE 2 courses, at most 8 UG elective credits (5XX or below), all other courses 6XX or above, and pre-approved MOOCs allowed for electives. EE rules that differ from Adv5 carry `overrides`. The common Adv5, Adv17, Adv24 and Adv42 rules now also apply to `MTech-EE`. The CSE structure rules and `applications_of_ai_course` (CS 621) stay CSE/AI only.
- The site describes only a thesis structure for EE, so `MTech-EE` has tracks `["thesis"]`. The site calls ICDT a separate degree, "MTech (Integrated Circuit Design & Technology)". It is modelled as an `MTech-EE` stream as instructed, and the rule `ee.icdt_degree` records this.
- `clean_catalog.py` was not run in this follow-up, so `courses.json` does not yet contain EE courses.
