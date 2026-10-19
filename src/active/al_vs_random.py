"""Compare disagreement-based active learning with random selection at the params.yaml budgets.

AL takes the top-k pool pairs by score; ties are broken by a shuffle seeded with each seed in
seeds.active_learning (results averaged, they only differ inside tied groups). Random takes k
pairs uniformly, averaged over the same seeds. Metrics per budget: share of all base-model
failures captured, share of the failure types present in the pool that are covered, and the
number of distinct programmes and intents covered.
"""
import argparse
import csv
import json
import random
from pathlib import Path
from statistics import mean, pstdev

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.active.disagreement import FAILURE_TYPES, OUT as SCORES  # noqa: E402
from src.augment.common import ROOT, read_jsonl, rel  # noqa: E402
from src.engine.catalog import load_params  # noqa: E402

OUT_DIR = ROOT / "supporting_files" / "D_active_learning"
METRICS = ["failures_captured", "failure_types_covered", "programmes_covered", "intents_covered"]


def metrics(picked, pool):
    total_fail = sum(p["failed"] for p in pool)
    types_pool = {t for p in pool for t in p["failures"]}
    types_got = {t for p in picked for t in p["failures"]}
    return {"failures_captured": sum(p["failed"] for p in picked) / total_fail if total_fail else 0.0,
            "failure_types_covered": len(types_got) / len(types_pool) if types_pool else 0.0,
            "programmes_covered": len({p["programme"] for p in picked}),
            "intents_covered": len({p["intent"] for p in picked})}


def al_pick(pool, k, seed):
    rng = random.Random(seed)
    order = list(pool)
    rng.shuffle(order)
    return sorted(order, key=lambda p: -p["score"])[:k]


def al_stratified_pick(pool, k, seed):
    """Same score, but the budget is shared evenly across intents (round robin over per-intent rankings).
    Added after the first run showed plain top-k drawing every pick from one intent."""
    rng = random.Random(seed)
    order = list(pool)
    rng.shuffle(order)
    ranked = {}
    for p in sorted(order, key=lambda p: -p["score"]):
        ranked.setdefault(p["intent"], []).append(p)
    queues = [ranked[i] for i in sorted(ranked)]
    picked = []
    while len(picked) < min(k, len(pool)):
        for q in queues:
            if q and len(picked) < k:
                picked.append(q.pop(0))
    return picked


def random_pick(pool, k, seed):
    return random.Random(seed).sample(pool, min(k, len(pool)))


STRATEGIES = (("active_learning", al_pick), ("active_learning_stratified", al_stratified_pick),
              ("random", random_pick))
LABELS = {"active_learning": "AL (disagreement, top-k)", "active_learning_stratified": "AL stratified by intent (added later)",
          "random": "random (5 seeds)"}
COLORS = {"active_learning": "#1f6feb", "active_learning_stratified": "#d4722b", "random": "#999999"}


def run(pool, budgets, seeds):
    rows = []
    for k in budgets:
        for name, fn in STRATEGIES:
            per_seed = [metrics(fn(pool, k, s), pool) for s in seeds]
            row = {"budget": k, "strategy": name, "n_seeds": len(seeds)}
            for m in METRICS:
                vals = [x[m] for x in per_seed]
                row[m] = round(mean(vals), 4)
                row[f"{m}_sd"] = round(pstdev(vals), 4)
            rows.append(row)
    return rows


def plot(rows, path):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    panels = [("failures_captured", "Share of base-model failures captured"),
              ("failure_types_covered", "Share of failure types covered"),
              ("intents_covered", "Distinct intents covered (of 3)")]
    for ax, (m, title) in zip(axes, panels):
        for name, _ in STRATEGIES:
            pts = [r for r in rows if r["strategy"] == name]
            xs, ys, sd = [r["budget"] for r in pts], [r[m] for r in pts], [r[f"{m}_sd"] for r in pts]
            ax.errorbar(xs, ys, yerr=sd, marker="o", capsize=3, color=COLORS[name], label=LABELS[name])
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("labelling budget (pairs)")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def write_summary(rows, pool, pool_note, path):
    lines = ["# Active learning vs random selection", "",
             f"Pool: {len(pool)} pairs ({pool_note}). Base-model failures in the pool: "
             f"{sum(p['failed'] for p in pool)}. Failure types present: "
             + ", ".join(f"{t} {sum(t in p['failures'] for p in pool)}" for t in FAILURE_TYPES) + ".", "",
             "Score (see src/active/disagreement.py): 3 for invalid JSON, else (1 - Jaccard of course code sets) "
             "+ 1 for wrong eligibility + 1 for a wrong total credit gap + 1 for any code not in courses.json.", "",
             "| budget | strategy | failures captured | failure types covered | programmes | intents |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['budget']} | {r['strategy']} | {r['failures_captured']:.2f} (sd {r['failures_captured_sd']:.2f}) | "
                     f"{r['failure_types_covered']:.2f} | {r['programmes_covered']:.1f} | {r['intents_covered']:.1f} |")
    lines += ["", "Reading the first column: the selection score is computed from the same comparison with the rule "
              "engine that defines a failure, so every pair top-k picks is a failure (precision 1 by construction) "
              "and its 'failures captured' is simply budget / failures in the pool. The informative comparison is "
              "which failures each strategy reaches: failure types and intents covered. No model is retrained on "
              "the picks, so this is a label-efficiency comparison, not a learning curve."]
    lines += ["", "active_learning_stratified was added after the first run, which showed plain top-k drawing every "
              "pick from remaining_core; the original strategy and its numbers are kept unchanged.",
              "", "Random is the mean over the 5 seeds in seeds.active_learning; AL uses the same seeds only to "
              "break ties. A budget at or above the number of failures lets AL capture all of them, so the "
              "interesting comparison is at budgets below that number.", ""]
    path.write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scores", default=str(SCORES))
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    params = load_params()
    pool = read_jsonl(args.scores)
    run_log = OUT_DIR / "base_model_run.json"
    pool_note = json.loads(run_log.read_text()).get("pool") if run_log.exists() else "see base_model_run.json"
    rows = run(pool, params["active_learning"]["budgets"], params["seeds"]["active_learning"])
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "label_efficiency.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    plot(rows, out_dir / "label_efficiency.png")
    write_summary(rows, pool, pool_note, out_dir / "summary.md")
    print(json.dumps(rows, indent=1))
    print("wrote", rel(out_dir / "label_efficiency.csv"), rel(out_dir / "label_efficiency.png"))


if __name__ == "__main__":
    main()
