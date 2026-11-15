"""Replay traffic that shifts gradually from val to the shifted split, and watch drift signals (Part E).

Requests: val rows (curriculum v1) before the shift; shifted rows (MTech-ICDT under curriculum v2) and the 19 real
Google Forms questions after it. The shifted share rises linearly between replay.shift_start and replay.shift_full
(params_a2.yaml), sampled with seeds.replay. Answers come from one registered model version (fp16 on GPU, same
weights as the int8 service, cached per version).
Signals per window: label-free rule_rejection_rate (service rule check, forms excluded: no transcript codes),
query_drift (cosine distance of the hashed bag-of-words centroid from val), answer_chars, unknown_code_rate;
labelled set_f1 (forms excluded). Thresholds: replay.quantile of each signal over val-only windows.
Outputs: supporting_files/E_monitoring/<name>/; thresholds also go to release/serving/monitoring_thresholds.json (UI, image).
"""
import argparse
import datetime
import json

import matplotlib
import numpy as np
import pandas as pd
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.augment.common import ROOT, read_jsonl, write_jsonl
from src.engine.catalog import RULES_PATH, load_catalog
from src.eval.evaluate import resolve
from src.eval.metrics import score_row
from src.active.base_model_answers import parse_json
from src.active.disagreement import STRICT_CODE_RE, norm
from src.serve.core import hashed_query, rule_answer, rule_check

params = yaml.safe_load(open(ROOT / "params_a2.yaml"))
P = params["replay"]

parser = argparse.ArgumentParser()
parser.add_argument("--model", default="advisor@production", help="registered model, advisor@<alias> or advisor/<version>")
opt = parser.parse_args()
print(opt)

import mlflow
mlflow.set_tracking_uri(f"sqlite:///{ROOT}/mlflow.db")
name, run_id, adapter = resolve(opt.model)
out = ROOT / "supporting_files/E_monitoring" / name
out.mkdir(parents=True, exist_ok=True)

# ----------
#  Answers for every request candidate (cached per version)
# ----------
pools = {"val": read_jsonl(ROOT / "data/sft/val.jsonl"), "shifted": read_jsonl(ROOT / "data/sft/shifted.jsonl"),
         "forms": read_jsonl(ROOT / "data/sft/forms.jsonl")}
cache = out / "answers.jsonl"
if not cache.exists():
    from src.model import predict
    tok, model = predict.load_model(str(adapter))
    rows = [r for p in pools.values() for r in p]
    answers = predict.generate(tok, model, [r["prompt"] for r in rows])
    write_jsonl(cache, [{"split": r["split"], "query_id": r["query_id"], "response": a} for r, a in zip(rows, answers)])
answer = {(a["split"], a["query_id"]): a["response"] for a in read_jsonl(cache)}

# Per-request features (computed once per candidate)
v1, v2 = load_catalog(), load_catalog(ROOT / "data/a2/courses_v2.json", RULES_PATH)
students = {s["student_id"]: s for f in ["data/processed/students.jsonl", "data/processed/students_augmented.jsonl"]
            for s in read_jsonl(ROOT / f)}
feats = {}
for split, rows in pools.items():
    cat = v1 if split == "val" else v2
    for r in rows:
        text = answer[(r["split"], r["query_id"])]
        f = {"query_vec": np.array(hashed_query(r["query"]), float), "answer_chars": len(text),
             "unknown_code": float(bool({norm(m.group(0)) for m in STRICT_CODE_RE.finditer(text)} - set(cat.courses))),
             "rule_rejected": np.nan, "set_f1": np.nan}
        if split != "forms":
            st = students[r["student_id"]]
            ref = rule_answer(r["intent"], st, r.get("target_course"), catalog=cat)
            f["rule_rejected"] = float(not rule_check(r["intent"], parse_json(text), ref, st, catalog=cat)[0])
            f["set_f1"] = score_row(text, r, st, cat)["set_f1"]
        feats[(split, r["query_id"])] = f
ref_vec = np.mean([feats[("val", r["query_id"])]["query_vec"] for r in pools["val"]], 0)


def window_signals(keys):
    """Signals of one window of request keys."""
    fs = [feats[k] for k in keys]
    c = np.mean([f["query_vec"] for f in fs], 0)
    return {"rule_rejection_rate": np.nanmean([f["rule_rejected"] for f in fs]),
            "query_drift": 1 - float(c @ ref_vec / (np.linalg.norm(c) * np.linalg.norm(ref_vec))),
            "answer_chars": np.mean([f["answer_chars"] for f in fs]),
            "unknown_code_rate": np.mean([f["unknown_code"] for f in fs]),
            "set_f1": np.nanmean([f["set_f1"] for f in fs])}


