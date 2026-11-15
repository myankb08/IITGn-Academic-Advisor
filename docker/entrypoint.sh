#!/bin/sh
# serve: API + UI on $PORT | validate [--subset N]: offline gold validation | smoke: one offline request
set -e
case "$1" in
  serve) exec python -m src.serve.app ;;
  validate) shift; exec python -m src.serve.validate "$@" ;;
  smoke)
    python -m src.serve.app > /tmp/app.log 2>&1 &
    for i in $(seq 1 60); do python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:$PORT/health')" 2>/dev/null && break; sleep 2; done
    python - <<'PY'
import json, os, urllib.request
req = urllib.request.Request(f"http://127.0.0.1:{os.environ['PORT']}/predict", method="POST",
    headers={"content-type": "application/json"},
    data=json.dumps({"query": "Can I register for EE 618 next term?", "intent": "eligibility", "programme": "MTech-ICDT",
                     "track": "coursework", "semesters_completed": 1, "completed_courses": ["EE 644"], "target_course": "EE 618"}).encode())
r = json.load(urllib.request.urlopen(req, timeout=300))
assert "rule_check" in r and r["commit"] != "unknown", r
print("smoke ok:", r["latency_ms"], "ms, rule check", r["rule_check"], "commit", r["commit"][:10])
PY
    ;;
  *) exec "$@" ;;
esac
