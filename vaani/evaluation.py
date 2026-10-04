"""Scripted end-state checks. These are not audio or production conversion metrics."""
import json
import hashlib
from pathlib import Path
import tempfile
import time
import uuid
from .service import Service, now_iso


def run_evaluations(planner="rules", version="few-shot-v2"):
    from .planner import PROMPTS, make_planner
    if version not in PROMPTS:
        raise ValueError("Unknown prompt version")
    make_planner(planner)
    cases = json.loads(Path(__file__).with_name("scenarios.json").read_text())
    suite_hash = hashlib.sha256(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    results = []
    for case in cases:
        with tempfile.TemporaryDirectory(prefix="vaani-eval-") as folder:
            service = Service(Path(folder) / "eval.sqlite3")
            session = service.create(case["language"], planner, version, "evaluation")
            started = time.perf_counter()
            transcript = []
            errors = []
            for i, turn in enumerate(case["turns"]):
                result = service.turn(session["id"], turn["text"], f"eval-{i}")
                transcript.append({"user": turn["text"], "agent": result["reply"], "stage": result["state"]["stage"], "planner_status": result["planner_status"]})
                if result["state"]["stage"] != turn["stage"]:
                    errors.append(f"Turn {i+1}: expected {turn['stage']}, got {result['state']['stage']}")
                if result["planner_status"] == "provider_error":
                    errors.append(f"Turn {i+1}: provider error")
                for field, value in turn.get("fields", {}).items():
                    if result["state"][field] != value:
                        errors.append(f"Turn {i+1}: incorrect {field}")
                for phrase in turn.get("contains", []):
                    if phrase not in result["reply"]:
                        errors.append(f"Turn {i+1}: missing expected reply phrase")
            with service.connect() as db:
                bookings = db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
            if bookings != case.get("bookings", 0):
                errors.append(f"Expected {case.get('bookings', 0)} bookings, got {bookings}")
            results.append({"name": case["name"], "category": case["category"], "language": case["language"], "passed": not errors,
                            "errors": errors, "duration_ms": round((time.perf_counter()-started)*1000, 2), "transcript": transcript})
    return {"id": str(uuid.uuid4()), "created_at": now_iso(), "planner": planner, "prompt_version": version, "suite_hash": suite_hash,
            "total": len(results), "passed": sum(r["passed"] for r in results), "results": results,
            "scope": "Scripted text scenarios; no acoustic, latency-to-audio, or real customer conversion claims."}
