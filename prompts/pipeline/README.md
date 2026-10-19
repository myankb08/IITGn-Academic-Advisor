# Pipeline prompts

These are the exact prompt templates the code sends to the language model. `src/queries/llm_client.py`
(`load_prompt`) reads `prompts/pipeline/<prompt_id>.txt` and fills its placeholders; no prompt text lives in the code.
The files are kept unchanged because the LLM cache (`data/interim/llm_cache.jsonl`) is keyed on the prompt id and
the filled prompt, so model and version details are listed here instead of inside the files.

## Model
Qwen2.5-1.5B-Instruct, one model for every prompt:
- local: Ollama tag `qwen2.5:1.5b`, digest `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`,
  GGUF blob sha256 `183715c435899236895da3869489cc30ac241476b4971a20285b1a462818a5b4`, served by llama.cpp
  `llama-server` b11643 because Ollama 0.1.38 could not load the qwen2 tokenizer;
- Kaggle: Hugging Face `Qwen/Qwen2.5-1.5B-Instruct` at revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`,
  transformers 5.16.1, torch 2.11.0+cu128, Tesla T4, fp16.

Every cached answer records the backend, model digest or revision, seed and batch position
(see `supporting_files/D_augmentation/llm_backend.md`).

## Prompts

| prompt id | sent by | backends used | sampling | output |
|---|---|---|---|---|
| `paraphrase_query_v1` | `src/queries/paraphrase_llm.py` | llama.cpp (all test-split rows), Kaggle (the rest) | temperature 0.7, seed `seeds.paraphrase` (205) | `para_query` in `data/processed/queries_para.jsonl` |
| `paraphrase_justification_v1` | `src/queries/paraphrase_llm.py` | llama.cpp (all test-split rows and the 53 D5 re-runs), Kaggle (the rest) | temperature 0.7, seed 205 | `para_justification` in `data/processed/queries_para.jsonl` |
| `augment_paraphrase_v1` | `src/augment/paraphrase.py` | Kaggle | temperature 0.7, seed `seeds.augmentation` (206) | `data/interim/aug_paraphrase.jsonl`, checked by `src/augment/verify.py` |
| `base_model_answer_v1` | `src/active/base_model_answers.py` | Kaggle (4 cache entries come from early llama.cpp test calls) | temperature 0 (greedy) | `data/interim/base_model_answers.jsonl` |

Which backend produced each paraphrase is stored per row in `para_backend`.

The cache also holds entries no output uses: answers for query texts from before the final 600-pair regeneration,
and two entries with prompt id `t_check`, which were throughput tests of the llama.cpp server (a fixed short test
prompt, not a template in this folder). Replay only looks up the prompts listed above.

## What the model receives besides these files
Each prompt is sent as a single user message with no system message. Qwen2.5's chat template then inserts its
built-in default system prompt ("You are Qwen, created by Alibaba Cloud. You are a helpful assistant."), on both
backends. No other text is added.
