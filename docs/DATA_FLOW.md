# Data flow

How data moves from the original sources to the processed curriculum files, `data/metadata.csv`, and the later stages.
Each box is a file, each arrow is one command (`.venv/bin/python -m src.collect.<module>`).

```mermaid
flowchart TD
    subgraph sources["data/raw/sources (untouched, sha256 in source_metadata.json)"]
        PDF["Advisory PDFs<br/>Adv5, Adv17, Adv24, Adv42, ..."]
        CSE["Revised CSE MTech<br/>Course Structure 2025-26.pdf"]
        TT["Timetable, Sem-I, 2026-27.xlsx"]
    end

    PDF --> EX[extract_sources]
    CSE --> EX
    TT --> EX
    EX --> PAGES["data/raw/extracted/pages.jsonl"]
    EX --> ROWS["data/raw/extracted/timetable_rows.jsonl"]

    PAGES --> FETCH[fetch_course_plans]
    ROWS --> FETCH
    WEB(("public course plan links")) --> FETCH
    FETCH --> PLANS["data/raw/course_plans/*"]
    FETCH --> PTEXT["data/raw/extracted/course_plan_text.jsonl"]
    FETCH --> FLOG["supporting_files/A_collection/course_plan_fetch_log.csv"]

    EESITE(("EE M.Tech Google Site<br/>URL supplied by hem436")) --> EEF[fetch_ee_pages]
    ROWS --> EEF
    EEF --> EEHTML["data/raw/sources/ee_mtech_site/*.html"]
    EEF --> EEP["data/raw/extracted/ee_pages.jsonl"]
    EEF --> PLANS
    EEP --> CAT
    EEP --> RULES

    PAGES --> CAT[build_catalog]
    ROWS --> CAT
    CAT --> RAWCAT["data/raw/catalog_raw.json<br/>(defects kept)"]

    RAWCAT --> CLEAN[clean_catalog]
    PTEXT --> CLEAN
    FLOG --> CLEAN
    MAN["data/raw/prereq_manual.csv"] --> CLEAN
    CLEAN --> COURSES["data/processed/courses.json"]
    CLEAN --> CHG["supporting_files/A_collection/cleaning_changes.csv"]

    PAGES --> RULES[build_rules]
    RULES --> RJ["data/processed/rules.json"]

    sources --> META[build_metadata]
    PAGES --> META
    ROWS --> META
    PLANS --> META
    RAWCAT --> META
    COURSES --> META
    RJ --> META
    META --> MCSV["data/metadata.csv"]

    COURSES --> ENG["rule engine (src/engine)"]
    RJ --> ENG
    ENG --> STU["data/processed/students.jsonl"]
    ENG --> Q["queries (src/queries)<br/>data/processed/queries.jsonl"]
    FORMS["Google Form responses<br/>(anonymised, consent register)"] --> Q
    Q --> LAB["Label Studio<br/>data/labels/"]
```

Run order for Part A:

```
.venv/bin/python -m src.collect.extract_sources
.venv/bin/python -m src.collect.fetch_course_plans      # add --refresh to download again
.venv/bin/python -m src.collect.fetch_ee_pages          # EE site pages and EE course plans
.venv/bin/python -m src.collect.build_catalog
.venv/bin/python -m src.collect.clean_catalog
.venv/bin/python -m src.collect.build_rules
.venv/bin/python -m src.collect.build_metadata
```

Notes:

- Raw files are never edited. All fixes happen in `clean_catalog`, and each one is a row in `cleaning_changes.csv`.
- `build_rules` stores a verbatim quote for every rule and fails if the quote is not on a page of the cited PDF, so `source_page` cannot drift.
- `fetch_course_plans` reuses earlier downloads unless `--refresh` is given. Failed links are retried on every run.
