"""One LoRA fine-tuning run of the advisor SLM, logged to MLflow, then scored on val.

Data mixes (train split only): base = 336 original pairs, base_aug = base + A1 paraphrases + A1 Part D augmentations
(1541 rows), al100 / random100 = 100 base pairs picked by the A1 stratified active-learning score or at random.
The loss is on the answer tokens only. Defaults come from params_a2.yaml; command-line options override them.
"""
import argparse
import hashlib
import json
import platform
import random
import subprocess
import time

import mlflow
import numpy as np
import torch
import yaml
from peft import LoraConfig, get_peft_model
from transformers import get_linear_schedule_with_warmup

from src.active.al_vs_random import al_stratified_pick, random_pick
from src.augment.common import ROOT, read_jsonl, write_jsonl
from src.engine.catalog import load_catalog
from src.eval.metrics import score_row, summarise
from src.model.predict import generate, load_model

params = yaml.safe_load(open(ROOT / "params_a2.yaml"))
d = params["train"]

parser = argparse.ArgumentParser()
parser.add_argument("--rank", type=int, default=d["rank"], help="LoRA rank")
parser.add_argument("--lr", type=float, default=d["lr"], help="learning rate")
parser.add_argument("--epochs", type=int, default=d["epochs"], help="number of epochs")
parser.add_argument("--data_mix", default=d["data_mix"], choices=["base", "base_aug", "al100", "random100"], help="training rows")
parser.add_argument("--base", default=params["model"]["base"], help="base model on the Hugging Face hub")
parser.add_argument("--revision", default=params["model"]["revision"], help="base model revision")
parser.add_argument("--batch_size", type=int, default=d["batch_size"], help="rows per step")
parser.add_argument("--grad_accum", type=int, default=d["grad_accum"], help="steps per optimizer update")
parser.add_argument("--seed", type=int, default=params["seeds"]["train"], help="random seed")
parser.add_argument("--train_file", default="data/sft/train.jsonl", help="training rows")
parser.add_argument("--init_adapter", default=None, help="continue training this adapter (retraining)")
parser.add_argument("--experiment", default="advisor-search", help="MLflow experiment")
parser.add_argument("--run_name", default=None, help="MLflow run name")
opt = parser.parse_args()
print(opt)

random.seed(opt.seed)
np.random.seed(opt.seed)
torch.manual_seed(opt.seed)
sha = lambda p: hashlib.sha256(open(ROOT / p, "rb").read()).hexdigest()[:16]

# ----------
#  Data
# ----------
train = read_jsonl(ROOT / opt.train_file)
base = [r for r in train if not r["augmentation"]]
if opt.data_mix == "base":
    rows = base
elif opt.data_mix == "base_aug":
    rows = train
else:
    # A1 Part D selection on the same train pool (seed 11 = first active-learning seed)
    scores = {s["query_id"]: s for s in read_jsonl(ROOT / "data/interim/al_scores.jsonl")}
    pool = [{**scores[r["query_id"]], "row": r} for r in base if r["query_id"] in scores]
    pick = al_stratified_pick if opt.data_mix == "al100" else random_pick
    rows = [p["row"] for p in pick(pool, 100, params["seeds"]["train"])]
val = read_jsonl(ROOT / "data/sft/val.jsonl")
print(f"train rows: {len(rows)}, val rows: {len(val)}")

# Initialize model and LoRA adapter
tok, model = load_model(base=opt.base, revision=opt.revision)
tok.padding_side = "right"
model.gradient_checkpointing_enable()
model.enable_input_require_grads()
if opt.init_adapter:
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, opt.init_adapter, is_trainable=True)
else:
    model = get_peft_model(model, LoraConfig(r=opt.rank, lora_alpha=opt.rank * d["alpha_ratio"], lora_dropout=0.05,
                                             task_type="CAUSAL_LM", target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                                                                    "gate_proj", "up_proj", "down_proj"]))
model.print_trainable_parameters()


def encode(r):
    """Prompt ids and answer ids; labels mask the prompt."""
    p = tok.apply_chat_template([{"role": "user", "content": r["prompt"]}], add_generation_prompt=True)
    a = tok(r["target"] + "<|im_end|>", add_special_tokens=False).input_ids
    return p + a, [-100] * len(p) + a


