import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

try:
    from livekit.agents import Agent, ChatContext, ChatMessage, StopResponse
    from vaani.voice import SalesVoiceAgent, voice_providers
    AVAILABLE = True
except ImportError:
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE, "Install .[voice] for LiveKit contract tests")
class VoiceContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_committed_transcript_updates_shared_service_and_speaks(self):
        from vaani.service import Service
        with tempfile.TemporaryDirectory() as folder:
            service = Service(Path(folder) / "voice.sqlite3")
            record = service.create("hi", "rules", source="voice")
            tts = Mock()
            agent = SalesVoiceAgent(service, record, tts)
            session = Mock()
            session.say = AsyncMock()
            message = ChatMessage(role="user", content=["हाँ"])
            with patch.object(Agent, "session", new_callable=PropertyMock, return_value=session):
                with self.assertRaises(StopResponse):
                    await agent.on_user_turn_completed(ChatContext(), message)
            self.assertEqual(service.get(record["id"])["state"]["stage"], "city")
            session.say.assert_awaited_once()
            tts.update_options.assert_called_once_with(target_language_code="hi-IN")

    async def test_provider_constructors_match_installed_sdk(self):
        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-not-real"}):
            stt, tts = voice_providers("hi")
            self.assertIsNotNone(stt)
            self.assertIsNotNone(tts)
            await stt.aclose()
            await tts.aclose()

    async def test_interrupted_booking_acknowledgement_does_not_undo_reservation(self):
        from vaani.service import Service
        class InterruptedSpeech:
            interrupted = True
            def __await__(self):
                async def complete():
                    return None
                return complete().__await__()
        with tempfile.TemporaryDirectory() as folder:
            service = Service(Path(folder) / "voice.sqlite3")
            record = service.create("en", "rules", source="voice")
            for i, text in enumerate(["Yes", "Delhi", "100000", "This month", "1"]):
                service.turn(record["id"], text, f"prepare-{i}")
            agent = SalesVoiceAgent(service, record, Mock())
            session = Mock()
            session.say.return_value = InterruptedSpeech()
            message = ChatMessage(role="user", content=["Yes"])
            with patch.object(Agent, "session", new_callable=PropertyMock, return_value=session):
                with self.assertRaises(StopResponse):
                    await agent.on_user_turn_completed(ChatContext(), message)
            stored = service.get(record["id"])
            self.assertEqual(stored["state"]["stage"], "booked")
            self.assertEqual(stored["voice_metrics"]["interrupted_replies"], 1)
