# Requests given to Claude Code by hem436 (17 to 19 Oct 2026)

Assistant: Claude Code CLI, model claude-opus-5-5. Each line is one request that changed files in this repository,
summarised, with the files its output went into. Conversation that changed no file is not listed. The prompts the
assistant then gave its sub-agents are in this folder, verbatim, as `agent_*.md`.

| # | request (summary) | output |
|---|---|---|
| 1 | Plan Assignment 1 for Project 4 and build it with sub-agents; scope CS M.Tech first | repo skeleton, `docs/DATA_CONTRACT.md`, `params.yaml`, agent tasks A to C |
| 2 | Follow the Project 4 requirements of Section 8 exactly | agent tasks A to F |
| 3 | Add M.Tech EE from the EE M.Tech site | `agent_A2_ee_pages.md`, `src/collect/fetch_ee_pages.py`, EE rules |
| 4 | ICDT is a separate programme; every student is on the thesis or coursework track | `docs/DECISIONS.md` D2, D3, engine and form changes |
| 5 | Build the Google Form in the IITGN account; add examples and a purpose statement | the live form, `docs/GOOGLE_FORM.md`, `src/collect/import_forms.py` (v1/v2 tagging), `supporting_files/C_labelling/forms_log.md` |
| 6 | Run the LLM steps on a Kaggle GPU (token kept outside the repo) | `notebooks/kaggle_llm_runs.ipynb`, `kaggle/`, `scripts/kaggle_run.sh`, `.gitignore` |
| 7 | Do not warn M.Tech students about undergraduate courses (ES 666 needing ES 112) | `docs/DECISIONS.md` D5, `src/engine/rule_engine.py`, `supporting_files/B_engine/gold_fix_ug_background.md` |
| 8 | Labelling support: Label Studio, round 1 and round 2 kits, how to edit | `labelstudio/ANNOTATOR_SETUP.md`, kit pages, `LABELLING_PROTOCOL.md` |
| 9 | Import the form responses (10, then all 19; 9 entered by hem436 after ChatGPT rewording) | `data/raw/forms/`, `src/collect/import_forms.py` (provenance), `src/split/shifted_forms.py`, `prompts/assistant/chatgpt_form_rewording.md` |
| 10 | Remove Claude co-author lines from the commit history | rewritten history (no file content changed) |
| 11 | Compute agreement, draft adjudication proposals, build a readable review page, then build adjudication and freeze the gold set | `supporting_files/C_labelling/`, `src/queries/build_adjudication.py`, `src/queries/kappa_ci.py`, `data/gold/` |
| 12 | Simplify the codebase, complete the pipeline and write the report | cleanup commits, `dvc.yaml`, `agent_G_report.md`, `reports/` |
| 13 | Clean remaining files | `.gitignore`, `dvc.yaml` evidence stages, `src/split/handoff.py` |
| 14 | Emulate the AI and TA grading | `agent_H_mock_grading.md` (read-only check) |
| 15 | Apply the grading fixes; CS 613 decision confirmed by hem436 | `src/augment/verify.py` slot check, `validate_corrupted` stage, per-sample `data/metadata.csv`, `ENVIRONMENT.md`, `prompts/pipeline/README.md`, `data/raw/prereq_manual.csv` |
| 16 | Make the report simpler and easier to read | `agent_G2_report_redesign.md`, `reports/make_figures.py`, `reports/report.tex` |
| 17 | Replace the verbatim chat logs in this folder with this summary | `prompts/assistant/user_requests.md` |
