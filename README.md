# CS203 Project 4: Course Advisory SLM data (Assignment 1)

Dataset and pipeline for a small language model that answers M.Tech course advising questions at IIT Gandhinagar:
"which core courses do I still need", "can I register for CS 621 next term", "suggest electives for me".
Every answer is computed by a deterministic rule engine built from the institute's own documents (norms PDFs,
the CSE course structure, the Sem-I 2026-27 timetable and the EE M.Tech site), so the gold labels are traceable
to a source page. A local LLM (qwen2.5:1.5b on CPU) paraphrases questions and justifications, and humans audit
those paraphrases in Label Studio.

Scope: four programmes, MTech-CSE and MTech-AI (CS department), MTech-EE and MTech-ICDT (EE department), each with a
thesis and a coursework track (`docs/DECISIONS.md` D1 to D3).

GitHub: https://github.com/hem436/CS203_Project

## Rebuild the data

From the repo root, with Python 3.10 on Linux:

```bash
python3.10 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/dvc pull
.venv/bin/dvc repro
.venv/bin/pytest -q
```

- `dvc pull` reads the local DVC remote at `../dvc_remote` (a folder next to the repo root, stored in `.dvc/config`
  as `../../dvc_remote` because DVC keeps it relative to `.dvc/`). In the submission zip that folder sits next to
  `code/`, so the commands above work offline.
- `dvc repro` should print "Data and pipelines are up to date" after a pull. If you change code or params, it reruns
  only the affected stages. The LLM stages (`paraphrase_llm`, `augment`, `base_model_answers`) need Ollama running
  with `qwen2.5:1.5b` (see ENVIRONMENT.md); answers already in `data/interim/llm_cache.jsonl` are reused, so a rerun
  with the same model digest gives the same text.
- Pipeline definition: `dvc.yaml`. Stage order: extract_sources, fetch_course_plans (offline), fetch_ee_pages
  (frozen raw input), build_catalog, build_rules, clean_catalog, prereq_graph, synth_transcripts, inject_violations (test fixture data), assign_students, make_queries,
  paraphrase_llm, augment, make_splits, base_model_answers, al_vs_random, validate, build_metadata.

### Human inputs (tracked with `dvc add`, never produced by a stage)

| input | how it is added |
|---|---|
| `data/raw/sources/` (PDFs, timetable xlsx, EE site HTML) | `dvc add data/raw/sources` |
| `data/raw/course_plans/`, `data/raw/course_plans_manual/` | `dvc add data/raw/course_plans data/raw/course_plans_manual` |
| `data/raw/forms/responses_raw.csv` (Google Forms download) | `dvc add data/raw/forms/responses_raw.csv`, then uncomment `import_forms` and `shifted_forms` in dvc.yaml |
| `data/labels/roundN/export_A1.json`, `export_A2.json`, `adjudication.csv` | `dvc add` each file, then uncomment `adjudicate` and `freeze_gold` in dvc.yaml |

## Where each part lives

| part | what | code | outputs and evidence |
|---|---|---|---|
| A | source collection, raw catalog, cleaning, rules, metadata | `src/collect/` | `data/raw/`, `data/processed/{courses,rules}.json`, `data/metadata.csv`, `supporting_files/A_collection/` |
| B | rule engine, synthetic transcripts, advisory pairs, validation suite | `src/engine/`, `src/queries/make_queries.py`, `src/validate/` | `data/processed/{students,queries}.jsonl`, `supporting_files/B_engine/`, `supporting_files/B_validation/` |
| C | LLM paraphrases, Label Studio tasks, agreement, adjudication, forms | `src/queries/`, `labelstudio/`, `LABELLING_PROTOCOL.md` | `data/processed/queries_para.jsonl`, `data/labels/`, `supporting_files/C_labelling/` |
| D | augmentation with invariance checks, active learning vs random | `src/augment/`, `src/active/` | `data/processed/queries_augmented.jsonl`, `supporting_files/D_augmentation/`, `supporting_files/D_active_learning/` |
| E | splits by student and template, programme holdout, gold test set | `src/split/` | `data/splits/`, `data/gold/`, `supporting_files/E_splits/` |
| F | reproducibility: DVC, environment, handoff, dataset card | `dvc.yaml`, `scripts/` | `ENVIRONMENT.md`, `HANDOFF_A2.md`, `DATASET_CARD.md` |

## Repo map

```
data/                 raw, interim, processed, splits, labels, gold (all DVC tracked)
docs/                 DATA_CONTRACT.md (schemas), DECISIONS.md, DATA_FLOW.md, consent and form docs
labelstudio/          Label Studio config and annotation guidelines v1, v2
prompts/pipeline/     every prompt the code sends to an LLM
prompts/assistant/    instructions given to the coding assistants
src/collect/          Part A extraction and cleaning
src/engine/           rule engine, prerequisite graph, synthetic transcripts
src/queries/          advisory pairs, LLM client and paraphrasing, Label Studio import/export
src/augment/          augmentations and their verification
src/active/           base model answers, disagreement score, AL vs random
src/split/            splits, shifted forms split, gold set, handoff table
src/validate/         validation checks (Pandera, graph, engine)
scripts/              make_submission.sh, check_submission.sh
supporting_files/     logs, tables, plots per part
tests/                pytest suite and fixtures
```

Schemas for every file are in `docs/DATA_CONTRACT.md`. Seeds and run parameters are in `params.yaml`.
