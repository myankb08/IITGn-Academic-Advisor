#!/bin/sh
# Reproduce the final Assignment 2 model and its evaluation from tag a2-final (one CUDA GPU with 12 GB or more).
# Needs the data from `dvc pull` (or `dvc repro`), which includes data/sft/ (stage build_sft) and data/a2/ (make_pool).
# 1. trains the selected configuration (docs/A2_PLAN.md D10) into a fresh MLflow experiment, 2. registers it as
# advisor@reproduce, 3. evaluates it on val, test, gold and shifted with paired tests against the baselines' saved
# scores. Every protected-split evaluation is appended to TEST_SET_LOG.md with the reason "reproduction".
set -e
cd "$(dirname "$0")/.."
PY=.venv/bin/python
$PY -m src.model.train_lora --data_mix base_aug --rank 32 --lr 5e-4 --epochs 3 --seed 301 \
    --experiment advisor-reproduce --run_name reproduce-final
RID=$($PY -c "import mlflow; mlflow.set_tracking_uri('sqlite:///mlflow.db'); print(mlflow.search_runs(experiment_names=['advisor-reproduce'], order_by=['attributes.start_time DESC']).iloc[0].run_id)")
$PY -m src.model.register run --run_id "$RID" --alias reproduce --note "scripts/reproduce_a2.sh"
for s in val test gold shifted; do
  $PY -m src.eval.evaluate --model advisor@reproduce --split $s --compare supporting_files/C_eval/few_shot/$s/scores.jsonl --reason "reproduction"
done
echo "Compare supporting_files/C_eval/advisor_v<new>/<split>/metrics.json with supporting_files/C_eval/advisor_v1 (GPU training is not bit-exact; README states the measured spread)."
