"""Local LLM client with a deterministic on-disk cache keyed by (prompt id, input hash, model digest).

Backends (env LLM_BACKEND), all fed the same prompt files as one user chat message:
- "ollama": Ollama /api/chat on http://localhost:11434 (default).
- "llamacpp": a llama.cpp llama-server /v1/chat/completions loaded with the Ollama GGUF blob of the
  tag. Used because the local Ollama 0.1.38 cannot load qwen2 (see supporting_files/D_augmentation/llm_backend.md).
- "kaggle-transformers": transformers Qwen/Qwen2.5-1.5B-Instruct at a pinned revision, in process
  (Kaggle GPU). Without torch/transformers installed it is cache-only: a miss raises.
For GGUF backends the model digest is the Ollama tag digest (the GGUF blob sha256 is stored too);
for transformers it is "hf:<repo>@<revision>". Cache rows from different backends never collide
because the backend is part of the input hash.
"""
import hashlib
import json
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = ROOT / "prompts" / "pipeline"
CACHE_PATH = ROOT / "data" / "interim" / "llm_cache.jsonl"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
LLAMACPP_URL = os.environ.get("LLAMACPP_URL", "http://127.0.0.1:8091")
OLLAMA_MODELS = Path(os.environ.get("OLLAMA_MODELS", Path.home() / ".ollama" / "models"))
HF_REPO = "Qwen/Qwen2.5-1.5B-Instruct"
HF_REVISION = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
HF_FOR_TAG = {"qwen2.5:1.5b": (HF_REPO, HF_REVISION)}


def load_prompt(prompt_id):
    """Prompt text from prompts/pipeline/<prompt_id>.txt."""
    return (PROMPTS / f"{prompt_id}.txt").read_text()


def render(template, **fields):
    out = template
    for k, v in fields.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def manifest_path(model):
    name, _, tag = model.partition(":")
    return OLLAMA_MODELS / "manifests" / "registry.ollama.ai" / "library" / name / (tag or "latest")


def gguf_blob(model):
    """sha256 of the GGUF weights layer of an Ollama tag, from its local manifest."""
    manifest = manifest_path(model)
    if not manifest.exists():
        return None
    layers = json.loads(manifest.read_text()).get("layers", [])
    return next((x["digest"] for x in layers if x["mediaType"].endswith("image.model")), None)


def model_info(model, cache_rows=(), backend=None):
    """Name, Ollama tag digest and GGUF blob digest, without needing a running server.

    The tag digest is the sha256 of the local manifest file (what Ollama reports in /api/tags).
    Without the manifest, the digest already recorded in the cache for this model and backend is
    used, so cache replay works on a machine with no model files or server at all.
    """
    manifest = manifest_path(model)
    if manifest.exists():
        return {"name": model, "digest": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "gguf_blob": gguf_blob(model), "source": "ollama manifest"}
    seen = {(r["model_digest"], r.get("gguf_blob")) for r in cache_rows
            if r.get("model") == model and (r.get("backend") or {}).get("backend") == backend}
    if len(seen) == 1:
        digest, blob = seen.pop()
        return {"name": model, "digest": digest, "gguf_blob": blob, "source": "llm cache"}
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        for m in r.json().get("models", []):
            if m["name"] == model:
                return {"name": model, "digest": m["digest"], "gguf_blob": None, "source": "ollama api"}
    except requests.RequestException:
        pass
    raise SystemExit(f"cannot find the digest of {model}: no Ollama manifest, no cache rows, no server")


def backend_info(backend):
    if backend == "kaggle-transformers":
        info = {"backend": backend, "hf_repo": HF_REPO, "hf_revision": HF_REVISION}
        try:
            import torch
            import transformers
            info.update(torch=torch.__version__, transformers=transformers.__version__,
                        gpu=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None)
        except ImportError:
            info["mode"] = "cache_only"
        return info
    if backend == "ollama":
        v = requests.get(f"{OLLAMA_URL}/api/version", timeout=10).json().get("version")
        return {"backend": "ollama", "url": OLLAMA_URL, "version": v}
    props = requests.get(f"{LLAMACPP_URL}/props", timeout=10).json()
    return {"backend": "llamacpp", "url": LLAMACPP_URL, "version": props.get("build_info"),
            "model_path": Path(props.get("model_path", "")).name}


