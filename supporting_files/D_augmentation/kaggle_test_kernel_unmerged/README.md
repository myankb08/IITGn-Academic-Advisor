# Kaggle test-split kernel output (not merged)

Downloaded by hem436 from the Kaggle notebook `hemant436/course-advisory-llm-test` (version 2) on 2026-10-18 ~01:12 IST.
The archive was a GNU tar named out.zip; only its logs are kept here (the jsonl outputs are not used).

- Ran on Tesla T4, torch 2.11.0+cu128, transformers 5.16.1, Qwen/Qwen2.5-1.5B-Instruct @ 989aa79.
- 172 new calls, 2.51 s per call, 436 s of generation; the long RUNNING time on Kaggle was setup and waiting, not generation.
- Not merged: its inputs were built before the MTech-AI gold fix (input hash differs from the final queries.jsonl), and the test split was already complete from the local llama.cpp backend, so merging would mix two backends for the same items.
