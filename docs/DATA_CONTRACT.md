# Data contract (Project 4, Course Advisory SLM, Assignment 1)

Scope: IIT Gandhinagar M.Tech programmes from the CS and EE disciplines.
Programmes: `MTech-CSE` (streams AI/ML, Systems, Theory), `MTech-AI` (AI/ML stream only) and
`MTech-EE` (streams `Power Engineering & Control Systems`, `Signal Processing & Machine Learning`,
`Integrated Circuit Design & Technology`; thesis track only, as described on the EE M.Tech site).
Stream names are unique across programmes, so a course's `streams` list also tells which programmes use it as a basket.
Tracks: `thesis`, `coursework` (`thesis` only for `MTech-EE`).

All paths are relative to the repo root. All randomness reads seeds from `params.yaml`.
Course codes are normalised as `<PREFIX> <NUMBER>[-<SUFFIX>]`, for example `CS 610`, `ES 678`, `CS 691-XIV`.
Section markers such as `(E)`, `(H)`, `(A)` are stripped during cleaning, never during raw extraction.

## Raw layer (`data/raw/`)
- `sources/` original PDFs and xlsx, untouched. `sources/source_metadata.json` has their sha256.
- `sources/ee_mtech_site/<slug>.html` raw HTML of the EE M.Tech Google Site (home and three specialisation pages), untouched.
- `extracted/ee_pages.jsonl` one row per `<h1>` section of an EE site page: `file, section, text`.
- `extracted/ee_course_plan_text.jsonl` same shape as `course_plan_text.jsonl`, for EE-prefixed courses.
- `course_plans/` downloaded course plan files (one per course code), untouched. File name is the code with the space replaced by `_`, for example `CS_619.txt`, `ES_616.pdf`.
- `extracted/course_plan_text.jsonl` one row per plan: `code, file, format, source_url, text, extractor, sha256_file, collector, method`.
- `course_plans_manual/<CODE with space as _>.(pdf|docx|txt|html)` plans downloaded by hem436 with an IITGN login; ingested on every run of `fetch_course_plans` (collector `hem436`, method "manual download with IITGN login") and preferred over a fetched file.
- `prereq_manual.csv` manual prerequisite decisions: `code, prerequisites (; separated), reason, evidence, decided_by, decided_at`.
- `extracted/pages.jsonl` one row per PDF page: `file, page, text, tables, sha256_file`.
- `extracted/timetable_rows.jsonl` one row per timetable row: `sheet, row, course_number_raw, title, L, T, P, C, instructors, course_plan_url, remarks`.
- `catalog_raw.json` course records as extracted, with defects kept (duplicates, typos, float credits, section suffixes).
  Each record has `programmes` (null for timetable rows) and `source_section` (set for EE site records, else null).

## Processed layer (`data/processed/`)
### `courses.json` (list)
```
code            str   "CS 610"
title           str | null   (null only for ug_background codes with no title in any source)
credits         int | null   (null only for ug_background: never counted for credit)
credits_source  str   "timetable", "rules_doc: <doc> p<n>" or "default: <doc> p<n> (...)"
ltp             [L, T, P] floats or null
level           int   first digit * 100 (600 for CS 610), null for REQ-* placeholders
prerequisites   [str] codes, may be empty
prereq_source   "course_plan" | "manual" | "none_stated"
prereq_evidence str   quoted line from the course plan, or the reason for a manual entry
recommended_background [{any_of: [codes], evidence, source_doc}]  codes a plan names as optional, recommended,
                "or equivalent", background, or at UG level (below 600); "/" or "or" alternatives share one entry.
                Missing background only warns, it never blocks (docs/DECISIONS.md D4)
category        "compulsory" | "stream_core" | "basket" | "open_elective" | "requirement" | "ug_background"
streams         [str] streams where this is core or in the basket, e.g. ["AI/ML"]; empty for ICDT-only courses
programmes      [str] union of the programmes whose structure lists the course (e.g. ["MTech-CSE", "MTech-AI"]).
                Empty for open electives found only in the timetable and for ug_background codes
offered_parity  "odd" | "even" | null   only where a document states it (CS 610 odd, CS 621 even, CSE structure p1)
offered_terms   [str] terms whose timetable lists the course, e.g. ["2026-27 Sem-I"]
offering_evidence str | null  where the parity or term comes from
source_doc      str   file name under data/raw/sources or course_plans
source_page     int   1-based page, or null for xlsx (then source_row is set) or HTML (then source_section is set)
source_section  str | null  heading of the HTML section (e.g. "Curriculum") for EE site sources
source_row      int | null
source_url      str | null
other_sources   [{source_doc, source_page, source_row}] secondary provenance (e.g. timetable row of a structure course)
record_sha256   str   sha256 of the canonical JSON of this record without this field
```
`ug_background` records are UG codes referenced by a plan (e.g. ES 331, MA 202, EE 341) that are not M.Tech courses; they exist so every referenced code resolves. `level` comes from the code.
Requirement placeholders (category `requirement`, no timetable code): `REQ-HSS`, `REQ-THESIS` (4-credit thesis unit), `REQ-PROJECT`.
Requirements with real codes: `FP 601` Aarohan, `FP 602` Writing, `PE 600` Physical Education, `CS 621` Applications of AI.

