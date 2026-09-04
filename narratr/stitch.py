"""Mux each scene with its audio, then concatenate into one video.

Stream copy throughout for the video, so this is measured in milliseconds
rather than minutes and nothing is re-encoded.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from narratr.state import Manifest


class StitchError(Exception):
	"""Assembly cannot proceed."""


def _ffmpeg(args: list[str], what: str) -> None:
	result = subprocess.run(["ffmpeg", "-y", "-v", "error", *args], capture_output=True, text=True)
	if result.returncode != 0:
		tail = (result.stderr or result.stdout).strip().splitlines()[-5:]
		raise StitchError(f"{what} failed:\n  " + "\n  ".join(tail))


def probe_duration(path: Path) -> float:
	out = subprocess.run(
		["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
		capture_output=True,
		text=True,
		check=True,
	)
	return float(out.stdout.strip())


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
		out = muxed_dir / f"{scene['id']}.{entry['key']}.mp4"

		if not out.exists():
			tmp = out.with_name(f".{out.name}.partial.mp4")
			# Video is copied; only the audio is encoded. -shortest trims the
			# frame-rounded video back to the audio, which is the master clock.
			_ffmpeg(
				[
					"-i",
					str(run_dir / "video" / entry["video"]),
					"-i",
					str(run_dir / "audio" / entry["audio"]),
					"-c:v",
					"copy",
					"-c:a",
					"aac",
					"-b:a",
					"192k",
					"-shortest",
					"-movflags",
					"+faststart",
					str(tmp),
				],
				f"mux {scene['id']}",
			)
			tmp.rename(out)

		segments.append(out)
		durations[scene["id"]] = probe_duration(out)

	listing = run_dir / "concat.txt"
	listing.write_text("".join(f"file '{p.relative_to(run_dir)}'\n" for p in segments))

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
	print(f"✓ stitch: {total:.0f}s -> {final.name}")

	# Captions are re-derived from the muxed segment durations, not the raw
	# audio: frame rounding shifts each scene slightly, and over dozens of
	# scenes that drift would be audible against the subtitles.
	from narratr.align import write_captions

	write_captions(spec, manifest, run_dir, durations=durations)
