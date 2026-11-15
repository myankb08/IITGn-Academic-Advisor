"""Merge a LoRA adapter into the base model and save it for CPU serving (int8 quantisation happens at load).

Writes <out>/merged (fp16 safetensors and tokenizer), model_info.json (version, run id, base, adapter) and
SHA256.txt (checksums of the weight files). Example:
python -m src.serve.export_model --adapter models/runs/<run_id>/adapter --version 3 --run_id <run_id> --out models/production
"""
import argparse
import hashlib
import json
from pathlib import Path

import torch
import yaml
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
params = yaml.safe_load(open(ROOT / "params_a2.yaml"))

parser = argparse.ArgumentParser()
parser.add_argument("--adapter", required=True, help="LoRA adapter folder")
parser.add_argument("--out", required=True, help="output folder")
parser.add_argument("--version", default="dev", help="registered model version")
parser.add_argument("--run_id", default=None, help="MLflow run id of the adapter")
parser.add_argument("--base", default=params["model"]["base"], help="base model")
parser.add_argument("--revision", default=params["model"]["revision"], help="base model revision")
opt = parser.parse_args()
print(opt)

out = Path(opt.out)
tok = AutoTokenizer.from_pretrained(opt.base, revision=opt.revision)
model = AutoModelForCausalLM.from_pretrained(opt.base, revision=opt.revision, torch_dtype=torch.float16)
model = PeftModel.from_pretrained(model, opt.adapter).merge_and_unload()
model.save_pretrained(out / "merged")
tok.save_pretrained(out / "merged")

for p in (out / "merged").iterdir():
    p.chmod(0o644)  # save_pretrained can write 600; the image runs as another user on other machines
sums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((out / "merged").glob("*.safetensors"))}
(out / "SHA256.txt").write_text("".join(f"{s}  merged/{n}\n" for n, s in sums.items()))
json.dump({"version": str(opt.version), "run_id": opt.run_id, "base": f"{opt.base}@{opt.revision}",
           "adapter": opt.adapter, "serving": "weight-only int8 nn.Linear (per-channel scales), fp32 activations, CPU, greedy",
           "weights_sha256": sums}, open(out / "model_info.json", "w"), indent=1)
print(f"saved {out}: {sums}")
