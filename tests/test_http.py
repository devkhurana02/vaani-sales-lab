import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from vaani.server import make_server
from vaani.service import Service


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = make_server(Service(Path(cls.tmp.name) / "http.sqlite3"), 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        with urlopen(cls.base) as r:
            cls.token = re.search(r'name="vaani-token" content="([^"]+)"', r.read().decode())[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.tmp.cleanup()

    def request(self, path, data=None, **headers):
        req = Request(self.base + path, data=json.dumps(data).encode() if data is not None else None,
                      headers={"Content-Type": "application/json", **headers})
        return urlopen(req)

    def test_csrf_required(self):
        with self.assertRaises(HTTPError) as err:
            self.request("/api/sessions", {})
        self.assertEqual(err.exception.code, 403)

    def test_wrong_origin_denied(self):
        with self.assertRaises(HTTPError) as err:
            self.request("/api/sessions", {}, **{"X-Vaani-Token": self.token, "Origin": "https://example.com"})
        self.assertEqual(err.exception.code, 403)

    def test_wrong_host_denied(self):
        with self.assertRaises(HTTPError) as err:
            self.request("/api/overview", Host="evil.example")
        self.assertEqual(err.exception.code, 403)

    def test_complete_http_conversation(self):
        with self.request("/api/sessions", {"language": "hi"}, **{"X-Vaani-Token": self.token}) as r:
            s = json.load(r)
        with self.request(f"/api/sessions/{s['id']}/turns", {"text": "हाँ", "request_id": "hello"}, **{"X-Vaani-Token": self.token}) as r:
            result = json.load(r)
        self.assertEqual(result["state"]["stage"], "city")

    def test_unknown_session_404(self):
        with self.assertRaises(HTTPError) as err:
            self.request("/api/sessions/missing")
        self.assertEqual(err.exception.code, 404)

    def test_no_filesystem_traversal(self):
        with self.assertRaises(HTTPError) as err:
            self.request("/../schema.sql")
        self.assertEqual(err.exception.code, 404)

    def test_security_headers(self):
        with self.request("/api/health") as r:
            self.assertIn("frame-ancestors 'none'", r.headers["Content-Security-Policy"])
            self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")

    def test_paid_eval_requires_acknowledgement(self):
        with self.assertRaises(HTTPError) as err:
            self.request("/api/evaluations", {"planner": "gemini"}, **{"X-Vaani-Token": self.token})
        self.assertEqual(err.exception.code, 400)

    def test_voice_status_only_returns_configuration_checks(self):
        with self.request("/api/voice/status") as r:
            status = json.load(r)
        self.assertIn("ready", status)
        self.assertTrue(all(type(v) is bool for v in status["checks"].values()))

    def test_voice_connection_requires_local_token(self):
        with self.assertRaises(HTTPError) as err:
            self.request("/api/voice/connect", {})
        self.assertEqual(err.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
