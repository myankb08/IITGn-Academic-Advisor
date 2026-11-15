# Course advisor service: CPU only, linux/amd64, no network needed at run time.
# Build from the repo root (code/): docker build -t iitgn-advisor:a2 .
# The build checks the released LoRA adapter (release/ADAPTER_SHA256.txt), downloads the base model at the pinned
# revision and merges them; the merged weights' SHA-256 is recorded in model_info.json (fp16 CPU merges can differ in
# the last bits between CPU types, so validation uses a stated tolerance). The running container never uses the network.

# Commit of the build context, read from .git so no build argument is needed
FROM alpine/git:2.47.2@sha256:062a01ad7a0eb17cff382bc5e26086b4d710e56dfdfdf001109a49b6d9bd378c AS commit
COPY .git /repo/.git
RUN git -C /repo rev-parse HEAD > /COMMIT

FROM python:3.10.12-slim-bookworm@sha256:4d440b214e447deddc0a94de23a3d97d28dfafdf125a8b4bb8073381510c9ee2 AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY docker/requirements-serve.txt docker/requirements-serve.txt
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r docker/requirements-serve.txt

# Merge stage: base model at the pinned revision + released adapter -> fp16 merged weights
FROM base AS merge
RUN pip install --no-cache-dir peft==0.13.2
COPY params_a2.yaml ./
COPY src/serve/export_model.py src/serve/export_model.py
COPY release/adapter release/adapter
COPY release/VERSION release/RUN_ID release/ADAPTER_SHA256.txt release/
RUN chmod -R a+r release && sha256sum -c release/ADAPTER_SHA256.txt \
    && python src/serve/export_model.py --adapter release/adapter --out models/production \
        --version "$(cat release/VERSION)" --run_id "$(cat release/RUN_ID)" \
    && rm -rf /root/.cache/huggingface

FROM base
ENV GRADIO_ANALYTICS_ENABLED=False HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    MODEL_DIR=/app/models/production LOG_DIR=/app/logs OUT_DIR=/app/out PORT=7860
COPY params.yaml params_a2.yaml ./
COPY src src
COPY prompts/pipeline prompts/pipeline
COPY data/processed/courses.json data/processed/rules.json data/processed/students.jsonl \
     data/processed/students_augmented.jsonl data/processed/
COPY data/gold data/gold
COPY data/sft/gold.jsonl data/sft/gold.jsonl
COPY --from=merge /app/models/production models/production
COPY release/serving models/production/
COPY docker/entrypoint.sh /entrypoint.sh
COPY --from=commit /COMMIT /app/COMMIT
RUN sha256sum -c data/gold/GOLD_SHA256.txt && cd models/production && sha256sum -c SHA256.txt
EXPOSE 7860
ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve"]
