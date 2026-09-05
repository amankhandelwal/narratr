"""Playback speed, applied after narration.

Kept separate from narration deliberately. Tempo is a cheap resample; narration
is the most expensive stage in the pipeline. Keying them apart means trying a
different speed costs about a second per scene instead of a re-narration.

It has to run before alignment, because word timings are measured from whatever
audio actually ships.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from narratr.media import MediaError, ffmpeg
from narratr.paths import STORE
from narratr.state import Manifest

# ffmpeg's atempo filter is only defined over this range per instance.
MIN_TEMPO = 0.5
MAX_TEMPO = 2.0

# Chatterbox's natural pace is a shade fast for narration you are meant to
# follow rather than skim. 0.92 was chosen by listening.
DEFAULT_SPEED = 0.92


class SpeedError(MediaError):
	"""The requested speed cannot be applied."""


def tempo_chain(speed: float) -> str:
	"""Express any speed as a chain of atempo filters inside their valid range.

	atempo handles 0.5-2.0. Anything beyond that is split into factors, so 0.4
	becomes two stages rather than a silent clamp.
	"""
	if speed <= 0:
		raise SpeedError(f"speed must be positive, got {speed}")
	factors: list[float] = []
	remaining = speed
	while remaining < MIN_TEMPO:
		factors.append(MIN_TEMPO)
		remaining /= MIN_TEMPO
	while remaining > MAX_TEMPO:
		factors.append(MAX_TEMPO)
		remaining /= MAX_TEMPO
	factors.append(remaining)
	return ",".join(f"atempo={f:.6f}" for f in factors)


def apply(src: Path, speed: float, out: Path) -> None:
	"""Resample to `speed` without shifting pitch."""
	tmp = out.with_name(f".{out.name}.partial.wav")
	try:
		ffmpeg(
			[
				"-i",
				str(src),
				"-filter:a",
				tempo_chain(speed),
				"-c:a",
				"pcm_f32le",
				str(tmp),
			],
			"tempo",
		)
		tmp.rename(out)
	finally:
		tmp.unlink(missing_ok=True)


def run(spec: dict[str, Any], manifest: Manifest, run_dir: Path) -> None:
	todo = manifest.pending("speech")
	if not todo:
		print("speed: nothing to do")
		return

	missing = [sid for sid in todo if not manifest.data["scenes"][sid].get("audio")]
	if missing:
		raise SpeedError(f"no narration yet for {', '.join(missing[:3])}; run narration first")

	speed = float(spec.get("voice", {}).get("speed", DEFAULT_SPEED))
	speech_dir = STORE / "speech"
	speech_dir.mkdir(parents=True, exist_ok=True)

	made = 0
	for scene_id in todo:
		entry = manifest.data["scenes"][scene_id]
		source = STORE / "audio" / entry["audio"]

		out = speech_dir / f"{entry['speech_key']}.wav"
		if not out.exists():
			if speed == 1.0:
				# No resample to do, but the artifact still has to exist under
				# its own key. The manifest used to hold "../audio/<name>.wav"
				# here -- one field carrying a bare filename at every other
				# speed and a traversing path at this one, which is why
				# `path_for` needed a `.resolve()` and why the manifest's
				# existence check only worked when store/speech happened to be
				# there. A hardlink costs nothing and keeps the field one type.
				try:
					out.hardlink_to(source)
				except OSError:
					shutil.copy(source, out)
			else:
				apply(source, speed, out)
			made += 1
		manifest.mark(scene_id, "speech", out.name)

	if made:
		print(f"✓ speed: {made} scene(s) at {speed}x")
	else:
		print("speed: nothing to do")


def path_for(entry: dict[str, Any]) -> Path:
	"""Where a scene's shipping audio lives, tempo applied or not."""
	return STORE / "speech" / entry["speech"]
