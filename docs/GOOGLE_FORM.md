# Google Form: student advisory questions

Create this form exactly as written. The question titles must match character for character,
because `src/collect/import_forms.py` maps CSV columns by title.

## Settings (do these first)
- Settings > Responses > Collect email addresses: **Do not collect**.
- Settings > Responses > Limit to 1 response: **off** (it would force a Google sign-in and link responses to accounts).
- Settings > Responses > Allow response editing: off.
- Do not add any question asking for name, roll number, email or phone.
- Responses > link to Sheets is optional. For the dataset, use Responses > Download responses (.csv), unzip,
  and save the file as `data/raw/forms/responses_raw.csv` without editing it.

## Title
Course advisory questions from M.Tech students (anonymous)

## Description (intro text)
We are building a small dataset of the questions M.Tech students at IIT Gandhinagar (CS and EE disciplines) ask about
their degree requirements, course eligibility and electives. It is for a course project (CS 203, Assignment 1).
The form is anonymous: we do not collect your name, email or roll number, and the timestamp Google adds is
deleted before the data is used. Please do not write anything in the answers that identifies you.
It takes about 3 minutes.

## Questions

1. **Consent** (Checkboxes, required)
   - Option: `I agree that my anonymous answers may be used in a course project dataset`
   - Help text: The answers are stored without names or emails and may be published as part of the project dataset.
     If you do not agree, please close the form.

2. **Programme** (Multiple choice, required)
   - `MTech-CSE`
   - `MTech-AI`
   - `MTech-EE`
   - `MTech-ICDT`
   - `Other`

3. **Stream** (Multiple choice, required)
   - `AI/ML`
   - `Systems`
   - `Theory`
   - `Power Engineering & Control Systems`
   - `Signal Processing & Machine Learning`
   - `Not decided / not applicable`

4. **Track** (Multiple choice, required)
   - `Thesis`
   - `Coursework`

5. **Current semester** (Multiple choice, required)
   - `1`
   - `2`
   - `3`
   - `4`

6. **Courses completed so far** (Paragraph, optional)
   - Help text: Course codes are enough, for example CS 610, CS 621. Leave empty if this is your first semester.

7. **Your question for an academic advisor** (Paragraph, required)
   - Help text: Write the question the way you would ask a faculty advisor, about remaining requirements,
     whether you can take a course, or which electives to choose.

8. **What kind of question is this?** (Multiple choice, required)
   - `Remaining requirements`
   - `Eligibility for a course`
   - `Elective advice`
   - `Other`

## What the importer does
`.venv/bin/python -m src.collect.import_forms`
- drops the `Timestamp` column and any email column,
- removes email addresses and phone numbers from free text (counts are logged, values are not),
- reorders rows by a hash of their content so ids do not follow submission order, then assigns `R001`, `R002`, ...,
- writes consenting rows with a non-empty question to `data/raw/forms/responses_anonymised.jsonl`,
- writes one row per response to `data/consent_register.csv`,
- logs counts to `supporting_files/C_labelling/forms_import_log.json`.

Test without real data: `.venv/bin/python -m src.collect.import_forms --fixture`.
