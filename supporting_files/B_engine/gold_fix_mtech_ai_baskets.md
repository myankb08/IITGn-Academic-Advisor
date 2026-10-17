# Gold answer fix: MTech-AI other baskets (2026-10-18 ~01:00 IST)

Found by: hem436 and the assistant while reviewing the first round-1 labelling item (R1-Q0124), whose gold text read "Other baskets (): 0 credits earned".

Cause: `src/engine/rule_engine.py` took the "other baskets" from the student's own programme. MTech-AI has a single stream, so the list was empty and Systems/Theory basket courses were counted as plain electives.

Source rule: CSE M.Tech structure p1, "MTech in AI is deemed to be in the AI-ML stream only and should follow the corresponding curriculum", which includes at least 4 credits from the other two baskets.

Fix: `CURRICULUM_OF = {"MTech-AI": "MTech-CSE"}` and `basket_streams()`; regression test `tests/test_engine.py::test_mtech_ai_other_baskets_use_cse_streams`.

Effect: 100 of 600 gold answers changed (remaining_core 52, elective_recommendation 44, eligibility 4), all MTech-AI; no query text changed; splits unchanged. 16 test-split justifications were re-paraphrased (run log supporting_files/C_labelling/paraphrase_run_test_split_after_gold_fix.json). Round 1/2 labelling tasks were rebuilt before any labelling started.
