# Labelling protocol

This file records how the paraphrased advisory pairs were audited by humans. Items marked TODO need facts that only
the annotators can supply. Everything else is fixed by the code and config in this repo.

## 1. Who labelled what
| Annotator ID | Person (kept private, initials only) | Round 1 items | Round 2 items | Adjudication role |
|---|---|---|---|---|
| A1 | SMH | all 40 (overlapping) | all 40 (overlapping) | TODO |
| A2 | MSB | all 40 (overlapping) | all 40 (overlapping) | TODO |

Both annotators label the same 40 items in each round, so every item has two independent labels.
Round 1 and round 2 item sets are disjoint. The item lists are in `data/labels/round{1,2}/manifest.csv`.

## 2. Tools and versions
- Label Studio: 1.23.2 (pip package `label-studio==1.23.2`), installed in a separate venv `.venv-labelstudio` (Python 3.10).
- Task files: `src/queries/to_labelstudio.py`. Agreement: `src/queries/agreement.py`. Merge: `src/queries/adjudicate.py`.
- Analysis Python: `.venv` (scikit-learn, pandas, matplotlib, versions in requirements.txt).
- Machine(s) used by each annotator: A1 on their own Ubuntu 22.04 laptop, Label Studio served locally on port 8095 (8080 was held by another local process). A2: TODO.

## 3. Labelling config per round
| Round | Config file | Notes |
|---|---|---|
| 1 | `labelstudio/config_v1.xml` | decision (Choices), error_category (Choices), edit_text (TextArea, shown only when decision = edit) |
| 2 | `labelstudio/config_v1.xml` | same label set unless round 1 shows a category is missing; if it changes, add `config_v2.xml` and note it here (TODO confirm) |

## 4. Guideline version per round
| Round | Guidelines | Status |
|---|---|---|
| 1 | `labelstudio/guidelines_v1.md` | final |
| 2 | `labelstudio/guidelines_v2.md` | to be revised after round 1, list each change and the round-1 disagreement behind it (TODO) |

## 5. Order of label levels and rationale
Fixed order, top to bottom in the interface: 1) decision accept | edit | reject, 2) error category, 3) edit text
(required when decision = edit). The decision is the main outcome and the first agreement measure, so it is chosen
before the category list can steer it. The edit is written last, after the problem has been named. The categories
are listed in `docs/DATA_CONTRACT.md`.

## 6. Order of items and seed
Items are sampled from `data/processed/queries_para.jsonl` (original queries with both paraphrase fields filled),
stratified by intent with proportional allocation, disjoint between rounds. Both rounds come from the test split only
(`data/splits/test.csv`, 102 pairs, see HANDOFF_A2.md), so the audited items are the gold test set. The manifest
records each item's split. Sampling and the within-round order both
use `seeds.annotation_order` = 208 from `params.yaml`. Both annotators see the same order, given by the `position`
column of the manifest. In Label Studio set Settings > Annotation > Task sampling to **Sequential** so this order
is kept.

## 7. What annotators could see
Student summary, template query, paraphrased query, rule-engine gold answer and paraphrased justification. They
could not see the other annotator's labels, any model prediction of the label, or the agreement numbers until both
exports of a round were saved. Each annotator used a separate Label Studio project (or separate account) TODO confirm.

## 8. Disagreement resolution
1. After both exports of a round are saved, run `.venv/bin/python -m src.queries.agreement --round N`.
2. `supporting_files/C_labelling/roundN/disagreements.csv` lists every item where decision or category differ,
   with both labels and both edits. Items where both chose edit with different text also need a decision.
3. The adjudicator(s) fill `data/labels/roundN/adjudication.csv` with columns
   `item_id, final_decision, final_category, final_edit, decided_by`.
4. Run `.venv/bin/python -m src.queries.adjudicate` to write `data/labels/audited.jsonl`. It stops and lists any
   item still unresolved.
- Who decided: TODO (for example "A1 and A2 together by discussion", or a third person).
- Rule when no consensus: TODO.

## 9. Timeline matched to export files
| Step | Date (UTC) | File |
|---|---|---|
| Round 1 tasks generated | 2026-10-18 17:01 IST (rebuilt after the D5 gold fix; tasks sha256 f6633acb...; first build 00:49 was superseded before any finished labelling, see supporting_files/B_engine/gold_fix_ug_background.md) | `data/labels/round1/tasks.json`, `manifest.csv` |
| Round 1 A1 finished | labelled 2026-10-18 19:00 to 20:10 IST, exported 20:12 (export sha256 0238baff...) | `data/labels/round1/export_A1.json` |
| Round 1 A2 finished | committed by A2 from their own account on 2026-10-19 00:32 IST | `data/labels/round1/export_A2.json` |
| Round 1 agreement | 2026-10-19: decision kappa 0.227, category kappa 0.171 | `supporting_files/C_labelling/round1/agreement_summary.json` |
| Round 1 adjudication | TODO | `data/labels/round1/adjudication.csv` |
| Guidelines v2 frozen | 2026-10-19, issued with the round 2 kit (guidelines_v2.md sha256 f16d8801cb2e8b71...); changes and their round-1 sources in supporting_files/C_labelling/round1/disagreement_analysis.md | `labelstudio/guidelines_v2.md` |
| Round 2 tasks generated | 2026-10-18 17:01 IST (tasks sha256 210e06e4...), kit issued 2026-10-19 | `data/labels/round2/tasks.json`, `manifest.csv` |
| Round 2 A1 finished | exported 2026-10-19 07:12 IST (Label Studio project 3, R2-A1); during the round A1 asked the assistant one guideline question about item R2-Q0114 and got rule-level feedback only, no label | `data/labels/round2/export_A1.json` |
| Round 2 A2 finished | committed by A2 from their own account on 2026-10-19 02:50 IST | `data/labels/round2/export_A2.json` |
| Round 2 agreement | 2026-10-19: decision kappa 0.377, category kappa 0.350 (CIs in supporting_files/C_labelling/kappa_ci.json) | `supporting_files/C_labelling/round2/agreement_summary.json` |
| Round 2 adjudication | TODO | `data/labels/round2/adjudication.csv` |

Export files are saved exactly as Label Studio produced them (Export > JSON) and are never edited.

## 10. Running Label Studio
```
.venv-labelstudio/bin/label-studio start --port 8080 --data-dir labelstudio/ls_data
```
For each annotator create one project per round: Settings > Labeling Interface > Code, paste the config, then
import `data/labels/roundN/tasks.json`. When done: Export > JSON, save as `data/labels/roundN/export_<ID>.json`.
Remote annotator (A2): either A2 installs the same Label Studio version, imports the same `tasks.json` and config,
and sends back the JSON export; or A1 starts the server with `--host 0.0.0.0` on a shared network and A2 logs in
with a separate account to a separate project. Used: A1 local install on own machine; A2 local install on own machine from the round-1 kit (labelstudio/ANNOTATOR_SETUP.md), shared as a download page, not a shared server.