def input_hash(prompt_text, options):
    body = json.dumps({"prompt": prompt_text, "options": options}, sort_keys=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


class LLM:
    """Calls the backend once per uncached input and appends each result to the cache file."""

    def __init__(self, model, cache_path=CACHE_PATH, backend=None):
        self.model, self.cache_path = model, Path(cache_path)
        self.backend = backend or os.environ.get("LLM_BACKEND", "ollama")
        rows = []
        if self.cache_path.exists():
            with open(self.cache_path) as f:
                rows = [json.loads(line) for line in f if line.strip()]
        if self.backend == "kaggle-transformers":
            repo, rev = HF_FOR_TAG[model]
            self.info = {"name": model, "digest": f"hf:{repo}@{rev}", "gguf_blob": None}
        else:
            self.info = model_info(model, rows, self.backend)
        self.digest = self.info["digest"]
        self._server = None
        self._hf = None
        self.cache = {(r["prompt_id"], r["input_hash"], r["model_digest"]): r for r in rows}
        self.hits = self.calls = 0
        self.seconds = 0.0

    @property
    def server(self):
        """Backend details; the server is only contacted when a call is actually needed."""
        if self._server is None:
            self._server = backend_info(self.backend)
        return self._server

    def _hf_load(self):
        """Tokenizer and fp16 model pinned to cuda:0. Fails loudly without CUDA."""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        if self._hf is None:
            if not torch.cuda.is_available():
                raise RuntimeError("kaggle-transformers needs CUDA and none is available")
            repo, rev = HF_FOR_TAG[self.model]
            tok = AutoTokenizer.from_pretrained(repo, revision=rev, padding_side="left")
            if tok.pad_token is None:
                tok.pad_token = tok.eos_token
            mdl = AutoModelForCausalLM.from_pretrained(repo, revision=rev, dtype=torch.float16).to("cuda:0").eval()
            print(f"model on {mdl.device}, {torch.cuda.get_device_name(0)}, {torch.cuda.device_count()} GPU(s) visible", flush=True)
            self._hf = (tok, mdl)
        return self._hf

    def _hf_batch(self, prompt_texts, options):
        """[(text, prompt tokens, generated tokens)] for a batch, left padded; one seed per batch."""
        import torch
        tok, mdl = self._hf_load()
        texts = [tok.apply_chat_template([{"role": "user", "content": t}], tokenize=False, add_generation_prompt=True)
                 for t in prompt_texts]
        enc = tok(texts, return_tensors="pt", padding=True).to("cuda:0")
        torch.manual_seed(options["seed"])
        sample = options["temperature"] > 0
        kw = {"do_sample": True, "temperature": options["temperature"]} if sample else {"do_sample": False}
        with torch.no_grad():
            out = mdl.generate(**enc, max_new_tokens=options["num_predict"], pad_token_id=tok.pad_token_id, **kw)
        width = enc["input_ids"].shape[1]
        res = []
        for i, row in enumerate(out):
            new = row[width:].tolist()
            n_new = next((k + 1 for k, t in enumerate(new) if t in (tok.eos_token_id, tok.pad_token_id)), len(new))
            res.append((tok.decode(new, skip_special_tokens=True), int(enc["attention_mask"][i].sum()), n_new))
        return res

    def _hf_call(self, msgs, options):
        return self._hf_batch([msgs[0]["content"]], options)[0]

    def _call(self, prompt_text, options, fmt):
        """(text, prompt tokens, generated tokens) for one user message."""
        msgs = [{"role": "user", "content": prompt_text}]
        if self.backend == "kaggle-transformers":
            if self.server.get("mode") == "cache_only":
                raise RuntimeError("cache miss for kaggle-transformers; run the Kaggle notebook and merge its cache")
            return self._hf_call(msgs, options)
        if self.backend == "ollama":
            body = {"model": self.model, "messages": msgs, "stream": False, "options": options}
            if fmt:
                body["format"] = fmt
            r = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=900)
            r.raise_for_status()
            d = r.json()
            return d["message"]["content"], d.get("prompt_eval_count"), d.get("eval_count")
        body = {"messages": msgs, "seed": options["seed"], "temperature": options["temperature"],
                "max_tokens": options["num_predict"], "cache_prompt": True}
        if fmt == "json":
            body["response_format"] = {"type": "json_object"}
        r = requests.post(f"{LLAMACPP_URL}/v1/chat/completions", json=body, timeout=900)
        r.raise_for_status()
        d = r.json()
        u = d.get("usage", {})
        return d["choices"][0]["message"]["content"], u.get("prompt_tokens"), u.get("completion_tokens")

    def _key(self, prompt_id, prompt_text, options, fmt):
        return (prompt_id, input_hash(prompt_text, {**options, "format": fmt, "backend": self.backend}), self.digest)

    def lookup(self, prompt_id, prompt_text, options, fmt=None, num_predict=256):
        """Cached row or None, without calling the model."""
        return self.cache.get(self._key(prompt_id, prompt_text, {**options, "num_predict": num_predict}, fmt))

    def generate(self, prompt_id, prompt_text, options, fmt=None, num_predict=256):
        options = {**options, "num_predict": num_predict}
        key = self._key(prompt_id, prompt_text, options, fmt)
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        t0 = time.time()
        text, n_in, n_out = self._call(prompt_text, options, fmt)
        dt = time.time() - t0
        self.calls += 1
        self.seconds += dt
        return self._store(key, prompt_id, options, fmt, text, n_in, n_out, dt)

    def _store(self, key, prompt_id, options, fmt, text, n_in, n_out, dt, batch=None):
        row = {"prompt_id": prompt_id, "input_hash": key[1], "model": self.model, "model_digest": self.digest,
               "gguf_blob": self.info.get("gguf_blob"), "backend": self.server, "options": options,
               "format": fmt, "response": text.strip(), "seconds": round(dt, 3),
               "prompt_eval_count": n_in, "eval_count": n_out}
        if batch:
            row["batch"] = batch
        self.cache[key] = row
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def generate_many(self, prompt_id, prompt_texts, options, fmt=None, num_predict=256, batch_size=None):
        """generate() for many prompts. On kaggle-transformers with LLM_BATCH > 1 the misses run in
        left-padded batches (seeded once per batch; batch size and position stored in each row)."""
        batch_size = batch_size or int(os.environ.get("LLM_BATCH", "1"))
        options = {**options, "num_predict": num_predict}
        keys = [self._key(prompt_id, t, options, fmt) for t in prompt_texts]
        out = [self.cache.get(k) for k in keys]
        self.hits += sum(r is not None for r in out)
        miss = [i for i, r in enumerate(out) if r is None]
        if self.backend != "kaggle-transformers" or batch_size <= 1:
            for i in miss:
                out[i] = self.generate(prompt_id, prompt_texts[i], options, fmt, num_predict)
            return out
        for b in range(0, len(miss), batch_size):
            idx = miss[b:b + batch_size]
            t0 = time.time()
            res = self._hf_batch([prompt_texts[i] for i in idx], options)
            dt = time.time() - t0
            self.calls += len(idx)
            self.seconds += dt
            print(f"{prompt_id} batch {b // batch_size + 1}: {len(idx)} prompts in {dt:.1f}s "
                  f"({dt / len(idx):.2f}s per call, {sum(r[2] for r in res)} new tokens)", flush=True)
            for pos, (i, (text, n_in, n_out)) in enumerate(zip(idx, res)):
                out[i] = self._store(keys[i], prompt_id, options, fmt, text, n_in, n_out, dt / len(idx),
                                     batch={"size": len(idx), "position": pos, "batch_seconds": round(dt, 3)})
        return out

    def stats(self):
        server = self._server if self._server is not None else {"backend": self.backend, "mode": "cache_replay"}
        return {"model": self.model, "model_digest": self.digest, "gguf_blob": self.info.get("gguf_blob"),
                "backend": server, "new_calls": self.calls,
                "cache_hits": self.hits, "llm_seconds": round(self.seconds, 1),
                "mean_seconds_per_call": round(self.seconds / self.calls, 2) if self.calls else None}
