# Open-source attribution

Vaani's optional voice adapter uses LiveKit Agents and follows lifecycle patterns from:

- Project: LiveKit Agents starter for Python
- Source: https://github.com/livekit-examples/agent-starter-python
- Inspected file: https://github.com/livekit-examples/agent-starter-python/blob/main/src/agent.py
- License: MIT, Copyright (c) 2025 LiveKit, Inc.
- Retrieved/reviewed: 4 October 2026
- Relevant patterns: Agent subclass, AgentServer registration, AgentSession startup, and CLI entry point.

The business service, campaign rules, prompts, local dashboard, SQL reports, and evaluation scenarios were authored for this project. The upstream starter was not copied as a complete repository. No claim is made that LiveKit's audio framework or Sarvam's speech models are original work by this project's author.

The MIT notice is preserved in `licenses/livekit-starter-MIT.txt`. LiveKit and its installed plugins retain their respective upstream license notices in their distributions. Google Gemini and Sarvam are optional external services with their own usage terms and billing.

Other research references, not copied or bundled:

- Pipecat / Pipecat Flows: https://github.com/pipecat-ai/pipecat
- Bolna: https://github.com/bolna-ai/bolna

## Browser voice SDK

The unmodified `vaani/static/livekit-client.umd.js` is LiveKit Client **2.22.3**, obtained from the official npm registry package `livekit-client`. The npm tarball's SHA-512 integrity was verified before copying the browser bundle. Its Apache-2.0 license is preserved at `licenses/livekit-client-LICENSE.txt`.

- Package: https://www.npmjs.com/package/livekit-client
- Source: https://github.com/livekit/client-sdk-js
- The microphone UI and connection lifecycle in `voice-ui.js` are original application code. The project does not claim ownership of the bundled SDK.