# ----------
#  Thresholds from val-only windows
# ----------
rng = np.random.default_rng(params["seeds"]["replay"])
val_keys = [("val", r["query_id"]) for r in pools["val"]]
calib = pd.DataFrame([window_signals([val_keys[i] for i in rng.integers(0, len(val_keys), P["window_size"])])
                      for _ in range(P["calib_windows"])])
signals = ["rule_rejection_rate", "query_drift", "answer_chars", "unknown_code_rate"]
thresholds = {s: float(calib[s].quantile(P["quantile"])) for s in signals}

# ----------
#  Replay
# ----------
shift_keys = [("shifted", r["query_id"]) for r in pools["shifted"]]
form_keys = [("forms", r["query_id"]) for r in pools["forms"]]
log, windows = [], []
for w in range(P["windows"]):
    share = float(np.clip((w - P["shift_start"] + 1) / (P["shift_full"] - P["shift_start"] + 1), 0, 1))
    keys = []
    for i in range(P["window_size"]):
        if rng.random() >= share:
            keys.append(val_keys[rng.integers(len(val_keys))])
        elif rng.random() < P["forms_share"]:
            keys.append(form_keys[rng.integers(len(form_keys))])
        else:
            keys.append(shift_keys[rng.integers(len(shift_keys))])
        log.append({"window": w, "request": i, "split": keys[-1][0], "query_id": keys[-1][1]})
    s = window_signals(keys)
    windows.append({"window": w, "shift_share": share, **s,
                    **{f"alert_{k}": bool(s[k] > thresholds[k]) for k in P["alert_signals"]}})
df = pd.DataFrame(windows)
df["alert"] = df[[f"alert_{k}" for k in P["alert_signals"]]].any(axis=1)

# Detection delay, false alarms, and whether the label-free signals track quality
first_shift = int(df.index[df.shift_share > 0][0])
alerts_after = df.index[(df.shift_share > 0) & df.alert]
summary = {"model": opt.model, "name": name, "run_id": run_id, "thresholds": thresholds, "params": P,
           "shift_start_window": first_shift,
           "first_alert_window": int(alerts_after[0]) if len(alerts_after) else None,
           "detection_delay_windows": int(alerts_after[0]) - first_shift if len(alerts_after) else None,
           "false_alarms_before_shift": int(df.alert[df.shift_share == 0].sum()),
           "pre_shift_windows": int((df.shift_share == 0).sum()),
           "spearman_with_set_f1": {k: float(df[k].corr(df.set_f1, method="spearman")) for k in signals}}
write_jsonl(out / "replay_log.jsonl", log)
df.to_csv(out / "windows.csv", index=False)
calib.to_csv(out / "calibration_windows_val.csv", index=False)
json.dump(summary, open(out / "summary.json", "w"), indent=1)
json.dump({**{k: thresholds[k] for k in signals}, "window_size": P["window_size"], "query_ref_vec": ref_vec.tolist()},
          open(ROOT / "release/serving/monitoring_thresholds.json", "w"), indent=1)  # shipped in the image
with open(ROOT / "TEST_SET_LOG.md", "a") as f:
    f.write(f"| {datetime.datetime.utcnow():%Y-%m-%d %H:%M} | shifted | {opt.model} ({name}) | {run_id} | Part E replay: labelled set_f1 per window |\n")

# Plot: signals with thresholds, and set_f1, per window
fig, axes = plt.subplots(5, 1, figsize=(8, 11), sharex=True)
for ax, k in zip(axes, signals + ["set_f1"]):
    ax.plot(df.window, df[k], marker="o")
    if k in thresholds:
        ax.axhline(thresholds[k], color="red", ls="--", label=f"threshold (val q{P['quantile']})")
        ax.legend(loc="upper left", fontsize=8)
    ax.axvline(first_shift - 0.5, color="grey", ls=":")
    ax.set_ylabel(k, fontsize=9)
axes[-1].set_xlabel("window (25 requests); dotted line = shift starts")
fig.suptitle(f"Replay with gradual shift, {name}")
fig.tight_layout()
fig.savefig(out / "replay.png", dpi=120)
print(json.dumps({k: v for k, v in summary.items() if k != "params"}, indent=1))
