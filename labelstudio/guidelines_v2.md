# Annotation guidelines v2: auditing paraphrased advisory queries

Revised after round 1 (kappa 0.23 on decision, 0.17 on category). Every change from v1 is marked **[v2]** and
points to the round-1 items behind it in `supporting_files/C_labelling/round1/disagreement_analysis.md`.
The label set and the Label Studio config (`config_v1.xml`) are unchanged.

## Purpose
Each item is one advisory question about an IIT Gandhinagar M.Tech degree (**[v2]** CS and EE departments:
MTech-CSE, MTech-AI, MTech-EE, MTech-ICDT). A rule engine produced the template query and the gold answer, so the
gold answer is correct by construction. A small language model then rewrote the query and the justification. Your
job is to check that the rewrite still asks the same thing and still says what the gold answer says. The audited
items become the gold test set, so a wrong item you accept becomes a wrong test answer.

## What you see
1. Student summary: programme, stream, track, semesters done, completed courses.
2. Template query: the original question.
3. Paraphrased query: audit this.
4. Rule-engine gold answer: treat it as the truth.
5. Paraphrased justification: audit this.

You do not see the other annotator's labels or any model guess of the label. Do not discuss items until both of
you have exported the round.

## Label order (always top to bottom)
1. **Decision**, 2. **error category**, 3. **edit text** (only for edit). Choosing the decision first stops the
category list from steering your overall judgement; writing the edit last means you have already named the problem.

## How to check one item (about 1 minute)
1. Query: same student, same course, same kind of question as the template?
2. Justification: list the facts in the gold answer (outcome, every number, every course, every open item).
   Tick each one off in the justification. Then look for anything in the justification that is not in gold.

## Decisions
- **accept**: the query asks the same question, and the justification states the gold outcome and all gold facts
  with nothing wrong or extra. Style, tone and formatting do not matter.
- **edit**: worth keeping and fixable with a short correction. **[v2]** Edit when the fix changes at most two
  sentences of the justification or one phrase of the query (R3). Write the corrected text in the edit box,
  starting with "Query:" or "Justification:" for each part you fix.
- **reject**: the fix would need more than that, the item is about a different course, or the text is unreadable.
  **[v2]** A missing fact alone is never a reason to reject; add it with an edit (R3, items Q0109, Q0175).

## Error categories (pick the single main problem)
Priority when several apply, highest first: hallucinated_course, wrong_fact_or_policy, meaning_drift,
incomplete_justification, ambiguous_query, fluency.
- **none**: no problem. Only with accept. **[v2]** "edit" or "reject" always needs a category other than none (R7).
- **hallucinated_course**: a course code or title that is not in the summary, the template query or gold, or does
  not exist.
- **wrong_fact_or_policy**: a credit count, rule, semester, status or eligibility outcome that contradicts gold.
  **[v2]** This includes vague wording that implies the wrong status, for example "a few more credits to go" when
  gold says 0 to go, and any number that is not in gold (R2, items Q0124, Q0161, Q0177, Q0179).
- **meaning_drift**: the paraphrased query asks something different. **[v2]** Also: adding scope gold cannot answer
  ("documentation", "courses and coursework"), "available" in place of "remaining" or "left", and a turned-around
  question addressed to the student ("Are you an MTech-CSE student ...?") (R4, items Q0120, Q0177, Q0178, Q0320).
- **incomplete_justification**: the outcome is right but a gold fact is missing. **[v2]** Pure encouragement with no
  facts ("almost there, keep it up") is incomplete_justification, fixed with an edit that adds the gold facts.
  For remaining-requirements answers, the "open items" list at the end of gold counts as facts. For recommendations,
  every recommended course in gold must appear (R1, items Q0033, Q0120, Q0175, Q0178, Q0197, Q0404).
- **fluency**: meaning and facts are right but the text is ungrammatical or garbled. **[v2]** Line breaks, bullets,
  capitalisation and friendly tone are not fluency errors (R7, items Q0421, Q0495).
- **ambiguous_query**: the paraphrased query can reasonably be read in more than one way.

## [v2] Gold is the truth, even when you know better (R6)
Judge only against the gold answer. Do not add requirements gold does not list and do not correct gold from your own
knowledge. Example from round 1: for an MTech-EE student, gold says CS 621 counts only as an elective. That is right
(CS 621 is compulsory only for MTech-CSE and MTech-AI), and the item should be accepted (items Q0366, Q0390). If you
really think gold is wrong, still label against gold and write "GOLD?" plus one line in the edit box.

## [v2] Two problems in one item (R5)
Pick the category by the priority list and fix both texts in the edit (item Q0192).

## Edge cases kept from v1
- Common abbreviations ("sem", "ML", "elec", "CS610") are fine. An abbreviation that hides the course is
  ambiguous_query.
- If the paraphrase drops a semester that changes the answer, meaning_drift; if it does not matter, accept.
- Unsure: pick your best label and move on.

## Worked examples
1. Gold: own basket 0 to go, other baskets 0 to go. Justification: "You're almost there, just a few more credits!"
   -> edit, wrong_fact_or_policy (implies credits are missing). Edit: "Justification: Your own and other basket
   requirements are complete (0 credits to go)."
2. Gold: CS 621 missing, own basket 4 to go. Justification: "Keep going, you're doing great!"
   -> edit, incomplete_justification. Edit adds "CS 621 is still missing and you need 4 more own-basket credits."
3. Template: "What credits are still left?" Paraphrase: "What credits are still available to me?"
   -> edit, meaning_drift. Edit: "Query: What credits do I still need?"
4. Gold recommends CS 613, CS 618 and a third course; justification names only CS 613 and CS 618.
   -> edit, incomplete_justification, add the third course.
5. Justification correct, only reformatted with bullets -> accept, none.
6. Justification recommends "CS 699 Quantum Robotics" (not in the item) -> reject or edit, hallucinated_course.
