"""Forced alignment: word timings and captions.

The text is known exactly — it is what we asked Chatterbox to say — so this is
forced alignment rather than transcription. torchaudio ships a CTC aligner and
the MMS_FA bundle, which means no extra dependency and better accuracy than
transcribing the audio back and hoping it matches.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from narratr import speed
from narratr.device import release_cache, select
from narratr.paths import STORE
from narratr.spoken import say
from narratr.state import Manifest, atomic_write

# MMS_FA's vocabulary is lowercase latin plus apostrophe.
UNSPEAKABLE = re.compile(r"[^a-z']")

MAX_CUE_WORDS = 8
MAX_CUE_SECONDS = 3.5


class AlignmentError(Exception):
	"""Alignment cannot proceed."""


def normalise(word: str) -> str:
	"""Reduce a display word to what the aligner's vocabulary accepts.

	Numbers and symbols are spelled out first. Stripping them instead dropped
	the token from the alignment target while Chatterbox went on speaking it,
	so the neighbouring words swallowed that audio and their timings skewed --
	and the token never reached the captions. See `narratr/spoken.py`.
	"""
	return UNSPEAKABLE.sub("", say(word).lower())


def _timestamp(seconds: float) -> str:
	ms = round(seconds * 1000)
	h, ms = divmod(ms, 3_600_000)
	m, ms = divmod(ms, 60_000)
	s, ms = divmod(ms, 1000)
	return f"{h:02}:{m:02}:{s:02},{ms:03}"


def to_cues(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Group word timings into caption cues short enough to read."""
	cues: list[dict[str, Any]] = []
	current: list[dict[str, Any]] = []

	for word in words:
		if current and (
			len(current) >= MAX_CUE_WORDS or word["end"] - current[0]["start"] > MAX_CUE_SECONDS
		):
			cues.append(
				{
					"start": current[0]["start"],
					"end": current[-1]["end"],
					"text": " ".join(w["word"] for w in current),
				}
			)
			current = []
		current.append(word)

	if current:
		cues.append(
			{
				"start": current[0]["start"],
				"end": current[-1]["end"],
				"text": " ".join(w["word"] for w in current),
			}
		)
	return cues


def to_srt(cues: list[dict[str, Any]]) -> str:
	blocks = [
		f"{n}\n{_timestamp(c['start'])} --> {_timestamp(c['end'])}\n{c['text']}\n"
		for n, c in enumerate(cues, 1)
	]
	return "\n".join(blocks)


def _align_one(
	narration: str, wav_path: Path, model, tokenizer, aligner, bundle, device: str
) -> list[dict[str, Any]]:
	import torch
	import torchaudio

	waveform, sample_rate = torchaudio.load(str(wav_path))
	waveform = torchaudio.functional.resample(waveform, sample_rate, bundle.sample_rate)

	# Keep the display word beside its normalised form so punctuation and
	# capitalisation survive into the captions.
	pairs = [(w, normalise(w)) for w in narration.split()]
	speakable = [(display, norm) for display, norm in pairs if norm]
	if not speakable:
		raise AlignmentError(f"nothing alignable in: {narration[:60]!r}")

	with torch.inference_mode():
		emission, _ = model(waveform.to(device))

	# torchaudio::forced_align has no MPS kernel. Move the emission to CPU
	# explicitly rather than setting PYTORCH_ENABLE_MPS_FALLBACK, which would
	# silently send *any* unimplemented op to the CPU and hide the cost. The
	# expensive part is the forward pass above; the CTC search is cheap.
	emission = emission.cpu()
	spans = aligner(emission[0], tokenizer([norm for _, norm in speakable]))

	# Emission frames are coarser than samples; convert back to seconds.
	seconds_per_frame = waveform.shape[-1] / emission.shape[1] / bundle.sample_rate
	return [
		{
			"word": display,
			"start": round(span[0].start * seconds_per_frame, 3),
			"end": round(span[-1].end * seconds_per_frame, 3),
			"score": round(float(span[0].score), 3),
		}
		# strict: one span per speakable word, or the alignment is wrong
		for (display, _), span in zip(speakable, spans, strict=True)
	]


