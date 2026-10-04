"""Transactional application service shared by the web lab and voice adapter."""
from contextlib import contextmanager
from datetime import datetime
import hashlib
import math
import json
from pathlib import Path
import re
import sqlite3
import time
import uuid
from .domain import IST, Decision, advance, choose, fresh_state, greeting, slot_label
from .planner import PROMPTS, PlannerUnavailable, make_planner


class Conflict(ValueError):
    pass


def now_iso():
    return datetime.now(IST).isoformat()


def redact(text):
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email removed]", text)
    return re.sub(r"(?<!\w)(?:\+91[ -]?)?[6-9]\d{9}(?!\w)", "[phone removed]", text)


class Service:
    def __init__(self, path="data/vaani.sqlite3"):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(Path(__file__).with_name("schema.sql").read_text())

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, language="en", planner="rules", version="few-shot-v2", source="interactive"):
        if language not in {"en", "hi"} or version not in PROMPTS or source not in {"interactive", "synthetic", "voice", "evaluation"}:
            raise ValueError("Invalid session configuration")
        make_planner(planner)  # Fail immediately when optional provider isn't configured.
        state = fresh_state(language)
        sid = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO sessions(id,created_at,language,source,planner,prompt_version,state_json) VALUES(?,?,?,?,?,?,?)",
                       (sid, now_iso(), language, source, planner, version, json.dumps(state)))
        return self.get(sid)

    def get(self, sid):
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
            if row is None:
                raise KeyError("Session not found")
            result = dict(row)
            result["state"] = json.loads(result.pop("state_json"))
            result["turns"] = [dict(r) for r in db.execute("SELECT id,user_text,agent_text,intent,state_before,state_after,latency_ms,planner_status FROM turns WHERE session_id=? ORDER BY id", (sid,))]
            result["greeting"] = greeting(fresh_state(row["language"]))
            result["voice_events"] = [dict(r) for r in db.execute("SELECT created_at,kind,value,detail FROM voice_events WHERE session_id=? ORDER BY id DESC LIMIT 40", (sid,))]
            timings = [r[0] for r in db.execute("SELECT value FROM voice_events WHERE session_id=? AND kind='transcript_to_speech_ms' ORDER BY value", (sid,))]
            result["voice_metrics"] = {"sample_size": len(timings),
                "p50_ms": timings[math.ceil(len(timings)*.5)-1] if timings else None,
                "p95_ms": timings[math.ceil(len(timings)*.95)-1] if timings else None,
                "interrupted_replies": db.execute("SELECT COUNT(*) FROM voice_events WHERE session_id=? AND kind='interrupted'", (sid,)).fetchone()[0]}
            return result

    def turn(self, sid, text, request_id, planner_override=None, now=None):
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError("Message must contain 1–2000 characters")
        if not isinstance(request_id, str) or not re.fullmatch(r"[\w-]{1,80}", request_id):
            raise ValueError("A valid request_id is required")
        started = time.perf_counter()
        text = redact(text.strip())
        digest = hashlib.sha256(text.encode()).hexdigest()
        with self.connect() as db:
            cached = db.execute("SELECT * FROM turns WHERE session_id=? AND request_id=?", (sid, request_id)).fetchone()
            if cached:
                return self._cached(cached, digest)
        session = self.get(sid)
        state = session["state"]
        original = json.dumps(state)
        before = state["stage"]
        planner = planner_override or make_planner(session["planner"])
        try:
            decision, status = planner.decide(text, state.copy(), session["prompt_version"])
            decision = Decision.validated(decision.__dict__)
        except PlannerUnavailable:
            decision, status = Decision(), "provider_error"
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cached = db.execute("SELECT * FROM turns WHERE session_id=? AND request_id=?", (sid, request_id)).fetchone()
            if cached:
                return self._cached(cached, digest)
            current = db.execute("SELECT state_json FROM sessions WHERE id=?", (sid,)).fetchone()
            count = db.execute("SELECT COUNT(*) FROM turns WHERE session_id=?", (sid,)).fetchone()[0]
            if not current or current[0] != original or count != len(session["turns"]):
                raise Conflict("The session changed. Refresh and retry your message.")
            if status == "provider_error":
                reply = choose(state, "The language service is temporarily unavailable. Nothing was changed; please try again.", "भाषा सेवा अभी उपलब्ध नहीं है। कोई बदलाव नहीं हुआ; कृपया फिर कोशिश करें।")
                effect = None
            else:
                reply, effect = advance(state, decision, now)
            if effect == "book":
                if not state["consent"] or not all(state[k] is not None for k in ("city", "budget", "timeline", "selected_slot")):
                    raise ValueError("Booking prerequisites are incomplete")
                clock = now or datetime.now(IST)
                expired = datetime.fromisoformat(state["selected_slot"]) <= clock
                booking_id = "DEMO-" + uuid.uuid4().hex[:8].upper()
                try:
                    if expired:
                        raise sqlite3.IntegrityError("expired")
                    db.execute("INSERT INTO bookings VALUES(?,?,?,?,?)", (booking_id, sid, state["city"], state["selected_slot"], now_iso()))
                except sqlite3.IntegrityError:
                    state["stage"] = "handoff"
                    state["selected_slot"] = None
                    reply = choose(state, "That slot is no longer available. No booking was made; I’ve flagged the demo session for follow-up.", "वह स्लॉट अब उपलब्ध नहीं है। बुकिंग नहीं हुई; डेमो में सहायता के लिए दर्ज किया है।")
                else:
                    state["stage"] = "booked"
                    state["booking_id"] = booking_id
                    label = slot_label(state["selected_slot"])
                    reply = choose(state, f"Your sandbox test ride in {state['city']} is booked for {label}. Reference: {booking_id}. This is a demo reservation, not a real dealership booking.", f"{state['city']} में {label} की डेमो टेस्ट राइड बुक हो गई। संदर्भ: {booking_id}। यह असली डीलरशिप बुकिंग नहीं है।")
            outcome = state["stage"] if state["stage"] in {"booked", "opted_out", "declined", "handoff", "not_serviceable"} else "active"
            latency = round((time.perf_counter() - started) * 1000, 2)
            response = {"reply": reply, "state": state, "intent": decision.intent, "planner_status": status, "latency_ms": latency, "outcome": outcome}
            db.execute("UPDATE sessions SET state_json=?,outcome=? WHERE id=?", (json.dumps(state), outcome, sid))
            db.execute("INSERT INTO turns(session_id,request_id,request_hash,created_at,user_text,agent_text,intent,state_before,state_after,latency_ms,planner_status,response_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                       (sid, request_id, digest, now_iso(), text, reply, decision.intent, before, state["stage"], latency, status, json.dumps(response)))
            return response

    @staticmethod
    def _cached(row, digest):
        if row["request_hash"] != digest:
            raise Conflict("This request_id was already used for another message")
        return json.loads(row["response_json"])

    def overview(self):
        with self.connect() as db:
            sessions = [dict(r) for r in db.execute("SELECT id,created_at,language,source,planner,prompt_version,outcome FROM sessions ORDER BY created_at DESC LIMIT 100")]
            funnel = [dict(r) for r in db.execute("SELECT outcome, COUNT(*) AS count FROM sessions GROUP BY outcome ORDER BY count DESC")]
            cohorts = [dict(r) for r in db.execute("""SELECT language, source, planner, COUNT(*) AS sessions,
                SUM(outcome='booked') AS bookings,
                ROUND(100.0*SUM(outcome='booked')/COUNT(*),1) AS booking_pct
                FROM sessions GROUP BY language, source, planner ORDER BY source,language""")]
            timing = db.execute("SELECT COUNT(*),ROUND(AVG(latency_ms),2),SUM(planner_status='provider_error') FROM turns").fetchone()
            latest = db.execute("SELECT result_json FROM eval_runs ORDER BY created_at DESC LIMIT 1").fetchone()
            return {"sessions": sessions, "funnel": funnel, "cohorts": cohorts,
                    "totals": {"sessions": sum(x["count"] for x in funnel), "bookings": db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0],
                               "turns": timing[0], "mean_processing_ms": timing[1], "provider_errors": timing[2] or 0},
                    "evaluation": json.loads(latest[0]) if latest else None}

    def save_evaluation(self, result):
        with self.connect() as db:
            db.execute("INSERT INTO eval_runs VALUES(?,?,?,?,?,?,?)", (result["id"], result["created_at"], result["planner"], result["prompt_version"], result["total"], result["passed"], json.dumps(result)))

    def voice_event(self, sid, kind, value=None, detail=""):
        if kind not in {"connected", "agent_state", "user_state", "transcript_to_speech_ms", "interrupted", "disconnected"}:
            raise ValueError("Unknown voice event")
        if kind == "transcript_to_speech_ms" and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError("Invalid timing")
        with self.connect() as db:
            db.execute("INSERT INTO voice_events(session_id,created_at,kind,value,detail) VALUES(?,?,?,?,?)", (sid, now_iso(), kind, value, detail[:100]))

    def evaluation_history(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT id,created_at,planner,prompt_version,total,passed FROM eval_runs ORDER BY created_at DESC LIMIT 50")]

    def compare_evaluations(self, baseline_id, candidate_id):
        with self.connect() as db:
            rows = [db.execute("SELECT result_json FROM eval_runs WHERE id=?", (run_id,)).fetchone() for run_id in (baseline_id, candidate_id)]
        if any(row is None for row in rows):
            raise KeyError("Evaluation not found")
        baseline, candidate = [json.loads(row[0]) for row in rows]
        maps = [{case["name"]: case for case in run["results"]} for run in (baseline, candidate)]
        names = sorted(set(maps[0]) | set(maps[1]))
        changes = []
        for name in names:
            old, new = [cases.get(name) for cases in maps]
            comparable = bool(baseline.get("suite_hash")) and baseline.get("suite_hash") == candidate.get("suite_hash") and old is not None and new is not None and [t["user"] for t in old["transcript"]] == [t["user"] for t in new["transcript"]]
            change = "not_comparable" if not comparable else "unchanged" if old["passed"] == new["passed"] else "recovered" if new["passed"] else "regressed"
            changes.append({"name": name, "change": change, "baseline_passed": old["passed"] if old else None, "candidate_passed": new["passed"] if new else None})
        return {"baseline": {k:baseline[k] for k in ("id","planner","prompt_version","passed","total")},
                "candidate": {k:candidate[k] for k in ("id","planner","prompt_version","passed","total")},
                "changes": changes,
                "note": "Observed outcomes only, not proof of prompt causality. Rules mode ignores prompt variants. Different scenario inputs are marked not comparable."}
