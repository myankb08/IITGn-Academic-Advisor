"""Advisor service core: the merged advisor model with weight-only int8 Linear layers on CPU, the curriculum, and the rule-engine check.

Used by the REST API and the UI (src/serve/app.py) and by offline validation (src/serve/validate.py).
Paths come from environment variables so the same code runs in the repo and in the container:
MODEL_DIR (folder with merged/ and model_info.json from src.serve.export_model), LOG_DIR (request log), GIT_COMMIT.
"""
import hashlib
import json
import math
import os
import threading
import time
import uuid
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from src.active.base_model_answers import catalog_context, parse_json, rules_line
from src.active.disagreement import STRICT_CODE_RE, code_set, norm, valid
from src.engine.catalog import load_catalog
from src.engine.rule_engine import eligibility, passed_codes, recommend_electives, remaining_requirements, upcoming_term
from src.model.d6 import REPEAT, eligibility_d6
from src.engine.synth_transcripts import ADMIT_YEAR
from src.model.build_sft import load_template
from src.queries.llm_client import render
from src.queries.to_labelstudio import student_summary

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = Path(os.environ.get("MODEL_DIR", ROOT / "models/production"))
LOG_DIR = Path(os.environ.get("LOG_DIR", ROOT / "logs"))
INFO = json.load(open(MODEL_DIR / "model_info.json")) if (MODEL_DIR / "model_info.json").exists() else {}
# The image writes the build commit to COMMIT; in the repo the env var or "unknown" is used
COMMIT = (ROOT / "COMMIT").read_text().strip() if (ROOT / "COMMIT").exists() else os.environ.get("GIT_COMMIT", "unknown")
MAX_TOKENS = 360

catalog = load_catalog()
tpl, schemas = load_template("advisor_retrieval_v1")

tok = model = None
# One generation at a time: parallel requests share the same CPU threads and each gets slower (load test,
# supporting_files/D_deploy/loadtest_c2.json); queued requests wait instead.
generate_lock = threading.Lock()


def cpu_threads():
    """CPUs this process may use: the container quota (cgroup v2 cpu.max) when set, else the CPU count.
    os.cpu_count() ignores `docker run --cpus`, and too many threads on a quota slow every matmul."""
    try:
        quota, period = open("/sys/fs/cgroup/cpu.max").read().split()
        if quota != "max":
            return max(1, int(int(quota) / int(period)))
    except (OSError, ValueError):
        pass
    return os.cpu_count()


class Int8Linear(torch.nn.Module):
    """Weight-only int8 Linear: int8 weights with one fp32 scale per output channel, fp32 activations.
    Dynamic int8 (int8 activations too) breaks this model: Qwen2's activation outliers (|x| up to ~300) give
    40-80% error in the MLP layers. Decoding (one row) uses the int8 kernel; the prompt pass (many rows) expands
    one layer's weights to fp32 for that matmul, which is much faster than the int8 kernel there."""

    def __init__(self, lin):
        super().__init__()
        w = lin.weight.data.float()
        s = w.abs().amax(1).clamp(min=1e-8) / 127
        self.register_buffer("w", torch.round(w / s[:, None]).clamp(-128, 127).to(torch.int8))
        self.register_buffer("s", s)
        self.bias = None if lin.bias is None else torch.nn.Parameter(lin.bias.data.float(), requires_grad=False)

    def forward(self, x):
        x2 = x.reshape(-1, x.shape[-1])
        y = x2 @ (self.w.float() * self.s[:, None]).T if x2.shape[0] > 8 else torch._weight_int8pack_mm(x2, self.w, self.s)
        y = y.reshape(*x.shape[:-1], -1)
        return y if self.bias is None else y + self.bias


def load():
    """Load the merged fp16 weights and replace every nn.Linear by a weight-only int8 Linear, one layer at a time;
    the rest (norms, embedding) runs in fp32."""
    global tok, model
    torch.set_num_threads(int(os.environ.get("N_THREADS", cpu_threads())))
    tok = AutoTokenizer.from_pretrained(MODEL_DIR / "merged")
    model = AutoModelForCausalLM.from_pretrained(MODEL_DIR / "merged", torch_dtype=torch.float16)
    for parent in list(model.modules()):
        for name, child in parent.named_children():
            if isinstance(child, torch.nn.Linear):
                setattr(parent, name, Int8Linear(child))
    model = model.float().eval()


def make_student(programme, stream, track, semesters_completed, completed_codes):
    """Student record from UI/API fields; completed courses get catalog credits and a passing grade."""
    codes = [c for c in map(norm, completed_codes) if c]
    sem = int(semesters_completed)
    return {"student_id": "USER", "programme": programme, "stream": stream, "track": track,
            "admit_year": ADMIT_YEAR[min(sem, max(ADMIT_YEAR))], "semesters_completed": sem, "ug_background": [],
            "transcript": [{"code": c, "credits": (catalog.courses.get(c) or {}).get("credits", 0), "grade": "B",
                            "semester": max(sem, 1)} for c in codes]}


