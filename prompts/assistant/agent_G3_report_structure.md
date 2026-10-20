# Agent G, follow-up: restructure the report to the assignment's format

Follow `prompts/assistant/agent_common_rules.md`. Start from the current `reports/report.tex` (commit 9f2012d).
Keep every fact, number, macro value and evidence id; change structure and add diagrams. Only write in `reports/`.

The brief (CS203_Assignment1.pdf, Section 9) says report.pdf is at most 6 pages plus appendices and covers:
Parts A to F (method, validation findings, agreement results, augmentation and active-learning results, splits,
the dataset card, a summary of software versions and the labelling protocol), a contribution table, an appendix that
indexes the submission (each number and finding to the file in the zip), and an appendix on AI assistance.

Use exactly this structure; subheadings are the brief's own requirement names, so a grader can tick them off:

1 Introduction (3 to 4 lines, plus the existing headline key-number box)
2 Part A: Collection and instrumentation
  2.1 Collection pipeline (metadata.csv fields: source, timestamp, collector, tool version, content hash; curriculum
      JSON with source document and page; prerequisite graph; rule engine; synthetic transcripts)
  2.2 Consent and licensing (consent register, anonymisation, licences of institute documents)
  2.3 Data flow: DIAGRAM required (sources -> extraction -> catalog/rules -> rule engine -> students -> pairs ->
      LLM paraphrase -> Label Studio audit -> splits/gold; and the metadata.csv branch). Draw it with TikZ inside the
      .tex (tikz is installed) or graphviz (`dot` is installed; keep the .dot source in reports/ and render it in
      reports/build.sh). Mention the collection log.
3 Part B: Data validation
  3.1 Validation suite (25 checks, tools, which Project 4 checks they cover)
  3.2 Before and after (the existing figure; full table in the detailed-tables appendix)
  3.3 Corrupted data (15 of 15 caught, one not injected and why)
  3.4 What human review added (the two gold bugs)
4 Part C: Labelling and agreement
  4.1 Guidelines (v1 and v2, what changed)
  4.2 Independent annotation (who, tool, items, seed); a small DIAGRAM of the labelling workflow
      (pairs -> paraphrase -> round 1 (v1) -> disagreement analysis -> v2 -> round 2 -> adjudication -> gold)
  4.3 Label order
  4.4 Agreement (kappa before/after with CIs, confusion matrix figure, disagreement analysis summary)
  4.5 Gold test set (76 items, checksum)
  4.6 Real queries (19, provenance, OOD set)
5 Part D: Augmentation and active learning
  5.1 Augmentation (figure; slot check)
  5.2 Active learning (figure; precision 1 by construction; coverage)
6 Part E: Versioning and splits
  6.1 Versioning (DVC, remote, reproducibility)
  6.2 Splits (by student and programme, held-out templates, shifted split); the existing split figure counts as the
      diagram, or replace it with a clearer one showing students -> train/val/test, ICDT -> holdout, forms -> shifted
  6.3 Final tag (a1-final)
7 Part F: Report and reproducibility
  7.1 Dataset card (sources, size, class/intent balance, known biases): a compact summary
  7.2 Data reproducibility (software versions, models, seeds)
  7.3 Label reproducibility (labelling protocol summary)
  7.4 Repository and README (clean repo, 4-command rebuild)
8 Limitations (short bullets)
9 Contribution table
Appendix A Evidence index (keep E-ids; update grouping to the new section numbers)
Appendix B AI assistance
Appendix C Guideline v2 changes and label levels
Appendix D Detailed tables

Rules: body (sections 1 to 9) at most 6 pages; keep the readable style (key-number boxes, short paragraphs, no
large tables in the body). Diagrams small and clean, one accent colour, readable at print size. No em or en
dashes. Keep \ncommitsH and \ncommitsM as they are. Rebuild with reports/build.sh; report body pages, total pages,
overfull boxes, and confirm every \ev{} reference resolves.
