"""Local-only lab server. Explicit routes, same-origin writes, no external assets."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import logging
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit
from .evaluation import run_evaluations
from .service import Conflict
from .voice_config import voice_status, create_voice_connection, voice_csp_origins

log = logging.getLogger("vaani.http")
STATIC = Path(__file__).with_name("static")


def make_server(service, port=8765):
    token = secrets.token_urlsafe(32)
    eval_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Request paths contain session IDs; do not log message bodies or keys.
            log.info("%s %s", self.command, self.path.split("?")[0])

        def send(self, status, body, content_type="application/json"):
            data = json.dumps(body, ensure_ascii=False).encode() if content_type == "application/json" else body
            self.send_response(status)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", f"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self' {voice_csp_origins()}; frame-ancestors 'none'; base-uri 'none'")
            self.send_header("Permissions-Policy", "microphone=(self), camera=()")
            self.end_headers()
            self.wfile.write(data)

        def allowed(self):
            actual_port = self.server.server_address[1]
            allowed_hosts = {f"127.0.0.1:{actual_port}", f"localhost:{actual_port}"}
            return self.headers.get("Host") in allowed_hosts

        def do_GET(self):
            if not self.allowed():
                return self.send(403, {"error": "Local host required"})
            path = urlsplit(self.path).path
            if path == "/":
                return self.send(200, (STATIC / "index.html").read_text().replace("__TOKEN__", token).encode(), "text/html")
            if path in {"/app.js", "/style.css", "/voice-ui.js", "/livekit-client.umd.js"}:
                return self.send(200, (STATIC / path[1:]).read_bytes(), "text/javascript" if path.endswith("js") else "text/css")
            if path == "/api/overview":
                return self.send(200, service.overview())
            if path == "/api/voice/status":
                return self.send(200, voice_status())
            if path == "/api/evaluations":
                return self.send(200, service.evaluation_history())
            if path.startswith("/api/sessions/"):
                try:
                    return self.send(200, service.get(path.rsplit("/", 1)[1]))
                except KeyError:
                    return self.send(404, {"error": "Session not found"})
            if path == "/api/health":
                return self.send(200, {"status": "ok", "mode": "local-lab"})
            self.send(404, {"error": "Not found"})

        def do_POST(self):
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            if not self.allowed() or (origin and origin != "http://" + host) or not hmac.compare_digest(self.headers.get("X-Vaani-Token", ""), token):
                return self.send(403, {"error": "Invalid local request token or origin"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError("Invalid request size")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object")
                path = urlsplit(self.path).path
                if path == "/api/voice/connect":
                    return self.send(201, create_voice_connection(service, data.get("language", "hi"), data.get("planner", "rules"), data.get("version", "few-shot-v2")))
                if path == "/api/evaluations/compare":
                    return self.send(200, service.compare_evaluations(data.get("baseline_id"), data.get("candidate_id")))
                if path == "/api/sessions":
                    return self.send(201, service.create(data.get("language", "en"), data.get("planner", "rules"), data.get("version", "few-shot-v2")))
                if path.startswith("/api/sessions/") and path.endswith("/turns"):
                    sid = path.split("/")[3]
                    return self.send(200, service.turn(sid, data.get("text"), data.get("request_id")))
                if path == "/api/evaluations":
                    planner = data.get("planner", "rules")
                    if planner == "gemini" and data.get("acknowledge_paid_inference") is not True:
                        raise ValueError("Acknowledge paid inference before running Gemini evaluations")
                    if planner not in {"rules", "gemini"}:
                        raise ValueError("Unknown planner")
                    if not eval_lock.acquire(blocking=False):
                        return self.send(409, {"error": "An evaluation is already running"})
                    try:
                        result = run_evaluations(planner, data.get("version", "few-shot-v2"))
                        service.save_evaluation(result)
                        return self.send(200, result)
                    finally:
                        eval_lock.release()
                self.send(404, {"error": "Not found"})
            except Conflict as exc:
                self.send(409, {"error": str(exc)})
            except KeyError:
                self.send(404, {"error": "Session not found"})
            except (ValueError, TypeError) as exc:
                self.send(400, {"error": str(exc)})
            except Exception:
                log.exception("Request failed")
                self.send(500, {"error": "Local service error; check server logs"})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server
