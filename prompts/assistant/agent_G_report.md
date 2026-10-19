# Agent G: Assignment 1 report (report/report.pdf)

Follow `prompts/assistant/agent_common_rules.md` (plain human prose, no em or en dashes, no invented numbers).

Write `reports/report.tex` and build `reports/report.pdf` with pdflatex (run twice). At most 6 pages for the body
(11pt, a4paper, 2 cm margins, compact but readable), then appendices without a page limit. Use booktabs tables.
Figures allowed: `supporting_files/D_active_learning/label_efficiency.png`,
`supporting_files/C_labelling/round1/confusion_decision.png` / round2 (pick what fits). Keep figures small.

Audience: the CS 203 TAs and an AI checker that verifies every number against the file the index points to. So:
every number in the report must be copied from a file in the repo (read the file, do not recompute in your head),
and every number must appear in Appendix A (evidence index) with the exact file path that backs it.

Read first: CS203_Assignment1.pdf text is summarised in docs/; the rubric parts are A Collection (15), B Validation
(20), C Labelling and agreement (25), D Augmentation and active learning (20), E Versioning and splits (10),
F Report and reproducibility (10). Project 4 specifics: curriculum JSON with provenance, prerequisite graph and rule
engine, synthetic transcripts; checks (prereqs exist, no cycles, credit totals, no duplicate codes, transcripts pass,
no student/template in train and test); >= 300 pairs; humans audit LLM paraphrases (accept/edit/reject + error
category), 2 annotators >= 60 items, kappa; >= 30 real Google Form queries as OOD set; augmentations (paraphrase,
typos/abbrev, transcript length/order) verified by the rule engine; active learning prioritising base-model
disagreement vs random; splits by student and programme; shifted split = real form queries; DVC.

Sources to read (all relative to repo root): README.md, DATASET_CARD.md, ENVIRONMENT.md, LABELLING_PROTOCOL.md,
HANDOFF_A2.md, docs/DECISIONS.md, docs/DATA_FLOW.md, docs/CONSENT_AND_LICENSING.md, docs/GOOGLE_FORM.md,
supporting_files/** (A_collection/collection_log.md, cleaning_changes.csv, course_plan_fetch_log.csv,
B_validation/before_after.md and raw|processed|corrupted/results.csv, B_engine/*.json and gold_fix_*.md,
C_labelling/round1|round2/agreement_summary.json, disagreement_analysis.md, kappa_ci.json,
adjudication_proposals.json, adjudication_decisions_export.json, forms_log.md, forms_import_log.json,
D_augmentation/invariance.csv, llm_backend.md, D_active_learning/summary.md, label_efficiency.csv,
E_splits/split_summary.json), data/labels/audited.jsonl, data/gold/GOLD_SHA256.txt, data/metadata.csv (row count),
data/splits/*.csv (counts), params.yaml, dvc.yaml, prompts/ (list of prompt files), git log (for the contribution
table: count commits per author with `git log --format=%an | sort | uniq -c`).
Do not cite anything under tests/fixtures or any file whose name contains "fixture".

Body structure (aim for these weights):
1. Overview (5 lines): task, scope (4 programmes in CS and EE: MTech-CSE, MTech-AI, MTech-EE, MTech-ICDT), what was
   built, headline numbers.
2. Part A Collection: sources and provenance (source doc/page per record, sha256, metadata.csv rows), course plans
   fetched vs login-gated, catalog and rules counts, prerequisites finding (no enforceable PG prerequisite in
   sources; two-tier design; decisions D4/D5), synthetic students, consent and licensing in one paragraph, data flow.
3. Part B Validation: suite size and tooling, before/after table (compact), corrupted-data result, the two gold
   bugs found later by human review (MTech-AI baskets; UG background) as evidence that validation plus review work.
4. Part C Labelling: task and label levels and their order, guidelines v1 -> v2, round 1 and round 2 kappa with
   CIs and raw agreement in one table, main disagreement causes, adjudication process (assistant proposals, human
   final call, counts by decided_by), audit outcome (accept/edit/reject), gold set size and checksum, real form
   queries (count, form versions, how they differ from templates).
5. Part D: augmentation table (invariance rates), active learning table and figure, honest reading (top-k finds more
   failures but one intent; stratified variant added afterwards, reported as such).
6. Part E: DVC (what is tracked, remote), split design and counts table, shifted split, programme holdout, tag.
7. Part F: dataset card summary, software versions summary, labelling protocol summary, rebuild commands.
8. Limitations (short, honest): synthetic students, no enforceable prerequisites, small kappa samples, LLM backends
   mixed (llama.cpp and Kaggle T4, recorded per row), form examples added mid-collection (v1/v2), ICDT list
   incomplete.

Then:
- Contribution table: Hemant (SMH) and Myank (MSB), stating plainly what each did (Myank: first data-loading commit,
  annotator A2 in both rounds, joint adjudication, form distribution if stated in docs; Hemant: everything else, A1).
  Include commit counts per author from git.
- Appendix A, evidence index: a table of every number/claim in the body -> file path (and field or row).
- Appendix B, AI assistance: Claude Code (claude-opus-5-5) built most code via sub-agents (list prompts in
  prompts/assistant/), drafted adjudication proposals (human final call), built the review and kit pages, Google Form
  built in the browser at the user's request; pipeline LLM (Qwen2.5-1.5B-Instruct) prompts in prompts/pipeline/.
  Say what humans did: all labelling, adjudication decisions, scope decisions (docs/DECISIONS.md), form distribution.
- Appendix C: guideline v2 changes (short list), label levels and order.

Leave the form-response numbers as they are now but mark each with a LaTeX macro defined at the top
(\newcommand{\nforms}{...} etc.) so they can be updated in one place after the final form import. Same for any number
that depends on the final dvc repro (metadata rows).

Write a tiny `reports/build.sh` (pdflatex twice, quiet). Report the page count of the body and anything you could
not source.
