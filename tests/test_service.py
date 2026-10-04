from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from vaani.domain import Decision, IST
from vaani.evaluation import run_evaluations
from vaani.planner import PlannerUnavailable
from vaani.service import Service, Conflict, redact


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.service = Service(Path(self.tmp.name) / "test.sqlite3")
        self.now = datetime(2030, 1, 1, 12, tzinfo=IST)
        self.session = self.service.create()
        self.sid = self.session["id"]
        self.counter = 0

    def tearDown(self):
        self.tmp.cleanup()

    def turn(self, text, sid=None, **kwargs):
        self.counter += 1
        return self.service.turn(sid or self.sid, text, str(self.counter), now=self.now, **kwargs)

    def ready(self, sid=None):
        for text in ["Yes", "Delhi", "100000", "This month", "1"]:
            self.turn(text, sid)

    def test_booking_requires_consent(self):
        r = self.turn("Delhi 100000")
        self.assertEqual(r["state"]["stage"], "consent")
        self.assertIsNone(r["state"]["city"])

    def test_idempotent_confirmation(self):
        self.ready()
        r = self.service.turn(self.sid, "Yes", "confirmation", now=self.now)
        again = self.service.turn(self.sid, "Yes", "confirmation", now=self.now)
        self.assertEqual(r, again)
        self.assertEqual(self.service.overview()["totals"]["bookings"], 1)

    def test_request_id_cannot_be_reused_with_other_text(self):
        self.service.turn(self.sid, "Yes", "same")
        with self.assertRaises(Conflict):
            self.service.turn(self.sid, "No", "same")

    def test_simultaneous_slot_reservations_only_one_wins(self):
        other = self.service.create()["id"]
        self.ready()
        self.ready(other)
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda sid: self.service.turn(sid, "Yes", "confirm", now=self.now), [self.sid, other]))
        self.assertEqual(sorted(r["state"]["stage"] for r in results), ["booked", "handoff"])
        self.assertEqual(self.service.overview()["totals"]["bookings"], 1)

    def test_same_session_concurrent_duplicate_is_idempotent(self):
        self.ready()
        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: self.service.turn(self.sid, "Yes", "confirm", now=self.now), range(2)))
        self.assertEqual(results[0], results[1])

    def test_expired_slot_not_booked(self):
        self.ready()
        r = self.service.turn(self.sid, "Yes", "late", now=self.now + timedelta(days=2))
        self.assertEqual(r["state"]["stage"], "handoff")
        self.assertEqual(self.service.overview()["totals"]["bookings"], 0)

    def test_failed_provider_does_not_mutate_state(self):
        class Failed:
            def decide(self, *args):
                raise PlannerUnavailable()
        before = self.service.get(self.sid)["state"]
        r = self.turn("Yes", planner_override=Failed())
        self.assertEqual(r["state"], before)
        self.assertEqual(r["planner_status"], "provider_error")

    def test_correction_requires_new_confirmation(self):
        self.ready()
        r = self.turn("Bengaluru")
        self.assertEqual(r["state"]["stage"], "slot")
        self.assertIsNone(r["state"]["selected_slot"])
        r = self.turn("Yes")
        self.assertIsNone(r["state"]["booking_id"])

    def test_conditional_yes_does_not_book(self):
        self.ready()
        self.assertEqual(self.turn("yes maybe")["state"]["stage"], "confirm")

    def test_opt_out_is_terminal(self):
        self.turn("Stop calling")
        r = self.turn("Yes")
        self.assertEqual(r["state"]["stage"], "opted_out")

    def test_phone_email_redacted_before_storage(self):
        self.turn("email me at demo@example.com or 9876543210")
        text = self.service.get(self.sid)["turns"][0]["user_text"]
        self.assertNotIn("9876543210", text)
        self.assertNotIn("demo@example.com", text)
        self.assertEqual(redact("My budget is 100000"), "My budget is 100000")

    def test_sql_injection_stays_text(self):
        self.turn("'; DROP TABLE sessions; --")
        self.assertEqual(self.service.overview()["totals"]["sessions"], 1)

    def test_invalid_decision_rejected(self):
        for payload in [{"intent": "book"}, {"budget": True}, {"budget": -1}, {"slot_choice": 3}, {"city": 42}, {"unknown": "x"}]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                Decision.validated(payload)

    def test_message_length_limit(self):
        for value in ["", " " * 10, "x" * 2001, 45]:
            with self.subTest(value=str(value)[:20]), self.assertRaises(ValueError):
                self.turn(value)

    def test_data_persists_across_service_instances(self):
        self.turn("Yes")
        reopened = Service(self.service.path)
        self.assertEqual(reopened.get(self.sid)["state"]["stage"], "city")

    def test_scenario_suite_and_eval_isolation(self):
        result = run_evaluations()
        self.assertEqual(result["passed"], result["total"], [(c["name"], c["errors"]) for c in result["results"] if not c["passed"]])
        self.service.save_evaluation(result)
        self.assertEqual(self.service.overview()["totals"]["sessions"], 1)
        self.assertEqual(self.service.overview()["evaluation"]["total"], 26)


if __name__ == "__main__":
    unittest.main()
