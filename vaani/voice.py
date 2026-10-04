"""Optional LiveKit/Sarvam adapter. See THIRD_PARTY.md for upstream attribution.

Business decisions run only after a committed user turn; speculative generation
is disabled because a confirmation can write a reservation.
"""
import asyncio
import os
import json
import time
from dotenv import load_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, StopResponse, cli
from livekit.plugins import sarvam, silero
from .service import Service

load_dotenv()


def voice_providers(language):
    code = "hi-IN" if language == "hi" else "en-IN"
    return (
        sarvam.STT(language="unknown", model=os.getenv("SARVAM_STT_MODEL", "saaras:v4"), mode="transcribe"),
        sarvam.TTS(target_language_code=code, model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"), speaker=os.getenv("SARVAM_SPEAKER", "shubh")),
    )


class SalesVoiceAgent(Agent):
    def __init__(self, service, record, tts):
        super().__init__(instructions="A bilingual test-ride assistant. Conversation policy is enforced by the application.")
        self.service = service
        self.record = record
        self.speech = tts
        self.turn_lock = asyncio.Lock()
        self.transcript_at = None

    async def on_enter(self):
        await self.session.say(self.record["greeting"], allow_interruptions=True)

    async def on_user_turn_completed(self, turn_ctx, new_message):
        text = new_message.text_content
        if not text or not text.strip():
            raise StopResponse()
        async with self.turn_lock:
            self.transcript_at = time.perf_counter()
            result = await asyncio.to_thread(self.service.turn, self.record["id"], text, new_message.id)
            self.speech.update_options(target_language_code="hi-IN" if result["state"]["language"] == "hi" else "en-IN")
            speech = self.session.say(result["reply"], allow_interruptions=True)
            await speech
            if getattr(speech, "interrupted", False):
                self.service.voice_event(self.record["id"], "interrupted", detail="Committed reply interrupted; database action is retained")
        # The shared service already interpreted and answered this turn.
        raise StopResponse()


server = AgentServer()


@server.rtc_session(agent_name="vaani-sales")
async def entrypoint(ctx: JobContext):
    service = Service(os.getenv("VAANI_DB", "data/vaani.sqlite3"))
    metadata = json.loads(ctx.job.metadata or "{}")
    if metadata.get("session_id"):
        record = service.get(metadata["session_id"])
        if record["source"] != "voice" or ctx.room.name != "vaani-" + record["id"]:
            raise ValueError("Voice session does not match dispatched room")
    else:
        record = service.create(os.getenv("VAANI_LANGUAGE", "hi"), os.getenv("VAANI_PLANNER", "gemini"), os.getenv("VAANI_PROMPT", "few-shot-v2"), "voice")
    language = record["language"]
    stt, tts = voice_providers(language)
    agent = SalesVoiceAgent(service, record, tts)
    session = AgentSession(stt=stt, tts=tts, vad=silero.VAD.load(),
                           turn_handling={"turn_detection": "vad", "preemptive_generation": {"enabled": False}})

    @session.on("agent_state_changed")
    def agent_state(event):
        service.voice_event(record["id"], "agent_state", detail=event.new_state)
        if event.new_state == "speaking" and agent.transcript_at is not None:
            service.voice_event(record["id"], "transcript_to_speech_ms", round((time.perf_counter()-agent.transcript_at)*1000,2))
            agent.transcript_at = None

    @session.on("user_state_changed")
    def user_state(event):
        service.voice_event(record["id"], "user_state", detail=event.new_state)

    async def on_shutdown():
        service.voice_event(record["id"], "disconnected")
    ctx.add_shutdown_callback(on_shutdown)
    await session.start(agent=agent, room=ctx.room)
    await ctx.connect()
    service.voice_event(record["id"], "connected")


if __name__ == "__main__":
    cli.run_app(server)
