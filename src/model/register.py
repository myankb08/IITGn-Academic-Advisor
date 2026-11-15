"""Model registry actions for the advisor (MLflow registry "advisor", aliases staging / production / previous).

  best:     register the FINISHED advisor-search run with the highest val_set_f1 and point `staging` at it
  run:      register a given run id (used by the retraining pipeline) and point --alias at it
  promote:  production -> the version behind --source (default staging); the old production becomes `previous`
  rollback: production -> the version behind `previous`
Every action is appended to supporting_files/B_search/registry_log.jsonl.
"""
import argparse
import datetime
import json

import mlflow

from src.augment.common import ROOT

parser = argparse.ArgumentParser()
parser.add_argument("action", choices=["best", "run", "promote", "rollback"], help="registry action")
parser.add_argument("--run_id", default=None, help="run to register (action run)")
parser.add_argument("--alias", default="staging", help="alias for a newly registered version")
parser.add_argument("--source", default="staging", help="alias to promote (action promote)")
parser.add_argument("--note", default="", help="reason, kept in the log")
opt = parser.parse_args()
print(opt)

mlflow.set_tracking_uri(f"sqlite:///{ROOT}/mlflow.db")
client = mlflow.MlflowClient()
NAME = "advisor"


def alias_version(alias):
    try:
        return client.get_model_version_by_alias(NAME, alias).version
    except mlflow.exceptions.MlflowException:
        return None


if opt.action in ("best", "run"):
    if opt.action == "best":
        runs = mlflow.search_runs(experiment_names=["advisor-search"], filter_string="attributes.status = 'FINISHED'",
                                  order_by=["metrics.val_set_f1 DESC"])
        opt.run_id = runs.iloc[0].run_id
        print(f"best val run: {runs.iloc[0]['tags.mlflow.runName']} val_set_f1={runs.iloc[0]['metrics.val_set_f1']:.4f}")
    mv = mlflow.register_model(f"runs:/{opt.run_id}/adapter", NAME)
    client.set_registered_model_alias(NAME, opt.alias, mv.version)
    entry = {"action": opt.action, "version": mv.version, "run_id": opt.run_id, "alias": opt.alias}
else:
    old = alias_version("production")
    new = alias_version(opt.source) if opt.action == "promote" else alias_version("previous")
    assert new is not None, f"no version behind the source alias for {opt.action}"
    client.set_registered_model_alias(NAME, "production", new)
    if old is not None:
        client.set_registered_model_alias(NAME, "previous", old)
    entry = {"action": opt.action, "production": new, "previous": old}

entry.update(utc=f"{datetime.datetime.utcnow():%Y-%m-%d %H:%M}", note=opt.note,
             aliases={a: alias_version(a) for a in ("staging", "production", "previous", "candidate")})
with open(ROOT / "supporting_files/B_search/registry_log.jsonl", "a") as f:
    f.write(json.dumps(entry) + "\n")
print(json.dumps(entry))
