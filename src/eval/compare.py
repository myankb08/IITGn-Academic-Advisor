"""Comparison table: one model against every baseline on every split, from saved scores (no new predictions).

For each split: mean and 95% bootstrap CI of set_f1 and exact_match per system (from metrics.json), and paired
tests of the model against each baseline: paired bootstrap on set_f1 and exact McNemar on exact_match
(src.eval.evaluate.paired). Output: supporting_files/C_eval/comparison_<name>.{json,md}.
Example: python -m src.eval.compare --name advisor_v1
"""
import argparse
import json

import yaml

from src.augment.common import ROOT, read_jsonl
from src.eval.evaluate import paired

params = yaml.safe_load(open(ROOT / "params_a2.yaml"))
BASELINES = ["trivial", "zero_shot", "few_shot", "retrieval"]
SPLITS = ["val", "test", "gold", "shifted"]

parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True, help="model folder in supporting_files/C_eval, e.g. advisor_v1")
opt = parser.parse_args()
print(opt)

E = ROOT / "supporting_files/C_eval"
pval = lambda p: "<0.001" if p == 0 else f"={p:.3f}"  # 1000 bootstrap resamples: 0 means below 1/1000
fmt = lambda c: f"{c['mean']:.3f} [{c['ci95'][0]:.3f}, {c['ci95'][1]:.3f}]"
out, md = {}, ["| split | system | set F1 [95% CI] | exact match [95% CI] | vs model: F1 diff [CI], p | McNemar p |",
               "|---|---|---|---|---|---|"]
for split in SPLITS:
    m = json.load(open(E / opt.name / split / "metrics.json"))
    ms = read_jsonl(E / opt.name / split / "scores.jsonl")
    md.append(f"| {split} | **{opt.name}** (run {m['run_id'][:8]}) | {fmt(m['ci']['set_f1'])} | {fmt(m['ci']['exact_match'])} | | |")
    out[split] = {opt.name: m["ci"]}
    for b in BASELINES:
        bm = json.load(open(E / b / split / "metrics.json"))
        bs = {s["query_id"]: s for s in read_jsonl(E / b / split / "scores.jsonl")}
        t = paired(ms, [bs[s["query_id"]] for s in ms], params["seeds"]["bootstrap"])
        out[split][b] = {**bm["ci"], "paired_model_minus_baseline": t}
        d = t["set_f1_diff_ci95"]
        md.append(f"| {split} | {b} | {fmt(bm['ci']['set_f1'])} | {fmt(bm['ci']['exact_match'])} | "
                  f"{t['set_f1_diff']:+.3f} [{d[0]:+.3f}, {d[1]:+.3f}], p{pval(t['set_f1_p_one_sided'])} | "
                  f"{t['mcnemar_exact_match']['p']:.2g} |")
json.dump(out, open(E / f"comparison_{opt.name}.json", "w"), indent=1)
(E / f"comparison_{opt.name}.md").write_text("\n".join(md) + "\n")
print("\n".join(md))