### `rules.json`
Degree rules per programme and track, every number with `source_doc` and `source_page` (or `source_section` for HTML sources).
Shape: `{programmes, precedence, placeholder_codes, requirement_codes, applications_of_ai_by_programme, rules: {rule_id: {rule_id, value, unit, applies_to: {programmes, tracks, admitted}, ..., source_doc, source_page, source_section, quote, record_sha256}}}`.
EE-department rules use the prefix `ee.` and apply to `MTech-EE` and `MTech-ICDT`. A rule with `overrides: <common rule_id>` replaces that common rule for those programmes; an `ee.<name>` rule without it replaces the common rule `<name>`. The 42 + 40 split is thesis-track only; the other EE rules apply to both tracks (docs/DECISIONS.md D3).
Discipline lists are `ee.discipline_list.<stream>` for MTech-EE and `ee.discipline_list.MTech-ICDT` (value = codes, min 16 credits, list courses may also count as electives).
`programmes.<name>` has `department` (CS | EE), `streams` (empty for MTech-ICDT) and `tracks` (both, D3).
Track-specific ids use a suffix, e.g. `coursework_min_credits.thesis`. Rules absent from the sources have `value: null, not_stated: true`.
Must hold: total_min_credits (82), coursework/thesis/project minimums per track, Aarohan (2),
Writing (4), HSS (4), compulsory courses (CS 610, CS 621), stream core lists, own-basket min (4),
other-basket min (4), discipline-specified min (16), electives min (8), cap on <600 level credits,
max credits per semester if stated, pass/fail rules if relevant.

### `students.jsonl` (synthetic, made only by the rule engine)
```
student_id, programme, stream (null for MTech-ICDT), track, admit_year, semesters_completed,
ug_background: [codes from ug_background records, completed in UG or equivalent],
transcript: [{code, semester, credits, grade, mooc (optional, true for an approved MOOC)}], seed
```
Programme semester k of a student maps to term `term_label(admit_year, k)`, e.g. 2025 and k = 3 give `2026-27 Sem-I`.
Admit years are set so every student's upcoming term (k = semesters_completed + 1) is in 2026-27:
0 or 2 semesters done gives Sem-I (timetable known), 1 or 3 gives Sem-II (no timetable yet).
### `queries.jsonl` (advisory pairs)
```
query_id, student_id, template_id, template_family, intent ("remaining_core" | "eligibility" | "elective_recommendation"),
target_course (eligibility only), query_text (template render),
gold_json (rule engine output), gold_text (deterministic NL answer + justification),
para_query, para_justification, para_model, para_prompt_id,
augmentation (null | "paraphrase" | "typo_abbrev" | "transcript_reorder" | "transcript_length"), parent_query_id
```

