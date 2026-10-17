"""Read Label Studio JSON exports into one flat row per item (read-only)."""
import json

DECISIONS = ["accept", "edit", "reject"]
CATEGORIES = ["none", "hallucinated_course", "wrong_fact_or_policy", "meaning_drift",
              "incomplete_justification", "fluency", "ambiguous_query"]


def _pick_annotation(task):
    """Latest non-cancelled annotation of a task, or None."""
    anns = [a for a in task.get("annotations", []) if not a.get("was_cancelled")]
    if not anns:
        return None
    return max(anns, key=lambda a: (a.get("updated_at") or a.get("created_at") or "", a.get("id") or 0))


def _value(result, name):
    for r in result:
        if r.get("from_name") != name:
            continue
        v = r.get("value", {})
        if "choices" in v:
            return v["choices"][0] if v["choices"] else None
        if "text" in v:
            text = v["text"]
            return "\n".join(text) if isinstance(text, list) else text
    return None


def read_export(path, annotator):
    """Return {item_id: row} for one annotator's export, plus a list of warnings."""
    with open(path, encoding="utf-8") as f:
        tasks = json.load(f)
    rows, warnings = {}, []
    for task in tasks:
        data = task.get("data", {})
        item_id = data.get("item_id")
        ann = _pick_annotation(task)
        if item_id is None or ann is None:
            warnings.append(f"{annotator}: task {task.get('id')} has no item_id or no annotation")
            continue
        res = ann.get("result", [])
        row = {
            "item_id": item_id,
            "query_id": data.get("query_id"),
            "decision": _value(res, "decision"),
            "error_category": _value(res, "error_category"),
            "edit_text": (_value(res, "edit_text") or "").strip(),
            "data": data,
        }
        if row["decision"] not in DECISIONS:
            warnings.append(f"{annotator}: {item_id} unknown decision {row['decision']!r}")
        if row["error_category"] not in CATEGORIES:
            warnings.append(f"{annotator}: {item_id} unknown category {row['error_category']!r}")
        if row["decision"] == "edit" and not row["edit_text"]:
            warnings.append(f"{annotator}: {item_id} decision=edit but edit_text is empty")
        if item_id in rows:
            warnings.append(f"{annotator}: {item_id} appears twice, keeping the later task")
        rows[item_id] = row
    return rows, warnings
