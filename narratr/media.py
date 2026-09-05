"""ffmpeg and ffprobe: the shared media primitives.

Split out of `stitch.py`, which had grown six responsibilities and was being
imported by `intro.py` for its ffmpeg wrappers while itself importing `intro`
to build the title card. Both now depend on this instead, and the cycle -- and
the two function-local imports that worked around it -- are gone.

Everything here runs a subprocess with a timeout. A wedged `mmdc` or a hung
Remotion render used to block a run forever, and under `--detach` it did so in
an orphaned session with no handle to kill.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from narratr.errors import PipelineError

# Must match FPS in render/remotion/src/Root.tsx, which is asserted by
# tests/test_frame_alignment.py rather than left to a comment.
FPS = 30

# Generous on purpose. A long scene legitimately takes minutes to render, so
# this is a hang detector, not a performance budget.
TIMEOUT = 30 * 60


class MediaError(PipelineError):
	"""An ffmpeg or ffprobe call failed."""


def _run(cmd: list[str], what: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
	try:
		return subprocess.run(
			cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT, check=False
		)
	except subprocess.TimeoutExpired:
		raise MediaError(f"{what} timed out after {TIMEOUT // 60} min: {cmd[0]}")
	except FileNotFoundError:
		raise MediaError(f"{what} failed: {cmd[0]} not found. Run 'narratr doctor'")


def ffmpeg(args: list[str], what: str) -> None:
	result = _run(["ffmpeg", "-y", "-v", "error", *args], what)
	if result.returncode != 0:
		tail = (result.stderr or result.stdout).strip().splitlines()[-5:]
		raise MediaError(f"{what} failed:\n  " + "\n  ".join(tail))


def probe_duration(path: Path) -> float:
	result = _run(
		["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
		f"probe {path.name}",
	)
	if result.returncode != 0:
		raise MediaError(f"probe {path.name} failed: {result.stderr.strip()[:200]}")
	try:
		return float(result.stdout.strip())
	except ValueError:
		# ffprobe reports "N/A" for a stream it cannot measure. Left to float()
		# this surfaced as a bare ValueError traceback.
		raise MediaError(f"probe {path.name}: no readable duration ({result.stdout.strip()!r})")


def audio_layout(path: Path) -> tuple[int, int]:
	"""Sample rate and channel count of the first audio stream."""
	result = _run(
		[
			"ffprobe",
			"-v",
			"error",
			"-select_streams",
			"a:0",
			"-show_entries",
			"stream=sample_rate,channels",
			"-of",
			"csv=p=0",
			str(path),
		],
		f"probe {path.name}",
	)
	fields = result.stdout.strip().split(",")
	if result.returncode != 0 or len(fields) != 2:
		raise MediaError(f"probe {path.name}: no readable audio layout ({result.stdout.strip()!r})")
	try:
		return int(fields[0]), int(fields[1])
	except ValueError:
		raise MediaError(f"probe {path.name}: unreadable audio layout ({fields})")


def frame_aligned(seconds: float, fps: int = FPS) -> float:
	"""The exact length the renderer will produce for this scene.

	Remotion rounds to whole frames, so this is what the video will be. Padding
	the audio to match is what makes the two lengths identical and the drift
	exactly zero rather than a per-scene coin flip.
	"""
	return max(1, round(seconds * fps)) / fps


def pad_to(src: Path, target: float, out: Path) -> None:
	"""Copy audio, silence-padded (or trimmed) to exactly `target` seconds."""
	tmp = out.with_name(f".{out.name}.partial.wav")
	try:
		ffmpeg(
			["-i", str(src), "-af", "apad", "-t", f"{target:.6f}", "-c:a", "pcm_f32le", str(tmp)],
			f"pad {src.name}",
		)
		tmp.rename(out)
	finally:
		tmp.unlink(missing_ok=True)


def strip_audio(src: Path, out: Path) -> None:
	"""Drop the renderer's silent track, keeping the video stream untouched.

	Remotion writes a silent AAC track into every scene. AAC encoder padding
	makes that track ~50ms longer than the picture, and a container's duration
	is the longest stream in it. The concat demuxer advances the timeline by
	container duration, so each join inserted a gap and the picture drifted late
	-- the same failure as the audio side, arriving from the other direction.
	"""
	tmp = out.with_name(f".{out.name}.partial.mp4")
	try:
		ffmpeg(["-i", str(src), "-an", "-c:v", "copy", str(tmp)], f"strip audio {src.name}")
		tmp.rename(out)
	finally:
		tmp.unlink(missing_ok=True)


def concat_list(paths: list[Path], out: Path) -> None:
	"""Write an ffmpeg concat demuxer list.

	The demuxer reads `file '...'` and takes a backslash-escaped `'` inside the
	quotes. A checkout under a path with an apostrophe in it broke assembly with
	an opaque ffmpeg error -- the one place a path is embedded in a text format
	rather than passed as argv.
	"""

	def quote(path: Path) -> str:
		# Close the quote, emit an escaped apostrophe, reopen: ' -> '\''
		return str(path.resolve()).replace("'", "'\\''")

	out.write_text("".join(f"file '{quote(p)}'\n" for p in paths))


# ---------------------------------------------------------------- silence

# Digital silence reports around -91 dB; real narration sits near -27 dB.
SILENCE_DB = -80.0

MEAN_VOLUME = re.compile(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB")


def parse_mean_volume(ffmpeg_stderr: str) -> float | None:
	"""Pull mean_volume out of ffmpeg's volumedetect output."""
	found = MEAN_VOLUME.search(ffmpeg_stderr)
	return float(found.group(1)) if found else None


def mean_volume(path: Path) -> float | None:
	result = _run(
		["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
		f"measure {path.name}",
	)
	return parse_mean_volume(result.stderr)


def check_audible(path: Path, scene_id: str) -> None:
	"""Refuse to pass on audio that contains only silence.

	A silent track has a codec, a duration and a bitrate, so every structural
	check passes it. This is the one that does not.
	"""
	level = mean_volume(path)
	if level is None:
		raise MediaError(f"{scene_id}: could not measure audio in {path.name}")
	if level < SILENCE_DB:
		raise MediaError(f"{scene_id}: audio is silent ({level:.1f} dB)")
