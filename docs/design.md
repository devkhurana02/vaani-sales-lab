# Design decisions and boundaries

## One policy, two channels

The browser sends text to the application service. The voice adapter receives a committed transcript and sends it to the same service. A planner extracts a typed decision; the domain module advances a state machine; the service commits state, transcript, and any reservation together.

The optional Gemini planner uses structured output and versioned prompts. It has no booking capability, SQL access, or tool-execution privilege. Domain logic interprets an `affirm` only in the appropriate state. A slot choice transitions to confirmation; it does not book. Entity corrections invalidate pending confirmation. A model can still misinterpret consent or a field, so this design limits authority but does not prove semantic correctness.

## Database integrity

Planner inference occurs outside the SQLite write transaction. The transaction then compares the stored state and turn count with the snapshot used for inference. If another request won, the request is rejected with 409; the client refreshes rather than silently applying a stale decision.

The write uses `BEGIN IMMEDIATE`. `UNIQUE(city,slot)` arbitrates competing reservations and `UNIQUE(session_id)` prevents multiple reservations for one session. `UNIQUE(session_id,request_id)` plus a request hash allows an exact retry to return its original response and rejects reusing the same key for different content. The response, transcript, state, and booking are committed atomically.

Capacity is intentionally only one per city/slot. A production inventory would include dealership/resource IDs and capacity, and use PostgreSQL transaction semantics for multiple workers. Availability is optimistic: an offered slot can disappear before confirmation. The current fallback flags human review instead of searching a calendar indefinitely.

## Response quality and AI scope

Approved English/Hindi templates keep prices and reservations grounded and make debugging simple. This is intentionally less flexible than unconstrained generative dialogue. New FAQs currently require a domain entry and tests. There is no decorative RAG layer because the fictional catalog has only a few facts.

The offline parser covers documented examples; it does not understand arbitrary Hindi or complex negation reliably. Gemini is intended for broader paraphrases but remains unmeasured. An LLM-free passing scenario suite is evidence of policy regression behavior only. Prompt variants are ignored by the offline parser. No quality gain between versions is fabricated.

## Failure handling

- API timeout, malformed JSON, or invalid output: no state change; record `provider_error` and ask for retry.
- Unknown input: clarification, then a local human-review outcome after three unclear turns.
- Opt-out: terminal conversation, no further outreach from the app.
- Concurrent or expired slot: no booking; explicit unavailability response.
- Duplicate confirmation: return cached result or terminal response; never double-book.
- Interrupted speech: a committed database reservation can outlive an interrupted spoken acknowledgement. Inspect the stored booking and use the reference; do not repeat a write based only on whether speech finished.

## Security/privacy

The HTTP server binds to loopback and accepts expected localhost hosts only, preventing simple DNS rebinding. Writes require an unpredictable page token and a same-origin check. Static files are explicitly enumerated. The frontend uses textContent for customer messages. SQL uses parameters. CSP disables external scripts and frames. These are local-demo measures, not public-service authentication.

Basic email and contiguous Indian phone redaction runs before persistence and model calls. Spaced phone numbers, names, addresses, and other sensitive data are not comprehensively removed. Use invented data. API credentials are server-side environment values and ignored by Git. The database is not encrypted; it is local to this workspace and has no automatic retention policy.

## Observability and honest metrics

Per-turn records show interpreted intent, before/after state, provider status, and time spent processing text. Text processing timing does not measure speech recognition or playback. Voice Studio additionally records committed-transcript-to-speaking-state timing, also excluding recognition and network playback; it is not end-to-end acoustic latency. The service records generated replies, not proof a caller heard them. SQL counts real sandbox activity; evaluation sessions use disposable databases. Initial language, source, and planner are separate cohort dimensions.

For real audio testing, add end-of-user-speech → first-agent-audio timestamps, interruption recovery checks, reference transcripts and WER, and bilingual human ratings. Keep audio evaluation separate from scripted text pass rates. Pin model/provider versions and report sample size, repeated runs, and failed requests.

## Sources consulted

- https://github.com/livekit-examples/agent-starter-python
- https://docs.livekit.io/agents/logic/nodes/
- https://docs.livekit.io/agents/models/stt/sarvam/
- https://docs.livekit.io/agents/models/tts/sarvam/
- https://ai.google.dev/gemini-api/docs/structured-output

Source review and dependency verification took place on 4 October 2026. Actual installed voice SDK: livekit-agents 1.8.4. Live provider behavior remains unverified.

## Voice transport and browser lifecycle (v0.2)

The authenticated local POST `/api/voice/connect` creates a voice session and issues a room-scoped 10-minute LiveKit token, with a dispatch configuration carrying the local session ID. The worker checks that the dispatched session is a voice session and matches the room name. The worker and web server must share the same SQLite database; this is a single-machine architecture.

Only the token and LiveKit URL go to the browser. Provider secrets remain server-side. A local configuration checklist returns booleans only. The browser loads a bundled SDK rather than a runtime third-party CDN. CSP permits the configured secure LiveKit origin and, for LiveKit Cloud, its regional subdomains. Token expiration limits future joins; it does not automatically end a connected call.

End-call disconnects the room and releases published tracks. A generation counter prevents an in-flight connection from enabling the microphone after cancellation. A denied microphone request cleans up the room. If no agent appears after 30 seconds, the app disconnects and provides instructions. These paths have mocked client tests; provider connectivity remains unverified.

Metrics summarize the complete session, independent of the last 40 events returned for inspection. A booking acknowledged by interrupted speech stays committed. No fabricated audio accuracy, cost, or timing is shown when no call has occurred.
