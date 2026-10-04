# Why Vaani is the selected project

The supplied SquadStack JD explicitly emphasizes Python, SQL, LLM prompting (zero-shot, few-shot, role and persona), English/Hindi communication, translating business goals into conversation flows, structured testing, debugging, reusable components, and evidence-driven iteration. It names no mandatory web framework, cloud platform, database vendor, or ML training library.

Its discussion of proprietary STT and large GPU clusters is company context, not a requirement to train a speech model for this junior role. The strongest feasible portfolio signal is one complete bilingual business flow with explainable decisions and evaluation evidence.

## Existing foundations considered

| Foundation | Useful existing work | Gap for this JD | Decision |
|---|---|---|---|
| [LiveKit Python starter](https://github.com/livekit-examples/agent-starter-python) | Voice lifecycle, provider integration, deployment example, evaluation setup | Starter is generic; the inspected source defaults to English STT and lacks this campaign's SQL/business policy | Adapt lifecycle patterns; use SDK; build substantial original application logic |
| [Pipecat + Flows](https://github.com/pipecat-ai/pipecat/tree/main/examples/flows) | Explicit nodes, transitions, Python/YAML flow examples | Still requires original campaign, bilingual validation, persistence and analytics | Strong alternative, especially for a visual flow authoring focus |
| [Bolna](https://github.com/bolna-ai/bolna) | Voice orchestration and telephony integrations | Broader setup, hosted UI/API are separate from open repository; extra infrastructure distracts from the first portfolio milestone | Use for inspiration; revisit if real telephony becomes a requirement |

The review used repository documentation plus selected source/config files, not a full security audit or load test. LiveKit's starter exposes a compact application surface; Pipecat's reservation handler separates business logic from routing; Bolna's inspected local setup includes Redis and telephony services. None supplies the original JD-specific evidence by merely being cloned.

## Top project directions and judgment

Scores are planning judgments, not hiring probabilities. Components use the user's requested weighting: alignment /30, depth /20, relevance /15, resume /15, interview /10, architecture /10.

| Proposed completed project | Alignment | Depth | Relevance | Resume | Interview | Architecture | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bilingual sales agent + evaluations + SQL (selected) | 29 | 17 | 14 | 14 | 10 | 9 | 93 |
| Pipecat bilingual appointment-flow builder + test harness | 27 | 17 | 13 | 13 | 9 | 9 | 88 |
| Bolna call-quality/telephony extension + SQL reports | 25 | 18 | 14 | 12 | 9 | 8 | 86 |

These scores describe the intended finished projects, not the current unfinished voice integration or ownership of the upstream repositories. Real audio evidence and the candidate's understanding matter more than a score.

**Build vs adapt:** Rebuilding media transport would consume time without demonstrating the JD's core responsibilities. Merely forking a voice demo would show little original judgment. An existing framework plus original business logic, tests, and analysis gives the best balance. That is the selected approach.

## JD requirement → feature → evidence

| Priority | Requirement | Feature | Inspectable evidence |
|---|---|---|---|
| Must have | Python | State machine, transactional service, evaluation runner | `domain.py`, `service.py`, `evaluation.py` |
| Must have | SQL | Sessions/turns/bookings schema; grouped outcomes | `schema.sql`, SQL insights, uniqueness constraints |
| Must have | Prompt engineering | Versioned zero-shot/few-shot extraction prompts | `planner.py`; live comparison remains to be measured |
| Must have | English and Hindi | Bilingual script and selected Hinglish inputs | 26 scenario transcripts; live speech remains unverified |
| Must have | Business goals → workflows | Qualify and explicitly confirm a test ride | Consent-to-booking state transitions |
| High value | Evaluate and debug | Expected states, failure messages, provider status | Scenario runner and automated tests |
| High value | Reusable tools/components | One service for web and voice channels | `Service.turn`, provider adapters |
| High value | Ownership and communication | Reproducible demo, honest limitations, attribution | README, design notes, evidence report |
| Medium value | APIs/integrations | Local HTTP API, Gemini, LiveKit/Sarvam | Contract tests; paid integration pending |
| Medium value | Data-driven iteration | Cohorts, prompt versions, isolated eval runs | SQL dashboard and future comparison reports |
| Nice to have | Deployment/CI | Local runnable app and GitHub Actions file | CI configuration; no hosted deployment claim |

Relevant ATS language, only after you can explain the work: Python, SQL, prompt engineering, LLMs, conversational AI, voice AI, agentic workflows, conversation design, evaluation, automated testing, APIs, English/Hindi, debugging, conversational analytics.

The project does not demonstrate actual cross-functional employment experience or company-scale traffic. Do not imply either in a resume.