data = [encode(r) for r in rows]

# Optimizers
optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=opt.lr)
n_updates = opt.epochs * -(-len(data) // (opt.batch_size * opt.grad_accum))
scheduler = get_linear_schedule_with_warmup(optimizer, int(0.05 * n_updates), n_updates)
scaler = torch.amp.GradScaler("cuda")

# ----------
#  Training
# ----------
mlflow.set_tracking_uri(f"sqlite:///{ROOT}/mlflow.db")
mlflow.set_experiment(opt.experiment)
commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
dirty = bool(subprocess.run(["git", "status", "--porcelain", "src"], capture_output=True, text=True, cwd=ROOT).stdout)
with mlflow.start_run(run_name=opt.run_name) as run:
    mlflow.log_params({**vars(opt), "n_train_rows": len(rows), "alpha": opt.rank * d["alpha_ratio"],
                       "max_new_tokens": params["model"]["max_new_tokens"]})
    mlflow.set_tags({"git_commit": commit, "git_dirty_src": dirty, "gpu": torch.cuda.get_device_name(0),
                     "torch": torch.__version__, "python": platform.python_version(),
                     "data_train_sha": sha(opt.train_file), "data_val_sha": sha("data/sft/val.jsonl"),
                     "dvc_lock_sha": sha("dvc.lock"), "prompt_id": "advisor_retrieval_v1"})
    t0, step = time.time(), 0
    model.train()
    for epoch in range(opt.epochs):
        random.shuffle(data)
        for i in range(0, len(data), opt.batch_size):
            batch = data[i:i + opt.batch_size]
            n = max(len(x) for x, _ in batch)
            ids = torch.tensor([x + [tok.pad_token_id] * (n - len(x)) for x, _ in batch]).cuda()
            labels = torch.tensor([y + [-100] * (n - len(y)) for _, y in batch]).cuda()
            mask = torch.tensor([[1] * len(x) + [0] * (n - len(x)) for x, _ in batch]).cuda()
            with torch.autocast("cuda", dtype=torch.float16):
                loss = model(input_ids=ids, attention_mask=mask, labels=labels).loss / opt.grad_accum
            scaler.scale(loss).backward()
            step += 1
            if step % opt.grad_accum == 0 or i + opt.batch_size >= len(data):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()
                scheduler.step()
            if step % 20 == 0:
                mlflow.log_metric("train_loss", loss.item() * opt.grad_accum, step=step)
                print(f"[Epoch {epoch}/{opt.epochs}] [Step {step}] [loss: {loss.item() * opt.grad_accum:.4f}]", flush=True)
    train_secs = time.time() - t0

    # ----------
    #  Validation
    # ----------
    out_dir = ROOT / "models/runs" / run.info.run_id
    model.save_pretrained(out_dir / "adapter")
    model.base_model.model.gradient_checkpointing_disable()
    model.base_model.model.config.use_cache = True
    model.eval()
    tok.padding_side = "left"
    t1 = time.time()
    answers = generate(tok, model, [r["prompt"] for r in val])
    gen_secs = time.time() - t1
    catalog = load_catalog()
    students = {s["student_id"]: s for s in read_jsonl(ROOT / "data/processed/students.jsonl")
                + read_jsonl(ROOT / "data/processed/students_augmented.jsonl")}
    scores = [score_row(a, r, students[r["student_id"]], catalog) for r, a in zip(val, answers)]
    m = summarise(scores)
    write_jsonl(ROOT / "supporting_files/B_search/preds" / run.info.run_id / "val.jsonl",
                [{"query_id": r["query_id"], "response": a} for r, a in zip(val, answers)])
    adapter_mb = sum(f.stat().st_size for f in (out_dir / "adapter").iterdir()) / 2 ** 20
    mlflow.log_metrics({f"val_{k}": v for k, v in m.items() if v is not None})
    mlflow.log_metrics({"train_minutes": train_secs / 60, "val_gen_sec_per_row_gpu": gen_secs / len(val),
                        "adapter_mb": adapter_mb})
    mlflow.log_artifacts(str(out_dir / "adapter"), "adapter")
    print(json.dumps({"run_id": run.info.run_id, **m, "train_min": round(train_secs / 60, 1)}, indent=1))
