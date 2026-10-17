# Annotation guidelines v1: auditing paraphrased advisory queries

## Purpose
Each item is one advisory question about an IIT Gandhinagar M.Tech (CS discipline) degree. A rule engine produced
the template query and the gold answer, so the gold answer is correct by construction. A small language model then
rewrote the query and the justification. Your job is to check that the rewrite still asks the same thing and still
says what the gold answer says. The audited items become training and test data, so a wrong item you accept will
teach the model something false.

## What you see
1. Student summary: programme, stream, track, semesters done, completed courses.
2. Template query: the original question.
3. Paraphrased query: audit this.
4. Rule-engine gold answer: treat it as the truth.
5. Paraphrased justification: audit this.

You do not see the other annotator's labels or any model guess of the label. Do not discuss items with the other
annotator until both of you have exported the round.

## Label order (always top to bottom)
1. **Decision** first, 2. **error category** second, 3. **edit text** last (only for edit).
Why this order: the decision is the main outcome and the one we measure agreement on first. Choosing it before the
category stops the category list from steering your overall judgement, and writing the edit last means you have
already named the problem you are fixing.

## Decisions
- **accept**: the paraphrased query asks the same question for the same student and course, and the justification
  agrees with the gold answer with no missing or added facts. Small style issues are fine.
- **edit**: the item is worth keeping and you can fix it with a short correction (one or two sentences changed).
  Write the corrected paraphrased query and/or justification in the edit box. Keep the rest of the wording.
- **reject**: the item cannot be saved with a short edit, for example the question is about a different course,
  the justification contradicts the gold answer throughout, or the text is unreadable.

## Error categories (pick the single main problem)
- **none**: no problem. Use with accept.
- **hallucinated_course**: mentions a course code or title that is not in the student summary, the template query
  or the gold answer, or a course that does not exist.
- **wrong_fact_or_policy**: states a wrong credit count, rule, prerequisite, semester or eligibility outcome compared
  with the gold answer.
- **meaning_drift**: the paraphrased query asks something different (different target course, different intent,
  yes/no turned into a list request).
- **incomplete_justification**: the answer outcome is right but a reason from the gold answer is missing, for
  example a missing prerequisite or a missing remaining core course.
- **fluency**: meaning and facts are right but the text is ungrammatical, garbled or very awkward.
- **ambiguous_query**: the paraphrased query could reasonably be read in more than one way, so the gold answer
  may not fit it.
If two problems apply, choose the one higher in this priority: hallucinated_course, wrong_fact_or_policy,
meaning_drift, incomplete_justification, ambiguous_query, fluency.

## Edge cases
- **Partially correct justification**: if the outcome matches the gold answer but one reason is missing, use edit +
  incomplete_justification and add the missing reason. If the outcome itself is wrong, use wrong_fact_or_policy
  (edit if one sentence fixes it, otherwise reject).
- **Correct but awkward paraphrase**: if a student could still understand it easily, accept + none. If you had to
  read it twice, edit + fluency.
- **Paraphrase changes the target course**: always meaning_drift. Edit it back to the right course if the rest is
  fine; reject if the whole justification is about the wrong course.
- **Abbreviations**: common forms such as "sem", "ML", "elec", "reqs" or "CS610" for "CS 610" are fine and are
  not errors. An abbreviation that makes the course code unclear (for example "the 6-something course") is
  ambiguous_query.
- **Missing semester information**: if the template query names a semester (odd/even, next semester) and the
  paraphrase drops it in a way that could change the answer, use meaning_drift. If the semester does not matter
  for the answer, accept.
- **Unsure**: pick your best label and do not skip. Disagreements are resolved later, guessing is fine.

## Worked examples
These use made-up wording to show the labels. Course facts here are illustrative, always check against the gold answer.

1. Template: "What core courses do I still need to finish?" Paraphrase: "Which core courses are left for me?"
   Justification lists the same remaining courses as the gold answer.
   -> accept, none.
2. Template: "Am I eligible to take CS 621 next semester?" Paraphrase: "Can I register for CS 610 next semester?"
   -> edit, meaning_drift, edit text: "Can I register for CS 621 next semester?"
3. Gold answer: two compulsory courses remain, CS 610 and CS 621. Justification: "You still need CS 610."
   -> edit, incomplete_justification, edit text adds "and CS 621".
4. Justification recommends "CS 699 Quantum Robotics", which appears nowhere in the item.
   -> reject (or edit if it is one clause that can be deleted), hallucinated_course.
5. Gold answer says the student is not eligible because a prerequisite is missing. Justification says "Yes, you can
   take it." -> edit, wrong_fact_or_policy, edit text restates the gold outcome and reason.
6. Paraphrase: "core course what remain me need finishing degree for?"
   -> edit, fluency, edit text: "Which core courses do I still need to finish my degree?"
