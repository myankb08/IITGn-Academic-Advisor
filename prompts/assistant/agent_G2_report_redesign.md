# Agent G, follow-up: make the report simpler and easier on the eye

User feedback: "make the report simpler and aesthetic, these large tables are very hard to read and understand for
humans". Keep every fact and every number (all still sourced in the evidence index), but change how they are shown.
Follow `prompts/assistant/agent_common_rules.md` (plain prose, no em or en dashes, numbers copied from files).

Design rules for `reports/report.tex`:
1. Body at most 6 pages, aim for 4 to 5. Each Part (A to F) opens with one or two plain sentences saying what was
   done and what it shows, then a small "key numbers" box: 3 to 5 big numbers with a short label each (for example
   "76 | gold test items"). Use tcolorbox or a simple coloured frame if the TeX install has it (check with
   kpsewhich tcolorbox.sty); otherwise a light shaded minipage. One accent colour, used sparingly.
2. No table in the body with more than 5 rows or 4 columns. Prefer a figure or a key-number box over a table.
   The kappa comparison can be a 2x2 table or a tiny bar figure (matplotlib, saved under reports/fig_*.png, drawn by
   a script reports/make_figures.py that reads the evidence files, so the figure is reproducible). Keep the
   confusion-matrix and label-efficiency figures if they read well; drop anything that does not.
3. Move the detailed tables (before/after cleaning, full augmentation table, full split table, AL table) to an
   appendix "Detailed tables", each simplified (round numbers to 2 decimals, short column names, no file paths
   inside tables; put the source file in the caption).
4. Typography: a clean readable font that the install has (try `\usepackage[default]{sourcesanspro}` or
   `\usepackage{libertine}`; fall back to lmodern), 11pt, comfortable line spacing (1.1 to 1.15), clear section
   headings with a little space, short paragraphs. Use `\path{}` or `\texttt{}` with `\allowbreak`-friendly paths;
   keep file paths out of running text where possible (point to the evidence index instead, e.g. "[E12]").
5. Evidence index (Appendix A): keep it complete, but make it readable: group rows by Part with a small heading per
   group, give each row an id (E1, E2, ...) that the body cites in square brackets, two or three columns only
   (id, what, file and field). Every number in the body must appear here.
6. Keep: title block, Overview with the 4 or 5 headline numbers in a key-number box, Limitations as a short bullet
   list, Contributions table (2 rows), Appendix B (AI use) and Appendix C (guideline changes) in short prose.
7. Keep all the macros (\nforms..., \ncommitsH, \ncommitsM, \nmeta...) and their current values; do not change any
   number. Rebuild with reports/build.sh and check: no undefined references, no overfull boxes wider than 5pt,
   body page count.

Report: body pages, total pages, the list of figures made, and anything you could not keep.
