"""Base model answers for the unlabelled pool (prompt base_model_answer_v1, temperature from params).

The pool is the original (non-augmented) pairs marked train in data/splits/*.csv; without split
files it is every original pair. The model sees the student summary, a compact course list for
the student's programme and the query, and returns JSON in a projection of the gold_json shape
(see the schema blocks in the prompt file). Calls are sorted by programme so the shared prompt
prefix stays in the server's cache.
"""
import argparse
import json
import re
import time
from pathlib import Path

from src.augment.common import INTERIM, QUERIES, ROOT, STUDENTS, read_jsonl, rel, write_jsonl
from src.engine.catalog import load_catalog, load_params
from src.engine.rule_engine import upcoming_term
from src.queries.llm_client import CACHE_PATH, LLM, load_prompt, render
from src.queries.paraphrase_llm import load_splits
from src.queries.to_labelstudio import student_summary

PROMPT_ID = "base_model_answer_v1"
OUT = INTERIM / "base_model_answers.jsonl"
RUN_LOG = ROOT / "supporting_files" / "D_active_learning" / "base_model_run.json"
NUM_PREDICT = {"remaining_core": 200, "eligibility": 100, "elective_recommendation": 120}


def load_template():
    """(main template, {intent: schema text}) from the prompt file."""
    text = load_prompt(PROMPT_ID)
    parts = re.split(r"^=== schema: (\w+) ===\n", text, flags=re.M)
    return parts[0].rstrip() + "\n", {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def course_line(c):
    offered = c.get("offered_parity") or ", ".join(c.get("offered_terms") or []) or "unknown"
    return " | ".join([c["code"], c.get("title") or "", str(c.get("credits")), c.get("category") or "",
                       ", ".join(c.get("streams") or []) or "-", ", ".join(c.get("prerequisites") or []) or "-", offered])


def catalog_context(catalog, programme, extra=None):
    codes = [k for k, c in sorted(catalog.courses.items())
             if programme in (c.get("programmes") or []) and c.get("category") != "ug_background"]
    if extra and extra in catalog.courses and extra not in codes:
        codes.append(extra)
    return "\n".join(course_line(catalog.courses[k]) for k in codes)


def rules_line(catalog, student):
    rs = catalog.rules.for_programme(student["programme"])
    tr = student["track"]
    parts = [("total", rs.get("total_min_credits")), ("coursework", rs.get("coursework_min_credits", tr)),
             ("thesis", rs.get("thesis_min_credits", tr)), ("project", rs.get("project_min_credits", tr))]
    return ", ".join(f"{k} at least {v} credits" for k, v in parts if v is not None)


def build_prompt(row, student, catalog, tpl, schemas):
    return render(tpl, programme=student["programme"], track=student["track"], rules=rules_line(catalog, student),
                  catalog=catalog_context(catalog, student["programme"], row.get("target_course")),
                  student=student_summary(student), term=upcoming_term(student),
                  query=row["query_text"], schema=schemas[row["intent"]])


def parse_json(text):
    """Parsed object or None. Accepts a fenced block or leading/trailing chatter around one object."""
    text = (text or "").strip()
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def pool_rows(rows, splits):
    originals = [r for r in rows if r.get("augmentation") is None]
    if not splits:
        return originals, "no split files: pool is every original pair"
    return [r for r in originals if splits.get(r["query_id"]) == "train"], "train split of data/splits/*.csv"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queries", default=str(QUERIES))
    ap.add_argument("--students", default=str(STUDENTS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--cache", default=str(CACHE_PATH))
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    params = load_params()
    catalog = load_catalog()
    students = {s["student_id"]: s for s in read_jsonl(args.students)}
    pool, pool_note = pool_rows(read_jsonl(args.queries), load_splits())
    pool = sorted(pool, key=lambda r: (students[r["student_id"]]["programme"], r["intent"], r["query_id"]))[:args.limit]
    tpl, schemas = load_template()
    llm = LLM(params["llm"]["base_model"], cache_path=args.cache)
    opts = {"seed": params["seeds"]["active_learning"][0], "temperature": params["llm"]["base_temperature"]}
    out, t0 = [], time.time()
    by_intent = {}
    for r in pool:
        by_intent.setdefault(r["intent"], []).append(r)
    answers = {}
    for intent, part in by_intent.items():
        prompts = [build_prompt(r, students[r["student_id"]], catalog, tpl, schemas) for r in part]
        res = llm.generate_many(PROMPT_ID, prompts, opts, fmt="json", num_predict=NUM_PREDICT[intent])
        answers.update({r["query_id"]: x for r, x in zip(part, res)})
        print(f"{intent}: {len(part)} answers, {time.time() - t0:.0f}s, new calls {llm.calls}", flush=True)
    for r in pool:
        res = answers[r["query_id"]]
        out.append({"query_id": r["query_id"], "intent": r["intent"], "programme": students[r["student_id"]]["programme"],
                    "response": res["response"], "parsed": parse_json(res["response"]),
                    "model": llm.model, "model_digest": llm.digest, "prompt_id": PROMPT_ID, "backend": llm.backend})
    write_jsonl(args.out, out)
    log = {"pool": pool_note, "n": len(out), "invalid_json": sum(o["parsed"] is None for o in out),
           "prompt_id": PROMPT_ID, "options": opts, "num_predict": NUM_PREDICT, "output": rel(args.out),
           "wall_seconds": round(time.time() - t0, 1), **llm.stats()}
    Path(RUN_LOG).parent.mkdir(parents=True, exist_ok=True)
    with open(RUN_LOG, "w") as f:
        json.dump(log, f, indent=1)
    print(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
