"""Assemble the scenes into one video.

Every scene's audio is padded to a whole number of frames, so a scene's audio
and video are exactly the same length. The whole narration is then concatenated
losslessly and encoded once.

That last part is not an optimisation, it is the correctness fix. Encoding each
scene to AAC separately gives every segment its own encoder priming, which the
segment's edit list compensates for. A stream copy cannot carry per-file edit
lists, so from the second segment onward that priming became real audio and the
picture ran ahead by roughly 36 ms per join -- 229 ms by the sixth scene, and
linear in scene count.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from narratr import speed
from narratr.paths import STORE
from narratr.state import Manifest, digest

# Must match FPS in render/remotion/src/Root.tsx.
FPS = 30


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
	_ffmpeg(
		["-i", str(src), "-af", "apad", "-t", f"{target:.6f}", "-c:a", "pcm_f32le", str(tmp)],
		f"pad {src.name}",
	)
	tmp.rename(out)


def strip_audio(src: Path, out: Path) -> None:
	"""Drop the renderer's silent track, keeping the video stream untouched.

	Remotion writes a silent AAC track into every scene. AAC encoder padding
	makes that track ~50ms longer than the picture, and a container's duration
	is the longest stream in it. The concat demuxer advances the timeline by
	container duration, so each join inserted a gap and the picture drifted late
	-- the same failure as the audio side, arriving from the other direction.
	"""
	tmp = out.with_name(f".{out.name}.partial.mp4")
	_ffmpeg(["-i", str(src), "-an", "-c:v", "copy", str(tmp)], f"strip audio {src.name}")
	tmp.rename(out)


def _concat_list(paths: list[Path], out: Path) -> None:
	out.write_text("".join(f"file '{p.resolve()}'\n" for p in paths))


# ---------------------------------------------------------------- silence

# Digital silence reports around -91 dB; real narration sits near -27 dB.
SILENCE_DB = -80.0

MEAN_VOLUME = re.compile(r"mean_volume:\s*(-?\d+(?:\.\d+)?) dB")


def parse_mean_volume(ffmpeg_stderr: str) -> float | None:
	"""Pull mean_volume out of ffmpeg's volumedetect output."""
	found = MEAN_VOLUME.search(ffmpeg_stderr)
	return float(found.group(1)) if found else None


def mean_volume(path: Path) -> float | None:
	result = subprocess.run(
		["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
		capture_output=True,
		text=True,
	)
	return parse_mean_volume(result.stderr)


def check_audible(path: Path, scene_id: str) -> None:
	"""Refuse to pass on audio that contains only silence.

	A silent track has a codec, a duration and a bitrate, so every structural
	check passes it. This is the one that does not.
	"""
	level = mean_volume(path)
	if level is None:
		raise StitchError(f"{scene_id}: could not measure audio in {path.name}")
	if level < SILENCE_DB:
		raise StitchError(f"{scene_id}: audio is silent ({level:.1f} dB)")


# ---------------------------------------------------------------- chapters


def chapter_metadata(spec: dict[str, Any], durations: dict[str, float]) -> str:
	"""An ffmpeg metadata file marking each scene as a chapter."""
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


# ---------------------------------------------------------------- assembly


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

	padded_dir = STORE / "padded"
	padded_dir.mkdir(parents=True, exist_ok=True)
	mute_dir = STORE / "mute"
	mute_dir.mkdir(parents=True, exist_ok=True)

	audio_parts: list[Path] = []
	video_parts: list[Path] = []
	durations: dict[str, float] = {}

	print(f"stitch: {len(scenes)} scene(s)")
	for scene in scenes:
		entry = manifest.data["scenes"][scene["id"]]
		source = speed.path_for(entry)
		target = frame_aligned(probe_duration(source))

		padded = padded_dir / f"{entry['speech_key']}.{FPS}.wav"
		if not padded.exists():
			pad_to(source, target, padded)
		check_audible(padded, scene["id"])

		muted = mute_dir / f"{entry['video_key']}.mp4"
		if not muted.exists():
			strip_audio(STORE / "video" / entry["video"], muted)

		audio_parts.append(padded)
		video_parts.append(muted)
		durations[scene["id"]] = target

	# The assembled file is content-addressed too, so an unchanged re-run copies
	# rather than re-encoding the whole narration.
	final_key = digest(
		[
			[e["speech_key"], e["video_key"]]
			for e in (manifest.data["scenes"][s["id"]] for s in scenes)
		]
	)
	assembled = STORE / "final" / f"{final_key}.mp4"
	assembled.parent.mkdir(parents=True, exist_ok=True)

	if not assembled.exists():
		audio_list = run_dir / "audio.txt"
		video_list = run_dir / "video.txt"
		_concat_list(audio_parts, audio_list)
		_concat_list(video_parts, video_list)

		track = run_dir / "narration.wav"
		_ffmpeg(
			["-f", "concat", "-safe", "0", "-i", str(audio_list), "-c", "copy", str(track)],
			"concat audio",
		)
		silent = run_dir / "silent.mp4"
		_ffmpeg(
			["-f", "concat", "-safe", "0", "-i", str(video_list), "-c", "copy", str(silent)],
			"concat video",
		)

		chapters = run_dir / "chapters.txt"
		chapters.write_text(chapter_metadata(spec, durations))

		tmp = assembled.with_name(f".{assembled.name}.partial.mp4")
		# One audio encode over the whole timeline: no per-segment priming to
		# accumulate. Streams are named explicitly because the rendered video
		# carries its own silent track.
		_ffmpeg(
			[
				"-i",
				str(silent),
				"-i",
				str(track),
				"-i",
				str(chapters),
				"-map",
				"0:v:0",
				"-map",
				"1:a:0",
				"-map_metadata",
				"2",
				"-c:v",
				"copy",
				"-c:a",
				"aac",
				"-b:a",
				"192k",
				"-movflags",
				"+faststart",
				str(tmp),
			],
			"assemble",
		)
		tmp.rename(assembled)
		track.unlink(missing_ok=True)
		silent.unlink(missing_ok=True)

	final = run_dir / "video.mp4"
	final.unlink(missing_ok=True)
	try:
		final.hardlink_to(assembled)
	except OSError:  # different filesystem
		shutil.copy(assembled, final)

	print(f"✓ stitch: {probe_duration(final):.0f}s, {len(scenes)} chapters -> {final.name}")

	from narratr.align import write_captions

	write_captions(spec, manifest, run_dir, durations=durations)
