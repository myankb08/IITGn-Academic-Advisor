"""Hyperparameter search for the LoRA advisor: a queue of train_lora runs spread over the visible GPUs.

Stages, each selecting on val set_f1 only (MLflow experiment advisor-search):
  mix:   the 4 data mixes at the default rank, lr and epochs (Part A comparison)
  grid:  rank x lr (3 x 3) on the best mix
  extra: epochs 1 and 3 at the best grid point, and the 0.5B / 3B models (size and latency trade-off)
Example: python -m src.model.search --stage mix --gpus 0 1 2
"""
import argparse
import itertools
import os
import subprocess
import time

import mlflow
import yaml

from src.augment.common import ROOT

params = yaml.safe_load(open(ROOT / "params_a2.yaml"))
d, grid = params["train"], params["search"]

parser = argparse.ArgumentParser()
parser.add_argument("--stage", required=True, choices=["mix", "grid", "extra"], help="search stage")
parser.add_argument("--gpus", nargs="+", default=["0"], help="GPU ids, one run per GPU at a time")
opt = parser.parse_args()
print(opt)

mlflow.set_tracking_uri(f"sqlite:///{ROOT}/mlflow.db")
mlflow.set_experiment("advisor-search")  # create it once here; parallel runs racing to create it fail


def best(filter_string=""):
    """Params of the finished search run with the highest val_set_f1."""
    runs = mlflow.search_runs(experiment_names=["advisor-search"], filter_string=filter_string,
                              order_by=["metrics.val_set_f1 DESC"])
    runs = runs[runs["metrics.val_set_f1"].notna() & (runs["status"] == "FINISHED")]
    top = runs.iloc[0]
    print(f"best so far: {top['tags.mlflow.runName']} val_set_f1={top['metrics.val_set_f1']:.4f}")
    return {k[7:]: top[k] for k in runs.columns if k.startswith("params.")}


# Run list
if opt.stage == "mix":
    runs = [dict(data_mix=m) for m in grid["data_mix"]]
elif opt.stage == "grid":
    mix = best("tags.mlflow.runName LIKE 'mix-%' AND attributes.status = 'FINISHED'")["data_mix"]
    runs = [dict(data_mix=mix, rank=r, lr=lr) for r, lr in itertools.product(grid["rank"], grid["lr"])
            if not (r == d["rank"] and lr == d["lr"])]  # the default point already ran in stage mix
else:
    b = best()
    runs = [dict(data_mix=b["data_mix"], rank=b["rank"], lr=b["lr"], epochs=e) for e in grid["epochs"]
            if e != int(b["epochs"])]
    runs += [dict(data_mix=b["data_mix"], rank=b["rank"], lr=b["lr"], base=m, revision=rev)
             for m, rev in params["search_models"].items()]

# ----------
#  Queue
# ----------
(ROOT / "logs").mkdir(exist_ok=True)
queue, active = list(runs), {}
while queue or active:
    for gpu in opt.gpus:
        if gpu in active and active[gpu][0].poll() is not None:
            print(f"done on GPU {gpu}: {active.pop(gpu)[1]}", flush=True)
        if gpu not in active and queue:
            r = queue.pop(0)
            name = f"{opt.stage}-" + "-".join(f"{k}{str(v).split('/')[-1][:24]}" for k, v in r.items() if k != "revision")
            cmd = [str(ROOT / ".venv/bin/python"), "-m", "src.model.train_lora", "--run_name", name]
            cmd += [x for k, v in r.items() for x in (f"--{k}", str(v))]
            log = open(ROOT / "logs" / f"{name}.log", "w")
            proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                    env={**os.environ, "CUDA_VISIBLE_DEVICES": gpu})
            active[gpu] = (proc, name)
            print(f"start on GPU {gpu}: {name}", flush=True)
    time.sleep(20)
