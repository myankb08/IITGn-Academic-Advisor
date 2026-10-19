"""Draw the report figures (reports/fig_*.png) from the evidence files. Run: .venv/bin/python reports/make_figures.py"""
import csv
import json
import re
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
ACCENT = "#1f6f8b"
GREY = "#a7b0b7"
LIGHT = "#cfe3ea"

plt.rcParams.update({
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.titlesize": 9.5,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=200)
    plt.close(fig)


def validation():
    """Failures per check on the raw catalog and after cleaning, from before_after.md."""
    rows = []
    for line in (ROOT / "supporting_files/B_validation/before_after.md").read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and re.fullmatch(r"V\d\d", cells[0]):
            raw = int(cells[2].split()[0])
            if raw:
                rows.append((cells[0], raw, int(cells[5])))
    labels = {"V02": "code format", "V03": "credit values", "V05": "required fields", "V06": "duplicate codes",
              "V07": "duplicate records", "V08": "title vs timetable", "V09": "title spacing",
              "V10": "near-duplicate titles (warn)"}
    rows = rows[::-1]
    fig, ax = plt.subplots(figsize=(5.0, 2.1))
    y = range(len(rows))
    ax.barh(list(y), [r[1] for r in rows], height=0.6, color=GREY)
    for i, r in enumerate(rows):
        ax.text(r[1] + 0.8, i, f"{r[1]} \u2192 {r[2]}", va="center", fontsize=8,
                color=ACCENT if r[2] == 0 else "#7a5300")
    ax.set_yticks(list(y), [f"{r[0]} {labels.get(r[0], '')}" for r in rows])
    ax.set_xlabel("failing records (labels: raw \u2192 after cleaning)")
    ax.set_xlim(0, max(r[1] for r in rows) * 1.25)
    save(fig, "fig_validation.png")


def kappa():
    """Cohen's kappa per round with 95% CI (kappa_ci.json) and the decision confusion matrices (confusion_decision.csv)."""
    k = json.loads((ROOT / "supporting_files/C_labelling/kappa_ci.json").read_text())
    fig, axes = plt.subplots(1, 3, figsize=(6.5, 2.2), gridspec_kw={"width_ratios": [1.25, 1, 1]})
    ax = axes[0]
    for j, level in enumerate(["decision", "error_category"]):
        for i, (rnd, col) in enumerate([(1, GREY), (2, ACCENT)]):
            d = k[f"round{rnd}_{level}"]
            x = j + (i - 0.5) * 0.36
            ax.bar(x, d["kappa"], width=0.34, color=col, label=f"round {rnd}" if j == 0 else None)
            ax.errorbar(x, d["kappa"], yerr=[[d["kappa"] - d["ci95"][0]], [d["ci95"][1] - d["kappa"]]],
                        color="#333", capsize=3, lw=0.9)
            ax.text(x, 0.015, f"{d['kappa']:.2f}", ha="center", fontsize=7.5, color="white", fontweight="bold")
    ax.set_xticks([0, 1], ["decision", "category"])
    ax.set_ylabel("Cohen's kappa")
    ax.set_ylim(0, 0.85)
    ax.set_title("Kappa, 95% CI")
    ax.legend(frameon=False, fontsize=7.5, loc="upper center", ncol=2)
    for rnd, ax in zip((1, 2), axes[1:]):
        rows = list(csv.reader(open(ROOT / f"supporting_files/C_labelling/round{rnd}/confusion_decision.csv")))
        m = [[int(v) for v in r[1:]] for r in rows[1:]]
        ax.imshow(m, cmap="Blues", vmin=0, vmax=30)
        for i in range(3):
            for j in range(3):
                ax.text(j, i, str(m[i][j]), ha="center", va="center", fontsize=8.5,
                        color="white" if m[i][j] > 15 else "#222")
        ticks = ["accept", "edit", "reject"]
        ax.set_xticks(range(3), ticks, fontsize=7.5)
        ax.set_yticks(range(3), ticks, fontsize=7.5)
        ax.set_xlabel("A2", fontsize=8)
        ax.set_ylabel("A1", fontsize=8)
        ax.set_title(f"Decisions, round {rnd}")
        ax.spines[:].set_visible(False)
    save(fig, "fig_kappa.png")


def active_learning():
    """Failures captured and failure types covered per budget, from label_efficiency.csv."""
    rows = list(csv.DictReader(open(ROOT / "supporting_files/D_active_learning/label_efficiency.csv")))
    style = {"active_learning": ("top-k by disagreement", ACCENT, "-"),
             "active_learning_stratified": ("top-k per intent (added later)", "#c0752b", "-"),
             "random": ("random, 5 seeds", GREY, "--")}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.3, 2.1))
    for name, (label, col, ls) in style.items():
        r = [x for x in rows if x["strategy"] == name]
        b = [int(x["budget"]) for x in r]
        a1.plot(b, [float(x["failures_captured"]) for x in r], ls, marker="o", color=col, label=label, ms=4)
        a2.plot(b, [float(x["failure_types_covered"]) for x in r], ls, marker="o", color=col, ms=4)
    a1.set_title("Share of the 232 failures found")
    a2.set_title("Share of failure types covered")
    for a in (a1, a2):
        a.set_xlabel("labelling budget (pairs)")
        a.set_xticks([25, 50, 100])
    a2.set_ylim(0.5, 1.05)
    a1.legend(frameon=False, fontsize=7, loc="upper left")
    save(fig, "fig_al.png")


