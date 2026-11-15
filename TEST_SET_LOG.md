# Test set log

Every evaluation on the test split, the gold test set, the programme holdout or the shifted split, including each
Part E gate check. Gold checksum must stay `cd2e08dcb56f5716b06981e096c3c93fd417abab1989b5d22d45befeafbc383f`.

| date (UTC) | split | model version | run id | reason |
|---|---|---|---|---|
| 2026-11-10 17:19 | shifted | advisor@production (local scratch registry v1 = debug run al100-e1) | 7aa18747216d4c8f9dff539152cfce3f | DEBUG: replay code test on this PC with the debug model, results discarded |
| 2026-11-10 18:08 | test | trivial (trivial) | - | Part C final comparison: baseline |
| 2026-11-10 18:08 | gold | trivial (trivial) | - | Part C final comparison: baseline |
| 2026-11-10 18:08 | shifted | trivial (trivial) | - | Part C final comparison: baseline |
| 2026-11-10 18:13 | test | zero_shot (zero_shot) | - | Part C final comparison: baseline |
| 2026-11-10 18:14 | gold | zero_shot (zero_shot) | - | Part C final comparison: baseline |
| 2026-11-10 18:16 | shifted | zero_shot (zero_shot) | - | Part C final comparison: baseline |
| 2026-11-10 18:17 | test | retrieval (retrieval) | - | Part C final comparison: baseline |
| 2026-11-10 18:18 | gold | retrieval (retrieval) | - | Part C final comparison: baseline |
| 2026-11-10 18:21 | shifted | retrieval (retrieval) | - | Part C final comparison: baseline |
| 2026-11-10 18:23 | test | few_shot (few_shot) | - | Part C final comparison: baseline |
| 2026-11-10 18:24 | gold | few_shot (few_shot) | - | Part C final comparison: baseline |
| 2026-11-10 18:27 | shifted | few_shot (few_shot) | - | Part C final comparison: baseline |
| 2026-11-11 04:50 | gold | advisor@staging (advisor_v1) | cb7c02b778d342e2b5a30f163ac8ee74 | Part C final evaluation of the selected model (staging v1) |
| 2026-11-11 04:57 | test | advisor@staging (advisor_v1) | cb7c02b778d342e2b5a30f163ac8ee74 | Part C final evaluation of the selected model (staging v1) |
| 2026-11-11 05:02 | shifted | advisor@staging (advisor_v1) | cb7c02b778d342e2b5a30f163ac8ee74 | Part C final evaluation of the selected model (staging v1) |
| 2026-11-11 05:26 | shifted | advisor@production (advisor_v1) | cb7c02b778d342e2b5a30f163ac8ee74 | Part E replay: labelled set_f1 per window |
| 2026-11-11 11:08 | shifted | advisor@candidate (advisor_v2) | d12c4b8809ae462f88d5464735de76c4 | Part E gate check r1 |
| 2026-11-11 11:10 | gold | advisor@candidate (advisor_v2) | d12c4b8809ae462f88d5464735de76c4 | Part E gate check r1 |
| 2026-11-11 11:32 | shifted | advisor@candidate (advisor_v3) | 379b73e75c984ea9a18273d8e5927651 | Part E gate check r2 |
| 2026-11-11 11:35 | gold | advisor@candidate (advisor_v3) | 379b73e75c984ea9a18273d8e5927651 | Part E gate check r2 |
| 2026-11-11 12:17 | test | advisor@reproduce (advisor_v4) | 46c2f3f095df43e18366f313c5b5b07e | reproduction |
| 2026-11-11 12:20 | gold | advisor@reproduce (advisor_v4) | 46c2f3f095df43e18366f313c5b5b07e | reproduction |
| 2026-11-11 12:27 | shifted | advisor@reproduce (advisor_v4) | 46c2f3f095df43e18366f313c5b5b07e | reproduction |
| 2026-11-11 13:34 | test | trivial (trivial) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | gold | trivial (trivial) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | gold_a1 | trivial (trivial) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | shifted | trivial (trivial) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | test | zero_shot (zero_shot) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | gold | zero_shot (zero_shot) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | gold_a1 | zero_shot (zero_shot) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | shifted | zero_shot (zero_shot) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | test | few_shot (few_shot) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | gold | few_shot (few_shot) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | gold_a1 | few_shot (few_shot) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | shifted | few_shot (few_shot) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | test | retrieval (retrieval) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | gold | retrieval (retrieval) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | gold_a1 | retrieval (retrieval) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | shifted | retrieval (retrieval) | - | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:35 | test | advisor/1 (advisor_v1) | cb7c02b778d342e2b5a30f163ac8ee74 | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:36 | gold | advisor/1 (advisor_v1) | cb7c02b778d342e2b5a30f163ac8ee74 | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:36 | gold_a1 | advisor/1 (advisor_v1) | cb7c02b778d342e2b5a30f163ac8ee74 | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 13:36 | shifted | advisor/1 (advisor_v1) | cb7c02b778d342e2b5a30f163ac8ee74 | D14: rescore on D6 labels (gold_a1: original A1 labels) (rescored saved predictions) |
| 2026-11-11 16:17 | shifted | advisor@candidate (advisor_v10) | aa644d3c4b984c7e8f19446c7c060a72 | Part E gate check d6r1 |
| 2026-11-11 16:19 | gold | advisor@candidate (advisor_v10) | aa644d3c4b984c7e8f19446c7c060a72 | Part E gate check d6r1 |
| 2026-11-11 16:35 | shifted | advisor/1 (advisor_v1) | cb7c02b778d342e2b5a30f163ac8ee74 | Part E replay: labelled set_f1 per window |
| 2026-11-11 16:49 | shifted | advisor@production (advisor_v10) | aa644d3c4b984c7e8f19446c7c060a72 | Part E replay: labelled set_f1 per window |
| 2026-11-11 17:01 | test | advisor@production (advisor_v10) | aa644d3c4b984c7e8f19446c7c060a72 | deployed model (v10, promoted in Part E): test for the model card |
| 2026-11-11 17:01 | gold_a1 | advisor@production (advisor_v10) | aa644d3c4b984c7e8f19446c7c060a72 | deployed model v10: gold on original A1 labels (rescored saved predictions) |
| 2026-11-15 | gold, test | advisor_v1, advisor_v10 (saved predictions, no new run) | cb7c02b778d342e2b5a30f163ac8ee74, aa644d3c4b984c7e8f19446c7c060a72 | error review (myankb08) found that ES 643 is listed as PH 643 in the Sem-I 2026-27 timetable, so the "not offered" labels of gold Q0320, Q0362 (and test Q0320, Q0320-L/R/T, Q0362, Q0362-T) are very likely wrong; counted the effect on gold exact match from saved scores: v1 0.750 unchanged, v10 0.750 to 0.724. Labels, gold file and model choice not changed |
