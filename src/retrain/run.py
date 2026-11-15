"""One-command retraining after a drift alert: select, reveal, validate, retrain, evaluate, gate (Part E).

1. Production answers on the pre-labelled pool (data/sft/pool.jsonl, curriculum v2).
2. A1 active-learning selection: disagreement score of each answer with the v2 rule engine (src/active/disagreement.py),
   budget shared across intents (al_stratified_pick).
3. Reveal the selected pairs' labels (target answer and justification) from the pool: the simulated annotator.
4. Validate them: rule-engine target scores exactly, transcript valid, P-prefixed ids, no evaluation student.
5. Continue training the production adapter on revealed rows + retrain.replay_rows original train rows, or with
   --from_scratch (D12) train a new adapter on all train rows + the revealed rows with the production run's settings.
6. Val guard: reject, with no gold evaluation, a candidate whose val exact match drops more than the gold tolerance.
7. Register the result as alias `candidate`, evaluate candidate and production on shifted and gold (logged in
   TEST_SET_LOG.md), and apply the gate fixed in params_a2.yaml. Promote on pass, otherwise keep production.
Example: python -m src.retrain.run --tag r1
"""
import argparse
import json
import random
import subprocess
import sys

import mlflow
import yaml

from src.active.al_vs_random import al_stratified_pick
from src.active.base_model_answers import parse_json
from src.active.disagreement import score
from src.augment.common import ROOT, read_jsonl, write_jsonl
from src.engine.catalog import RULES_PATH, load_catalog
from src.engine.rule_engine import validate_transcript
from src.eval.evaluate import resolve
from src.eval.metrics import score_row

params = yaml.safe_load(open(ROOT / "params_a2.yaml"))
R, G = params["retrain"], params["gate"]

parser = argparse.ArgumentParser()
parser.add_argument("--tag", required=True, help="name of this retraining round")
parser.add_argument("--budget", type=int, default=R["budget"], help="pool pairs to label")
parser.add_argument("--replay_rows", type=int, default=R["replay_rows"], help="original train rows mixed in")
parser.add_argument("--epochs", type=int, default=R["epochs"], help="epochs over the retraining rows")
parser.add_argument("--lr", type=float, default=None, help="learning rate (default: the production run's)")
parser.add_argument("--prepare_only", action="store_true", help="stop after selection, reveal and validation (D16)")
parser.add_argument("--candidate_run", default=None, help="use this already trained run as the candidate instead of training (D13)")
parser.add_argument("--from_scratch", action="store_true",
                    help="train a new adapter on all train rows + the revealed rows with the production run's settings (D12)")
opt = parser.parse_args()
print(opt)

mlflow.set_tracking_uri(f"sqlite:///{ROOT}/mlflow.db")
out = ROOT / "supporting_files/E_retrain" / opt.tag
out.mkdir(parents=True, exist_ok=True)
py = [sys.executable, "-m"]
prod_name, prod_run, prod_adapter = resolve("advisor@production")
prod_params = mlflow.get_run(prod_run).data.params
print(f"production: {prod_name} run {prod_run}")

# ----------
#  1-2. Score the pool and select
# ----------
v2 = load_catalog(ROOT / "data/a2/courses_v2.json", RULES_PATH)
students = {s["student_id"]: s for s in read_jsonl(ROOT / "data/a2/students_pool.jsonl")}
pool = read_jsonl(ROOT / "data/sft/pool.jsonl")
cache = ROOT / "supporting_files/E_retrain" / f"pool_answers_{prod_name}.jsonl"
if not cache.exists():
    from src.model import predict
    tok, model = predict.load_model(str(prod_adapter))
    write_jsonl(cache, [{"query_id": r["query_id"], "response": a}
                        for r, a in zip(pool, predict.generate(tok, model, [r["prompt"] for r in pool]))])
    del model
answers = {a["query_id"]: a["response"] for a in read_jsonl(cache)}
scored = []
for r in pool:
    s, fails, _ = score({"parsed": parse_json(answers[r["query_id"]])}, r, students[r["student_id"]], v2)
    scored.append({"query_id": r["query_id"], "intent": r["intent"], "score": s, "failures": fails, "row": r})
picked = al_stratified_pick(scored, opt.budget, params["seeds"]["retrain_pool"])
print(f"selected {len(picked)} of {len(pool)}; mean score picked {sum(p['score'] for p in picked) / len(picked):.2f}, "
      f"pool {sum(p['score'] for p in scored) / len(scored):.2f}")

# ----------
#  3-4. Reveal labels and validate
# ----------
revealed = [p["row"] for p in picked]
eval_students = {r["student_id"] for s in ["val", "test", "gold", "shifted"] for r in read_jsonl(ROOT / f"data/sft/{s}.jsonl")}
problems = []
for r in revealed:
    st = students[r["student_id"]]
    if score_row(r["target"], r, st, v2)["exact_match"] != 1:
        problems.append((r["query_id"], "label disagrees with the v2 rule engine"))
    if not validate_transcript(st, v2)["valid"]:
        problems.append((r["query_id"], "invalid transcript"))
    if not r["query_id"].startswith("P") or r["student_id"] in eval_students:
        problems.append((r["query_id"], "not a pool row or evaluation student"))
json.dump({"n": len(revealed), "problems": problems, "selected": [p["query_id"] for p in picked],
           "scores": {p["query_id"]: [p["score"], p["failures"]] for p in picked}}, open(out / "selection_validation.json", "w"), indent=1)
assert not problems, f"validation failed: {problems[:5]}"

