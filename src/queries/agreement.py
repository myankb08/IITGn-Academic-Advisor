"""Inter-annotator agreement between A1 and A2 for one round.

Real run:    .venv/bin/python -m src.queries.agreement --round 1
Fixture run: .venv/bin/python -m src.queries.agreement --round 1 --fixture
Exports are only read, never modified.
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

from src.queries.ls_export import CATEGORIES, DECISIONS, read_export

ROOT = Path(__file__).resolve().parents[2]


def export_paths(rnd, fixture):
    if fixture:
        base = ROOT / "tests/fixtures"
        return base / f"fixture_round{rnd}_export_A1.json", base / f"fixture_round{rnd}_export_A2.json"
    base = ROOT / f"data/labels/round{rnd}"
    return base / "export_A1.json", base / "export_A2.json"


def save_confusion(a, b, labels, name, out):
    cm = confusion_matrix(a, b, labels=labels)
    pd.DataFrame(cm, index=[f"A1:{l}" for l in labels], columns=[f"A2:{l}" for l in labels]).to_csv(out / f"confusion_{name}.csv")
    fig, ax = plt.subplots(figsize=(1.2 + 0.9 * len(labels), 1.0 + 0.8 * len(labels)))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("A2")
    ax.set_ylabel("A1")
    ax.set_title(f"{name}: A1 vs A2")
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.tight_layout()
    fig.savefig(out / f"confusion_{name}.png", dpi=150)
    plt.close(fig)


def kappa(a, b, labels):
    if len(set(a) | set(b)) < 2:
        return None
    return float(cohen_kappa_score(a, b, labels=labels))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--fixture", action="store_true", help="read synthetic exports from tests/fixtures")
    args = ap.parse_args()
    p1, p2 = export_paths(args.round, args.fixture)
    for p in (p1, p2):
        if not p.exists():
            raise SystemExit(f"{p.relative_to(ROOT)} not found; run with --fixture to test")
    out = ROOT / "supporting_files/C_labelling" / (f"fixture_round{args.round}" if args.fixture else f"round{args.round}")
    out.mkdir(parents=True, exist_ok=True)
    r1, w1 = read_export(p1, "A1")
    r2, w2 = read_export(p2, "A2")
    common = sorted(set(r1) & set(r2))
    only = {"only_A1": sorted(set(r1) - set(r2)), "only_A2": sorted(set(r2) - set(r1))}
    rows = [(r1[i], r2[i]) for i in common if r1[i]["decision"] and r2[i]["decision"]]
    dec_a = [x["decision"] for x, _ in rows]
    dec_b = [y["decision"] for _, y in rows]
    cat_a = [x["error_category"] or "missing" for x, _ in rows]
    cat_b = [y["error_category"] or "missing" for _, y in rows]
    cat_labels = CATEGORIES + (["missing"] if "missing" in cat_a + cat_b else [])
    n = len(rows)
    summary = {
        "round": args.round,
        "fixture": args.fixture,
        "export_A1": str(p1.relative_to(ROOT)),
        "export_A2": str(p2.relative_to(ROOT)),
        "n_items_compared": n,
        "decision": {
            "cohen_kappa": kappa(dec_a, dec_b, DECISIONS),
            "percent_agreement": round(100 * sum(a == b for a, b in zip(dec_a, dec_b)) / n, 2) if n else None,
        },
        "error_category": {
            "cohen_kappa": kappa(cat_a, cat_b, cat_labels),
            "percent_agreement": round(100 * sum(a == b for a, b in zip(cat_a, cat_b)) / n, 2) if n else None,
        },
        "both_levels_percent_agreement": round(100 * sum(
            a == b and c == d for a, b, c, d in zip(dec_a, dec_b, cat_a, cat_b)) / n, 2) if n else None,
        "label_counts": {
            "A1_decision": pd.Series(dec_a).value_counts().to_dict(),
            "A2_decision": pd.Series(dec_b).value_counts().to_dict(),
            "A1_category": pd.Series(cat_a).value_counts().to_dict(),
            "A2_category": pd.Series(cat_b).value_counts().to_dict(),
        },
        **only,
        "warnings": w1 + w2,
    }
    if n:
        save_confusion(dec_a, dec_b, DECISIONS, "decision", out)
        save_confusion(cat_a, cat_b, cat_labels, "error_category", out)
    dis = []
    for x, y in rows:
        if x["decision"] != y["decision"] or x["error_category"] != y["error_category"]:
            d = x["data"]
            dis.append({
                "item_id": x["item_id"], "query_id": x["query_id"],
                "decision_A1": x["decision"], "decision_A2": y["decision"],
                "category_A1": x["error_category"], "category_A2": y["error_category"],
                "edit_A1": x["edit_text"], "edit_A2": y["edit_text"],
                "para_query": d.get("para_query"), "para_justification": d.get("para_justification"),
            })
    cols = ["item_id", "query_id", "decision_A1", "decision_A2", "category_A1", "category_A2",
            "edit_A1", "edit_A2", "para_query", "para_justification"]
    pd.DataFrame(dis, columns=cols).to_csv(out / "disagreements.csv", index=False)
    summary["n_disagreements"] = len(dis)
    with open(out / "agreement_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: summary[k] for k in ["n_items_compared", "decision", "error_category", "n_disagreements"]}, indent=2))
    for w in summary["warnings"]:
        print("warning:", w)
    print(f"written to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
