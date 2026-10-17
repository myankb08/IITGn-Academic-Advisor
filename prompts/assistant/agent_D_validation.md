# Agent D: Part B data validation

Follow `prompts/assistant/agent_common_rules.md`.

Build an automated validation suite with Pandera (dataframe checks) and pytest (graph and engine checks), at least 14 named checks, each with an id (V01..), a one-line description, and the requirement it covers. Required by the project spec: every prerequisite code exists; the prerequisite graph has no cycles; credit totals match the handbook (e.g. sum of minimums per track equals rules total 82, basket minimums, compulsory credits, course credits agree with the timetable L-T-P-C where both exist); no course code appears twice; synthetic transcripts pass the rule engine (no prerequisite violations, credit caps respected, below-600 cap); no student or template appears in both train and test (write this check now against `data/splits/*.csv` manifests with columns query_id, student_id, template_family, programme, split; skip with a clear message if splits do not exist yet). Also general ones: schema and types, code format regex, value ranges (credits 1..16, level), missing values, exact duplicates, near-duplicate titles (rapidfuzz, threshold documented), label validity (intent, error categories, decisions in allowed sets), gold answers recomputed by the rule engine equal stored gold_json, query text contains no leaked gold answer marker.

Files:
- `src/validate/checks.py`: the checks as functions returning a result row (check_id, description, target, passed, n_failures, examples).
- `src/validate/run_validation.py --stage {raw,processed,corrupted} --out supporting_files/B_validation/<stage>/`: runs every applicable check, writes `results.csv`, `results.md`, and failure examples JSON. Exit non-zero on any failure unless `--report-only`.
  - raw: run on `data/raw/catalog_raw.json` (expect real failures: duplicate CS 618, typo "Algrithms" via a spelling or near-duplicate-title check against the timetable title, float credits, section suffixes in codes, etc.).
  - processed: courses.json, rules.json, students.jsonl, queries.jsonl, splits if present (expect all pass).
  - corrupted: `src/validate/corrupt.py` makes `data/interim/corrupted/` copies with injected faults: a prerequisite cycle, an unknown prerequisite code, a duplicate course code, a wrong credit total, a transcript with a prereq violation and credit cap breach (use `synth_transcripts --inject-violations` output in data/interim if present), a gold answer that disagrees with the engine, a student in both train and test. Seeded. Show every injected fault is caught.
- `tests/test_validation.py`: pytest wrapper so `pytest -q` runs processed checks and asserts corrupted checks fail.
- `supporting_files/B_validation/before_after.md`: table of check, failures on raw, fix applied (point to rows in supporting_files/A_collection/cleaning_changes.csv), failures after. Build it from the results files with a script, not by hand.

Note: the rule engine agent is changing courses.json schema now (`offered_terms`, `offered_parity`, `recommended_background`, ug_background nodes, edge types). Read the latest docs/DATA_CONTRACT.md before finishing, rerun all stages at the end, and report the numbers.
