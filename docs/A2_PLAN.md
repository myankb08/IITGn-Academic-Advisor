# Assignment 2 plan (Project 4: Course Advisory SLM)

Deadline: 15 Nov 2026, 23:59. Start: 10 Nov 2026 (5 days). Branch `a2` from tag `a1-final`; final tag `a2-final`.

## Fixed decisions (set before any gold evaluation)

| # | decision |
|---|---|
| D1 | Model: Qwen2.5-1.5B-Instruct (A1 base model) with LoRA, fp16 on RTX 2080 Ti. Qwen2.5-0.5B-Instruct is a search candidate for the size/latency trade-off. |
| D2 | Prompt: the A1 retrieval prompt `base_model_answer_v1` (programme course list, rules, student, term, query). Output: one JSON line in the A1 schema plus a `justification` string. |
| D3 | Training target: projected `gold_json` and the rule-engine `gold_text` as justification. |
| D4 | Model selection on val only. Test, gold, holdout and shifted data are used only by `src/eval/evaluate.py` for final reports and gate checks. Every gold run goes into `TEST_SET_LOG.md`. |
| D5 | Gold errata: when scoring, "workshop" is replaced with "coursework" in `audited_query` of the 5 listed items. The file is not changed. |
| D6 | Shifted data: `data/sft/shifted.jsonl` = `programme_holdout` (MTech-ICDT, 288 rows) labelled again under the v2 curriculum. The 19 Google Forms questions are unlabelled drift traffic only: most are outside the three intents and their free-text course names cannot be mapped to codes without guessing (changed 2026-11-10, before any evaluation on these files). |
| D7 | Retraining pool: new ICDT students and pairs from the rule engine with a new seed, plus a curriculum update. The rule engine is the simulated annotator. The pool never overlaps evaluation data. |
| D8 | Gate (in `params_a2.yaml`): promote only if shifted F1 improves (paired bootstrap, p < 0.05) and gold exact match drops by at most 2 points. |
| D9 | Serving: LoRA merged into the base (fp16 safetensors, `src/serve/export_model.py`), every `nn.Linear` quantised to int8 with PyTorch dynamic quantisation at load, greedy decoding on CPU; FastAPI + Gradio in one container. Changed 2026-11-10 from GGUF: the GGUF converter is downloaded code we chose not to run, and GGUF is not required. Measured on the debug model: steady RAM 3.7 GB, load peak under an 8 GB container limit, image 4.4 GB. |

