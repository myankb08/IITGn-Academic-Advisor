"""Human rating of model justifications on the test split, and Cohen's kappa between the two annotators.

--make: 60 test base rows (seeds.bootstrap, stratified by intent) with the question, the model answer and
        justification, and the rule-engine answer; one CSV per annotator (A1, A2) with its own row order.
        Rating (one value): correct | partly_correct | incorrect  (is the justification true and does it support
        the answer, judged against the rule-engine answer), and faithful_to_answer: yes | no.
--score: Cohen's kappa (unweighted and linear-weighted for the 3-level rating) with a 1000-sample bootstrap CI.
Files: supporting_files/C_eval/<name>/justification_rating/.
"""
import argparse
import json
import random

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import cohen_kappa_score

from src.active.base_model_answers import parse_json
from src.augment.common import ROOT, read_jsonl

params = yaml.safe_load(open(ROOT / "params_a2.yaml"))
parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True, help="model folder in supporting_files/C_eval")
parser.add_argument("--make", action="store_true", help="write the rating sheets")
parser.add_argument("--score", action="store_true", help="compute kappa from filled sheets")
opt = parser.parse_args()
print(opt)

d = ROOT / "supporting_files/C_eval" / opt.name / "justification_rating"
d.mkdir(parents=True, exist_ok=True)
seed = params["seeds"]["bootstrap"]

if opt.make:
    preds = {p["query_id"]: p["response"] for p in read_jsonl(ROOT / "supporting_files/C_eval" / opt.name / "test/preds.jsonl")}
    rows = [r for r in read_jsonl(ROOT / "data/sft/test.jsonl") if not r["augmentation"]]
    rng = random.Random(seed)
    picked = [r for i in ["remaining_core", "eligibility", "elective_recommendation"]
              for r in rng.sample([r for r in rows if r["intent"] == i], 20)]
    items = []
    for r in picked:
        obj = parse_json(preds[r["query_id"]]) or {}
        items.append({"query_id": r["query_id"], "intent": r["intent"], "question": r["query"], "student": r["student"],
                      "model_answer": json.dumps({k: v for k, v in obj.items() if k != "justification"}),
                      "model_justification": obj.get("justification", "(no justification: invalid output)"),
                      "rule_engine_answer": json.dumps(json.loads(r["target"]) | {"justification": None}),
                      "rule_engine_justification": json.loads(r["target"])["justification"],
                      "rating": "", "faithful_to_answer": "", "notes": ""})
    for k, who in enumerate(["A1", "A2"]):
        sheet = items[:]
        random.Random(seed + k).shuffle(sheet)
        pd.DataFrame(sheet).to_csv(d / f"sheet_{who}.csv", index=False)
    print(f"wrote {len(items)} items to {d}/sheet_A1.csv and sheet_A2.csv")

if opt.score:
    a = pd.read_csv(d / "sheet_A1.csv").set_index("query_id").sort_index()
    b = pd.read_csv(d / "sheet_A2.csv").set_index("query_id").sort_index()
    assert a.rating.notna().all() and b.rating.notna().all(), "sheets not filled"
    levels = {"incorrect": 0, "partly_correct": 1, "correct": 2}
    x, y = a.rating.map(levels).values, b.rating.map(levels).values
    fx, fy = a.faithful_to_answer.values, b.faithful_to_answer.values
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), (1000, len(x)))
    ci = lambda f: [float(np.nanpercentile([f(i) for i in idx], q)) for q in (2.5, 97.5)]
    res = {"n": int(len(x)),
           "rating_kappa": cohen_kappa_score(x, y), "rating_kappa_ci95": ci(lambda i: cohen_kappa_score(x[i], y[i])),
           "rating_kappa_linear": cohen_kappa_score(x, y, weights="linear"),
           "faithful_kappa": cohen_kappa_score(fx, fy), "faithful_kappa_ci95": ci(lambda i: cohen_kappa_score(fx[i], fy[i])),
           "rating_counts": {"A1": a.rating.value_counts().to_dict(), "A2": b.rating.value_counts().to_dict()},
           "agreement": float((x == y).mean())}
    json.dump(res, open(d / "kappa.json", "w"), indent=1)
    print(json.dumps(res, indent=1))
