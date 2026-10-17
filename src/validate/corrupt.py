"""Make data/interim/corrupted/ copies of the processed data with seeded, injected faults.

    .venv/bin/python -m src.validate.corrupt

Writes courses.json, rules.json, students.jsonl, queries.jsonl, splits/*.csv, labels/audited.jsonl
and faults.json (fault id, description, target check, tokens that must appear in its failures).
Seed: params.yaml seeds.validation_corruption.
"""
import json
import random
import shutil
from pathlib import Path

import pandas as pd

from src.collect.common import record_sha
from src.engine.catalog import load_catalog, load_params

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "data" / "interim" / "corrupted"
SPLITS = ROOT / "data" / "splits"
INJECTED_STUDENTS = ROOT / "data" / "interim" / "students_corrupted.jsonl"
FIXTURE_LABELS = ROOT / "supporting_files" / "C_labelling" / "fixture_audited.jsonl"


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def rehash(rec):
    if "record_sha256" in rec:
        rec["record_sha256"] = record_sha(rec)
    return rec


def first_pass(student):
    out = {}
    for e in sorted(student["transcript"], key=lambda e: e["semester"]):
        out.setdefault(e["code"], e["semester"])
    return out


def pick_prereq_pair(students, courses, rng):
    """(student, before, after): a new edge `after` -> `before` that only this student violates."""
    regular = {c["code"] for c in courses if c["category"] not in ("requirement", "ug_background")}
    for s in rng.sample(students, len(students)):
        fp = {c: t for c, t in first_pass(s).items() if c in regular}
        pairs = sorted((a, b) for a in fp for b in fp if a != b and fp[a] >= fp[b])
        rng.shuffle(pairs)
        for later, earlier in pairs:
            # make `earlier` require `later`: this student took `earlier` before (or with) `later`
            clash = False
            for o in students:
                if o is s:
                    continue
                ofp = first_pass(o)
                if earlier in ofp and (later not in ofp or ofp[later] >= ofp[earlier]):
                    clash = True
                    break
            if not clash:
                return s, earlier, later
    return None


