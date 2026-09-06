"""Narration via Chatterbox Turbo.

The slow stage, and the only one currently built. Measured on an M4 Pro at a
real-time factor of 1.59, so a 36-minute video costs roughly 100 minutes here.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from narratr.device import release_cache, select
from narratr.errors import PipelineError
from narratr.paths import ROOT, STORE
from narratr.state import Manifest


class NarrationError(PipelineError):
	"""Narration cannot proceed as configured."""


# Chatterbox caps generation at `max_gen_len=1000` speech tokens, roughly forty
# seconds. Handed more text than fits, it does not truncate -- it compresses,
# rushing and slurring the whole scene to land inside the budget. A 155-word
# scene came back at 4.8 words/second against a natural 3.0. So narration is
# split into sentence-sized pieces, each generated well inside the ceiling and
# concatenated. The model already appends silence per call, which is what
# carries the sentence pause.
BUDGET = 280

_SENTENCE = re.compile(r"(?<=[.?!])\s+")
_CLAUSE = re.compile(r"(?<=[,;:])\s+")


def _pack(pieces: list[str], budget: int) -> list[str]:
	"""Greedily join pieces while they fit."""
	out: list[str] = []
	for piece in pieces:
		if out and len(out[-1]) + 1 + len(piece) <= budget:
			out[-1] = f"{out[-1]} {piece}"
		else:
			out.append(piece)
	return out


def split_narration(text: str, budget: int = BUDGET) -> list[str]:
	"""Narration as generation-sized chunks, in order, losing no words.

	Sentences first; a sentence longer than the budget falls back to clause
	boundaries, then to a hard word split, so no chunk can exceed the ceiling
	whatever the punctuation looks like.
	"""
	sentences = [s for s in (s.strip() for s in _SENTENCE.split(text)) if s]
	if not sentences:
		return []

	sized: list[str] = []
	for sentence in sentences:
		if len(sentence) <= budget:
			sized.append(sentence)
			continue
		clauses = _pack([c for c in (c.strip() for c in _CLAUSE.split(sentence)) if c], budget)
		for clause in clauses:
			if len(clause) <= budget:
				sized.append(clause)
				continue
			# No punctuation to lean on. Split on words, which is ugly to hear
			# but never drops any.
			words, line = clause.split(), ""
			for word in words:
				if line and len(line) + 1 + len(word) > budget:
					sized.append(line)
					line = word
				else:
					line = f"{line} {word}".strip()
			if line:
				sized.append(line)

	return _pack(sized, budget)


def _resolve_voice(spec: dict[str, Any]) -> Path:
	reference = spec.get("voice", {}).get("reference")
	if not reference:
		raise NarrationError(
			"no voice.reference in scenes.json. Chatterbox Turbo has no built-in "
			"voice, so point it at a 10s clip or one of the samples in assets/voices/"
		)
	# Resolved and contained. `reference` comes from an LLM-written scenes.json,
	# and an unconstrained path here read any file on the machine as a voice
	# prompt -- and told you, by its error, whether that file existed.
	path = Path(reference)
	if not path.is_absolute():
		path = ROOT / path
	resolved = path.resolve()
	if not resolved.is_relative_to(ROOT.resolve()):
		raise NarrationError(
			f"voice.reference must stay inside the project: {reference!r} resolves outside {ROOT}"
		)
	if not resolved.is_file():
		raise NarrationError(f"voice reference not found: {reference}")
	return resolved


def run(spec: dict[str, Any], manifest: Manifest, run_dir: Path) -> None:
	"""TTS, one clip per scene, resumable."""
	todo = manifest.pending("audio")

	# Claim content-addressed hits before loading anything. The model costs ~75s
	# to load, and a run where every scene is already narrated should not pay it.
	audio_dir = STORE / "audio"
	remaining = []
	for scene_id in todo:
		cached = audio_dir / f"{manifest.data['scenes'][scene_id]['audio_key']}.wav"
		if cached.exists():
			manifest.mark(scene_id, "audio", cached.name)
		else:
			remaining.append(scene_id)
	todo = remaining

	if not todo:
		print("narrate: nothing to do")
		return

	reference = _resolve_voice(spec)

	# Imported here rather than at module scope: loading torch costs seconds,
	# and `narratr doctor` should not pay for it.
	import torch
	import torchaudio
	from chatterbox.tts_turbo import ChatterboxTurboTTS

	audio_dir.mkdir(parents=True, exist_ok=True)

	device = select()
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

	# The plan called for pinning the reference clip *and* the seed, because
	# both are conditioning inputs. Only the clip was wired: the seed reached
	# `audio_key` and never the model, so it moved the cache without moving the
	# output and re-narration produced different audio for identical input.
	seed = spec.get("voice", {}).get("seed")

	for n, scene_id in enumerate(todo, 1):
		out = audio_dir / f"{manifest.data['scenes'][scene_id]['audio_key']}.wav"
		started = time.perf_counter()
		if seed is not None:
			# Re-seeded per scene, not once per run: a resumed run must give a
			# scene the same voice it would have had in a cold one, whatever
			# else was generated first.
			torch.manual_seed(seed)
		pieces = [
			model.generate(chunk, audio_prompt_path=str(reference))
			for chunk in split_narration(by_id[scene_id]["narration"])
		]
		wav = torch.cat(pieces, dim=-1) if len(pieces) > 1 else pieces[0]
		took = time.perf_counter() - started
		seconds = wav.shape[-1] / model.sr

		# The temp name keeps its .wav extension because torchaudio infers the
		# container from it. Same directory, so the rename stays atomic.
		tmp = out.with_name(f".{out.name}.partial.wav")
		torchaudio.save(str(tmp), wav, model.sr)
		tmp.rename(out)
		manifest.mark(scene_id, "audio", out.name)
		release_cache(device)

		spoken += seconds
		elapsed += took
		print(
			f"  [{n}/{len(todo)}] {scene_id}: {seconds:5.1f}s audio "
			f"in {took:5.1f}s (rtf {took / seconds:.2f})"
		)

	if spoken:
		print(f"✓ narrate: {spoken:.0f}s audio in {elapsed:.0f}s (rtf {elapsed / spoken:.2f})")
