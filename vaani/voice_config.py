"""Browser-room token issuance. Credentials never leave the local server."""
from datetime import timedelta
import importlib.util
import json
import os
from urllib.parse import urlsplit
import uuid


def livekit_origin():
    raw = os.getenv("LIVEKIT_URL", "").strip()
    parsed = urlsplit(raw)
    if parsed.scheme != "wss" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        return None
    # Restrict values that will also appear in a CSP header.
    if any(c.isspace() or c in ";'\"" for c in raw):
        return None
    return f"wss://{parsed.netloc}"


def voice_status():
    try:
        installed = importlib.util.find_spec("livekit.api") is not None
    except ModuleNotFoundError:
        installed = False
    checks = {"LiveKit SDK": installed, "LiveKit secure URL": bool(livekit_origin()),
              "LiveKit API key": bool(os.getenv("LIVEKIT_API_KEY")),
              "LiveKit API secret": bool(os.getenv("LIVEKIT_API_SECRET")),
              "Sarvam speech key": bool(os.getenv("SARVAM_API_KEY"))}
    return {"checks": checks, "ready": all(checks.values()),
            "gemini_ready": bool(os.getenv("GEMINI_API_KEY") and os.getenv("GEMINI_MODEL")),
            "worker_verified": False,
            "note": "Checks confirm local configuration only. Run the voice worker separately; provider access and audio quality require a live call."}


def voice_csp_origins():
    origin = livekit_origin()
    if not origin:
        return ""
    origins = [origin, origin.replace("wss:", "https:")]
    if urlsplit(origin).hostname.endswith(".livekit.cloud"):
        origins.extend(["wss://*.livekit.cloud", "https://*.livekit.cloud"])
    return " ".join(origins)


def create_voice_connection(service, language="hi", planner="rules", version="few-shot-v2"):
    status = voice_status()
    if not status["ready"]:
        missing = ", ".join(k for k, ok in status["checks"].items() if not ok)
        raise ValueError("Voice setup incomplete: " + missing)
    from livekit import api
    record = service.create(language, planner, version, "voice")
    room = "vaani-" + record["id"]
    metadata = json.dumps({"session_id": record["id"]})
    token = (api.AccessToken(os.environ["LIVEKIT_API_KEY"], os.environ["LIVEKIT_API_SECRET"])
             .with_identity("customer-" + uuid.uuid4().hex)
             .with_name("Demo customer")
             .with_ttl(timedelta(minutes=10))
             .with_grants(api.VideoGrants(room_join=True, room=room, can_publish=True,
                                          can_subscribe=True, can_publish_data=True))
             .with_room_config(api.RoomConfiguration(name=room, max_participants=2, empty_timeout=60,
                 agents=[api.RoomAgentDispatch(agent_name="vaani-sales", metadata=metadata)]))
             .to_jwt())
    return {"url": livekit_origin(), "token": token, "session_id": record["id"], "room": room}
