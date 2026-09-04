"""Narration via Chatterbox Turbo.

The slow stage, and the only one currently built. Measured on an M4 Pro at a
real-time factor of 1.59, so a 36-minute video costs roughly 100 minutes here.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from narratr.paths import ROOT
from narratr.state import Manifest


class NarrationError(Exception):
	"""Narration cannot proceed as configured."""


def _resolve_voice(spec: dict[str, Any]) -> Path:
	reference = spec.get("voice", {}).get("reference")
	if not reference:
		raise NarrationError(
			"no voice.reference in scenes.json. Chatterbox Turbo has no built-in "
			"voice, so point it at a 10s clip or one of the samples in assets/voices/"
		)
	path = Path(reference)
	if not path.is_absolute():
		path = ROOT / path
	if not path.exists():
		raise NarrationError(f"voice reference not found: {path}")
	return path


def run(spec: dict[str, Any], manifest: Manifest, run_dir: Path) -> None:
	"""TTS, one clip per scene, resumable."""
	todo = manifest.pending("audio")
	if not todo:
		print("narrate: nothing to do")
		return

	reference = _resolve_voice(spec)

	# Imported here rather than at module scope: loading torch costs seconds,
	# and `narratr doctor` should not pay for it.
	import torch
	import torchaudio
	from chatterbox.tts_turbo import ChatterboxTurboTTS

	audio_dir = run_dir / "audio"
	audio_dir.mkdir(exist_ok=True)

	device = "mps" if torch.backends.mps.is_available() else "cpu"
	print(f"narrate: {len(todo)} scene(s) on {device}")

	# One process, many scenes. The model costs ~75s to load, so never spawn
	# per scene. Checkpoints ship as CUDA tensors, hence the remap.
	real_load = torch.load
	torch.load = lambda *a, **kw: real_load(*a, **{**kw, "map_location": device})
	try:
		model = ChatterboxTurboTTS.from_pretrained(device=device)
	finally:
		torch.load = real_load

	by_id = {s["id"]: s for s in spec["scenes"]}
	spoken = 0.0
	elapsed = 0.0

	for n, scene_id in enumerate(todo, 1):
		key = manifest.data["scenes"][scene_id]["key"]
		out = audio_dir / f"{scene_id}.{key}.wav"

		if out.exists():  # content-addressed hit
			manifest.mark(scene_id, "audio", out.name)
			print(f"  [{n}/{len(todo)}] {scene_id}: cached")
			continue

		started = time.perf_counter()
		wav = model.generate(by_id[scene_id]["narration"], audio_prompt_path=str(reference))
		took = time.perf_counter() - started
		seconds = wav.shape[-1] / model.sr

		# The temp name keeps its .wav extension because torchaudio infers the
		# container from it. Same directory, so the rename stays atomic.
		tmp = out.with_name(f".{out.name}.partial.wav")
		torchaudio.save(str(tmp), wav, model.sr)
		tmp.rename(out)
		manifest.mark(scene_id, "audio", out.name)

		spoken += seconds
		elapsed += took
		print(
			f"  [{n}/{len(todo)}] {scene_id}: {seconds:5.1f}s audio "
			f"in {took:5.1f}s (rtf {took / seconds:.2f})"
		)

	if spoken:
		print(f"✓ narrate: {spoken:.0f}s audio in {elapsed:.0f}s (rtf {elapsed / spoken:.2f})")
