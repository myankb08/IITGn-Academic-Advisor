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
| 10 | Use plain commit messages without co-author lines; AI use is documented in this folder and in the report appendix | commit messages only (no file content changed) |
| 11 | Compute agreement, draft adjudication proposals, build a readable review page, then build adjudication and freeze the gold set | `supporting_files/C_labelling/`, `src/queries/build_adjudication.py`, `src/queries/kappa_ci.py`, `data/gold/` |
| 12 | Simplify the codebase, complete the pipeline and write the report | cleanup commits, `dvc.yaml`, `agent_G_report.md`, `reports/` |
| 13 | Clean remaining files | `.gitignore`, `dvc.yaml` evidence stages, `src/split/handoff.py` |
| 14 | Quality fixes (semantic paraphrase check, pipeline coverage, per-sample metadata, records); CS 613 decision confirmed by hem436 | `src/augment/verify.py` slot check, `validate_corrupted` stage, per-sample `data/metadata.csv`, `ENVIRONMENT.md`, `prompts/pipeline/README.md`, `data/raw/prereq_manual.csv` |
| 15 | Make the report simpler and easier to read | `agent_G2_report_redesign.md`, `reports/make_figures.py`, `reports/report.tex` |
| 16 | Record the requests as this per-request summary with output files, instead of full chat transcripts | `prompts/assistant/user_requests.md` |
| 17 | Rewrite the report in the assignment's format, with its subheadings and diagrams where needed | `agent_G3_report_structure.md`, `reports/report.tex` |
| 18 | Edits to the AI-assistance appendix by hem436; add the known gold-set limitation | `reports/report.tex`, `HANDOFF_A2.md` (gold set errata) |

# Requests given to Claude Code by hem436 for Assignment 2 (10 to 15 Nov 2026)

Assistant: Claude Code CLI, model claude-opus-5-5, one session (no sub-agent prompts). Same format as above: one line
per request that changed files, summarised, with its output.

| # | request (summary) | output |
|---|---|---|
| 1 | Plan Assignment 2 for Project 4 and build it; run the heavy jobs on the lab machine arka over SSH, in /mnt/zone_C | `docs/A2_PLAN.md`, `params_a2.yaml`, branch `a2` |
| 2 | Use PyTorch int8 instead of GGUF, because GGUF is not required | `docs/A2_PLAN.md` D9, `src/serve/core.py`, `src/serve/export_model.py` |
| 3 | Both members commit their own parts | no file change (the assistant made no commits until request 16) |
| 4 | Deploy the 1.5B 3-epoch run, not the 3B run (both members, val only) | `docs/A2_PLAN.md` D10, registry v1 |
| 5 | Relabel the already-taken eligibility answers under Adv24 B.1 (D6 option 1), retrain on correct labels, stop round r4 | `src/model/d6.py`, `docs/A2_PLAN.md` D13 to D16, `DATA_CHANGES.md`, `supporting_files/C_eval_a1_labels/` |
| 6 | Seed check and one final retraining round | `supporting_files/E_retrain/d6r1/`, registry v7 to v10 |
| 7 | Keep v10 deployed and report the test regression | `docs/A2_PLAN.md` D17, `MODEL_CARD.md` |
| 8 | Build a rating page for the justification ratings; keep the ratings and correct only the reference to D6 | `src/eval/justification_rating.py`, `supporting_files/C_eval/advisor_v1/justification_rating/` |
| 9 | Build an error review page for both members | `src/eval/error_sheet.py`, `supporting_files/C_eval/advisor_v1/test/error_sheet.csv` |
| 10 | Docker image, offline validation, load test, CI, documentation | `Dockerfile`, `docker/`, `src/serve/`, `release/`, `DOCKER.md`, `.github/workflows/ci.yml`, `supporting_files/D_deploy/` |
| 11 | Replay with drift signals and the one-command retraining loop with the gate | `src/monitor/replay.py`, `src/retrain/`, `supporting_files/E_monitoring/`, `supporting_files/E_retrain/` |
| 12 | Clean-machine test on a machine with more RAM | `DOCKER.md` (section to fill) |
| 13 | Draft the report as an editable doc | report doc (exported to `report/report.pdf`) |
| 14 | Merge both error reviews; check the reviewers' findings (ES 643 is PH 643 in the timetable) | `src/eval/error_review.py`, `error_review/`, `MODEL_CARD.md`, `DATA_CHANGES.md`, `TEST_SET_LOG.md` |
| 15 | Do the remaining tasks | `supporting_files/F_reproducibility/pytest.txt`, `requirements_freeze_a2.txt`, `dvc push` |
| 16 | Commit hem436's part and make a package for myankb08 to commit his part | the hem436 commits on `a2`; package outside the repo |
| 17 | Push hem436's commits (myankb08 had already pushed them with his own); tag the release | tag `a2-final`; release image and archive (`artefacts/`, outside git) |
| 18 | Show the labelling pages, their database and sample answers in the slides; then UI screenshots | slides (outside git); `supporting_files/D_deploy/ui_screenshots/` |
| 19 | The UI screenshot shows a rejected answer: show an accepted one too; add the one-shot and few-shot results | `supporting_files/D_deploy/ui_screenshots/` (accepted and rejected answers), slides |
| 20 | Turn STE mode on and simplify the wording of the report and slides | report source and PDF, slides (outside git) |
| 21 | The full validation is too slow on the second machine: complete the check without a full run | clean-machine record in `artefacts/DOCKER.md` and `artefacts/clean_machine/` (outside git) |
| 22 | Commit everything; skip the recording | this commit |
