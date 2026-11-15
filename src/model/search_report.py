"""Search analysis for Part B: every advisor-search run as a table, and two plots.

1. Heatmap of val set F1 over LoRA rank x learning rate (base_aug mix, 1.5B, 2 epochs).
2. Quality against cost: val set F1 against GPU generation time per answer, marker size = adapter size, one colour
   per base model size; the selected run is circled.
Outputs: supporting_files/B_search/search_runs.csv, search_heatmap.png, search_tradeoff.png.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np

from src.augment.common import ROOT

SELECTED = "cb7c02b778d342e2b5a30f163ac8ee74"
out = ROOT / "supporting_files/B_search"
out.mkdir(parents=True, exist_ok=True)
mlflow.set_tracking_uri(f"sqlite:///{ROOT}/mlflow.db")

r = mlflow.search_runs(experiment_names=["advisor-search"])
cols = {"run_id": "run_id", "tags.mlflow.runName": "name", "status": "status", "params.base": "base",
        "params.data_mix": "data_mix", "params.rank": "rank", "params.lr": "lr", "params.epochs": "epochs",
        "params.n_train_rows": "train_rows", "metrics.val_set_f1": "val_set_f1", "metrics.val_exact_match": "val_exact_match",
        "metrics.val_violations": "val_violations", "metrics.val_invented_rate": "val_invented_rate",
        "metrics.train_minutes": "train_minutes", "metrics.val_gen_sec_per_row_gpu": "gen_sec_per_row_gpu",
        "metrics.adapter_mb": "adapter_mb", "tags.gpu": "gpu", "tags.git_commit": "git_commit"}
t = r[list(cols)].rename(columns=cols).sort_values("val_set_f1", ascending=False)
t["model"] = t.base.str.extract(r"Qwen2\.5-([\d.]+B)")[0]
t.to_csv(out / "search_runs.csv", index=False)
done = t[t.status == "FINISHED"].copy()
for c in ["rank", "lr", "epochs"]:
    done[c] = done[c].astype(float)
print(done[["name", "model", "data_mix", "rank", "lr", "epochs", "val_set_f1", "val_exact_match", "train_minutes", "adapter_mb"]]
      .round(3).to_string(index=False))

# 1. rank x lr heatmap (1.5B, base_aug, 2 epochs)
g = done[(done.model == "1.5B") & (done.data_mix == "base_aug") & (done.epochs == 2)]
ranks, lrs = sorted(g["rank"].unique()), sorted(g["lr"].unique())
grid = np.full((len(ranks), len(lrs)), np.nan)
for _, x in g.iterrows():
    grid[ranks.index(x["rank"]), lrs.index(x["lr"])] = x.val_set_f1
fig, ax = plt.subplots(figsize=(5.2, 3.8))
im = ax.imshow(grid, cmap="viridis", vmin=0.5, vmax=1.0)
for i in range(len(ranks)):
    for j in range(len(lrs)):
        if not np.isnan(grid[i, j]):
            ax.text(j, i, f"{grid[i, j]:.3f}", ha="center", va="center", color="white" if grid[i, j] < 0.8 else "black")
ax.set_xticks(range(len(lrs)), [f"{x:g}" for x in lrs])
ax.set_yticks(range(len(ranks)), [int(x) for x in ranks])
ax.set_xlabel("learning rate")
ax.set_ylabel("LoRA rank")
ax.set_title("Val set F1, 1.5B, base_aug, 2 epochs")
fig.colorbar(im, ax=ax)
fig.tight_layout()
fig.savefig(out / "search_heatmap.png", dpi=130)

# 2. quality vs cost
fig, ax = plt.subplots(figsize=(6.4, 4.2))
for m, c in [("0.5B", "#d4722b"), ("1.5B", "#1f6feb"), ("3B", "#2a9d58")]:
    s = done[done.model == m]
    ax.scatter(s.gen_sec_per_row_gpu, s.val_set_f1, s=s.adapter_mb * 1.5, color=c, alpha=0.7, label=f"Qwen2.5-{m}")
sel = done[done.run_id == SELECTED]
ax.scatter(sel.gen_sec_per_row_gpu, sel.val_set_f1, s=420, facecolors="none", edgecolors="black", linewidths=1.5,
           label="selected (1.5B, r32, lr 5e-4, 3 epochs)")
ax.set_xlabel("generation time per val answer on GPU (s); marker area = adapter size")
ax.set_ylabel("val set F1")
ax.set_title("Search: quality against latency and size")
ax.legend(fontsize=8, loc="lower right")
fig.tight_layout()
fig.savefig(out / "search_tradeoff.png", dpi=130)
print(f"{len(t)} runs ({len(done)} finished) -> {out}")
