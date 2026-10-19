# Handoff to Assignment 2

What Assignment 2 (training and evaluating the advisory model) can rely on. Everything listed here is produced by
`dvc repro` from the frozen inputs, and the files are fixed at git tag `a1-final` together with `dvc.lock`.
Do not edit these files in place: change the code or params, rerun the pipeline, and refresh this page.

## Frozen files

Refresh with `.venv/bin/python -m src.split.handoff` after the last `dvc repro` (it rewrites only this table).

<!-- FROZEN_FILES_START -->
| file | rows | sha256 |
|---|---|---|
| `params.yaml` |  | `c1a9b9561ca8cb1268d011977443110c8f75036aad5abdef99b3224a548db652` |
| `data/processed/courses.json` |  | `b6118a747d544235751005af3d115a5eab80959a5b1a02896fa6cda2391420e3` |
| `data/processed/rules.json` |  | `00ef71f6433f3bc71e2a29d82604e6d646df65f90d136b9cfc2f866ba35914a0` |
| `data/processed/prereq_graph.json` |  | `db94f3d3c36a086bb08f8da9caa29b130cb6408443f94f861bbae224768197cc` |
| `data/processed/students.jsonl` | 180 | `544322fc9acfda301dd60771e2c6a2c6bf72f3972ef4b7f6e4485b248005ce7f` |
| `data/processed/students_augmented.jsonl` | 347 | `015cdb1cda781eed8b0246dab93db4df533fc4b9c7a978bb2af70c1676bbfbc9` |
| `data/processed/queries.jsonl` | 600 | `3b4653aab793befe950cfcb6f940f7f73f40da7a4f9613340e194bd3c81e6059` |
| `data/processed/queries_para.jsonl` | 600 | `2451af9d7c9bf5cd405fe6b1d337c48a36276409c242ef87d7b7610e8bb8257e` |
| `data/processed/queries_augmented.jsonl` | 2126 | `28c58d6a90c9d2f3add0122aca3e9ae58a68310180b7539a1496b9f1f5b116dd` |
| `data/splits/train.csv` | 1205 | `a6054ebcb025731745e7f17b26e826f3c0ab0ed7c9e6ca5fdaf75a03550ff7b5` |
| `data/splits/val.csv` | 280 | `7ce8497c8029659ddec10a0efa1b32dac2e8969254ae4d8c62c52abb26a3122e` |
| `data/splits/test.csv` | 353 | `22d859eda38e142c3495a6f923e9ac651ed38d6065b6862ed66c26064d526702` |
| `data/splits/programme_holdout.csv` | 288 | `5f82ec424dd573ad133ac2ee52b2d704939d1f80ce62dea7a29e0eb20dd478b0` |
| `data/splits/shifted_forms.csv` | 10 | `28c096a6e951788f094c1b9cbbe5013a6c00ba93cf53c9b49e978846e436f68c` |
| `data/labels/audited.jsonl` | 80 | `4615a5bbd9e9425a12bfb22c4dde2e301c8a1b021a66dc159986497302b1eae5` |
| `data/gold/gold_test.jsonl` | 76 | `cd2e08dcb56f5716b06981e096c3c93fd417abab1989b5d22d45befeafbc383f` |
<!-- FROZEN_FILES_END -->

Gold test set checksum (filled by `src.split.freeze_gold`, also in `data/gold/GOLD_SHA256.txt`):
<!-- GOLD_SHA256 -->`cd2e08dcb56f5716b06981e096c3c93fd417abab1989b5d22d45befeafbc383f` (76 items)<!-- /GOLD_SHA256 -->

## Splits

Students are assigned first by `src/split/assign_students.py` (`seeds.splits` = 207, written to
`data/splits/assignment/students.csv` and `templates.csv`), then `src/queries/make_queries.py` renders every pair with
a surface template allowed in its student's split, and `src/split/make_splits.py` writes the manifests and checks the
rules. No pair is dropped. Manifests in `data/splits/` have the columns
`query_id, student_id, template_family, template_id, programme, split`. Counts and overlap checks:
`supporting_files/E_splits/split_summary.json`.

