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
| GPU | none used. The only graphics device is the integrated Radeon Vega (no CUDA); all models ran on CPU |
| Free disk during the build | about 6 GB |

## Python and tools
| tool | version | where it is pinned |
|---|---|---|
| Python | 3.10.12 (`.venv`) | `python3.10 -m venv .venv` |
| pip | 26.2.1 | |
| Python packages | direct deps pinned with `==` | `requirements.txt` |
| full package list | `.venv/bin/pip freeze` output | `requirements_freeze.txt` |
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
the Kaggle backend and are not installed locally. If a Kaggle notebook was used, its runtime (GPU type, torch and
transformers versions) is in the run logs under `server`.

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
