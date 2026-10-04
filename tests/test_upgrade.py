import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from vaani.evaluation import run_evaluations
from vaani.service import Service
from vaani.voice_config import voice_status, livekit_origin, voice_csp_origins, create_voice_connection


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = Service(Path(self.tmp.name) / "test.db")

    def test_configuration_status_never_exposes_values(self):
        with patch.dict(os.environ, {"LIVEKIT_API_SECRET": "private-value", "SARVAM_API_KEY": "speech-secret"}, clear=True):
            status = voice_status()
        self.assertFalse(status["ready"])
        self.assertNotIn("private-value", json.dumps(status))
        self.assertNotIn("speech-secret", json.dumps(status))

    def test_bad_connection_url_not_accepted(self):
        for url in ["https://example.com", "wss://u:p@example.com", "wss://example.com?key=x", "wss://example.com; bad", "wss://example.com/path"]:
            with self.subTest(url=url), patch.dict(os.environ, {"LIVEKIT_URL": url}, clear=True):
                self.assertIsNone(livekit_origin())
                self.assertEqual(voice_csp_origins(), "")

    def test_connection_checks_before_session_creation(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            create_voice_connection(self.service)
        self.assertEqual(self.service.overview()["totals"]["sessions"], 0)

    def test_sdk_token_is_room_scoped_and_short_lived(self):
        if importlib.util.find_spec("jwt") is None:
            self.skipTest("Optional LiveKit dependencies not installed")
        import jwt
        env = {"LIVEKIT_URL": "wss://demo.livekit.cloud", "LIVEKIT_API_KEY": "test-key", "LIVEKIT_API_SECRET": "test-secret-"*4, "SARVAM_API_KEY": "test-speech"}
        with patch.dict(os.environ, env, clear=True):
            connection = create_voice_connection(self.service, "hi", "rules")
            payload = jwt.decode(connection["token"], env["LIVEKIT_API_SECRET"], algorithms=["HS256"])
        self.assertEqual(payload["video"]["room"], connection["room"])
        self.assertEqual(payload["exp"]-payload["nbf"], 600)
        self.assertFalse(payload["video"].get("roomAdmin", False))
        agent = payload["roomConfig"]["agents"][0]
        self.assertEqual(agent["agentName"], "vaani-sales")
        self.assertEqual(json.loads(agent["metadata"])["session_id"], connection["session_id"])
        self.assertEqual(self.service.get(connection["session_id"])["source"], "voice")

    def test_metrics_count_entire_session_not_recent_event_window(self):
        sid = self.service.create(source="voice")["id"]
        for i in range(1, 101):
            self.service.voice_event(sid, "transcript_to_speech_ms", i)
        self.service.voice_event(sid, "interrupted")
        record = self.service.get(sid)
        self.assertEqual(len(record["voice_events"]), 40)
        self.assertEqual(record["voice_metrics"], {"sample_size": 100, "p50_ms": 50, "p95_ms": 95, "interrupted_replies": 1})

    def test_invalid_metric_rejected(self):
        sid = self.service.create()["id"]
        for value in [-1, float('nan'), True, None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.service.voice_event(sid, "transcript_to_speech_ms", value)

    def test_saved_runs_compare_failures_and_recoveries(self):
        baseline = run_evaluations()
        candidate = copy.deepcopy(baseline)
        candidate["id"] = "candidate"
        baseline["results"][0]["passed"] = False
        candidate["results"][1]["passed"] = False
        self.service.save_evaluation(baseline)
        self.service.save_evaluation(candidate)
        result = self.service.compare_evaluations(baseline["id"], candidate["id"])
        changes = [r["change"] for r in result["changes"]]
        self.assertEqual(changes.count("recovered"), 1)
        self.assertEqual(changes.count("regressed"), 1)
        self.assertEqual(len(self.service.evaluation_history()), 2)

    def test_different_suite_not_comparable(self):
        baseline = run_evaluations()
        candidate = copy.deepcopy(baseline)
        candidate.update(id="candidate", suite_hash="changed-scenarios")
        self.service.save_evaluation(baseline)
        self.service.save_evaluation(candidate)
        result = self.service.compare_evaluations(baseline["id"], candidate["id"])
        self.assertTrue(all(r["change"] == "not_comparable" for r in result["changes"]))

    def test_unknown_prompt_rejected_even_in_rules_mode(self):
        with self.assertRaises(ValueError):
            run_evaluations(version="bad")
