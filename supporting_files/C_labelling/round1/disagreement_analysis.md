# Round 1 disagreement analysis (guidelines v1)

Source files: `data/labels/round1/export_A1.json`, `data/labels/round1/export_A2.json` (raw Label Studio exports,
unmodified), computed by `src/queries/agreement.py` into `supporting_files/C_labelling/round1/`.

## Headline numbers (from agreement_summary.json)
| level | Cohen's kappa | raw agreement |
|---|---|---|
| decision (accept / edit / reject) | 0.227 | 65.0% (26 of 40) |
| error category | 0.171 | 62.5% (25 of 40) |

17 of 40 items differ on decision or category (disagreements.csv).

## The main pattern: strictness, not category confusion
Decision confusion (rows A1, columns A2, confusion_decision.csv):

| | A2 accept | A2 edit | A2 reject |
|---|---|---|---|
| A1 accept | 23 | 0 | 1 |
| A1 edit | 8 | 3 | 0 |
| A1 reject | 3 | 2 | 0 |

A2 accepted 34 of 40 items and A1 accepted 24. In 11 of the 17 disagreements A1 flagged a problem (8 edits,
3 rejects) on an item A2 accepted. The two annotators almost never disagreed in the other direction (1 item).
So the guidelines did not pin down how much missing or vague content is still acceptable.

## Item-by-item analysis (all 17)

| item | intent | A1 | A2 | what happened | cause | v2 rule |
|---|---|---|---|---|---|---|
| R1-Q0033 | remaining_core | reject / wrong_fact | accept / none | Justification says "almost done ... a few more credits"; gold has CS 621 missing, own basket 4 to go, 16 coursework and 32 thesis credits to go | v1 never said whether content-free encouragement counts as agreeing with gold | R1 |
| R1-Q0124 | remaining_core | reject / wrong_fact | accept / none | "A few more courses and credits" while gold says both baskets are complete (0 to go) | same as Q0033; here the vague text also implies something is still missing | R1, R2 |
| R1-Q0120 | remaining_core | edit / meaning_drift | edit / incomplete | Justification is pure encouragement (no facts); query adds "courses and coursework" | both saw a problem but named different main errors | R1, R4 |
| R1-Q0192 | remaining_core | edit / ambiguous | edit / incomplete | Vague justification; query drops "coursework track" | A1 fixed the query, A2 fixed the justification: two problems, no tie-break used | R4, R5 |
| R1-Q0109 | remaining_core | reject / wrong_fact | edit / wrong_fact | Justification says 4 more own-basket credits needed; gold says 0 to go | same category, different edit-vs-reject threshold | R3 |
| R1-Q0175 | remaining_core | reject / wrong_fact | edit / incomplete | "A few credits short" (gold: 3 to go, which is right) but it drops the other open items gold lists (physical education and writing missing, coursework, project and total gaps); A2's edit adds them back from gold | the outcome was not wrong, so wrong_fact and reject were too strong; A2 matched gold | R1, R3 |
| R1-Q0179 | remaining_core | edit / wrong_fact | edit / incomplete | "16 earned, need 32 more ... halfway there"; gold: 16 coursework + 32 thesis to go | any contradicted number should outrank incomplete | R2 |
| R1-Q0161 | remaining_core | edit / meaning_drift | accept / none | Justification says own basket "need 4 more"; gold says 0 to go | A2 missed a wrong number; A1 named it meaning_drift though the query was fine | R2 |
| R1-Q0177 | remaining_core | edit / meaning_drift | accept / none | Query adds "documentation"; justification says AI/ML core missing (gold: none) | wrong fact present, but A1 picked the query problem first | R2, R4 |
| R1-Q0178 | remaining_core | edit / incomplete | accept / none | Query says "still available" instead of "still left"; justification omits other-basket gap | "available" vs "remaining" changes the question | R4, R1 |
| R1-Q0197 | remaining_core | edit / incomplete | accept / none | "66 out of 82, 16 to go" matches gold, but the justification leaves out that the 16 are thesis credits (gold: thesis 12 to go, coursework done); A1 added the thesis gap | a correct total that hides which requirement is open was tolerated by A2 | R1 |
| R1-Q0320 | eligibility | accept / none | reject / wrong_fact | Paraphrased query is turned around ("Are you an MTech-CSE student ...?"); justification is correct | query role reversal not covered by v1 | R4 |
| R1-Q0366 | eligibility | edit / meaning_drift | accept / none | Justification: CS 621 "not on the list for your stream, counts as an elective"; gold for this MTech-EE student says the same | A1 corrected it from personal knowledge (CS 621 is compulsory for CSE and AI only); gold was right | R6 |
| R1-Q0390 | eligibility | edit / incomplete | accept / none | Same as Q0366 for another MTech-EE student | same | R6 |
| R1-Q0404 | elective_rec | edit / incomplete | accept / none | Justification lists 2 of the 3 recommended courses | v1 did not say a recommendation list must be complete | R1 |
| R1-Q0421 | elective_rec | edit / none | accept / none | A1's edit only adds line breaks; decision "edit" with category "none" breaks v1 | formatting-only edits not covered | R7 |
| R1-Q0495 | elective_rec | reject / fluency | accept / none | Word-for-word the same item as Q0421 (another student in the identical state); A1 labelled the two copies differently | intra-annotator inconsistency on a repeated item | R7 |

## Changes for guidelines v2 (each tied to the items above)
- **R1 Vague or content-free justification.** A justification must state the gold outcome and every number or course
  the gold answer lists for that question, including the "open items" at the end of a remaining-requirements answer.
  Pure encouragement ("almost there, keep it up") with no facts is `incomplete_justification` (edit, adding the
  facts). Items: Q0033, Q0124, Q0120, Q0175, Q0178, Q0197, Q0404.
- **R2 Contradicted or invented numbers.** Any number, course or status that contradicts gold, or is not in gold
  at all, is `wrong_fact_or_policy` and outranks every category except `hallucinated_course`. Items: Q0124, Q0161,
  Q0177, Q0179.
- **R3 Edit or reject.** Edit when the fix touches at most two sentences of the justification or one phrase of the
  query; otherwise reject. A missing fact is never a reason to reject on its own. Items: Q0109, Q0175.
- **R4 Query checks.** Added scope the gold cannot answer ("documentation", "courses and coursework"), "available"
  instead of "remaining/left", or a turned-around question addressed to the student are `meaning_drift`. Items:
  Q0120, Q0177, Q0178, Q0192, Q0320.
- **R5 Two problems.** Use the v1 priority list for the category and fix both texts in the edit. Item: Q0192.
- **R6 Gold is the truth, even when you know better.** Do not correct gold from your own knowledge (for example,
  CS 621 is compulsory only for MTech-CSE and MTech-AI, so for an MTech-EE student gold rightly calls it an elective).
  Flag a suspected gold error in the edit box as "GOLD?" instead of changing the facts. Items: Q0366, Q0390.
- **R7 Formatting.** Line breaks, bullet style and capitalisation are not errors: accept + none. "Edit" always needs
  a category other than "none". Items: Q0421, Q0495.

## Notes for the report
- The repeated item (Q0421 / Q0495) works as an unplanned intra-annotator check: A1 gave the identical item two
  different decisions.
- Q0366 and Q0390 show that annotators can over-correct a correct gold answer from memory; v2 R6 addresses this.
- The agreement numbers above are before adjudication and before the v2 revision; round 2 measures the effect of v2.
