# Data contract (Project 4, Course Advisory SLM, Assignment 1)

Scope: IIT Gandhinagar M.Tech programmes from the CS discipline only.
Programmes: `MTech-CSE` (streams AI/ML, Systems, Theory) and `MTech-AI` (AI/ML stream only).
Tracks: `thesis`, `coursework`.

All paths are relative to the repo root. All randomness reads seeds from `params.yaml`.
Course codes are normalised as `<PREFIX> <NUMBER>[-<SUFFIX>]`, for example `CS 610`, `ES 678`, `CS 691-XIV`.
Section markers such as `(E)`, `(H)`, `(A)` are stripped during cleaning, never during raw extraction.

## Raw layer (`data/raw/`)
- `sources/` original PDFs and xlsx, untouched. `sources/source_metadata.json` has their sha256.
- `course_plans/` downloaded course plan files (one per course code), untouched.
- `extracted/pages.jsonl` one row per PDF page: `file, page, text, tables, sha256_file`.
- `extracted/timetable_rows.jsonl` one row per timetable row: `sheet, row, course_number_raw, title, L, T, P, C, instructors, course_plan_url, remarks`.
- `catalog_raw.json` course records as extracted, with defects kept (duplicates, typos, float credits, section suffixes).

## Processed layer (`data/processed/`)
### `courses.json` (list)
```
code            str   "CS 610"
title           str
credits         int
ltp             [L, T, P] floats or null
level           int   first digit * 100 (600 for CS 610)
prerequisites   [str] codes, may be empty
prereq_source   "course_plan" | "manual" | "none_stated"
prereq_evidence str   quoted line from the course plan, or the reason for a manual entry
category        "compulsory" | "stream_core" | "basket" | "open_elective" | "requirement"
streams         [str] streams where this is core or in the basket, e.g. ["AI/ML"]
programmes      [str] ["MTech-CSE", "MTech-AI"]
offered         "odd" | "even" | "both" | null
source_doc      str   file name under data/raw/sources or course_plans
source_page     int   1-based page, or null for xlsx (then source_row is set)
source_row      int | null
source_url      str | null
record_sha256   str   sha256 of the canonical JSON of this record without this field
```
### `rules.json`
Degree rules per programme and track, every number with `source_doc` and `source_page`.
Must hold: total_min_credits (82), coursework/thesis/project minimums per track, Aarohan (2),
Writing (4), HSS (4), compulsory courses (CS 610, CS 621), stream core lists, own-basket min (4),
other-basket min (4), discipline-specified min (16), electives min (8), cap on <600 level credits,
max credits per semester if stated, pass/fail rules if relevant.

### `students.jsonl` (synthetic, made only by the rule engine)
```
student_id, programme, stream, track, admit_year, semesters_completed,
transcript: [{code, semester, credits, grade}], seed
```
### `queries.jsonl` (advisory pairs)
```
query_id, student_id, template_id, template_family, intent ("remaining_core" | "eligibility" | "elective_recommendation"),
target_course (eligibility only), query_text (template render),
gold_json (rule engine output), gold_text (deterministic NL answer + justification),
para_query, para_justification, para_model, para_prompt_id,
augmentation (null | "paraphrase" | "typo_abbrev" | "transcript_reorder" | "transcript_length"), parent_query_id
```

## Labels (`data/labels/`)
Label levels, filled in this fixed order: 1) `decision` accept | edit | reject, 2) `error_category`, 3) `edit_text`.
Error categories: `none`, `hallucinated_course`, `wrong_fact_or_policy`, `meaning_drift`, `incomplete_justification`, `fluency`, `ambiguous_query`.

## Metadata (`data/metadata.csv`)
One row per sample in raw and processed layers:
`sample_id, layer, artifact, source, source_doc, source_page, source_url, collected_at_utc, collector, tool, tool_version, content_sha256`.