def rule_answer(intent, student, target_course=None, catalog=catalog):
    """Rule-engine reference answer for the request."""
    if intent == "remaining_core":
        return remaining_requirements(student, catalog)
    if intent == "eligibility":
        return eligibility_d6(student, target_course, catalog=catalog)  # D6: a passed course may be repeated
    return recommend_electives(student, k=3, catalog=catalog)


def rule_check(intent, obj, ref, student, catalog=catalog):
    """(passed, reason): is the model answer consistent with the rule engine?"""
    if not valid(obj, intent):
        return False, "answer is not valid JSON in the expected shape"
    unknown = sorted(c for c in code_set(obj, intent) if c not in catalog.courses)
    if unknown:
        return False, f"unknown course codes: {', '.join(unknown)}"
    if intent == "remaining_core" and code_set(obj, intent) != code_set(ref, intent):
        return False, "remaining core courses differ from the rule engine"
    if intent == "eligibility" and bool(obj["eligible"]) != bool(ref["eligible"]):
        return False, "eligibility differs from the rule engine"
    if intent == "elective_recommendation":
        passed = set(passed_codes(student, catalog))
        bad = [c for c in code_set(obj, intent) if c in passed or not eligibility(student, c, catalog=catalog)["eligible"]]
        if bad:
            return False, f"recommended courses not allowed: {', '.join(bad)}"
    return True, "consistent with the rule engine"


@torch.inference_mode()
def generate(prompt):
    """(text, confidence) with greedy decoding; confidence = exp(mean log-probability of the generated tokens).
    Uses the same chat template as training (tokenizer.apply_chat_template)."""
    text = tok.apply_chat_template([{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True)
    enc = tok(text, return_tensors="pt")
    with generate_lock:
        out = model.generate(**enc, max_new_tokens=MAX_TOKENS, do_sample=False, pad_token_id=tok.pad_token_id,
                             output_scores=True, return_dict_in_generate=True)
    lps = model.compute_transition_scores(out.sequences, out.scores, normalize_logits=True)[0]
    new = out.sequences[0, enc.input_ids.shape[1]:]
    return tok.decode(new, skip_special_tokens=True), math.exp(lps.float().mean().item()) if len(lps) else None


def hashed_query(text, dim=64):
    """Bag-of-words hashed to dim counts: a drift feature that does not keep the text."""
    vec = [0] * dim
    for w in text.lower().split():
        vec[int(hashlib.md5(w.encode()).hexdigest(), 16) % dim] += 1
    return vec


def predict(query, intent, programme, stream, track, semesters_completed, completed_codes, target_course=None):
    """Full request: prompt, model answer, rule check, log line. Returns a dict for the API and UI."""
    t0 = time.time()
    student = make_student(programme, stream, track, semesters_completed, completed_codes)
    target = norm(target_course) if target_course else None
    prompt = render(tpl, programme=programme, track=track, rules=rules_line(catalog, student),
                    catalog=catalog_context(catalog, programme, target), student=student_summary(student),
                    term=upcoming_term(student), query=query, schema=schemas[intent])
    text, conf = generate(prompt)
    obj = parse_json(text)
    ref = rule_answer(intent, student, target)
    ok, reason = rule_check(intent, obj, ref, student)
    unknown = sorted({norm(m.group(0)) for m in STRICT_CODE_RE.finditer(text)} - set(catalog.courses))
    result = {"request_id": uuid.uuid4().hex[:12], "answer": obj, "raw_answer": text,
              "justification": (obj or {}).get("justification"), "confidence": conf,
              "rule_check": {"passed": ok, "reason": reason}, "rule_engine_answer": ref,
              "model_version": INFO.get("version", "unknown"), "commit": COMMIT,
              "latency_ms": round(1000 * (time.time() - t0)), "notes": []}
    if intent == "eligibility" and REPEAT in ref.get("warnings", []):
        result["notes"].append(f"{target} is already passed: registering again is a repeat to improve the grade (Academic "
                               f"Advisory 24, B.1); the better grade counts and it earns no new credits.")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / "requests.jsonl", "a") as f:
        f.write(json.dumps({"ts": time.time(), "request_id": result["request_id"], "model_version": result["model_version"],
                            "commit": COMMIT, "intent": intent, "programme": programme, "latency_ms": result["latency_ms"],
                            "confidence": conf, "valid_json": valid(obj, intent), "unknown_codes": len(unknown),
                            "rule_passed": ok, "answer": obj, "answer_chars": len(text), "query_chars": len(query),
                            "query_vec": hashed_query(query)}) + "\n")
    return result
