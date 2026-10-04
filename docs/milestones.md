# Development and learning milestones

## 1. Explainable local application — implemented

Read `domain.py` first. Trace consent through booking. Then read `service.py` and explain why booking, state, and transcript belong in the same transaction. Run the dashboard and reproduce one Hindi journey and one refusal. Inspect the tests before editing logic.

Learning checkpoint: explain the difference between an intent, a state, and a side effect; explain why a slot choice is not confirmation; show a SQL query with its denominator.

## 2. Measured LLM understanding — comparison UI implemented; live validation pending

Configure Gemini locally, run both prompt variants on the same cases, and inspect errors by category. Create a held-out set of paraphrases that were not used to write prompts. Have a fluent Hindi speaker review intent labels and responses. Record model, prompt version, sample size, repeated runs, errors, and cost. Do not tune on the held-out set and then call it independent.

Learning checkpoint: defend zero-shot versus few-shot prompts, persona constraints, structured outputs, schema validation, model errors, and fail-closed handling.

## 3. Real voice evidence — browser and worker implemented; audio testing pending

Configure Sarvam and run the LiveKit console. Test English, Hindi, code-mixed phrases, background noise, interruptions, and silence using consenting participants or your own voice. Test a booking acknowledgement interrupted halfway through. Add audio fixtures and reference transcripts; measure speech latency separately from local policy time.

Learning checkpoint: explain STT → intent extraction → policy → TTS, VAD versus semantic turn detection, and why preemptive generation is disabled around state changes.

## 4. Resume and interview evidence — after the above checks

Prepare a short recorded demo, a clear contribution statement, and an experiment report. Resume bullets must distinguish application logic from LiveKit/Sarvam internals. Report only actual measured test counts or supported behavior. Do not claim better conversion, production users, company-scale traffic, or model accuracy from scripted examples.

Suggested interview questions to practice now:

1. What happens if two sessions confirm the same slot simultaneously?
2. Why can an LLM decide intent but not commit a booking?
3. Why does a perfect offline test score not imply perfect conversational accuracy?
4. How do you distinguish an API retry from a new customer message?
5. What exactly is the denominator in your booking-rate query?
6. What changes when the caller switches from Hindi to English mid-conversation?
7. How would you evaluate whether few-shot prompting helped?
8. How would you migrate this local system to several voice workers?

Estimated remaining effort depends on Python/SQL familiarity and provider access: roughly 1–2 weeks part-time for careful LLM/audio validation and presentation, with more time if those concepts are new. This is an estimate, not a promised completion date.