def augment():
    """Pass rate per augmentation and the slots lost by failing LLM paraphrases, from invariance.csv."""
    rows = list(csv.DictReader(open(ROOT / "supporting_files/D_augmentation/invariance.csv")))
    names = {"paraphrase": "LLM paraphrase", "typo_abbrev": "typos, abbreviations",
             "transcript_reorder": "transcript order", "transcript_length": "transcript length"}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.3, 2.0), gridspec_kw={"width_ratios": [1.1, 1]})
    rows = rows[::-1]
    for i, r in enumerate(rows):
        rate = float(r["invariance_rate"])
        a1.barh(i, 1, color=LIGHT, height=0.6)
        a1.barh(i, rate, color=ACCENT if rate < 1 else GREY, height=0.6)
        a1.text(1.02, i, f"{r['n_pass']} / {r['n_children']}", va="center", fontsize=7.5)
    a1.set_yticks(range(len(rows)), [names[r["augmentation"]] for r in rows])
    a1.set_xlim(0, 1.55)
    a1.set_xticks([0, 0.5, 1])
    a1.set_title("Children kept by the check")
    slots = Counter()
    para = next(r for r in rows if r["augmentation"] == "paraphrase")
    for part in para["fail_reasons"].split(";"):
        key, n = part.split("=")
        for s in key.split(":")[1].split("+"):
            slots[s] += int(n)
    order = slots.most_common()[::-1]
    a2.barh(range(len(order)), [n for _, n in order], color=ACCENT, height=0.6)
    for i, (_, n) in enumerate(order):
        a2.text(n + 0.8, i, str(n), va="center", fontsize=7.5)
    a2.set_yticks(range(len(order)), [s.replace("_", " ") for s, _ in order])
    a2.set_title(f"Facts lost, {para['n_fail']} failures")
    a2.set_xlim(0, max(slots.values()) * 1.2)
    fig.tight_layout(w_pad=2.5)
    fig.savefig(OUT / "fig_augment.png", dpi=200)
    plt.close(fig)


def splits():
    """Original pairs and augmented children per split, plus the real form questions, from the split summaries."""
    s = json.loads((ROOT / "supporting_files/E_splits/split_summary.json").read_text())
    f = json.loads((ROOT / "supporting_files/E_splits/shifted_summary.json").read_text())
    names = ["train", "val", "test", "programme_holdout"]
    orig = [s["original_rows_per_split"][n] for n in names] + [f["n_rows"]]
    child = [s["child_rows_per_split"][n] for n in names] + [0]
    labels = ["train", "val", "test", "ICDT holdout", "shifted (forms)"][::-1]
    orig, child = orig[::-1], child[::-1]
    fig, ax = plt.subplots(figsize=(5.0, 2.2))
    y = range(len(labels))
    ax.barh(y, orig, color=ACCENT, height=0.6, label="original pairs")
    ax.barh(y, child, left=orig, color=GREY, height=0.6, label="augmented children")
    for i in y:
        ax.text(orig[i] + child[i] + 12, i, f"{orig[i]} + {child[i]}" if child[i] else str(orig[i]),
                va="center", fontsize=7.5)
    ax.set_yticks(list(y), labels)
    ax.set_xlabel("rows")
    ax.set_xlim(0, max(o + c for o, c in zip(orig, child)) * 1.18)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=8)
    save(fig, "fig_splits.png")


if __name__ == "__main__":
    validation()
    kappa()
    augment()
    active_learning()
    splits()
