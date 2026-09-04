# Chatterbox TTS demo

Local text-to-speech on the M4 Pro. No API key, no cost.

## Run

```sh
./.venv/bin/python tts_demo.py                  # built-in voice, sample text
./.venv/bin/python tts_demo.py --text mine.txt  # your own narration
./.venv/bin/python tts_demo.py --voice ref.wav  # clone a voice (Turbo model)
```

Output lands in `out/` — one wav per scene plus a concatenated `full.wav`.

## Notes

- **Two models.** Standard `ChatterboxTTS` has a built-in voice and needs no
  reference clip. `ChatterboxTurboTTS` only speaks as a voice you give it, so
  `--voice` switches to Turbo automatically.
- **Chunking is deliberate.** Text is split into ~400-char scenes before
  synthesis. Local models drift over long single passes; short ones they handle
  fine. The real pipeline chunks per scene anyway.
- **RTF** in the output is the real-time factor — seconds of compute per second
  of audio. That number is the actual argument against local TTS, not quality.
