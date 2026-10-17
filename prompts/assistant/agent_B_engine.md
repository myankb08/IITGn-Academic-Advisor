# Agent B: prerequisite graph, deterministic rule engine, synthetic transcripts, advisory pairs

Follow `prompts/assistant/agent_common_rules.md`.

Another agent is building `data/processed/courses.json` and `data/processed/rules.json` right now. Work against the schemas in `docs/DATA_CONTRACT.md`. Until those files exist, develop with a small hand-written fixture in `tests/fixtures/` (clearly a fixture, a few courses with a prerequisite chain). Your code must load the real files by default and the fixture only in tests.

Build:
1. `src/engine/prereq_graph.py`: networkx DiGraph from courses.json, functions for missing-prerequisite codes, cycle detection, topological order, export to `data/processed/prereq_graph.json` (node-link) and a PNG plot to `supporting_files/A_collection/prereq_graph.png`.
2. `src/engine/rule_engine.py`: pure deterministic functions, no randomness:
   - `remaining_requirements(student)` -> compulsory courses missing, stream core missing, basket credit gaps (own basket, other baskets), Writing/HSS/Aarohan/AI-applications status, coursework credit gap per track, total gap to 82, below-600 credit cap usage.
   - `eligibility(student, course_code, semester_parity=None)` -> eligible bool, unmet prerequisites, already taken, offered-in-parity check if known, reason codes.
   - `recommend_electives(student, k=3)` -> ranked list of eligible, not-taken courses that close the largest gaps (own basket first, then other basket, then open electives), each with a reason code. Ties broken by course code so the output is stable.
   - `validate_transcript(student)` -> list of violations (prereq taken later or same term as dependant, duplicate course, unknown code, per-semester credit cap from rules.json, below-600 cap). Used as the Part B transcript check.
   - Every function returns a plain dict that is JSON-serialisable with sorted lists.
3. `src/engine/synth_transcripts.py`: generate `params.yaml: transcripts.n_students` students across programmes/streams/tracks with seed from params.yaml, semesters_completed 0..3, only valid course sequences (respect prerequisites, parity offering if known, credit caps). Grades from a fixed set. Students get ids `S0001`... Also deliberately keep generator able to emit invalid transcripts via a flag `--inject-violations N` for Part B corruption tests (not used for the real dataset). Write `data/processed/students.jsonl`.
4. `src/queries/make_queries.py`: build at least `queries.min_pairs` advisory pairs. At least 6 template families, at least 2 per intent (remaining_core, eligibility, elective_recommendation), each family with 2 to 4 surface templates. Gold answer = rule engine output (`gold_json`) plus a deterministic natural-language `gold_text` with a short justification built from reason codes (no LLM). Balance intents roughly evenly. Eligibility targets mix eligible and not-eligible cases. Write `data/processed/queries.jsonl`. Leave the `para_*` fields null; another step fills them.
5. Tests in `tests/test_engine.py` (pytest) covering the engine on the fixture: eligibility with unmet prereq, remaining core, recommendation stability, transcript violation detection.

If `data/processed/courses.json` and `rules.json` exist when you finish, run the full pipeline on them and report counts (students, pairs per intent/family, any transcript violations, which should be zero). If they do not exist yet, say so; the orchestrator will rerun.
