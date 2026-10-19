# Round 2 disagreement analysis (guidelines v2)

Sources: `data/labels/round2/export_A1.json`, `export_A2.json` (raw, unmodified); `src/queries/agreement.py`
outputs in this folder; confidence intervals from `src/queries/kappa_ci.py` in `../kappa_ci.json`.

## Before and after the revision
| level | round 1 (v1) kappa [95% CI] | round 2 (v2) kappa [95% CI] | raw agreement r1 -> r2 |
|---|---|---|---|
| decision | 0.227 [0.000, 0.469] | 0.377 [0.094, 0.630] | 65.0% -> 77.5% |
| error category | 0.171 [0.007, 0.353] | 0.350 [0.064, 0.620] | 62.5% -> 75.0% |

Disagreements fell from 17 to 12. Both kappas rose, but with 40 items per round the bootstrap intervals overlap,
so the gain is in the expected direction and not statistically conclusive. The two rounds also use different
items (disjoint test-split samples), so part of the change can come from the item mix.

## What v2 fixed
- Vague "almost there" justifications: in round 1 these caused most accept-vs-edit splits. In round 2 both
  annotators edited or rejected the vague items with numbers missing (Q0014, Q0114) instead of one accepting.
- Formatting-only edits: none in round 2 (R7).
- Correcting gold from memory: none in round 2 (R6).

## What still splits the annotators
| item | A1 | A2 | what happened | remaining cause |
|---|---|---|---|---|
| R2-Q0052 | reject / wrong_fact | accept / none | Justification: "40 credits ... need at least 16 more"; gold: 40 earned, 0 to go | A2 missed a contradicted number (R2) |
| R2-Q0073 | reject / wrong_fact | accept / none | Justification says the AI/ML core course is missing and own basket "need at least 4" more; gold: core none missing, own basket 0 to go | same (R2) |
| R2-Q0091 | reject / wrong_fact | accept / none | "16 more coursework credits needed" (gold: the 16 to go are discipline-list credits); also invents "a full year of physical education" and an "own basket" that MTech-EE does not have | same (R2) |
| R2-Q0019 | reject / wrong_fact | edit / wrong_fact | "Take these courses to reach the minimum 16"; gold: 24 earned, 0 to go | same category; edit-vs-reject threshold (R3) |
| R2-Q0127 | reject / wrong_fact | edit / wrong_fact | "You'll have exactly 16 credits"; gold: 28 earned, 0 to go | same as Q0019 (R3) |
| R2-Q0014 | edit / fluency | edit / wrong_fact | "On track ... a few more credits"; gold: 0 earned, 16 discipline and 48 coursework to go | A1 under-rated an implied wrong status (R2) |
| R2-Q0114 | edit / meaning_drift | edit / fluency | Query says "workshop track" and "assessments"; justification vague | two problems; priority list picks meaning_drift (R5) |
| R2-Q0512 | edit / meaning_drift | accept / none | Query says "workshop track" instead of "coursework track" | A2 missed a query change (R4) |
| R2-Q0365 | edit / ambiguous | accept / none | Query drops "Sem-I" ("the 2026-27 semester") | v1/v2 edge case: dropped semester that does matter |
| R2-Q0059 | edit / incomplete | accept / none | Justification omits the thesis gap listed in gold | R1 applied by A1 only |
| R2-Q0126 | accept / none | edit / fluency | Correct numbered list; A2 removed the opening "You're almost done!" | A2 edited tone, which R7 says is not an error |
| R2-Q0417 | accept / none | accept / meaning_drift | Same decision; A2 gave accept a non-none category | label-entry slip; v2 says accept goes with none |

## Findings for the report
- The main remaining split is wrong numbers inside fluent text (Q0052, Q0073, Q0091, Q0014): A1 caught them, A2
  accepted. A v3 would add a checklist step: "find each number in the justification in gold".
- The edit-or-reject threshold (R3) still splits A1 (reject) and A2 (edit) when a justification gets the status
  wrong (Q0019, Q0127). v2 also has an internal tension, raised by A1 during round 2: R3 limits an edit to two
  sentences, while R1 says a missing fact is never a reason to reject. A v3 would let factual additions exceed
  the two-sentence limit.
- The paraphraser repeatedly turns "coursework track" into "workshop track" (Q0114, Q0512): a systematic LLM error
  that the audit catches and that a later prompt revision could prevent.
- Q0417 shows a label-entry slip the config could prevent by disabling categories when "accept" is chosen.
