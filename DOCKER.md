# Docker image: IITGN course advisor

CPU only, `linux/amd64`, no network at run time. The image holds the merged advisor model (weight-only int8 at load),
the curriculum and rule engine, the gold test set with its prompts, the UI and the REST API.

| item | value |
|---|---|
| image | `iitgn-advisor:a2` |
| archive | `artefacts/docker_image.tar.gz` <!-- IMAGE_SHA --> |
| image size | 4.44 GB (`docker images`); the gzipped archive is smaller |
| model | `advisor` v10, alias `production` (run `aa644d3c4b984c7e8f19446c7c060a72`), base `Qwen/Qwen2.5-1.5B-Instruct@989aa79`; merged weights sha256 `bbb11b0403d1df7f22393c6be92b00737774d9a9ea7d22c7c7b95b81e5f08baa` when built on arka (`/app/models/production/model_info.json`) |
| RAM | 3.5 GiB peak in the load test (`docker stats`); all runs used a `--memory 8g` container limit; the clean-machine test is below |
| CPU | 8 cores recommended; numbers below are for 8 cores of an Intel i9-10900X (`--cpus 8`) |
| commit | written into the image at build time (`/app/COMMIT`), shown in the UI and at `/version` |

## Load (from the archive) or build

```bash
docker load -i artefacts/docker_image.tar.gz          # loads iitgn-advisor:a2
# or rebuild from the repository at tag a2-final (needs network at build time only):
cd code && docker build -t iitgn-advisor:a2 .
```

The build reads the commit from `.git`, checks the released adapter (`release/ADAPTER_SHA256.txt`), downloads the base
model at the pinned revision, merges them and records the merged weights' SHA-256 in `models/production/model_info.json`.

## Start the service and UI

```bash
docker run --rm -p 7860:7860 --cpus 8 --memory 8g iitgn-advisor:a2
```

Open http://localhost:7860 (UI: Ask, Monitoring and Validation tabs). The same port serves the REST API:

```bash
curl localhost:7860/health
curl localhost:7860/version
curl -X POST localhost:7860/predict -H 'content-type: application/json' -d '{"query": "Can I register for EE 618 next term?",
  "intent": "eligibility", "programme": "MTech-ICDT", "track": "coursework", "semesters_completed": 1,
  "completed_courses": ["EE 644"], "target_course": "EE 618"}'
```

Request logs (no question text: a hashed word vector, lengths, parsed answer, latency, confidence, rule check) are
written to `/app/logs/requests.jsonl`; mount it with `-v $PWD/logs:/app/logs` to keep them.

## Validate the full gold set offline

```bash
mkdir -p out && docker run --rm --network none --cpus 8 --memory 8g -v $PWD/out:/app/out iitgn-advisor:a2 validate
```

It scores all 76 gold items on CPU, prints the metrics and the comparison with the reported values, saves
`out/validation.json` and exits 0 when every metric is within the tolerance (exit 1 otherwise). It takes about
66 minutes (3,952 s, 52 s per item) on 8 cores. Expected output (last lines; on another CPU the measured values may
differ within the tolerance):

```
{
 "set_f1": 0.8772,
 "precision": 0.9254,
 "recall": 0.9386,
 "exact_match": 0.7632,
 "valid_json": 1.0,
 "violations": 0.0132,
 "invented_codes": 0.0,
 "invented_rate": 0.0,
 "eligibility_acc": 0.8519
}
set_f1         measured 0.8772  reported 0.8772  tol 0.02  PASS
exact_match    measured 0.7632  reported 0.7632  tol 0.02  PASS
valid_json     measured 1.0000  reported 1.0000  tol 0.02  PASS
violations     measured 0.0132  reported 0.0132  tol 0.02  PASS
invented_rate  measured 0.0000  reported 0.0000  tol 0.02  PASS
saved /app/out/validation.json; 76 items in ...s
```

Tolerance: |measured - reported| <= 0.02 for set F1, exact match, valid JSON, violations and invented-code rate.
Greedy decoding is deterministic on one machine; other CPU types can change the last bits of the matmuls, which the
tolerance covers. The UI's Validation tab runs a fixed subset (the first 5 gold items by `item_id`, about 5 minutes)
because the full set is slow on CPU; `validate --subset 5` runs the same subset from the command line.

## Offline checks

1. `validate` above runs with `--network none`.
2. The UI: disconnect the machine from the internet, run the start command (only port 7860 published), open the UI,
   ask a bundled example and run the Validation tab. The code makes no outbound calls: Gradio analytics are off
   (`GRADIO_ANALYTICS_ENABLED=False`), the UI uses system fonts, and Hugging Face loading is offline
   (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`).
3. `docker run --rm --network none iitgn-advisor:a2 smoke` starts the service with no network and sends one request
   (also run by CI on each push).

## Latency, throughput and memory

Measured with `src/serve/loadtest.py` on 8 cores of an Intel i9-10900X (`--cpus 8 --memory 8g`), 10 val questions
per run, image with advisor v10 (`supporting_files/D_deploy/loadtest_c1.json`, `loadtest_c2.json`, memory samples in
`loadtest_mem_v10.txt`):

| clients | p50 latency | p95 latency | throughput | peak RAM |
|---|---|---|---|---|
| 1 | 60.9 s | 71.5 s | 1.00 requests/min | 3.5 GiB |
| 2 | 126.9 s | 147.9 s | 0.93 requests/min | 3.5 GiB |

The service runs one generation at a time and queues the rest (`generate_lock` in `src/serve/core.py`): with two
clients each request waits for the other, so latency doubles while throughput stays near one request per minute.
Before the lock (v1 image, `supporting_files/D_deploy/v1_before_lock/`), two clients shared the CPU threads and
throughput fell to 0.69 requests/min (p50 176 s). Latency is dominated by decoding about 200 answer tokens; the
prompt (about 1,500 tokens) takes about 5 s.

## Clean-machine test

<!-- CLEAN_MACHINE: on a second CPU-only machine (record its CPU, RAM and OS): load the archive, run validate with --network none, open the UI with the internet off, and record date, commands, time and result here -->