def run(spec: dict[str, Any], manifest: Manifest, run_dir: Path) -> None:
	"""Align every narrated scene, then write one captions file for the video."""
	todo = manifest.pending("aligned")

	# Same reasoning as narration: claim cached work before loading the model.
	timings_dir = STORE / "timings"
	remaining = []
	for scene_id in todo:
		cached = timings_dir / f"{manifest.data['scenes'][scene_id]['speech_key']}.json"
		if cached.exists():
			manifest.mark(scene_id, "aligned", cached.name)
		else:
			remaining.append(scene_id)
	todo = remaining

	if not todo:
		print("align: nothing to do")
		write_captions(spec, manifest, run_dir)
		return

	missing = [sid for sid in todo if not manifest.data["scenes"][sid].get("audio")]
	if missing:
		raise AlignmentError(f"no audio yet for {', '.join(missing[:3])}; run narration first")

	# Imported here, as in narrate: doctor should not pay for torch.
	import torchaudio
	from torchaudio.pipelines import MMS_FA

	timings_dir.mkdir(parents=True, exist_ok=True)

	device = select()
	print(f"align: {len(todo)} scene(s) on {device}")

	model = MMS_FA.get_model().to(device)
	tokenizer = MMS_FA.get_tokenizer()
	aligner = MMS_FA.get_aligner()

	by_id = {s["id"]: s for s in spec["scenes"]}
	spoken = 0.0
	elapsed = 0.0

	for n, scene_id in enumerate(todo, 1):
		entry = manifest.data["scenes"][scene_id]
		out = timings_dir / f"{entry['speech_key']}.json"
		wav_path = speed.path_for(entry)
		started = time.perf_counter()
		words = _align_one(
			by_id[scene_id]["narration"], wav_path, model, tokenizer, aligner, MMS_FA, device
		)
		took = time.perf_counter() - started

		info = torchaudio.info(str(wav_path))
		duration = info.num_frames / info.sample_rate

		atomic_write(out, json.dumps({"duration": duration, "words": words}, indent=2))
		manifest.mark(scene_id, "aligned", out.name)
		release_cache(device)

		spoken += duration
		elapsed += took
		weakest = min(w["score"] for w in words)
		print(
			f"  [{n}/{len(todo)}] {scene_id}: {len(words)} words in {took:5.1f}s "
			f"(worst score {weakest:.2f})"
		)

	if spoken:
		print(f"✓ align: {spoken:.0f}s audio in {elapsed:.0f}s (rtf {elapsed / spoken:.2f})")

	write_captions(spec, manifest, run_dir)


def write_captions(
	spec: dict[str, Any],
	manifest: Manifest,
	run_dir: Path,
	durations: dict[str, float] | None = None,
	offset: float = 0.0,
) -> Path:
	"""Stitch per-scene timings into one SRT on the video's timeline.

	`durations` overrides the per-scene audio length once the muxed segments
	exist, so captions track the video's real timeline rather than drifting
	by a frame per scene.

	`offset` is where the first scene starts, which is the length of the title
	card. Without it every cue would be four seconds early for the whole video.
	"""
	timings_dir = STORE / "timings"
	cues: list[dict[str, Any]] = []

	for scene in spec["scenes"]:
		entry = manifest.data["scenes"][scene["id"]]
		aligned = entry.get("aligned")
		if not aligned:
			# No cues for this scene, but the clock still runs through it. The
			# old `continue` skipped the offset too, so every later cue landed
			# early by this scene's whole duration. `durations` already carries
			# the right length whenever stitch is the caller.
			offset += (durations or {}).get(scene["id"], 0.0)
			continue
		payload = json.loads((timings_dir / aligned).read_text())
		shifted = [
			{**w, "start": w["start"] + offset, "end": w["end"] + offset} for w in payload["words"]
		]
		cues.extend(to_cues(shifted))
		offset += (durations or {}).get(scene["id"], payload["duration"])

	path = run_dir / "captions.srt"
	atomic_write(path, to_srt(cues))
	print(f"✓ captions: {len(cues)} cues over {offset:.0f}s -> {path.name}")
	return path
