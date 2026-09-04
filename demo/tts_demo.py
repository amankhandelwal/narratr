#!/usr/bin/env python3
"""Chatterbox TTS demo — narratr.

Renders narration text to a wav, chunked the way the real pipeline would
(one clip per scene), and reports the real-time factor so we know what
local TTS actually costs in wall clock on this machine.

Usage:
    python tts_demo.py                          # built-in voice, sample text
    python tts_demo.py --text script.txt        # your own text
    python tts_demo.py --voice ref.wav          # clone a voice (uses Turbo)
"""

import argparse
import os
import re
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import torch
import torchaudio as ta

SAMPLE = """Every doc-to-video project fails the same way. You build the slides
first, then try to make the narration fit them. Timing drift is unfixable, and
every edit re-breaks it.

So invert it. Narration becomes the master clock. The language model writes the
script, the text-to-speech engine renders each scene and hands back an exact
duration, and the renderer is simply told how long it has. Sync stops being a
problem you solve. It becomes a problem you never have."""

HERE = Path(__file__).parent
OUT = HERE / "out"


def pick_device() -> str:
	if torch.backends.mps.is_available():
		return "mps"
	return "cpu"


def load_model(device: str, cloning: bool):
	"""Turbo when we have a reference clip, standard otherwise.

	Turbo has no built-in voice — it only speaks as whatever you give it.
	"""
	# Checkpoints ship as CUDA tensors; remap them to whatever we're on.
	real_load = torch.load
	torch.load = lambda *a, **kw: real_load(*a, **{**kw, "map_location": device})
	try:
		if cloning:
			from chatterbox.tts_turbo import ChatterboxTurboTTS

			return ChatterboxTurboTTS.from_pretrained(device=device), "turbo"
		from chatterbox.tts import ChatterboxTTS

		return ChatterboxTTS.from_pretrained(device=device), "standard"
	finally:
		torch.load = real_load


def split_scenes(text: str, max_chars: int = 400) -> list[str]:
	"""Group sentences into scene-sized chunks.

	The real pipeline chunks per scene anyway, which is what keeps local
	models honest — they drift over long single passes, not short ones.
	"""
	scenes, current = [], ""
	for sentence in re.split(r"(?<=[.!?])\s+", " ".join(text.split())):
		if current and len(current) + len(sentence) + 1 > max_chars:
			scenes.append(current)
			current = sentence
		else:
			current = f"{current} {sentence}".strip()
	if current:
		scenes.append(current)
	return scenes


def main() -> None:
	ap = argparse.ArgumentParser()
	ap.add_argument("--text", type=Path, help="file of narration text")
	ap.add_argument("--voice", type=Path, help="10s reference clip to clone")
	ap.add_argument("--device", default=pick_device())
	args = ap.parse_args()

	text = args.text.read_text() if args.text else SAMPLE
	scenes = split_scenes(text)
	# Each variant gets its own directory so an A/B run cannot clobber
	# the other's clips — or the reference clip it is cloning from.
	outdir = OUT / ("turbo" if args.voice else "standard")
	outdir.mkdir(parents=True, exist_ok=True)

	print(f"device={args.device}  scenes={len(scenes)}")
	t0 = time.perf_counter()
	model, variant = load_model(args.device, cloning=bool(args.voice))
	print(f"loaded {variant} model in {time.perf_counter() - t0:.1f}s\n")

	kwargs = {"audio_prompt_path": str(args.voice)} if args.voice else {}
	clips, spoken, render = [], 0.0, 0.0

	for i, scene in enumerate(scenes, 1):
		t = time.perf_counter()
		wav = model.generate(scene, **kwargs)
		elapsed = time.perf_counter() - t
		seconds = wav.shape[-1] / model.sr

		path = outdir / f"scene_{i:02d}.wav"
		ta.save(str(path), wav, model.sr)
		clips.append(wav)
		spoken += seconds
		render += elapsed
		print(
			f"  scene {i}: {seconds:5.1f}s audio in {elapsed:5.1f}s  "
			f"(rtf {elapsed / seconds:.2f})  {path.name}"
		)

	full = outdir / "full.wav"
	ta.save(str(full), torch.cat(clips, dim=-1), model.sr)

	print(f"\n{spoken:.1f}s of audio in {render:.1f}s  (rtf {render / spoken:.2f})")
	print(f"→ {full}")
	# At this rate, extrapolate the plan's 36-minute reference video.
	print(f"  a 36-min video would take ~{36 * render / spoken:.0f} min of TTS")


if __name__ == "__main__":
	main()
