# LLM backend notes (environment)

## Why Ollama was not used directly

The machine has Ollama 0.1.38 (`/usr/local/bin/ollama`) with `qwen2.5:1.5b` pulled. Every request
to that model fails with HTTP 500 `llama runner process has terminated: signal: aborted (core dumped)`.
The runner log of a test server (`OLLAMA_HOST=127.0.0.1:11435 ollama serve`) shows the cause:

```
llama_model_load: error loading model: error loading model vocabulary: unknown pre-tokenizer type: 'qwen2'
```

Ollama 0.1.38 is older than qwen2 tokenizer support. Upgrading needs sudo, which is not available,
so the same weights were served with llama.cpp instead.

## Local backend actually used (`LLM_BACKEND=llamacpp`)

- Release: llama.cpp `b11643` (commit `1ddc26255`), CPU build for Ubuntu x64
- URL: https://github.com/ggml-org/llama.cpp/releases/download/b11643/llama-b11643-bin-ubuntu-x64.tar.gz
- sha256 of the downloaded archive: `9cf44cdf70003662977342789105a14e8349b4718f1d731450acecec27141b3d`
- sha256 of the extracted `llama-server` binary: `7c2fd424738fc82ef9fc99969bd6a917df1b2dc09e57bc8aeef6dc69214e454d`
- Kept outside the repo, in the session scratchpad. No other binaries were downloaded.
- Command: `llama-server -m ~/.ollama/models/blobs/sha256-183715c4... --port 8091 --host 127.0.0.1 -t 8 -c 8192 -np 1`
- Endpoint: `/v1/chat/completions` with `seed`, `temperature`, `max_tokens`, `cache_prompt: true`,
  and `response_format: json_object` for the base-model answers. The chat template is the one stored in the GGUF.

## Model identity

- Ollama tag: `qwen2.5:1.5b`, tag digest `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`
  (from `/api/tags`). This digest is the `model_digest` in every cache row and output.
- GGUF weights: `sha256:183715c435899236895da3869489cc30ac241476b4971a20285b1a462818a5b4`
  (Q4_K_M, 1.5B, from the Ollama manifest). Both llama.cpp and Ollama load this same file.
  Each cache row stores it as `gguf_blob`.

## Kaggle backend (`LLM_BACKEND=kaggle-transformers`)

- transformers `Qwen/Qwen2.5-1.5B-Instruct` at revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`, fp16 on a T4.
- `model_digest` is `hf:Qwen/Qwen2.5-1.5B-Instruct@989aa7980e4cf806f80c7fef2b1adb7bc71aa306`. The torch,
  transformers and GPU names are written to each cache row (`backend`) and to `kaggle_out/environment.json`.
- The JSON format is not enforced by a grammar here, unlike llama.cpp. The prompt asks for JSON in both cases.

## Same prompts and seeds on every backend

All backends get the rendered prompt file as a single user chat message, with the same seed
(`seeds.paraphrase`, `seeds.augmentation` or `seeds.active_learning[0]`), the same temperature
(`llm.temperature` or `llm.base_temperature`) and the same token cap. The backend name is part of
the cache input hash, so rows from different backends sit side by side in `data/interim/llm_cache.jsonl`
and are never confused. Outputs are not bit-identical across backends: quantisation (Q4_K_M vs fp16)
and sampler implementations differ.

## Measured local throughput

From the 5 timing calls: prompt evaluation about 35 tokens/s and generation about 5 to 8 tokens/s,
on 8 CPU cores shared with other work. A query paraphrase takes about 10 s and a justification rewrite
15 to 25 s, so the full local run (402 + 402 calls, then 175 base answers and 120 augment paraphrases)
takes roughly 5 to 6 hours.
