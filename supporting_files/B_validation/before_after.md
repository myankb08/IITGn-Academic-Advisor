# Before and after cleaning

Built by `src/validate/before_after.py` from `raw/results.csv`, `processed/results.csv` and `supporting_files/A_collection/cleaning_changes.csv` (line numbers count the header as line 1). Raw checks run on `data/raw/catalog_raw.json`, after checks on `data/processed/courses.json`.

| check | description | failures on raw | fix applied (cleaning_changes.csv lines) | status after | failures after |
|---|---|---|---|---|---|
| V01 | Records match the data contract schema and types (Pandera) | 0 (pass) | - | pass | 0 |
| V02 | Course codes match '<PREFIX> <NNN>[-<ROMAN>]' or 'REQ-*' | 6 (fail) | 6 rows (code, record): 2, 3, 4, 5, 6, 7 | pass | 0 |
| V03 | Credits are integers in 1..16 (0 only where rules.json states 0; ug_background excluded) | 49 (fail) | 52 rows (credits, record): 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17 ... | pass | 0 |
| V05 | Required fields are not null or empty | 9 (fail) | 3 rows (code): 2, 3, 4 | pass | 0 |
| V06 | No course code appears twice (raw: within one source document) | 5 (fail) | 7 rows (record): 5, 6, 7, 8, 9, 10, 20 | pass | 0 |
| V07 | No exact duplicate records (all content fields equal, provenance ignored) | 4 (fail) | 4 rows (record): 8, 9, 10, 20 | pass | 0 |
| V08 | Course titles agree with the timetable title for the same code (catches typos like 'Algrithms') | 5 (fail) | 5 rows (title): 16, 18, 32, 34, 64 | pass | 0 |
| V09 | Titles have no leading/trailing whitespace, double spaces or trailing punctuation | 4 (fail) | 4 rows (title): 22, 46, 47, 62 | pass | 0 |
| V10 | No two different codes have near-duplicate titles (rapidfuzz token_sort_ratio >= 92) | 2 (warn) | none logged | warn | 2 |
| V15 | Course credits and L-T-P agree with the timetable row where both exist | 0 (pass) | - | pass | 0 |

V01 checks a different schema in each layer (raw extraction format vs the processed contract), so its two columns are not a before/after pair of the same rule.
