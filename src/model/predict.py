"""Raw answers of one system on one split, written to supporting_files/A_models/preds/<name>/<split>.jsonl.

Systems: trivial (constant answer), zero_shot and few_shot (unadapted, no curriculum in the prompt), retrieval
(unadapted, A1 curriculum prompt) and lora (retrieval prompt plus a LoRA adapter). Greedy decoding on GPU with
transformers; the CPU GGUF path lives in src/serve. Run as a script or call generate() from the training script.
"""
import argparse
import collections
import json
import random
import time

import torch
import yaml
from transformers import AutoModelForCausalLM, AutoTokenizer

from src.augment.common import ROOT, read_jsonl, write_jsonl
from src.model.build_sft import load_template
from src.queries.llm_client import render

params = yaml.safe_load(open(ROOT / "params_a2.yaml"))


def few_shot_examples(intent, k=3):
    """k fixed train examples (base rows) of one intent, as text for the {examples} slot."""
    rows = [r for r in read_jsonl(ROOT / "data/sft/train.jsonl") if r["intent"] == intent and not r["augmentation"]]
    picks = random.Random(params["seeds"]["train"]).sample(rows, k)
    return "".join(f"Example student: {r['student']}\nExample question: {r['query']}\nExample answer: {r['target']}\n\n"
                   for r in picks)


def build_prompts(rows, system):
    """User prompt text for each row."""
    if system in ("retrieval", "lora"):
        return [r["prompt"] for r in rows]
    tpl, schemas = load_template("advisor_nocontext_v1")
    shots = {i: few_shot_examples(i) for i in schemas} if system == "few_shot" else {}
    return [render(tpl, programme=r["programme"], track=r["track"], rules=r["rules"], student=r["student"],
                   term=r["term"], query=r["query"], schema=schemas[r["intent"]], examples=shots.get(r["intent"], ""))
            for r in rows]


def trivial_answers(rows):
    """Constant answer per intent: empty sets, eligible, and the 3 most frequent train recommendations."""
    train = [r for r in read_jsonl(ROOT / "data/sft/train.jsonl") if r["intent"] == "elective_recommendation"]
    top = collections.Counter(x["course"] for r in train for x in r["gold_json"]["recommendations"]).most_common(3)
    const = {"remaining_core": {"compulsory_missing": [], "stream_core_missing": [], "total": {"earned": 0, "min": 0, "gap": 0}},
             "eligibility": {"eligible": True, "unmet_prerequisites": [], "reason_codes": []},
             "elective_recommendation": {"recommendations": [{"rank": i + 1, "course": c} for i, (c, _) in enumerate(top)]}}
    return [json.dumps({**const[r["intent"]], "justification": ""}) for r in rows]


def load_model(adapter=None, base=params["model"]["base"], revision=params["model"]["revision"], device="cuda"):
    """Tokenizer and fp16 model at the pinned revision, with an optional LoRA adapter."""
    tok = AutoTokenizer.from_pretrained(base, revision=revision, padding_side="left")
    model = AutoModelForCausalLM.from_pretrained(base, revision=revision, torch_dtype=torch.float16).to(device)
    if adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter)
    return tok, model.eval()


@torch.no_grad()
def generate(tok, model, prompts, batch_size=8):
    """Greedy answers for a list of user prompts, longest first so batches pad little."""
    texts = [tok.apply_chat_template([{"role": "user", "content": p}], tokenize=False, add_generation_prompt=True)
             for p in prompts]
    order = sorted(range(len(texts)), key=lambda i: -len(texts[i]))
    out = [None] * len(texts)
    for b in range(0, len(order), batch_size):
        idx = order[b:b + batch_size]
        enc = tok([texts[i] for i in idx], return_tensors="pt", padding=True).to(model.device)
        gen = model.generate(**enc, max_new_tokens=params["model"]["max_new_tokens"], do_sample=False,
                             pad_token_id=tok.pad_token_id)
        for i, g in zip(idx, gen[:, enc.input_ids.shape[1]:]):
            out[i] = tok.decode(g, skip_special_tokens=True)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", required=True, choices=["trivial", "zero_shot", "few_shot", "retrieval", "lora"])
    parser.add_argument("--split", default="val", help="file in data/sft/ (train, val, test, programme_holdout, gold)")
    parser.add_argument("--adapter", default=None, help="LoRA adapter folder for --system lora")
    parser.add_argument("--name", default=None, help="output folder name (default: the system)")
    parser.add_argument("--base_only", action="store_true", help="only rows without augmentation")
    parser.add_argument("--batch_size", type=int, default=8, help="generation batch size")
    opt = parser.parse_args()
    print(opt)

    rows = [r for r in read_jsonl(ROOT / f"data/sft/{opt.split}.jsonl") if not (opt.base_only and r["augmentation"])]
    t0 = time.time()
    if opt.system == "trivial":
        answers = trivial_answers(rows)
    else:
        tok, model = load_model(opt.adapter)
        answers = generate(tok, model, build_prompts(rows, opt.system), opt.batch_size)
    secs = time.time() - t0
    out = ROOT / "supporting_files/A_models/preds" / (opt.name or opt.system) / f"{opt.split}.jsonl"
    write_jsonl(out, [{"query_id": r["query_id"], "response": a} for r, a in zip(rows, answers)])
    print(f"{len(rows)} answers in {secs:.0f}s -> {out}")