### Rule engine outputs (`src/engine/`)
- `prereq_graph.json` networkx node-link data (`nodes`, `links`), edge `prerequisite -> course` with `type` `hard` (from `prerequisites`) or `recommended` (from `recommended_background`), plus `evidence`. Nodes carry `title, category, level, in_catalog`.
- Rules are applied per programme: common rules, then the programme's overrides from rules.json. For EE and ICDT the own basket is the discipline list (min 16), there is no stream core or other-basket minimum, the below-600 cap is 8 credits instead of 2 courses, and approved MOOCs count as electives (CSE/AI: "no online courses count"). When coursework min + thesis min equals the total (EE thesis track, 42 + 40 = 82), Aarohan counts inside coursework.
- The engine reads rule numbers from `rules.json` records `rules[<rule_id>].value` (per-track ids end in `.thesis` or `.coursework`), plus `requirement_codes` and `applications_of_ai_course`. If that shape is missing it matches keys by name. A rule it cannot find falls back to the value printed in Adv5 or the CSE course structure, with that document and page. What was used is written to `supporting_files/B_engine/transcripts_summary.json` under `rules_used`.
- Requirement entries are recognised by `category: requirement` plus the title or code (Writing, Aarohan, Physical Education, thesis, project, HSS). The Applications of AI course is the course titled "Ethics of AI" (Adv5 page 2).
- Transcript grades: courses `A, A-, B, B-, C, C-`, thesis and project units `A, B, C`, Aarohan and PE `P`. `F, U, NP, I, W` count as not passed. Thesis, project and PE codes may repeat; the entry's credits are the units taken that term.
- `gold_json` by intent: `remaining_core` is `remaining_requirements()` (missing compulsory and stream core codes, `own_basket`, `other_basket`, `discipline_specified`, `electives`, `coursework`, `thesis`, `project`, `total` as `{earned, min, gap}`, `requirements` status per Writing/Aarohan/PE/HSS/AI applications, `below_600` usage, `reason_codes`). `eligibility` is `eligibility(student, code, term=None)` for the student's upcoming term (`eligible, already_taken, prerequisites, unmet_prerequisites, missing_recommended, offered_parity, offered_terms, term, semester_parity, role, reason_codes, warnings, sources`). Blocking reasons: `ALREADY_TAKEN, PREREQ_UNMET, NOT_OFFERED_NEXT_TERM` (term has a timetable and the course is not on it), `NOT_OFFERED_IN_PARITY` (stated parity only), `UNKNOWN_COURSE, NOT_MTECH_COURSE`. Warnings (still eligible): `MISSING_RECOMMENDED_BACKGROUND, NOT_COUNTED_BELOW_600_CAP, OTHER_STREAM_CORE_AS_ELECTIVE, OUTSIDE_PROGRAMME_LIST, OFFERING_UNKNOWN`. `sources` maps each code to its citation. Unknown parity never blocks. `elective_recommendation` is `recommend_electives(student, k=3, term=None)` (`term, recommendations: [{rank, course, title, credits, role, reason_code, credits_toward_gap, below_600, warnings, prerequisites}]`, `gaps_before`). To recompute a stored answer pass `gold_json["term"]`, not `semester_parity`.
- `data/interim/students_corrupted.jsonl` (Part B tests only, made with `--inject-violations N`): same fields as students.jsonl plus `injected_violation`, one of `DUPLICATE_COURSE, PREREQ_SAME_OR_LATER_TERM, UNKNOWN_CODE, NOT_OFFERED_IN_PARITY, NOT_OFFERED_IN_TERM, SEMESTER_CREDIT_CAP` (only when a cap is stated), `CREDIT_MISMATCH`. `validate_transcript` also reports `PROGRAMME_STREAM_MISMATCH, PROGRAMME_TRACK_MISMATCH, NOT_MTECH_COURSE, UNKNOWN_BACKGROUND_CODE, MOOC_NOT_COUNTED, BELOW_600_CAP, SEMESTER_OUT_OF_RANGE, PREREQ_MISSING`.

## Labels (`data/labels/`)
Label levels, filled in this fixed order: 1) `decision` accept | edit | reject, 2) `error_category`, 3) `edit_text`.
Error categories: `none`, `hallucinated_course`, `wrong_fact_or_policy`, `meaning_drift`, `incomplete_justification`, `fluency`, `ambiguous_query`.

Per round N (1 or 2):
- `roundN/tasks.json` Label Studio import list, each `{"data": {item_id, query_id, round, guidelines_version, position, student_summary, template_query, para_query, gold_text, para_justification}}`. `item_id` is `R<N>-<query_id>`.
- `roundN/manifest.csv` `position, item_id, query_id, intent, round, guidelines_version, annotators, seed`.
- `roundN/export_A1.json`, `roundN/export_A2.json` raw Label Studio JSON exports, never edited.
- `roundN/adjudication.csv` filled by a human: `item_id, final_decision, final_category, final_edit, decided_by`.

`audited.jsonl` (one row per audited item):
```
item_id, query_id, round, guidelines_version, para_query, para_justification,
A1: {decision, error_category, edit_text}, A2: {decision, error_category, edit_text},
final_decision, final_category, final_edit (str | null), decided_by ("agreement" or the adjudicator)
```

## Forms (`data/raw/forms/`, `data/consent_register.csv`)
- `responses_raw.csv` Google Forms CSV download, untouched.
- `responses_anonymised.jsonl` consenting rows only: `response_id (R001..), form_version, programme, stream, track, semester, courses_completed, question, question_kind`. No timestamp, emails and phone numbers in free text replaced.
- `consent_register.csv` one row per response: `response_id, consent_given, consent_statement_version, form_version, included_in_dataset, reason`.

## Metadata (`data/metadata.csv`)
One row per sample in raw and processed layers:
`sample_id, layer, artifact, source, source_doc, source_page, source_url, collected_at_utc, collector, tool, tool_version, content_sha256`.

## Validation (Part B, `src/validate/`)
- `data/interim/corrupted/` (made by `src.validate.corrupt`, seed `seeds.validation_corruption`): copies of `courses.json`, `rules.json`, `students.jsonl`, `queries.jsonl`, `splits/*.csv`, `labels/audited.jsonl` with injected faults, plus `faults.json`: `{seed, faults: [{fault_id, description, check_id, match}], not_injected: [{fault, reason}]}`. A fault counts as caught when its check fails and every `match` token appears in that check's failures.
- `supporting_files/B_validation/<stage>/` for stage `raw | processed | corrupted`: `results.csv` and `results.md` with `check_id, description, requirement, target, status (pass | fail | warn | skip), passed, n_failures, examples, note`, `failures.json` (all failures per check), and for `corrupted` also `faults_caught.json`. `before_after.md` is built from these by `src.validate.before_after`.