def main():
    params = load_params()
    rng = random.Random(params["seeds"]["validation_corruption"])
    courses = json.loads((PROCESSED / "courses.json").read_text())
    rules = json.loads((PROCESSED / "rules.json").read_text())
    students = read_jsonl(PROCESSED / "students.jsonl")
    queries = read_jsonl(PROCESSED / "queries.jsonl")
    catalog = load_catalog(PROCESSED / "courses.json", PROCESSED / "rules.json")
    faults, not_injected = [], []

    def fault(fid, desc, check_id, match):
        faults.append({"fault_id": fid, "description": desc, "check_id": check_id, "match": match})

    by = {c["code"]: c for c in courses}
    uses = {}
    for st in students:
        for code in {e["code"] for e in st["transcript"]}:
            uses[code] = uses.get(code, 0) + 1
    # least-taken regular courses, so catalog faults disturb as few transcripts as possible
    pool = sorted((uses.get(c["code"], 0), c["code"]) for c in courses
                  if c["category"] not in ("requirement", "ug_background"))
    a, b, u = rng.sample([code for _, code in pool[:6]], 3)
    by[a]["prerequisites"] = sorted(set(by[a]["prerequisites"]) | {b})
    by[b]["prerequisites"] = sorted(set(by[b]["prerequisites"]) | {a})
    fault("F01", f"prerequisite cycle {a} <-> {b}", "V12", [a, b])
    by[u]["prerequisites"] = sorted(set(by[u]["prerequisites"]) | {"ZZ 901"})
    fault("F02", f"unknown prerequisite ZZ 901 on {u}", "V11", ["ZZ 901"])

    pair = pick_prereq_pair(students, courses, rng)
    if pair:
        s, earlier, later = pair
        by[earlier]["prerequisites"] = sorted(set(by[earlier]["prerequisites"]) | {later})
        s["injected_violation"] = "PREREQ_SAME_OR_LATER_TERM"
        fault("F03", f"transcript prerequisite violation: {s['student_id']} took {earlier} before its "
                     f"(injected) prerequisite {later}", "V18", [s["student_id"], "PREREQ"])
    else:
        not_injected.append({"fault": "transcript prerequisite violation", "reason": "no suitable course pair"})
    for c in (a, b, u) + ((pair[1],) if pair else ()):
        rehash(by[c])

    dup_code = rng.choice(sorted(c for c in by if by[c]["category"] == "open_elective") or sorted(by))
    dup = dict(by[dup_code], title=by[dup_code]["title"] + " (copy)")
    courses.append(rehash(dup))
    fault("F04", f"duplicate course code {dup_code}", "V06", [dup_code])

    rules["rules"]["total_min_credits"]["value"] = 80
    rehash(rules["rules"]["total_min_credits"])
    fault("F05", "total_min_credits changed from 82 to 80", "V13", ["total_min_credits", "80"])

    below = sorted(c for c in by if (by[c].get("level") or 999) < 600 and by[c]["category"] not in ("requirement", "ug_background"))
    cands = [s for s in students if s["semesters_completed"] >= 2 and not s.get("injected_violation")]
    s = rng.choice(cands)
    have = {e["code"] for e in s["transcript"]}
    extra = [c for c in below if c not in have][:3]
    for i, code in enumerate(extra):
        s["transcript"].append({"code": code, "semester": 1 + i % s["semesters_completed"],
                                "credits": by[code]["credits"], "grade": "B"})
    s["transcript"].sort(key=lambda e: (e["semester"], e["code"]))
    s["injected_violation"] = "BELOW_600_CAP"
    fault("F06", f"below-600 cap breach: {s['student_id']} gets {', '.join(extra)}", "V19", [s["student_id"], "BELOW_600_CAP"])
    if catalog.rules.get("max_credits_per_semester") is None:
        not_injected.append({"fault": "per-semester credit cap breach",
                             "reason": "rules.json max_credits_per_semester is not_stated, so no cap exists to breach"})

    if INJECTED_STUDENTS.exists():
        idx = {x["student_id"]: i for i, x in enumerate(students)}
        seen = set()
        for x in read_jsonl(INJECTED_STUDENTS):
            kind = x.get("injected_violation")
            if kind in seen or x["student_id"] not in idx or students[idx[x["student_id"]]].get("injected_violation"):
                continue
            seen.add(kind)
            students[idx[x["student_id"]]] = x
            check_id = {"PREREQ_SAME_OR_LATER_TERM": "V18", "SEMESTER_CREDIT_CAP": "V19"}.get(kind, "V20")
            fault(f"F{len(faults) + 1:02d}", f"synth_transcripts --inject-violations {kind} on {x['student_id']}",
                  check_id, [x["student_id"]])
    else:
        not_injected.append({"fault": "synth_transcripts injected violations", "reason": f"{INJECTED_STUDENTS.name} missing"})

    elig = [q for q in queries if q["intent"] == "eligibility"]
    q = rng.choice(elig)
    q["gold_json"]["eligible"] = not q["gold_json"]["eligible"]
    fault(f"F{len(faults) + 1:02d}", f"gold_json of {q['query_id']} flipped eligible", "V22", [q["query_id"]])
    q2 = rng.choice([x for x in queries if x is not q])
    q2["query_text"] = q2["query_text"] + " Answer: eligible"
    fault(f"F{len(faults) + 1:02d}", f"gold answer marker appended to {q2['query_id']} query_text", "V23", [q2["query_id"]])

    real = sorted(SPLITS.glob("*.csv"))
    if real:
        df = pd.concat([pd.read_csv(f) for f in real], ignore_index=True)
        split_src = "data/splits"
    else:
        sids = sorted({x["student_id"] for x in queries})
        rng.shuffle(sids)
        cut1, cut2 = int(0.7 * len(sids)), int(0.85 * len(sids))
        split_of = {sid: "train" if i < cut1 else "val" if i < cut2 else "test" for i, sid in enumerate(sids)}
        prog = {s["student_id"]: s["programme"] for s in students}
        df = pd.DataFrame([{"query_id": x["query_id"], "student_id": x["student_id"], "template_id": x["template_id"],
                            "template_family": x["template_family"], "programme": prog.get(x["student_id"]),
                            "split": split_of[x["student_id"]]} for x in queries])
        split_src = "seeded student split"
    test_rows = df[df.split == "test"]
    leak = test_rows.iloc[rng.randrange(len(test_rows))]
    train_like = df[df.split == "train"].iloc[0].to_dict()
    df = pd.concat([df, pd.DataFrame([{**train_like, "query_id": leak.query_id + "-leak", "student_id": leak.student_id}])],
                   ignore_index=True)
    fault(f"F{len(faults) + 1:02d}", f"student {leak.student_id} copied into train ({split_src})", "V25", [leak.student_id])

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "splits").mkdir(parents=True)
    (OUT / "labels").mkdir()
    for name, part in df.groupby("split"):
        part.to_csv(OUT / "splits" / f"{name}.csv", index=False)
    if FIXTURE_LABELS.exists():
        labels = read_jsonl(FIXTURE_LABELS)
        bad = rng.choice(labels)
        bad["final_decision"] = "maybe"
        write_jsonl(OUT / "labels" / "audited.jsonl", labels)
        fault(f"F{len(faults) + 1:02d}", f"label {bad['item_id']} final_decision 'maybe' (copy of the Part C fixture)",
              "V24", [bad["item_id"], "maybe"])
    else:
        not_injected.append({"fault": "invalid label", "reason": "fixture_audited.jsonl missing"})

    (OUT / "courses.json").write_text(json.dumps(courses, indent=1, ensure_ascii=False))
    (OUT / "rules.json").write_text(json.dumps(rules, indent=1, ensure_ascii=False))
    write_jsonl(OUT / "students.jsonl", students)
    write_jsonl(OUT / "queries.jsonl", queries)
    meta = {"seed": params["seeds"]["validation_corruption"], "faults": faults, "not_injected": not_injected}
    (OUT / "faults.json").write_text(json.dumps(meta, indent=1))
    print(f"{len(faults)} faults injected into {OUT.relative_to(ROOT)}, {len(not_injected)} not injectable")


if __name__ == "__main__":
    main()
