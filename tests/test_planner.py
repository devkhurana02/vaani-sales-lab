import io
import json
import os
import unittest
from unittest.mock import patch
from vaani.domain import fresh_state
from vaani.planner import GeminiPlanner, PlannerUnavailable


class GeminiContractTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-not-real", "GEMINI_MODEL": "test-model"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.planner = GeminiPlanner()

    def response(self, content):
        return io.BytesIO(json.dumps({"candidates": [{"content": {"parts": [{"text": content}]}}]}).encode())

    def test_valid_structured_output_and_auth_header(self):
        with patch('vaani.planner.urlopen', return_value=self.response('{"intent":"provide","budget":100000}')) as call:
            d, status = self.planner.decide("ek lakh", fresh_state("hi"))
        self.assertEqual(d.budget, 100000)
        self.assertEqual(status, "gemini")
        req = call.call_args.args[0]
        self.assertNotIn("test-key", req.full_url)
        self.assertEqual(req.headers["X-goog-api-key"], "test-key-not-real")

    def test_schema_violation_is_provider_failure(self):
        with patch('vaani.planner.urlopen', return_value=self.response('{"intent":"affirm","budget":true}')):
            with self.assertRaises(PlannerUnavailable):
                self.planner.decide("hello", fresh_state("en"))

    def test_invalid_json_is_provider_failure(self):
        with patch('vaani.planner.urlopen', return_value=self.response('not json')):
            with self.assertRaises(PlannerUnavailable):
                self.planner.decide("hello", fresh_state("en"))

    def test_opt_out_never_calls_provider(self):
        with patch('vaani.planner.urlopen') as call:
            d, status = self.planner.decide("Please don't call me", fresh_state("en"))
        call.assert_not_called()
        self.assertEqual(d.intent, "opt_out")

    def test_prompt_variants_change_model_request(self):
        prompts = []
        for version in ["zero-shot-v1", "few-shot-v2"]:
            with patch('vaani.planner.urlopen', return_value=self.response('{"intent":"unknown"}')) as call:
                self.planner.decide("hello", fresh_state("en"), version)
                prompts.append(json.loads(call.call_args.args[0].data)["systemInstruction"])
        self.assertNotEqual(prompts[0], prompts[1])