| D10 | Final model (2026-11-11, val only): Qwen2.5-1.5B, LoRA rank 32, lr 5e-4, 3 epochs, `base_aug` (run cb7c02b778d342e2b5a30f163ac8ee74, val set F1 0.912, EM 0.814), registered as advisor v1. The 3B run had the best val score (F1 0.954, EM 0.836) but about 2x the CPU latency, RAM and image size; the 1.5B run is within 4.2 F1 / 2.2 EM points. Chosen by both members before any test, gold or shifted evaluation of either model. |
| D11 | Retraining recipe (2026-11-11, before round r2): round r1 (lr 5e-4 = the production run's, 300 replay rows) lost 0.143 val exact match (0.814 to 0.671) and 0.104 val set F1, i.e. it forgot the original curriculum. From this val result alone, round r2 uses lr 1e-4 and 600 replay rows; budget, epochs and the gate are unchanged. Gold results of r1 were not used for this choice. |
| D12 | Retraining recipe and val guard (2026-11-11, before round r3): r1 and r2 both lost val exact match (0.814 to 0.671 and to 0.771), so continued training forgets the original curriculum. Round r3 trains a new adapter from the base model on all 1,541 train rows plus the 100 revealed pool pairs, with the production run's settings (rank 32, lr 5e-4, 3 epochs, seed 301). From r3 on, a candidate whose val exact match drops more than 0.02 is rejected before any gold evaluation. Gate thresholds (D8) are unchanged. |
| D13 | Final retraining round r4 (2026-11-11, before any of its runs): r3 (from scratch, seed 301) failed the val guard while a rerun of the production recipe reproduced val EM 0.814 exactly, so data order may matter. (a) Seed check: the production recipe with seeds 311 and 312 on the original train rows, val only, not registered. (b) r4: candidates trained on the r3 data (all train rows + the same 100 revealed pool pairs) with seeds 301 (= r3), 311 and 312; the one with the highest val exact match goes through the unchanged val guard and gate (D8, D12). If it fails, no model is promoted and the report says so. No further rounds. |
| D14 | D6 label fix and retraining (2026-11-11, decided by hem436 and myankb08 before any run on the new labels): the test error analysis showed 22 of 32 eligibility errors are A1 `ALREADY_TAKEN` labels, which contradict Academic Advisory 24 B.1 (a passed course may be repeated to improve the grade). A2 labels now follow `src/model/d6.py` (eligible for a repeat when nothing else blocks it, warning `REPEAT_FOR_GRADE_IMPROVEMENT`; 74 train, 21 val, 25 test, 12 holdout/shifted, 6 gold rows). `data/gold/gold_test.jsonl` is unchanged; `data/sft/gold.jsonl` carries the D6 labels and `data/sft/gold_a1.jsonl` the original ones, and both are reported. The selected configuration (D10) is trained again on the new labels without a new search; baselines and earlier models are rescored from their saved answers. Part E (replay, retraining with the unchanged gate D8 and val guard D12) is redone with the new production model; the rounds on v1 stay as history. Earlier results on A1 labels are kept in `supporting_files/C_eval_a1_labels/`. |
| D15 | Production after D14 (2026-11-11, before the D6 model's results): both models are scored on val with D6 labels by `src/eval/evaluate.py` (v1 rescored: set F1 0.926, exact match 0.821). The D6 model becomes production if its val exact match is at least 0.821; otherwise v1 stays production. Test, gold and shifted are evaluated for both but do not enter the choice. |
| D16 | Part E under D6 labels (2026-11-11, after D15 kept v1 as production, before any of these runs): one round `d6r1`. The A1 active-learning score now uses the D6 pool labels (same pool, same budget 100). Three candidates are trained from scratch on all train rows + the 100 revealed rows with the production settings and seeds 301, 311 and 312; the one with the highest val exact match (D6 labels, `src/eval/evaluate.py`) goes on. The val guard now compares `evaluate.py` val scores of candidate and production on the same labels (the training-time val score of v1 used A1 labels). Gate D8 unchanged, scored on D6 labels (`gold` = `data/sft/gold.jsonl`). If the candidate fails, nothing is promoted and the report says so. |
| D17 | Deployed model (2026-11-11, after the d6r1 gate promoted v10): v10 stays production as the gate decided. Its test evaluation, run afterwards for the model card, shows v10 worse than v1 on the old-curriculum test set (set F1 0.818 vs 0.924, paired p < 0.001; eligibility and electives), while far better on the shifted data (0.829 vs 0.691). The gate (shifted set F1, gold exact match on 76 items) and the val guard (overall val exact match) did not see the per-question-type val drops (eligibility -0.105). No model choice is made on test; the regression is reported, and a stronger gate (per-question-type val checks, set F1 as well as exact match) is proposed as future work. |

## Systems compared (Part A)

1. `trivial`: constant answer (empty sets, eligible = true, 3 most frequent train recommendations).
2. `zero_shot`: unadapted Qwen2.5-1.5B, no curriculum in the prompt.
3. `few_shot`: unadapted, 3 train examples of the same intent, no curriculum.
4. `retrieval`: unadapted, A1 prompt with the curriculum JSON (A1 base model setup).
5. `lora`: proposed system, LoRA on the retrieval prompt. Rule-engine check before display.

Data mix runs: base 336, base + augmented 1205, AL-selected 100 vs random 100.

## Files

| file | job |
|---|---|
| `params_a2.yaml` | seeds, search grid, replay schedule, drift thresholds, gate tolerance |
| `src/model/build_sft.py` | prompts and targets for each split and data mix |
| `src/model/train_lora.py` | one LoRA run, logged to MLflow |
| `src/model/predict.py` | predictions for any system (HF on GPU, GGUF on CPU) |
| `src/eval/evaluate.py` | metrics, bootstrap CIs, paired tests, slices, for one registered version and split |
| `src/serve/app.py` | REST + Gradio UI, rule check, request log, monitoring panel, `validate` entry |
| `src/monitor/replay.py` | replay with gradual shift, drift signals, alerts |
| `src/retrain/run.py` | AL selection, label reveal, validation, retrain, eval, gate, promote or roll back |
| `Dockerfile`, `.github/workflows/ci.yml` | image and CI |

## Schedule

| day | hem436 | myankb08 |
|---|---|---|
| 10 Nov | setup, SFT data, baselines on val, LoRA script | forms name-to-code map, retraining pool, Docker install |
| 11 Nov | search (about 18 runs), register model, final eval with CIs | GGUF conversion, Dockerfile, API and UI |
| 12 Nov | slices, robustness, 20+ error sheet, model card | rate 50 justifications (both members), CI, load test |
| 13 Nov | replay, drift thresholds, retrain pipeline and gate | offline checks, DOCKER.md, README, ENVIRONMENT.md |
| 14 Nov | report and evidence index | slides, 3-minute recording, clean-machine test |
| 15 Nov | final zip, unzip and reproduce, submit | |

## Risks

- Gold set: one tuning step on gold results invalidates the results that depend on it.
- CPU validation time: keep outputs short and measure early. Use a fixed documented subset in the UI if needed.
- The A1 proposal model is not in this folder; the report must explain any change from it.
