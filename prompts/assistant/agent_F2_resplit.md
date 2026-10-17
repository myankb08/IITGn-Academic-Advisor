# Agent F, follow-up: no dropped rows, bigger test split

Follow `prompts/assistant/agent_common_rules.md`. You may edit `src/queries/make_queries.py` (rendering only, not gold logic), `src/split/*`, `params.yaml`, `dvc.yaml`, and `src/validate/checks.py` (V25 only).

Problem: make_splits drops 121 of 402 pairs because their surface template does not match their split, leaving test with 25 pairs.

Changes:
1. Surface templates are wording only; gold depends on (student, intent, target). So do not drop rows: assign students to splits first (seeded, stratified by programme, ICDT to programme_holdout), then render each pair's query_text with a template allowed in its split: test rows use the held-out template of their family, train/val rows use the other templates (seeded choice). Cleanest: move student-to-split assignment into a small module used by make_queries before rendering (e.g. `src/split/assign_students.py` writing `data/splits/student_assignment.csv`), and make make_splits only write manifests and check invariants. Update dvc.yaml stage order and deps (assign_students -> make_queries -> make_splits -> paraphrase...). Record in the split summary that zero rows were dropped.
2. Size: set `queries.min_pairs: 600` and `splits` to train 0.65 / val 0.15 / test 0.20 by student, so test has roughly 100 pairs with every intent at least 25 and eligibility balanced eligible/not eligible. ICDT stays the programme holdout. Keep intents balanced overall. Increase `transcripts.n_students` if needed for enough distinct students (and say so).
3. Labelling sample: with this, both rounds (40 + 40) come from the test split only, stratified by intent; the gold test set is the audited test items. Update to_labelstudio.py, LABELLING_PROTOCOL.md sampling note and HANDOFF_A2.md accordingly.
4. V25: skip the programme comparison for split == "shifted" (the real forms share programmes with train by nature); still check no query/text overlap.
5. Rerun: synth_transcripts (if changed), assign_students, make_queries, make_splits, validate processed, pytest, build_metadata, handoff. Do not run the LLM stages. Report the new counts per split x intent x programme and eligible/not in test.
