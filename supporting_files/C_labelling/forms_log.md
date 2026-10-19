# Google Form collection log

| event | date | by | note |
|---|---|---|---|
| Form built in the IITGN Google account ("CS203 Course advisory questions (M.Tech)"), 8 questions per docs/GOOGLE_FORM.md, email collection off | 2026-10-17 | hem436 (built via Claude in Chrome) | form_version v1 |
| Form published ("anyone with the link") and shared with CS and EE M.Tech peers | 2026-10-17 | hem436 | |
| Form edited to v2 by hem436 (question 7 retitled "Your question ?") and by the assistant at hem436's request: description now explains the advisor being built; help text under question 7 with 3 example questions. Reason: respondents were unsure what to ask. Replies before 23:00 IST are tagged v1, after v2 (src/collect/import_forms.py, V2_FROM) | 2026-10-17 ~23:00 IST | hem436 | form_version v2; examples may pull some wording toward the examples (noted as a bias in DATASET_CARD.md) |
| 9 questions asked in person by classmates (verbal consent) entered in the form by hem436 after rewording them with ChatGPT for clarity; the students' original wording was not recorded | 2026-10-19 17:16 to 17:18 IST | hem436 | tagged `provenance = entered_by_hem436_chatgpt_reworded`, consent_mode `verbal_in_person` (src/collect/import_forms.py PROXY_FROM/PROXY_TO); the ChatGPT prompt was not kept (prompts/assistant/chatgpt_form_rewording.md) |
| Final responses downloaded (Responses > Download .csv) and saved unedited as data/raw/forms/responses_raw.csv: 19 rows (10 self-submitted, 9 entered by hem436) | 2026-10-19 17:22 IST | hem436 | the earlier 10-row download is in git history (responses_raw.csv.dvc) |
