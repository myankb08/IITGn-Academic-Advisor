# Validation results: raw

Checks run: 10. fail: 7, pass: 2, warn: 1.

| check_id | description | requirement | target | status | n_failures | note |
|---|---|---|---|---|---|---|
| V01 | Records match the data contract schema and types (Pandera) | general: schema and types | catalog_raw.json | pass | 0 |  |
| V02 | Course codes match '<PREFIX> <NNN>[-<ROMAN>]' or 'REQ-*' | general: code format regex | catalog_raw.json | fail | 6 |  |
| V03 | Credits are integers in 1..16 (0 only where rules.json states 0; ug_background excluded) | general: value ranges (credits) | catalog_raw.json | fail | 49 | zero-credit codes allowed by rules.json: ['PE 600'] |
| V05 | Required fields are not null or empty | general: missing values | catalog_raw.json | fail | 9 |  |
| V06 | No course code appears twice (raw: within one source document) | spec: no course code appears twice | catalog_raw.json | fail | 5 |  |
| V07 | No exact duplicate records (all content fields equal, provenance ignored) | general: exact duplicates | catalog_raw.json | fail | 4 |  |
| V08 | Course titles agree with the timetable title for the same code (catches typos like 'Algrithms') | general: spelling / title consistency against timetable | titles vs timetable_rows.jsonl | fail | 5 | typo when rapidfuzz ratio >= 85 and < 100 (case-insensitive) |
| V09 | Titles have no leading/trailing whitespace, double spaces or trailing punctuation | general: text hygiene | titles | fail | 4 |  |
| V10 | No two different codes have near-duplicate titles (rapidfuzz token_sort_ratio >= 92) | general: near-duplicate titles (warning, needs human review) | titles | warn | 2 | warning only: cross-listed UG/PG or special-topics versions can share a title |
| V15 | Course credits and L-T-P agree with the timetable row where both exist | spec: course credits agree with timetable L-T-P-C | catalog_raw.json vs timetable_rows.jsonl | pass | 0 |  |

Failure examples (first 8 per check) are in results.csv, all failures in failures.json.