train = read_jsonl(ROOT / "data/sft/train.jsonl")
rows = revealed + (train if opt.from_scratch else random.Random(params["seeds"]["retrain_pool"]).sample(train, opt.replay_rows))
train_file = f"data/a2/retrain_{opt.tag}.jsonl"
write_jsonl(ROOT / train_file, rows)
print(f"wrote {train_file}: {len(rows)} rows")
if opt.prepare_only:
    sys.exit(0)

# ----------
#  5. Retrain: continue the production adapter, or (D12) a new adapter with the production run's settings
# ----------
run_name = f"retrain-{opt.tag}"
lr = opt.lr or float(prod_params["lr"])
epochs = int(prod_params["epochs"]) if opt.from_scratch else opt.epochs
init = [] if opt.from_scratch else ["--init_adapter", str(prod_adapter)]
if opt.candidate_run:
    cand_run = opt.candidate_run
else:
    subprocess.run(py + ["src.model.train_lora", *init, "--train_file", train_file, "--epochs", str(epochs), "--lr", str(lr),
                         "--rank", prod_params["rank"], "--seed", prod_params["seed"], "--data_mix", "base_aug",
                         "--experiment", "advisor-retrain", "--run_name", run_name], check=True, cwd=ROOT)
    cand_run = mlflow.search_runs(experiment_names=["advisor-retrain"], filter_string=f"tags.mlflow.runName = '{run_name}'",
                                  order_by=["attributes.start_time DESC"]).iloc[0].run_id
subprocess.run(py + ["src.model.register", "run", "--run_id", cand_run, "--alias", "candidate", "--note", f"retrain {opt.tag}"],
               check=True, cwd=ROOT)
cand_name = resolve("advisor@candidate")[0]
settings = {"budget": opt.budget, "replay_rows": len(train) if opt.from_scratch else opt.replay_rows, "lr": lr, "epochs": epochs,
            "from_scratch": opt.from_scratch, "train_rows": len(rows), "candidate_run_given": opt.candidate_run}

# ----------
#  6. Evaluate and gate
# ----------
def evaluate(model, name, split, compare=None):
    """Run src.eval.evaluate once per (version, split) and return its metrics.json."""
    path = ROOT / "supporting_files/C_eval" / name / split / "metrics.json"
    if compare or not path.exists():
        cmd = py + ["src.eval.evaluate", "--model", model, "--split", split, "--reason", f"Part E gate check {opt.tag}"]
        subprocess.run(cmd + (["--compare", str(compare)] if compare else []), check=True, cwd=ROOT)
    return json.load(open(path))


# Val guard (D12, D16): both models scored by evaluate.py on val with the current labels, before any gold evaluation
val = lambda model, name: evaluate(model, name, "val")["summary"]["exact_match"]
v_prod, v_cand = val("advisor@production", prod_name), val("advisor@candidate", cand_name)
val_drop = v_prod - v_cand
if val_drop > G["gold_max_drop"]:
    gate = {"tag": opt.tag, "production": prod_name, "candidate": cand_name, "candidate_run": cand_run, **settings,
            "val_guard": {"production": v_prod, "candidate": v_cand, "drop": val_drop},
            "decision": "reject (val guard, no gold evaluation)"}
    with open(ROOT / "supporting_files/E_retrain/gate_log.jsonl", "a") as f:
        f.write(json.dumps(gate) + "\n")
    json.dump(gate, open(out / "gate.json", "w"), indent=1)
    print(json.dumps(gate, indent=1))
    sys.exit(0)

prod_shift = evaluate("advisor@production", prod_name, "shifted")
prod_gold = evaluate("advisor@production", prod_name, "gold")
scores = lambda name, split: ROOT / "supporting_files/C_eval" / name / split / "scores.jsonl"
cand_shift = evaluate("advisor@candidate", cand_name, "shifted", compare=scores(prod_name, "shifted"))
cand_gold = evaluate("advisor@candidate", cand_name, "gold", compare=scores(prod_name, "gold"))

shift_gain = cand_shift["summary"][G["shifted_metric"]] - prod_shift["summary"][G["shifted_metric"]]
gold_drop = prod_gold["summary"][G["gold_metric"]] - cand_gold["summary"][G["gold_metric"]]
p = cand_shift["paired_vs"]["set_f1_p_one_sided"]
passed = shift_gain > 0 and p < G["shifted_p_max"] and gold_drop <= G["gold_max_drop"]
gate = {"tag": opt.tag, "production": prod_name, "candidate": cand_name, "candidate_run": cand_run,
        **settings, "val_guard": {"production": v_prod, "candidate": v_cand, "drop": val_drop}, "gate": G,
        "shifted": {"production": prod_shift["summary"][G["shifted_metric"]], "candidate": cand_shift["summary"][G["shifted_metric"]],
                    "gain": shift_gain, "p_one_sided": p},
        "gold": {"production": prod_gold["summary"][G["gold_metric"]], "candidate": cand_gold["summary"][G["gold_metric"]],
                 "drop": gold_drop},
        "decision": "promote" if passed else "reject"}
with open(ROOT / "supporting_files/E_retrain/gate_log.jsonl", "a") as f:
    f.write(json.dumps(gate) + "\n")
json.dump(gate, open(out / "gate.json", "w"), indent=1)
print(json.dumps(gate, indent=1))
if passed:
    subprocess.run(py + ["src.model.register", "promote", "--source", "candidate", "--note", f"gate passed {opt.tag}"],
                   check=True, cwd=ROOT)
