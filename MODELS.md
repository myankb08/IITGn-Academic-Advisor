# Models

All models are LoRA adapters on `Qwen/Qwen2.5-1.5B-Instruct` at revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`
(Apache 2.0), unless a row says otherwise. Registry: MLflow model `advisor` (`artefacts/mlflow/`, exported from
`mlflow.db` and `mlruns/`). Every alias move is logged in `supporting_files/B_search/registry_log.jsonl`.

## Aliases at release

| alias | version | meaning |
|---|---|---|
| `production` | 10 | served by the image (`release/`, `DOCKER.md`) |
| `previous` | 1 | rollback target (`python -m src.model.register rollback`) |
| `staging` | 1 | the model selected in Part B |
| `candidate` | 10 | last candidate that went through the gate |
| `reproduce` | 4 | rerun of the Part B selection (`scripts/reproduce_a2.sh`) |
| `d6` | 6 | Part B configuration trained on the D6 labels |
| `d6r1-s301`, `d6r1-s311`, `d6r1-s312` | 7, 8, 9 | the three D16 candidates |

## Registered versions

| v | MLflow run | what | labels | outcome |
|---|---|---|---|---|
| 1 | `cb7c02b778d342e2b5a30f163ac8ee74` | Part B selection: rank 32, lr 5e-4, 3 epochs, `base_aug`, seed 301 (D10) | A1 | production until Part E; Part C system |
| 2 | `d12c4b8809ae462f88d5464735de76c4` | retrain r1: continued from v1, lr 5e-4, 100 revealed + 300 replay rows | A1 | rejected (gold EM drop 0.145) |
| 3 | `379b73e75c984ea9a18273d8e5927651` | retrain r2: continued from v1, lr 1e-4, 100 revealed + 600 replay rows (D11) | A1 | rejected (gold EM drop 0.053) |
| 4 | `46c2f3f095df43e18366f313c5b5b07e` | rerun of v1's configuration (reproducibility) | A1 | not deployed |
| 5 | `022eed302e4145f0bdc281e6560a3823` | retrain r3: from scratch on train + 100 revealed (D12) | A1 | rejected by the val guard (val EM drop 0.068), no gold run |
| 6 | `5fbec216ec044646906f147e8f05e75b` | v1's configuration trained on the D6 labels (D14) | D6 | not promoted (D15: val EM 0.807 < 0.821) |
| 7, 8, 9 | `f0bd1a89…`, `66af9762…`, `aa644d3c…` | d6r1 candidates, from scratch on train + 100 revealed, seeds 301 / 311 / 312 (D16) | D6 | val EM 0.764 / 0.786 / 0.814; seed 312 selected |
| 10 | `aa644d3c4b984c7e8f19446c7c060a72` | the selected d6r1 candidate (same run as v9) through the gate | D6 | **promoted**: shifted set F1 0.691 to 0.829 (p < 0.001), gold EM 0.750 to 0.750 |

Search runs that were not registered (27 in `advisor-search`, 3 killed seed-check and r4 runs) are in the MLflow export
and `supporting_files/B_search/search_runs.csv`.

## Released model (v10)

| item | value |
|---|---|
| adapter in git | `release/adapter/` (fp16 safetensors): `adapter_model.safetensors` sha256 `d81b20c323c0d221f7ee4dac0baccb25ab0ab9d3188ea264b708a7406a7e96c4`, `adapter_config.json` `bc91cd042a030f15f0e6030ab77c89e66a9b694d9291fa2afcd944735643a84b` (`release/ADAPTER_SHA256.txt`) |
| merged weights | built inside the image from the base revision above and the adapter; sha256 `bbb11b0403d1df7f22393c6be92b00737774d9a9ea7d22c7c7b95b81e5f08baa` when built on arka, recorded in `/app/models/production/model_info.json` (fp16 CPU merges on other CPU types may differ in the last bits) |
| serving format | every Linear layer weight-only int8 with per-channel scales at load (`src/serve/core.py`) |
| adapters of all versions | `models/runs/<run_id>/adapter/` (fp32), in `artefacts/models/` |

## Other pretrained models used

| model | revision | use |
|---|---|---|
| `Qwen/Qwen2.5-0.5B-Instruct` | `7ae557604adf67be50417f59c2c2f167def9a775` | search: size trade-off run |
| `Qwen/Qwen2.5-3B-Instruct` | `aa8e72537993ba99e69dfaafa59ed015b17504d1` | search: size trade-off run |
| `qwen2.5:1.5b` (GGUF Q4_K_M, A1) | Ollama digest `65ec0654…` | A1 paraphrases and base-model answers only (`ENVIRONMENT.md`) |
