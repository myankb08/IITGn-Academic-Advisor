# Validation results: corrupted

Checks run: 25. fail: 12, pass: 12, warn: 1.

| check_id | description | requirement | target | status | n_failures | note |
|---|---|---|---|---|---|---|
| V01 | Records match the data contract schema and types (Pandera) | general: schema and types | courses.json | pass | 0 |  |
| V02 | Course codes match '<PREFIX> <NNN>[-<ROMAN>]' or 'REQ-*' | general: code format regex | courses.json | pass | 0 |  |
| V03 | Credits are integers in 1..16 (0 only where rules.json states 0; ug_background excluded) | general: value ranges (credits) | courses.json | pass | 0 | zero-credit codes allowed by rules.json: ['PE 600'] |
| V04 | level is first digit of the course number * 100, null only for REQ-* placeholders | general: value ranges (level) | courses.json | pass | 0 |  |
| V05 | Required fields are not null or empty | general: missing values | courses.json, students.jsonl, queries.jsonl | pass | 0 |  |
| V06 | No course code appears twice (raw: within one source document) | spec: no course code appears twice | courses.json | fail | 1 |  |
| V07 | No exact duplicate records (all content fields equal, provenance ignored) | general: exact duplicates | courses.json | pass | 0 |  |
| V08 | Course titles agree with the timetable title for the same code (catches typos like 'Algrithms') | general: spelling / title consistency against timetable | titles vs timetable_rows.jsonl | fail | 1 | typo when rapidfuzz ratio >= 85 and < 100 (case-insensitive) |
| V09 | Titles have no leading/trailing whitespace, double spaces or trailing punctuation | general: text hygiene | titles | pass | 0 |  |
| V10 | No two different codes have near-duplicate titles (rapidfuzz token_sort_ratio >= 92) | general: near-duplicate titles (warning, needs human review) | titles | warn | 2 | warning only: cross-listed UG/PG or special-topics versions can share a title |
| V11 | Every prerequisite code exists in courses.json | spec: every prerequisite code exists | courses.json prerequisites and recommended_background | fail | 1 |  |
| V12 | The prerequisite graph has no cycles (and no self loops) | spec: prerequisite graph is acyclic | courses.json prerequisites | fail | 1 | 105 nodes, 4 edges |
| V13 | Credit totals agree with the handbook: every total is 82, per-track minimums fit in it, splits sum to it | spec: credit totals match the handbook | rules.json | fail | 1 | coursework+thesis+project minimums: {"MTech-AI/thesis": 64, "MTech-AI/coursework": 64, "MTech-CSE/thesis": 64, "MTech-CSE/coursework": 64, "MTech-EE/thesis": 82, "MTech-EE/coursework": 64, "MTech-ICDT/thesis": 82, "MTech-ICDT/coursework": 64}; credits above these minimums up to 82 are free choice (Adv5 p1 states minimums only) |
| V14 | Structure courses agree with rules: compulsory and core lists, core = 8 credits, baskets can meet minimums, rule codes exist | spec: compulsory credits, basket minimums | courses.json vs rules.json | pass | 0 | streams with core lists: ['AI/ML', 'Systems', 'Theory'] |
| V15 | Course credits and L-T-P agree with the timetable row where both exist | spec: course credits agree with timetable L-T-P-C | courses.json vs timetable_rows.jsonl | pass | 0 |  |
| V16 | Every rule has a value or not_stated, plus source_doc and source_page; course record hashes match | general: provenance integrity | rules.json, courses.json | pass | 0 |  |
| V17 | Students and transcript entries match the schema (Pandera) | general: schema and types (students) | students.jsonl | pass | 0 |  |
| V18 | Synthetic transcripts have no prerequisite violations (engine validate_transcript) | spec: transcripts pass the rule engine (prerequisites) | students.jsonl | fail | 6 |  |
| V19 | Transcripts respect credit caps: below-600 course cap and per-semester cap if stated | spec: credit caps respected, below-600 cap | students.jsonl | fail | 1 | per-semester cap not stated in sources (rules.json not_stated), only below-600 cap is enforced |
| V20 | Transcripts have no other engine violations (unknown code, duplicate pass, credit mismatch, parity, term range) | spec: transcripts pass the rule engine | students.jsonl | fail | 5 |  |
| V21 | Queries match the schema; intent, augmentation and template fields valid (Pandera) | general: label validity (intent) and schema | queries.jsonl | pass | 0 |  |
| V22 | Stored gold_json equals the rule engine output recomputed from the student | spec: gold answers recomputed by the engine equal stored gold_json | queries.jsonl | fail | 5 | 402 recomputed, 0 skipped (missing student or transcript_length augmentation) |
| V23 | Query text (and paraphrase) does not leak gold answer markers or the gold text | spec: query text contains no leaked gold answer marker | queries.jsonl | fail | 1 |  |
| V24 | Audited labels use allowed decisions and error categories, and edits carry text | general: label validity (decisions, error categories) | audited.jsonl | fail | 1 |  |
| V25 | No student or template in both train and test; held-out programmes and students not in train | spec: no student or template in both train and test | splits | fail | 1 | 985 rows; train vs test on student_id and template_id, train vs other held-out splits (['programme_holdout']) on student_id and programme; template families shared by train and test (by design): 7 |

## Injected faults

Caught 15 of 15 injected faults.

| fault_id | description | check_id | check_status | caught |
|---|---|---|---|---|
| F01 | prerequisite cycle EE 691-VII <-> EE 633 | V12 | fail | True |
| F02 | unknown prerequisite ZZ 901 on CS 691-XIV | V11 | fail | True |
| F03 | transcript prerequisite violation: S0002 took ES 417 before its (injected) prerequisite CS 610 | V18 | fail | True |
| F04 | duplicate course code ES 604 | V06 | fail | True |
| F05 | total_min_credits changed from 82 to 80 | V13 | fail | True |
| F06 | below-600 cap breach: S0148 gets CS 329, CS 434, CS 435 | V19 | fail | True |
| F07 | synth_transcripts --inject-violations DUPLICATE_COURSE on S0004 | V20 | fail | True |
| F08 | synth_transcripts --inject-violations UNKNOWN_CODE on S0007 | V20 | fail | True |
| F09 | synth_transcripts --inject-violations NOT_OFFERED_IN_TERM on S0017 | V20 | fail | True |
| F10 | synth_transcripts --inject-violations CREDIT_MISMATCH on S0019 | V20 | fail | True |
| F11 | synth_transcripts --inject-violations NOT_OFFERED_IN_PARITY on S0060 | V20 | fail | True |
| F12 | gold_json of Q0198 flipped eligible | V22 | fail | True |
| F13 | gold answer marker appended to Q0082 query_text | V23 | fail | True |
| F14 | student S0149-R copied into train (data/splits) | V25 | fail | True |
| F15 | label R1-FXQ0086 final_decision 'maybe' (copy of the Part C fixture) | V24 | fail | True |

Failure examples (first 8 per check) are in results.csv, all failures in failures.json.
