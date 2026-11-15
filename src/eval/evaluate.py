"""Evaluate one system on one split: metrics with 95% bootstrap CIs, slices, and an optional paired test.

--model is a baseline name (trivial, zero_shot, few_shot, retrieval) or a registered model, written
advisor@<alias> or advisor/<version>. Outputs go to supporting_files/C_eval/<model>/<split>/. Every run on a
protected split (test, gold, programme_holdout, shifted) is appended to TEST_SET_LOG.md with its reason.

Example: python -m src.eval.evaluate --model advisor@production --split gold --reason "final report"
"""
import argparse
import datetime
import json

import mlflow
import numpy as np
import yaml
from scipy.stats import binomtest

from src.augment.common import ROOT, read_jsonl, write_jsonl
from src.engine.catalog import RULES_PATH, load_catalog
from src.eval.metrics import score_row, summarise

PROTECTED = {"test", "gold", "gold_a1", "programme_holdout", "shifted"}
METRICS = ["set_f1", "exact_match", "precision", "recall", "valid_json", "violations", "invented_rate"]
params = yaml.safe_load(open(ROOT / "params_a2.yaml"))


def resolve(model):
    """(output name, run_id or None, adapter dir or None) for a baseline name or a registered model."""
    if "@" not in model and "/" not in model:
        return model, None, None
    client = mlflow.MlflowClient()
    name, ref = model.replace("@", "/").split("/")
    mv = client.get_model_version_by_alias(name, ref) if "@" in model else client.get_model_version(name, ref)
    return f"{name}_v{mv.version}", mv.run_id, ROOT / "models/runs" / mv.run_id / "adapter"


def bootstrap(scores, seed):
    """Mean and 95% percentile CI of each metric over row resamples."""
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(scores), (params["eval"]["n_bootstrap"], len(scores)))
    out = {}
    for k in METRICS:
        v = np.array([float(s["invented_codes"] > 0) if k == "invented_rate" else float(s[k]) for s in scores])
        means = v[idx].mean(1)
        out[k] = {"mean": float(v.mean()), "ci95": [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]}
    return out


def paired(a, b, seed):
    """Paired bootstrap on set_f1 difference (a - b) and exact McNemar test on exact_match."""
    rng = np.random.default_rng(seed)
    d = np.array([x["set_f1"] - y["set_f1"] for x, y in zip(a, b)])
    boots = d[rng.integers(0, len(d), (params["eval"]["n_bootstrap"], len(d)))].mean(1)
    n10 = sum(x["exact_match"] and not y["exact_match"] for x, y in zip(a, b))
    n01 = sum(y["exact_match"] and not x["exact_match"] for x, y in zip(a, b))
    return {"set_f1_diff": float(d.mean()), "set_f1_diff_ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "set_f1_p_one_sided": float((boots <= 0).mean()),
            "mcnemar_exact_match": {"a_only": n10, "b_only": n01,
                                    "p": float(binomtest(n10, n10 + n01).pvalue) if n10 + n01 else 1.0}}


def length_bin(n):
    return "0" if n == 0 else "1-6" if n <= 6 else "7-12" if n <= 12 else "13+"


