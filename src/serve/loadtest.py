"""CPU load test of the running service: p50/p95 latency and throughput for val questions sent to /predict.

Requests are the first --n val base rows (fixed), sent with --concurrency parallel clients. Memory is sampled
separately with `docker stats` (see DOCKER.md). Output: supporting_files/D_deploy/loadtest_c<concurrency>.json.
Example: python -m src.serve.loadtest --url http://127.0.0.1:7860 --n 20 --concurrency 1
"""
import argparse
import json
import platform
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from src.augment.common import ROOT, read_jsonl

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:7860", help="service base URL")
parser.add_argument("--n", type=int, default=20, help="number of requests")
parser.add_argument("--concurrency", type=int, default=1, help="parallel clients")
parser.add_argument("--hardware", default=platform.processor() or platform.machine(), help="hardware note for the record")
opt = parser.parse_args()
print(opt)

students = {s["student_id"]: s for s in read_jsonl(ROOT / "data/processed/students.jsonl")}
rows = [r for r in read_jsonl(ROOT / "data/sft/val.jsonl") if not r["augmentation"]][:opt.n]


def send(r):
    """One /predict call; returns (client latency s, server latency ms)."""
    s = students[r["student_id"]]
    body = {"query": r["query"], "intent": r["intent"], "programme": s["programme"], "stream": s["stream"],
            "track": s["track"], "semesters_completed": s["semesters_completed"],
            "completed_courses": [t["code"] for t in s["transcript"]], "target_course": r.get("target_course")}
    req = urllib.request.Request(f"{opt.url}/predict", data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json"})
    t0 = time.time()
    out = json.load(urllib.request.urlopen(req, timeout=900))
    return time.time() - t0, out["latency_ms"]


t0 = time.time()
with ThreadPoolExecutor(opt.concurrency) as pool:
    res = list(pool.map(send, rows))
wall = time.time() - t0
lat = np.array([r[0] for r in res])
result = {"n": len(res), "concurrency": opt.concurrency, "hardware": opt.hardware, "wall_s": round(wall, 1),
          "throughput_req_per_min": round(60 * len(res) / wall, 2),
          "latency_s": {"p50": round(float(np.percentile(lat, 50)), 2), "p95": round(float(np.percentile(lat, 95)), 2),
                        "mean": round(float(lat.mean()), 2)},
          "server_latency_ms_p50": float(np.percentile([r[1] for r in res], 50))}
out = ROOT / "supporting_files/D_deploy" / f"loadtest_c{opt.concurrency}.json"
out.parent.mkdir(parents=True, exist_ok=True)
json.dump(result, open(out, "w"), indent=1)
print(json.dumps(result, indent=1))
