# Environment

Everything in this repo was built and run on one laptop, CPU only. Values below were read on 2026-10-17
(`/etc/os-release`, `uname -a`, `lscpu`, `free -h`, `ollama --version`, `ollama list`, Ollama `/api/tags`).

## Machine
| item | value |
|---|---|
| OS | Ubuntu 22.04.5 LTS (Jammy Jellyfish) |
| Kernel | Linux 6.8.0-138-generic x86_64 (`#138~22.04.1-Ubuntu SMP PREEMPT_DYNAMIC`) |
| CPU | AMD Ryzen 5 2500U, 4 cores / 8 threads |
| RAM | 6.7 GiB, plus 2 GiB swap |
| GPU | local machine: none (integrated Radeon Vega, no CUDA). Kaggle: Tesla T4 (2 visible, model pinned to one), CUDA 12.8, torch 2.11.0+cu128, transformers 5.16.1, used for most LLM paraphrases, all base-model answers and the augmentation paraphrases (`supporting_files/D_augmentation/kaggle_merge_rest.json`, `llm_backend.md`) |
| Free disk during the build | about 6 GB |

## Python and tools
| tool | version | where it is pinned |
|---|---|---|
| Python | 3.10.12 (`.venv`) | `python3.10 -m venv .venv` |
| pip | 26.2.1 | |
| Python packages | direct deps pinned with `==` | `requirements.txt` |
| full package list | `.venv/bin/pip freeze` output | `requirements_freeze.txt` (A1 data pipeline); `requirements_freeze_a2.txt` (A2 training and evaluation on arka) |
| DVC | 3.67.1 | `requirements.txt` |
| Label Studio | 1.23.2, in a separate venv `.venv-labelstudio` (Python 3.10) | `labelstudio/requirements-labelstudio.txt` |
| Ollama | 0.1.38 | system install |

Label Studio has its own venv because its dependency pins clash with the analysis packages. Install it with
`python3.10 -m venv .venv-labelstudio && .venv-labelstudio/bin/pip install --no-cache-dir -r labelstudio/requirements-labelstudio.txt`.

