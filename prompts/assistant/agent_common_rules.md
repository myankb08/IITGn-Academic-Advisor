# Common rules for every sub-agent (Claude Code, claude-opus-5-5)

Repo root: the directory containing params.yaml. Python: `.venv/bin/python` (3.10). Install extra packages with `.venv/bin/pip install` and add them pinned to requirements.txt (exact `==` versions).

1. Read `docs/DATA_CONTRACT.md` and `params.yaml` first. Follow the schemas exactly. If you must extend a schema, add the field to DATA_CONTRACT.md in the same change.
2. Relative paths only, resolved from the repo root (use `Path(__file__).resolve().parents[N]`). No hard-coded absolute paths.
3. Every random choice reads its seed from params.yaml.
4. Every script is runnable as `.venv/bin/python -m src.<pkg>.<module>` and is idempotent.
5. Never invent data that should come from a human (annotations, survey answers). Never invent facts about courses: if a prerequisite or rule is not in a source, mark it `manual` with the reason, or leave it empty.
6. Raw data stays untouched. Fixes happen in a separate cleaning step that logs every change.
7. Any prompt your code sends to an LLM lives as a file in `prompts/pipeline/` and the code loads it from there. Record model name and tag/digest with each output.
8. Write logs and evidence (tables, plots, JSON outputs) under `supporting_files/<part>/`.
9. Prose you write in markdown: plain human style, no em dashes or en dashes (use commas, colons, or hyphens).
10. Do not run git commands. Do not delete files you did not create.
11. Code style: blank lines fully empty, follow the surrounding code idiom, short docstrings, no over-commenting.
12. End with a short report: files created, commands to run, numbers produced, anything you could not do and why.
