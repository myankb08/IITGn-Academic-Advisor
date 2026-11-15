"""Course advisor service: REST API (/predict, /health, /version) and a Gradio UI on one port (7860).

Runs fully offline: the weight-only int8 model, curriculum, rule engine and gold set are bundled; Gradio analytics are off and the
UI uses system fonts. Monitoring reads the request log; validation runs the fixed 20-item gold subset.
Start: python -m src.serve.app   (in the image: docker run -p 7860:7860 <image> serve)
"""
import os

os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

import json
import time

import gradio as gr
import numpy as np
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from src.augment.common import ROOT, read_jsonl
from src.serve import core, validate

core.load()

STREAMS = sorted({(s["programme"], s["stream"] or "") for s in read_jsonl(ROOT / "data/processed/students.jsonl")})
INTENTS = ["remaining_core", "eligibility", "elective_recommendation"]
THRESHOLDS = core.MODEL_DIR / "monitoring_thresholds.json"


class Request(BaseModel):
    query: str
    intent: str
    programme: str
    stream: str | None = None
    track: str = "thesis"
    semesters_completed: int = 1
    completed_courses: list[str] = []
    target_course: str | None = None


app = FastAPI(title="IITGN course advisor")


@app.post("/predict")
def predict(req: Request):
    return core.predict(req.query, req.intent, req.programme, req.stream, req.track, req.semesters_completed,
                        req.completed_courses, req.target_course)


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": core.model is not None}


@app.get("/version")
def version():
    return {"model": core.INFO, "commit": core.COMMIT}


# ----------
#  Monitoring
# ----------
def monitoring():
    """Signals over the last 25 logged requests (the replay window size), with alert flags when thresholds exist."""
    path = core.LOG_DIR / "requests.jsonl"
    rows = read_jsonl(path)[-25:] if path.exists() else []
    if not rows:
        return "No requests logged yet."
    lat = np.array([r["latency_ms"] for r in rows])
    sig = {"requests": len(rows), "unknown_code_rate": np.mean([r["unknown_codes"] > 0 for r in rows]),
           "rule_rejection_rate": 1 - np.mean([r["rule_passed"] for r in rows]),
           "mean_answer_chars": np.mean([r["answer_chars"] for r in rows]),
           "mean_confidence": np.mean([r["confidence"] or 0 for r in rows]),
           "latency_p50_ms": np.percentile(lat, 50), "latency_p95_ms": np.percentile(lat, 95)}
    thr = json.load(open(THRESHOLDS)) if THRESHOLDS.exists() else {}
    if "query_ref_vec" in thr:
        c, ref = np.mean([r["query_vec"] for r in rows], 0), np.array(thr.pop("query_ref_vec"))
        sig["query_drift"] = 1 - float(c @ ref / (np.linalg.norm(c) * np.linalg.norm(ref)))
    thr.pop("window_size", None)
    lines = ["| signal | value (last 25) | threshold | alert |", "|---|---|---|---|"]
    for k, v in sig.items():
        t = thr.get(k)
        lines.append(f"| {k} | {v:.3f} | {t if t is not None else '-'} | {'ALERT' if t is not None and v > t else ''} |")
    return "\n".join(lines) + ("" if thr else "\n\nThresholds not set (they come from the Part E replay on val).")


def run_validation():
    m = validate.run(subset=5)
    rep = core.MODEL_DIR / "reported_gold.json"
    rows = validate.compare(m, json.load(open(rep))) if rep.exists() else []
    head = f"Fixed subset: first 5 gold items by item_id, {m['seconds']} s on this CPU.\n\n"
    return head + "\n".join(["| metric | measured | reported | tolerance | pass |", "|---|---|---|---|---|"]
                            + [f"| {c['metric']} | {c['measured']} | {c['reported']} | {c['tolerance']} | {c['passed']} |" for c in rows])


# ----------
#  UI
# ----------
def ui_predict(query, intent, programme, stream, track, sems, courses, target):
    r = core.predict(query, intent, programme, stream or None, track, int(sems),
                     [c.strip() for c in courses.split(",") if c.strip()], target or None)
    check = ("PASS: " if r["rule_check"]["passed"] else "REJECTED: ") + r["rule_check"]["reason"]
    check += "".join(f"\nNote: {n}" for n in r["notes"])
    shown = r["answer"] if r["rule_check"]["passed"] else {"rule_engine_answer": r["rule_engine_answer"]}
    meta = (f"confidence {r['confidence']:.3f} | latency {r['latency_ms']} ms | model {r['model_version']} | "
            f"commit {r['commit'][:10]} | request {r['request_id']}")
    return json.dumps(shown, indent=1), r["justification"] or "", check, r["raw_answer"], meta


EXAMPLES = [
    ["Which core courses do I still need to finish?", "remaining_core", "MTech-CSE", "AI/ML", "thesis", 1, "CS 610, CS 614, FP 601", ""],
    ["Can I register for EE 618 next term?", "eligibility", "MTech-ICDT", "", "coursework", 1, "EE 644, EE 651", "EE 618"],
    ["Suggest electives for my next semester.", "elective_recommendation", "MTech-EE", "Signal Processing & Machine Learning", "thesis", 2, "EE 604, EE 605", ""],
    ["Am I allowed to take CS 613 in the coming term?", "eligibility", "MTech-AI", "AI/ML", "coursework", 2, "CS 610, CS 612", "CS 613"],
]

with gr.Blocks(title="IITGN course advisor", theme=gr.themes.Default(font=["sans-serif"], font_mono=["monospace"])) as demo:
    gr.Markdown(f"## IITGN M.Tech course advisor\nModel `{core.INFO.get('version', 'unknown')}`, commit `{core.COMMIT[:10]}`. "
                "Answers are checked against the rule engine before they are shown.")
    with gr.Tab("Ask"):
        with gr.Row():
            with gr.Column():
                query = gr.Textbox(label="Question", lines=2)
                intent = gr.Dropdown(INTENTS, value="remaining_core", label="Question type")
                programme = gr.Dropdown(sorted({p for p, _ in STREAMS}), value="MTech-CSE", label="Programme")
                stream = gr.Dropdown(sorted({s for _, s in STREAMS if s}), value="AI/ML", label="Stream", allow_custom_value=True)
                track = gr.Radio(["thesis", "coursework"], value="thesis", label="Track")
                sems = gr.Slider(0, 3, value=1, step=1, label="Semesters completed")
                courses = gr.Textbox(label="Completed course codes (comma separated)")
                target = gr.Textbox(label="Course to check (eligibility only)")
                go = gr.Button("Ask", variant="primary")
            with gr.Column():
                answer = gr.Code(label="Answer (rule-engine answer if the check rejects the model)", language="json")
                justification = gr.Textbox(label="Justification")
                check = gr.Textbox(label="Rule-engine check")
                meta = gr.Textbox(label="Confidence, latency, version")
                raw = gr.Textbox(label="Raw model output", lines=4)
        gr.Examples(EXAMPLES, [query, intent, programme, stream, track, sems, courses, target])
        go.click(ui_predict, [query, intent, programme, stream, track, sems, courses, target], [answer, justification, check, raw, meta])
    with gr.Tab("Monitoring"):
        mon = gr.Markdown()
        gr.Button("Refresh").click(monitoring, None, mon)
    with gr.Tab("Validation"):
        val = gr.Markdown("Runs the fixed 5-item gold subset (first 5 by item_id) on this CPU and compares it with the reported values.")
        gr.Button("Run validation").click(run_validation, None, val)

app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))
