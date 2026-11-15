"""Copy a registered model version's LoRA adapter into release/ (in git), which the Dockerfile builds from.

The adapter weights are stored as fp16 (half the size; GitHub's file limit is 100 MB), so the image always merges
exactly these bytes. Writes release/adapter/, VERSION, RUN_ID and ADAPTER_SHA256.txt. The other release files,
reported_gold.json (src.serve.validate --write_reported) and monitoring_thresholds.json (src.monitor.replay),
are written by their own steps. Example: python -m src.serve.make_release --model advisor@production
"""
import argparse
import hashlib
import shutil

import mlflow
from safetensors.torch import load_file, save_file

from src.augment.common import ROOT
from src.eval.evaluate import resolve

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="advisor@production", help="advisor@<alias> or advisor/<version>")
opt = parser.parse_args()
print(opt)

mlflow.set_tracking_uri(f"sqlite:///{ROOT}/mlflow.db")
name, run_id, adapter = resolve(opt.model)
rel = ROOT / "release"
shutil.rmtree(rel / "adapter", ignore_errors=True)
(rel / "adapter").mkdir(parents=True)
shutil.copy(adapter / "adapter_config.json", rel / "adapter")
weights = load_file(adapter / "adapter_model.safetensors")
save_file({k: v.half().contiguous() for k, v in weights.items()}, rel / "adapter/adapter_model.safetensors")
for p in (rel / "adapter").iterdir():
    p.chmod(0o644)  # save_file writes 600; the image build reads it as another user
(rel / "VERSION").write_text(name.rsplit("_v", 1)[1] + "\n")
(rel / "RUN_ID").write_text(run_id + "\n")
sums = {f"adapter/{p.name}": hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((rel / "adapter").iterdir())}
(rel / "ADAPTER_SHA256.txt").write_text("".join(f"{s}  release/{n}\n" for n, s in sums.items()))
print(f"release: {name} run {run_id}", {n: s[:12] for n, s in sums.items()},
      f"{(rel / 'adapter/adapter_model.safetensors').stat().st_size / 2 ** 20:.0f} MB")
