# Active learning vs random selection

Pool: 336 pairs (train split of data/splits/*.csv). Base-model failures in the pool: 232. Failure types present: invalid_json 18, hallucinated_code 2, wrong_eligibility 56, wrong_remaining 94, ineligible_recommendation 64.

Score (see src/active/disagreement.py): 3 for invalid JSON, else (1 - Jaccard of course code sets) + 1 for wrong eligibility + 1 for a wrong total credit gap + 1 for any code not in courses.json.

| budget | strategy | failures captured | failure types covered | programmes | intents |
|---|---|---|---|---|---|
| 25 | active_learning | 0.11 (sd 0.00) | 0.60 | 3.0 | 1.0 |
| 25 | random | 0.08 (sd 0.01) | 0.88 | 3.0 | 3.0 |
| 50 | active_learning | 0.22 (sd 0.00) | 0.60 | 3.0 | 1.0 |
| 50 | random | 0.15 (sd 0.01) | 0.92 | 3.0 | 3.0 |
| 100 | active_learning | 0.43 (sd 0.00) | 0.60 | 3.0 | 1.0 |
| 100 | random | 0.30 (sd 0.01) | 0.88 | 3.0 | 3.0 |

Random is the mean over the 5 seeds in seeds.active_learning; AL uses the same seeds only to break ties. A budget at or above the number of failures lets AL capture all of them, so the interesting comparison is at budgets below that number.
