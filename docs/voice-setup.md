# Activate Voice Studio

The UI and worker are implemented. Real calls remain untested until you configure your own provider accounts. Do not paste secrets into chat or commit them to Git.

1. In this project folder, copy `.env.example` to `.env` if you do not already have a private `.env`.
2. Set `LIVEKIT_URL` to your project's secure `wss://…` URL, plus `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`.
3. Set `SARVAM_API_KEY` for speech recognition and synthesis.
4. Optionally set `GEMINI_API_KEY` and `GEMINI_MODEL` for broader language understanding. Voice with the rules baseline still uses paid speech services but does not need Gemini.
5. Start both processes below from this same project folder, with the same `VAANI_DB` setting. The default database is `data/vaani.sqlite3`.

First terminal:

```sh
.venv/bin/python -m vaani serve
```

Second terminal:

```sh
.venv/bin/python -m vaani.voice download-files
.venv/bin/python -m vaani.voice dev
```

Open the local dashboard and choose **Voice studio**. The checklist confirms whether configuration values exist; it does not verify provider account access. Select English or Hindi, select the interpreter, start a conversation, and allow microphone access. Speak using invented customer information. End the call when finished.

## Troubleshooting

| Symptom | Check |
|---|---|
| Missing configuration | `.env` exists in the folder where the server starts; restart after changes |
| No agent joins | Voice worker is running, uses the same LiveKit project and database, and has valid speech keys |
| Microphone denied | Allow microphone access for the local page in browser settings |
| Agent silent | Use Enable sound if shown; inspect worker errors and Sarvam access/model availability |
| Rules parser fails a paraphrase | Try the documented demo phrases or configure Gemini; rules mode has a deliberately limited grammar |
| Gemini errors | Confirm model availability and structured-output support in your account; no provider request is retried automatically |
| Booking shown after an interruption | The database committed it before playback; interruption does not cancel or duplicate a reservation |

## Validation before resume claims

Test complete English, Hindi and mixed-language journeys, corrections, silence, noise, and interruptions. Keep recordings only with participant permission. Report the number and type of calls you actually tested. The current automated results verify code and mocked interfaces; they are not a speech-quality benchmark.
