# Gold answer fix: MTech-AI other baskets (2026-10-18 ~01:00 IST)

Found by: hem436 and the assistant while reviewing the first round-1 labelling item (R1-Q0124), whose gold text read "Other baskets (): 0 credits earned".

Cause: `src/engine/rule_engine.py` took the "other baskets" from the student's own programme. MTech-AI has a single stream, so the list was empty and Systems/Theory basket courses were counted as plain electives.

Source rule: CSE M.Tech structure p1, "MTech in AI is deemed to be in the AI-ML stream only and should follow the corresponding curriculum", which includes at least 4 credits from the other two baskets.

Fix: `CURRICULUM_OF = {"MTech-AI": "MTech-CSE"}` and `basket_streams()`; regression test `tests/test_engine.py::test_mtech_ai_other_baskets_use_cse_streams`.

Effect: 100 of 600 gold answers changed (remaining_core 52, elective_recommendation 44, eligibility 4), all MTech-AI; no query text changed; splits unchanged. 16 test-split justifications were re-paraphrased (run log supporting_files/C_labelling/paraphrase_run_test_split_after_gold_fix.json). Round 1/2 labelling tasks were rebuilt before any labelling started.

## Effect on the synthetic students (found 2026-10-19 during the full dvc repro)
The student generator assigns course roles through `role_of`. With the fixed basket rule, regenerating would have
changed the transcripts of 12 of the 180 students, all MTech-AI (for example S0007 would take CS 607 and ES 627
instead of CS 616 and ES 612). Every label and the gold set were built on the original students, which still pass
all transcript checks under the fixed rules, so `synth_transcripts` now calls
`role_of(..., own_programme_baskets=True)` and reproduces them exactly; gold answers use the fixed rule.
Evidence: supporting_files/F_reproducibility/repro_check.txt.
