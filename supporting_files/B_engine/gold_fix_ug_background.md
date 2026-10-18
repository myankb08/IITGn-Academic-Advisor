# Gold answer fix: no UG background warnings for M.Tech students (2026-10-18 ~12:00 IST)

Found by: hem436, who noticed eligibility answers telling M.Tech students they lacked IITGN undergraduate courses,
for example ES 666 (ES 112, MA 101, MA 102) and EE 663 (ES 244).

Cause: under D4, course-plan background lines ("ES 112 Computing, MA 101, MA 102, or equivalent") were stored as
`recommended_background` and raised a MISSING_RECOMMENDED_BACKGROUND warning when a synthetic student's
`ug_background` lacked them. M.Tech students did their UG elsewhere, so this is wrong advice.

Decision: docs/DECISIONS.md D5 (hem436). UG-level background (level below 500) never raises a warning; only
PG-level recommended background could, and none exists in the sources. The plan evidence stays in courses.json.

Fix: `src/engine/rule_engine.py` `_missing_recommended(..., include_ug=False)`. `make_queries` picks eligibility
cases with `eligibility(..., selection_view=True)`, which still sees the old background cases, so the same 600
pairs (same students, targets and wording) are kept and only gold answers change. Tests:
`tests/test_engine.py::test_ug_background_never_warns_mtech_students`, `test_recommended_background_warning`.

Effect: 0 query texts changed; 53 gold answers changed (16 lost the background note, 37 elective recommendations
re-ranked because those courses no longer carry the warning); 9 of them in the test split, at round-1 positions
3, 8, 29 and 39 (labelling had reached position 2, so no finished annotation was affected). The 53 justifications
were re-paraphrased with the local llama.cpp backend (run log supporting_files/C_labelling/paraphrase_run_after_d5.json).
