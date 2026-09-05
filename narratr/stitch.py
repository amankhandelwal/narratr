"""Mux each scene with its audio, then concatenate into one video.

Stream copy throughout for the video, so this is measured in milliseconds
rather than minutes and nothing is re-encoded.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from narratr.paths import STORE
from narratr.state import Manifest


class StitchError(Exception):
	"""Assembly cannot proceed."""


def _ffmpeg(args: list[str], what: str) -> None:
	result = subprocess.run(["ffmpeg", "-y", "-v", "error", *args], capture_output=True, text=True)
	if result.returncode != 0:
		tail = (result.stderr or result.stdout).strip().splitlines()[-5:]
		raise StitchError(f"{what} failed:\n  " + "\n  ".join(tail))


# Digital silence reports around -91 dB; real narration sits near -27 dB. The
# threshold is nowhere near either, so it needs no tuning.
SILENCE_DB = -80.0

MEAN_VOLUME = re.compile(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB")


def parse_mean_volume(ffmpeg_stderr: str) -> float | None:
	"""Pull mean_volume out of ffmpeg's volumedetect output."""
	found = MEAN_VOLUME.search(ffmpeg_stderr)
	return float(found.group(1)) if found else None


def mean_volume(path: Path) -> float | None:
	"""Measure a file's mean volume in dB, or None if ffmpeg reported nothing."""
	result = subprocess.run(
		["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
		capture_output=True,
		text=True,
	)
	return parse_mean_volume(result.stderr)


def check_audible(path: Path, scene_id: str) -> None:
	"""Refuse to pass on a segment that contains silence.

	A silent track has a codec, a duration and a bitrate, so every structural
	check passes. This is the one that does not. It exists because a silent
	video shipped once: ffmpeg picked Remotion's silent AAC over the narration
	and reported success.
	"""
	level = mean_volume(path)
	if level is None:
		raise StitchError(f"{scene_id}: could not measure audio in {path.name}")
	if level < SILENCE_DB:
		raise StitchError(
			f"{scene_id}: audio is silent ({level:.1f} dB). Check the -map arguments in mux_args"
		)


def mux_args(video: Path, audio: Path, out: Path) -> list[str]:
	"""Combine a rendered scene with its narration.

	The explicit -map is load-bearing. Remotion writes its own silent AAC track
	into every scene, at a higher bitrate than our narration wav, so ffmpeg's
	default stream selection picks *that* as the "best" audio and the result is
	silent with no warning. Name both streams rather than letting ffmpeg guess.

	Video is copied; only audio is encoded. -shortest trims the frame-rounded
	video back to the audio, which is the master clock.
	"""
	return [
		"-i",
		str(video),
		"-i",
		str(audio),
		"-map",
		"0:v:0",
		"-map",
		"1:a:0",
		"-c:v",
		"copy",
		"-c:a",
		"aac",
		"-b:a",
		"192k",
		"-shortest",
		"-movflags",
		"+faststart",
		str(out),
	]


def probe_duration(path: Path) -> float:
	out = subprocess.run(
		["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
		capture_output=True,
		text=True,
		check=True,
	)
	return float(out.stdout.strip())


def chapter_metadata(spec: dict[str, Any], durations: dict[str, float]) -> str:
	"""An ffmpeg metadata file marking each scene as a chapter.

	Titles come from the scene heading, falling back to the id. Offsets are
	cumulative measured segment durations, so they track the assembled video
	rather than the raw audio.
	"""
	lines = [";FFMETADATA1"]
	start = 0.0
	for scene in spec["scenes"]:
		end = start + durations[scene["id"]]
		title = scene.get("heading") or scene["id"]
		lines += [
			"[CHAPTER]",
			"TIMEBASE=1/1000",
			f"START={round(start * 1000)}",
			# One millisecond short so chapters do not overlap by a tick.
			f"END={max(round(end * 1000) - 1, round(start * 1000))}",
			f"title={title}",
		]
		start = end
	return "\n".join(lines) + "\n"


def run(spec: dict[str, Any], manifest: Manifest, run_dir: Path) -> None:
	scenes = spec["scenes"]
	incomplete = [
		s["id"]
		for s in scenes
		if not (
			manifest.data["scenes"][s["id"]].get("video")
			and manifest.data["scenes"][s["id"]].get("audio")
		)
	]
	if incomplete:
		raise StitchError(f"not ready: {', '.join(incomplete[:3])} missing audio or video")

	muxed_dir = run_dir / "muxed"
	muxed_dir.mkdir(exist_ok=True)
	segments: list[Path] = []
	durations: dict[str, float] = {}

	print(f"stitch: {len(scenes)} scene(s)")
	for scene in scenes:
		entry = manifest.data["scenes"][scene["id"]]
		out = muxed_dir / f"{entry['audio_key']}.{entry['video_key']}.mp4"

		if not out.exists():
			tmp = out.with_name(f".{out.name}.partial.mp4")
			_ffmpeg(
				mux_args(
					STORE / "video" / entry["video"],
					STORE / "audio" / entry["audio"],
					tmp,
				),
				f"mux {scene['id']}",
			)
			tmp.rename(out)

		check_audible(out, scene["id"])
		segments.append(out)
		durations[scene["id"]] = probe_duration(out)

	listing = run_dir / "concat.txt"
	listing.write_text("".join(f"file '{p.relative_to(run_dir)}'\n" for p in segments))

	chapters = run_dir / "chapters.txt"
	chapters.write_text(chapter_metadata(spec, durations))

	final = run_dir / "video.mp4"
	tmp = final.with_name(".video.partial.mp4")
	_ffmpeg(
		[
			"-f",
			"concat",
			"-safe",
			"0",
			"-i",
			str(listing),
			"-i",
			str(chapters),
			"-map_metadata",
			"1",
			"-c",
			"copy",
			"-movflags",
			"+faststart",
			str(tmp),
		],
		"concat",
	)
	tmp.rename(final)

	total = probe_duration(final)
	print(f"✓ stitch: {total:.0f}s, {len(scenes)} chapters -> {final.name}")

	# Captions are re-derived from the muxed segment durations, not the raw
	# audio: frame rounding shifts each scene slightly, and over dozens of
	# scenes that drift would be audible against the subtitles.
	from narratr.align import write_captions

	write_captions(spec, manifest, run_dir, durations=durations)
