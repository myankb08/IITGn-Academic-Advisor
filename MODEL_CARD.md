# Model card: IITGN M.Tech course advisor

## Models

| item | deployed: `advisor` v10 | Part B/C system: `advisor` v1 |
|---|---|---|
| registry | alias `production` | alias `previous` (rollback target), `staging` |
| MLflow run | `aa644d3c4b984c7e8f19446c7c060a72` | `cb7c02b778d342e2b5a30f163ac8ee74` |
| how it was made | Part E retraining round d6r1: new adapter on the 1,541 train rows + 100 pool pairs selected by the A1 active-learning score (curriculum v2), seed 312, best of 3 seeds on val (D16), passed the gate | best val trade-off of the Part B search (18 finished runs, D10) |
| labels | D6 (a passed course may be repeated to improve the grade) | A1 (trained before D6; scored on D6 labels below) |

Both: `Qwen/Qwen2.5-1.5B-Instruct` at revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` (Apache 2.0) with LoRA rank
32, alpha 64, dropout 0.05 on q/k/v/o/gate/up/down, lr 5e-4, 3 epochs, effective batch 16. Prompt
`prompts/pipeline/advisor_retrieval_v1.txt` (programme course list, degree rules, transcript, upcoming term, question).
Output: one JSON object in the A1 answer schema plus a `justification`. Serving: LoRA merged into the base (fp16), every
Linear layer weight-only int8 with per-channel scales, fp32 activations, greedy decoding, CPU (`DOCKER.md`).

## Intended use

- Answer three kinds of questions from IIT Gandhinagar M.Tech students (CSE, AI, EE, ICDT): missing core courses
  (`remaining_core`), whether a course can be taken next term (`eligibility`), and which electives to take
  (`elective_recommendation`).
- Every answer is checked against the deterministic rule engine before it is shown. When the check fails the service
  shows the rule-engine answer and says the model was rejected. The model explains; the rule engine decides.
- Not for: official degree audits, questions outside the three kinds (audit rules, stipends, thesis extensions; see
  `data/sft/forms.jsonl`), curricula other than the bundled ones, or any decision without a faculty advisor.

## Data

- Synthetic students and rule-engine answers from Assignment 1 (`DATASET_CARD.md`); no real student records. Splits are
  by student; test uses held-out question templates; the gold set is 76 human-audited test items (checksum
  `cd2e08dc…`, unchanged; the five "workshop" errata are fixed in the prompt only).
- D6 labels (`docs/A2_PLAN.md` D14): an A1 label "not eligible: already taken" contradicts Academic Advisory 24 B.1, which
  allows repeating a passed course to improve the grade (no new credits). A2 labels follow Adv24 (74 train, 21 val,
  25 test, 12 shifted, 6 gold rows changed). `gold` below uses D6 labels; `gold_a1` the original gold labels.
- Shifted data: the MTech-ICDT holdout (288 rows) under a simulated curriculum update (`data/a2/curriculum_update.json`).
- Known noise in training: 14 A1 paraphrases of eligibility questions name a different course or none, 5 say
  "workshop track", 5 rows recommend a course missing from the prompt's list (`DATA_CHANGES.md`).

## Metrics (raw model output, before the rule-engine check; 95% bootstrap CIs, 1,000 resamples)

Set F1 of the course set (eligibility: of the unmet-prerequisite set, 0 when yes/no is wrong), exact match with the rule
engine, constraint violations, invented codes (`src/eval/metrics.py`). GPU fp16, `supporting_files/C_eval/<model>/<split>/metrics.json`:

| model | split | n | set F1 | exact match | violations | invented-code rate |
|---|---|---|---|---|---|---|
| v10 (deployed) | val | 280 | 0.882 [0.846, 0.918] | 0.814 [0.771, 0.857] | 0.000 | 0.004 |
| v10 | test | 353 | 0.818 [0.783, 0.852] | 0.669 [0.623, 0.717] | 0.031 | 0.000 |
| v10 | gold | 76 | 0.873 [0.807, 0.930] | 0.750 [0.645, 0.842] | 0.039 | 0.000 |
| v10 | gold_a1 | 76 | 0.820 [0.741, 0.890] | 0.697 [0.592, 0.803] | 0.039 | 0.000 |
| v10 | shifted | 288 | **0.829** [0.790, 0.866] | **0.681** [0.622, 0.736] | 0.108 | 0.031 |
| v1 | val | 280 | 0.926 [0.899, 0.952] | 0.821 [0.779, 0.861] | 0.000 | 0.004 |
| v1 | test | 353 | **0.924** [0.901, 0.946] | **0.762** [0.717, 0.807] | 0.000 | 0.000 |
| v1 | gold | 76 | 0.904 [0.838, 0.961] | 0.750 [0.645, 0.842] | 0.000 | 0.000 |
| v1 | gold_a1 | 76 | 0.851 [0.772, 0.921] | 0.697 [0.592, 0.803] | 0.000 | 0.000 |
| v1 | shifted | 288 | 0.691 [0.639, 0.736] | 0.535 [0.472, 0.590] | 0.302 | 0.056 |

Deployed on CPU (weight-only int8, inside the image, `release/serving/reported_gold.json`): gold set F1 0.877, exact
match 0.763, valid JSON 1.0, violations 0.013, invented codes 0. The difference from GPU fp16 (one gold item) is within
the stated validation tolerance of 0.02.

Baselines (trivial, zero-shot, few-shot, curriculum retrieval) are lower than v1 on every split, paired bootstrap
p < 0.001 and McNemar p < 1e-8 (`supporting_files/C_eval/comparison_advisor_v1.md`); best baseline test set F1 0.549.

**v10 against v1:** v10 is much better on the shifted data (+0.138 set F1; rule-breaking recommendations 31 of 96 against
87 of 96) and equal on gold exact match, which is what the gate checks. On the old-curriculum test set it is worse: set
F1 -0.106 [-0.143, -0.074], McNemar p = 0.0006, mostly on eligibility (0.736 vs 0.900) and electives (0.741 vs 0.906).
The gate's metrics (overall exact match, 76 gold items) did not show this; the per-question-type val scores did
(eligibility 0.737 vs 0.842). See Limitations.

Justification quality (`supporting_files/C_eval/advisor_v1/justification_rating/`, model v1): two annotators rated 60
test justifications (20 per question kind) on their own against the rule-engine reference. Rater A1: 39 correct, 13
partly correct, 8 incorrect; rater A2: 41 / 10 / 9. Cohen's kappa 0.80 [0.66, 0.93] (linear-weighted 0.83; 54 of 60
identical). "Faithful to the model's own answer" was read differently (A1 marked 11 items unfaithful, A2 2): 85% raw
agreement but kappa 0.27 [0.00, 0.58]; that criterion needs a clearer definition. The ratings were made against the A1
reference; for 6 items (Q0208, Q0280, Q0334, Q0364, Q0376, Q0400) the reference changed under D6. The ratings are kept as
made; the sheets also hold the D6 reference (`rule_engine_answer_d6`, `rule_engine_justification_d6`).

## Slices (test, D6 labels; set F1 / exact match)

| slice | group (n) | v1 | v10 |
|---|---|---|---|
| programme | MTech-CSE (165) | 0.915 / 0.806 | 0.842 / 0.715 |
| | MTech-EE (105) | 0.965 / 0.743 | 0.841 / 0.733 |
| | MTech-AI (83) | 0.892 / 0.699 | 0.741 / 0.494 |
| question type | remaining core (122) | 0.964 / 0.664 | 0.969 / 0.779 |
| | electives (121) | 0.906 / 0.736 | 0.741 / 0.496 |
| | eligibility (110) | 0.900 / 0.900 | 0.736 / 0.736 |
| transcript length (courses) | 0 (107) | 0.950 / 0.944 | 0.972 / 0.972 |
| | 1-6 (108) | 0.944 / 0.833 | 0.770 / 0.630 |
| | 7-12 (69) | 0.903 / 0.783 | 0.763 / 0.551 |
| | 13+ (69) | 0.874 / 0.348 | 0.710 / 0.377 |
| shifted (288), set F1 | remaining core / eligibility / electives | 0.990 / 0.809 / 0.239 | 1.000 / 0.809 / 0.676 |

Weak groups: students with 13 or more courses (course sets mostly right, credit totals wrong: exact match about 0.35),
MTech-AI, and, for v10, electives and eligibility under the old curriculum.

Robustness (A1 Part D augmented test children against their parents, `robustness.json`): typos and abbreviations keep
97% (v1) and 98% (v10) of exact-match outcomes; transcript reordering 100% for both; paraphrases (n = 7) drop v1's set F1
from 0.952 to 0.810. Transcript-length children have their own, different gold answers, so they test other transcripts,
not invariance.

## Limitations

- The Part E gate passed a model (v10) that is worse on the old-curriculum test set; a better gate would check set F1 and
  each question type on val, not only overall exact match on 76 gold items (`docs/A2_PLAN.md` D17).
- Curriculum error in the labels: the A1 catalog has ES 643 with no offering, but the Sem-I 2026-27 timetable lists the
  same course as PH 643, so 2 gold and 6 test eligibility labels say "not offered" and are very likely wrong. With
  "offered", gold exact match is 0.750 for v1 (unchanged) and 0.724 for v10: a drop of 0.026, larger than the gate
  tolerance of 0.02, so the gate would have rejected v10. The gold file and the labels are unchanged (`DATA_CHANGES.md`,
  `TEST_SET_LOG.md`, 2026-11-15).
- Credit arithmetic is the most common v1 error: both annotators put 36 of the 84 test errors in "right courses, wrong
  credit total" (`supporting_files/C_eval/advisor_v1/test/error_sheet.csv`, review in `error_review/summary.json`).
- Elective errors are mostly allowed alternatives: in 26 of 32 elective errors every recommended course is one the
  student may take and that counts, but the list differs from the rule engine's priority order (A1 marked these
  "wrong courses", A2 "right courses suggested"); 6 recommend CS 431, which cannot count after the below-600 allowance
  is used. The set-F1 metric scores an allowed alternative as an error.
- Knows only the curricula it was trained on: after the simulated update v1 broke a rule in 87 of 96 recommendations,
  v10 in 31 of 96. The rule-engine check catches these before display.
- Trained only on synthetic students and template questions (plus paraphrases); real student questions (Google Forms)
  are often outside the three question kinds.
- CPU latency is about a minute per answer on 8 cores; answers are generated one at a time.

## Risks

- A wrong "you can register" or a missing core course can delay graduation. Mitigation: the rule-engine check, the
  rule-engine answer shown on rejection, and a statement that answers need a faculty advisor's confirmation.
- Fluent justifications can sound more certain than they are; the confidence shown is the mean token probability, not a
  calibrated correctness probability.
- Request logs keep no question text (a hashed word vector, lengths, the parsed answer and timings only).