| split | rule | students | pairs | remaining_core / eligibility / elective_rec | eligible / not | MTech-CSE / AI / EE / ICDT |
|---|---|---|---|---|---|---|
| train | 65% of each programme's students (CSE, AI, EE), non-held-out templates | 101 | 336 | 112 / 112 / 112 | 56 / 56 | 127 / 90 / 119 / 0 |
| val | 15% of each programme's students, non-held-out templates | 24 | 80 | 27 / 26 / 27 | 13 / 13 | 35 / 21 / 24 / 0 |
| test | 20% of each programme's students, held-out templates only | 31 | 102 | 34 / 34 / 34 | 17 / 17 | 49 / 21 / 32 / 0 |
| programme_holdout | every MTech-ICDT student, any template | 24 | 82 | 27 / 28 / 27 | 14 / 14 | 0 / 0 / 0 / 82 |
| shifted (`shifted_forms.csv`) | real Google Forms questions (`src/split/shifted_forms.py`), no gold answers | n/a | 19 | by student-chosen kind: remaining 9, eligibility 2, elective 5, other 3; provenance: 10 self-submitted, 9 entered by hem436 after ChatGPT rewording (filter on `provenance` for the students' own wording) | n/a | 8 / 3 / 5 / 3 |

- Grouping: a student's pairs all go to one split, so no student is in two splits.
- Pair slots: for each intent, every pair slot gets a split in proportion to the students in that split (seeded),
  then a student from that split. Eligibility slots come in eligible / not-eligible pairs that share a split, so every
  split is balanced on eligibility.
- Templates: in each of the 7 template families one surface template is test-only: `el_can_register_t1`,
  `el_prereq_check_t1`, `er_basket_fill_t1`, `er_next_semester_t2`, `rc_core_courses_t3`, `rc_credit_gap_t4`,
  `rc_degree_audit_t3`. Test pairs use only these, train and val pairs never do (a seeded choice among the
  others). Templates are wording only, the gold answer depends on (student, intent, target course). Template
  families are shared on purpose: the test checks generalisation to new wording of a known question type.
- Programme shift: MTech-ICDT is held out because it is the smallest programme (24 of 180 students) and the only one
  with no streams, under EE department rules (discipline list instead of stream core and baskets, 8-credit
  below-600 cap, MOOCs count). A model trained on CS and EE stream programmes is evaluated on it as an unseen
  programme.
- Augmented children (`parent_query_id` set) take the split of their root parent and are listed in the same
  manifests. Children whose parent changed since augmentation ran are left out and listed in
  `supporting_files/E_splits/dropped_rows.csv` until `augment` is rerun.
- Both labelling rounds (40 + 40 items) are drawn from the test split only, stratified by intent
  (`src/queries/to_labelstudio.py`), so the audited items are the gold test set.

## Labels

Label levels, filled in this order in Label Studio (`labelstudio/config_v1.xml`, guidelines v1 and v2):
1. `decision`: accept | edit | reject
2. `error_category`: none, hallucinated_course, wrong_fact_or_policy, meaning_drift, incomplete_justification,
   fluency, ambiguous_query
3. `edit_text`: the corrected paraphrased query and/or justification (only when decision = edit)

Two annotators (A1, A2) label the same 40 items per round, two disjoint rounds. Disagreements are settled in
`data/labels/roundN/adjudication.csv`, merged into `data/labels/audited.jsonl` by `src/queries/adjudicate.py`.

## Gold test set

`data/gold/gold_test.jsonl`, built by `src/split/freeze_gold.py`: audited items whose query is in the test split
and whose final decision is accept or edit. One row per item with the query record (`query_id, student_id,
template_id, template_family, intent, target_course, query_text, gold_json, gold_text, para_model,
para_prompt_id`), the audited text (`para_query, para_justification`), and the audit result (`final_decision,
final_category, final_edit, decided_by, item_id, round, guidelines_version`, `split` = test). Use
`audited_query` and `audited_justification`: they hold the human-corrected text for edited items and the
paraphrase for accepted ones (rejected items are not in the file). Check the file against `data/gold/GOLD_SHA256.txt` before use:
`sha256sum -c data/gold/GOLD_SHA256.txt`.

## How to load

```python
import json, pandas as pd

def jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]

courses  = json.load(open("data/processed/courses.json"))          # list of course records
rules    = json.load(open("data/processed/rules.json"))["rules"]    # rule_id -> record with value and source
students = {s["student_id"]: s for s in jsonl("data/processed/students.jsonl")
            + jsonl("data/processed/students_augmented.jsonl")}  # derived students live in the second file
pairs    = {q["query_id"]: q for q in jsonl("data/processed/queries_para.jsonl")}
pairs.update({q["query_id"]: q for q in jsonl("data/processed/queries_augmented.jsonl") if q.get("parent_query_id")})
splits   = pd.concat([pd.read_csv(f"data/splits/{s}.csv") for s in ["train", "val", "test", "programme_holdout"]])
train    = [pairs[q] for q in splits.query_id[splits.split == "train"] if q in pairs]
gold     = jsonl("data/gold/gold_test.jsonl")
```

To recompute any stored answer use the rule engine: `from src.engine.rule_engine import eligibility,
remaining_requirements, recommend_electives` with `src.engine.catalog.load_catalog()`, passing `gold_json["term"]`
for eligibility and recommendations. Field definitions are in `docs/DATA_CONTRACT.md`.
