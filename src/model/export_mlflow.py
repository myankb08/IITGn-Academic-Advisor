"""Portable export of the MLflow tracking store and registry for artefacts/mlflow/.

mlflow.db stores absolute artifact paths of the training machine, so this also writes plain files that open anywhere:
runs.csv (every run of every experiment: params, metrics, tags, status), registry.json (versions, run ids, aliases,
descriptions) and the registry log. Copy mlflow.db and mlruns/ beside them for the full store.
Example: python -m src.model.export_mlflow --out ../artefacts/mlflow
"""
import argparse
import json
import shutil
from pathlib import Path

import mlflow

from src.augment.common import ROOT

parser = argparse.ArgumentParser()
parser.add_argument("--out", default=str(ROOT.parent / "artefacts/mlflow"), help="output folder")
opt = parser.parse_args()
print(opt)

out = Path(opt.out)
out.mkdir(parents=True, exist_ok=True)
mlflow.set_tracking_uri(f"sqlite:///{ROOT}/mlflow.db")
client = mlflow.MlflowClient()

names = [e.name for e in client.search_experiments()]
runs = mlflow.search_runs(experiment_names=names)
runs.insert(0, "experiment", runs.experiment_id.map({e.experiment_id: e.name for e in client.search_experiments()}))
runs.to_csv(out / "runs.csv", index=False)

model = client.get_registered_model("advisor")
versions = [{"version": int(v.version), "run_id": v.run_id, "source": v.source, "created_ms": v.creation_timestamp}
            for v in client.search_model_versions("name='advisor'")]
json.dump({"name": "advisor", "aliases": model.aliases, "versions": sorted(versions, key=lambda v: v["version"])},
          open(out / "registry.json", "w"), indent=1)
shutil.copy(ROOT / "supporting_files/B_search/registry_log.jsonl", out / "registry_log.jsonl")
print(f"{len(runs)} runs in {len(names)} experiments, {len(versions)} registered versions -> {out}")