## LLM
| item | value |
|---|---|
| model tag | `qwen2.5:1.5b` (params.yaml `llm.paraphrase_model` and `llm.base_model`) |
| Ollama tag digest | `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b` |
| GGUF weights blob | `sha256:183715c435899236895da3869489cc30ac241476b4971a20285b1a462818a5b4` |
| format | GGUF, Q4_K_M, family qwen2, 1.5B parameters |
| temperature | 0.7 for paraphrases (`llm.temperature`), 0.0 for base model answers (`llm.base_temperature`) |
| backends | `ollama` (default, http://localhost:11434), `llamacpp` (llama-server loaded with the same GGUF blob, for when Ollama 0.1.38 cannot load the model), `kaggle-transformers` (`Qwen/Qwen2.5-1.5B-Instruct` at revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`) |

`src/queries/llm_client.py` records the model digest, the GGUF blob and the backend version with every cached
answer in `data/interim/llm_cache.jsonl`, and each run log (`supporting_files/C_labelling/paraphrase_run.json`,
`supporting_files/D_active_learning/base_model_run.json`) repeats them. torch and transformers are needed only for
the Kaggle backend and are not installed locally; the Kaggle runtime (Tesla T4, CUDA 12.8, torch 2.11.0+cu128,
transformers 5.16.1, Qwen/Qwen2.5-1.5B-Instruct at revision 989aa7980e4cf806f80c7fef2b1adb7bc71aa306) is recorded in
`supporting_files/D_augmentation/kaggle_merge_rest.json` and in every cached answer. Rebuilding never needs a GPU:
`dvc repro` replays the cache.

## Seeds (params.yaml)
| key | value | what it controls |
|---|---|---|
| `seeds.transcripts` | 203 | synthetic students: programme, stream, track, admit year and transcripts (`src/engine/synth_transcripts.py`) |
| `seeds.queries` | 204 | split of each pair slot, then which student, allowed template and target course it uses (`src/queries/make_queries.py`) |
| `seeds.paraphrase` | 205 | Ollama `seed` option for query and justification paraphrases (`src/queries/paraphrase_llm.py`) |
| `seeds.augmentation` | 206 | augmentation sampling, typos, abbreviations, code formats, transcript shuffles and snapshots (`src/augment/`) |
| `seeds.active_learning` | 11, 12, 13, 14, 15 | random-sampling baselines averaged over five seeds, and tie-breaks (`src/active/`) |
| `seeds.splits` | 207 | held-out template per family and student assignment to train/val/test (`src/split/assign_students.py`) |
| `seeds.annotation_order` | 208 | which items go to labelling rounds 1 and 2 and their order (`src/queries/to_labelstudio.py`) |
| `seeds.validation_corruption` | 209 | where faults are injected in the corrupted validation copy (`src/validate/corrupt.py`) |

Other run parameters in params.yaml: `transcripts.n_students` (180) and the programme and track mix,
`queries.min_pairs` (600), `active_learning.budgets` (25, 50, 100), `splits` fractions by student (0.65 / 0.15 / 0.20).

# Assignment 2 environment

Values read on 2026-11-10 and 2026-11-11 (`lscpu`, `free -g`, `nvidia-smi`, `docker --version`, package `__version__`).

## Machines
| machine | used for | CPU | RAM | GPU | OS / tools |
|---|---|---|---|---|---|
| arka (lab workstation, work folder `/mnt/zone_C/hem/cs203_a2`) | LoRA search and training, evaluation, replay, retraining, image build and CPU validation | Intel i9-10900X, 10 cores / 20 threads | 125 GB | NVIDIA RTX A5000 24 GB, 2x Quadro RTX 5000 16 GB | Ubuntu 24.04.5 (kernel 6.8.0-147), driver 595.99.02, Docker 29.9.3 |
| hem436 PC | baselines on val/test/gold/shifted, service development | 8 threads | 31 GB | 2x RTX 2080 Ti 11 GB | Ubuntu 22.04.5 (kernel 6.8.0-138), driver 595.84 |
| second CPU-only machine | clean-machine test of the image | <!-- CLEAN_CPU --> | <!-- CLEAN_RAM --> | not used | <!-- CLEAN_OS --> |

GPU runs record the device in the MLflow tag `gpu` (training time depends on it).

## Python and packages
| item | value |
|---|---|
| Python | 3.10.12 in `.venv`, made with `uv venv --python 3.10.12` (arka: Python installed by `uv python install 3.10.12`) |
| training and evaluation | torch 2.5.1+cu124, transformers 4.46.3, peft 0.13.2, accelerate 1.1.1, safetensors 0.8.0, huggingface-hub 0.36.2, mlflow 2.18.0, scipy 1.14.1 (`requirements.txt`, full list in `requirements_freeze_a2.txt`) |
| service image | `docker/requirements-serve.txt` (compiled with `uv pip compile` from `docker/requirements-serve.in`): torch 2.5.1+cpu, transformers 4.46.3, gradio 4.44.1, fastapi 0.115.6, uvicorn 0.32.1; base images pinned by digest in `Dockerfile` (python:3.10.12-slim-bookworm, alpine/git:2.47.2) |
| experiment tracking | MLflow with a SQLite store (`mlflow.db`) and file artefacts (`mlruns/`), exported to `artefacts/mlflow/` |

## Pretrained models
| model | revision | use |
|---|---|---|
| `Qwen/Qwen2.5-1.5B-Instruct` | `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` | base of the final model; all baselines |
| `Qwen/Qwen2.5-0.5B-Instruct` | `7ae557604adf67be50417f59c2c2f167def9a775` | size trade-off run |
| `Qwen/Qwen2.5-3B-Instruct` | `aa8e72537993ba99e69dfaafa59ed015b17504d1` | size trade-off run |

## Assignment 2 seeds (`params_a2.yaml`)
| key | value | what it controls |
|---|---|---|
| `seeds.train` | 301 | LoRA training order and init, few-shot example choice, AL/random subsets of the data-mix runs |
| `seeds.bootstrap` | 302 | bootstrap CIs and paired tests, justification-rating sample and sheet order |
| `seeds.replay` | 303 | Part E replay traffic and the val calibration windows |
| `seeds.retrain_pool` | 304 | retraining-pool students and pairs, AL tie-breaks, replay rows mixed into retraining |