def slices(rows, scores):
    """Mean set_f1 and exact_match per slice value."""
    keys = {"programme": lambda r: r["programme"], "intent": lambda r: r["intent"],
            "template_family": lambda r: r["template_family"], "transcript_length": lambda r: length_bin(r["n_courses"]),
            "augmentation": lambda r: r.get("augmentation") or "none"}
    out = {}
    for name, f in keys.items():
        groups = {}
        for r, s in zip(rows, scores):
            groups.setdefault(f(r), []).append(s)
        out[name] = {g: {"n": len(v), "set_f1": float(np.mean([s["set_f1"] for s in v])),
                         "exact_match": float(np.mean([s["exact_match"] for s in v]))} for g, v in sorted(groups.items())}
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="baseline name, advisor@<alias> or advisor/<version>")
    parser.add_argument("--split", required=True, help="file in data/sft/: val, test, programme_holdout, gold, shifted, ...")
    parser.add_argument("--reason", default="", help="why a protected split is used (goes to TEST_SET_LOG.md)")
    parser.add_argument("--compare", default=None, help="scores.jsonl of another system on the same split, for paired tests")
    parser.add_argument("--batch_size", type=int, default=8, help="generation batch size")
    parser.add_argument("--rescore", action="store_true",
                        help="score the saved predictions again (labels changed, prompts did not); gold_a1 reuses gold's")
    opt = parser.parse_args()
    print(opt)

    mlflow.set_tracking_uri(f"sqlite:///{ROOT}/mlflow.db")
    name, run_id, adapter = resolve(opt.model)
    if opt.split in PROTECTED and not opt.reason:
        raise SystemExit("protected split: give --reason")
    rows = read_jsonl(ROOT / f"data/sft/{opt.split}.jsonl")

    # Raw answers
    out = ROOT / "supporting_files/C_eval" / name / opt.split
    saved = out / "preds.jsonl" if (out / "preds.jsonl").exists() else out.parent / "gold" / "preds.jsonl"
    from src.model import predict
    if opt.rescore:
        by_id = {p["query_id"]: p["response"] for p in read_jsonl(saved)}
        answers = [by_id[r["query_id"]] for r in rows]
    elif name == "trivial":
        answers = predict.trivial_answers(rows)
    else:
        tok, model = predict.load_model(str(adapter) if adapter else None)
        answers = predict.generate(tok, model, predict.build_prompts(rows, "lora" if adapter else name), opt.batch_size)

    # Scores
    catalogs = {"v1": load_catalog(), "v2": None}
    if any(r.get("catalog_version") == "v2" for r in rows):
        catalogs["v2"] = load_catalog(ROOT / "data/a2/courses_v2.json", RULES_PATH)  # shifted and pool rows
    students = {s["student_id"]: s for s in read_jsonl(ROOT / "data/processed/students.jsonl")
                + read_jsonl(ROOT / "data/processed/students_augmented.jsonl")}
    for extra in ROOT.glob("data/a2/students_*.jsonl"):
        students.update({s["student_id"]: s for s in read_jsonl(extra)})
    scores = [{"query_id": r["query_id"], **score_row(a, r, students[r["student_id"]], catalogs[r.get("catalog_version", "v1")])}
              for r, a in zip(rows, answers)]

    write_jsonl(out / "preds.jsonl", [{"query_id": r["query_id"], "response": a} for r, a in zip(rows, answers)])
    write_jsonl(out / "scores.jsonl", scores)
    result = {"model": opt.model, "name": name, "run_id": run_id, "split": opt.split, "n": len(rows),
              "labels": "D6" if opt.split != "gold_a1" else "A1", "rescored": opt.rescore, "summary": summarise(scores), "ci": bootstrap(scores, params["seeds"]["bootstrap"]),
              "slices": slices(rows, scores)}
    if opt.compare:
        other = {s["query_id"]: s for s in read_jsonl(opt.compare)}
        result["paired_vs"] = {"other": opt.compare, **paired(scores, [other[s["query_id"]] for s in scores],
                                                              params["seeds"]["bootstrap"])}
    json.dump(result, open(out / "metrics.json", "w"), indent=1)
    print(json.dumps({k: result[k] for k in ("name", "split", "n", "ci")}, indent=1))

    if opt.split in PROTECTED:
        with open(ROOT / "TEST_SET_LOG.md", "a") as f:
            f.write(f"| {datetime.datetime.utcnow():%Y-%m-%d %H:%M} | {opt.split} | {opt.model} ({name}) | {run_id or '-'} | "
                    f"{opt.reason}{' (rescored saved predictions)' if opt.rescore else ''} |\n")
