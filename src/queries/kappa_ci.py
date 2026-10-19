"""Bootstrap 95% confidence intervals for the round-1 and round-2 Cohen's kappa (items resampled, seeded)."""
import json
import random
from pathlib import Path

import yaml
from sklearn.metrics import cohen_kappa_score

from src.queries.ls_export import read_export

ROOT = Path(__file__).resolve().parents[2]
N_BOOT = 2000


def pairs(rnd, level):
    a, _ = read_export(ROOT / f"data/labels/round{rnd}/export_A1.json", "A1")
    b, _ = read_export(ROOT / f"data/labels/round{rnd}/export_A2.json", "A2")
    ids = sorted(set(a) & set(b))
    return [(a[i][level], b[i][level]) for i in ids]


def boot_ci(p, seed):
    rng = random.Random(seed)
    ks = []
    for _ in range(N_BOOT):
        s = [rng.choice(p) for _ in p]
        x, y = zip(*s)
        if len(set(x) | set(y)) > 1:
            ks.append(cohen_kappa_score(x, y))
    ks.sort()
    return ks[int(0.025 * len(ks))], ks[int(0.975 * len(ks)) - 1]


def main():
    seed = yaml.safe_load(open(ROOT / "params.yaml"))["seeds"]["annotation_order"]
    out = {"n_boot": N_BOOT, "seed": seed}
    for rnd in (1, 2):
        for level in ("decision", "error_category"):
            p = pairs(rnd, level)
            x, y = zip(*p)
            lo, hi = boot_ci(p, seed)
            out[f"round{rnd}_{level}"] = {"kappa": round(cohen_kappa_score(x, y), 3), "ci95": [round(lo, 3), round(hi, 3)], "n": len(p)}
    path = ROOT / "supporting_files/C_labelling/kappa_ci.json"
    path.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
