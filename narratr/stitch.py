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

The ffmpeg primitives live in `narratr/media.py` and chapter generation in
`narratr/chapters.py`; what is left here is assembly.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from narratr import chapters, speed
from narratr import intro as title_card
from narratr.align import write_captions
from narratr.media import (
	FPS,
	MediaError,
	check_audible,
	concat_list,
	ffmpeg,
	frame_aligned,
	pad_to,
	probe_duration,
	strip_audio,
)
from narratr.paths import STORE
from narratr.state import Manifest, digest

__all__ = ["FPS", "StitchError", "preview", "run"]


class StitchError(MediaError):
	"""Assembly cannot proceed."""


def _measured(padded: Path, scene_id: str) -> float:
	"""Silence check plus duration, recorded beside the padded file.

	`volumedetect` decodes the whole clip, and it ran on every stitch even when
	the padded audio was already cached. The measurement cannot change once the
	bytes are fixed, so it is cached with them.
	"""
	sidecar = padded.with_suffix(".db")
	if not sidecar.exists():
		check_audible(padded, scene_id)
		sidecar.write_text("ok")
	return probe_duration(padded)


def preview(manifest: Manifest, scene_id: str, run_dir: Path) -> Path | None:
	"""Mux one scene's picture with its own narration, for --only.

	The rendered scene mp4 carries Remotion's silent track, so the artifact
	--only pointed at could not be listened to -- against a working agreement
	that says to look at the artifact rather than the exit code.

	Kept in its own directory. A scene id is `^[a-z0-9_-]+$`, so `video` is a
	legal one and `<scene_id>.mp4` in the run root would have overwritten the
	finished video with a single scene. It also keeps an iteration artifact out
	of the directory holding the deliverable.
	"""
	entry = manifest.data["scenes"].get(scene_id, {})
	if not (entry.get("video") and entry.get("speech")):
		return None
	preview_dir = run_dir / "preview"
	preview_dir.mkdir(parents=True, exist_ok=True)
	out = preview_dir / f"{scene_id}.mp4"
	tmp = out.with_name(f".{out.name}.partial.mp4")
	try:
		ffmpeg(
			[
				"-i",
				str(STORE / "video" / entry["video"]),
				"-i",
				str(speed.path_for(entry)),
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
				str(tmp),
			],
			f"preview {scene_id}",
		)
		tmp.rename(out)
	finally:
		tmp.unlink(missing_ok=True)
	return out


def run(spec: dict[str, Any], manifest: Manifest, run_dir: Path) -> None:
	scenes = spec["scenes"]
	incomplete = [
		s["id"]
		for s in scenes
		if not all(manifest.data["scenes"][s["id"]].get(k) for k in ("video", "audio", "aligned"))
	]
	if incomplete:
		# `aligned` is checked too: without it a scene contributes no cues and
		# the captions for everything after it used to shift early.
		raise StitchError(f"not ready: {', '.join(incomplete[:3])} missing audio, video or timings")

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
		_measured(padded, scene["id"])

		muted = mute_dir / f"{entry['video_key']}.mp4"
		if not muted.exists():
			strip_audio(STORE / "video" / entry["video"], muted)

		audio_parts.append(padded)
		video_parts.append(muted)
		durations[scene["id"]] = target

	# Built after the scenes so its audio can be matched to theirs: the concat
	# demuxer copies streams and will not join a card at a different rate.
	intro_video, intro_audio, intro_duration = title_card.build(
		spec["source"]["title"], reference=audio_parts[0]
	)
	check_audible(intro_audio, "intro")
	audio_parts.insert(0, intro_audio)
	video_parts.insert(0, intro_video)
	print(f"  intro: {intro_duration:.1f}s title card")

	# The assembled file is content-addressed too, so an unchanged re-run copies
	# rather than re-encoding the whole narration. Scene ids and headings are in
	# the key because they name the chapters: renaming a scene with no heading
	# changed the chapter titles but no per-scene key, so the cached mp4 shipped
	# with the old ones.
	final_key = digest(
		[
			[s["id"], s.get("heading"), e["speech_key"], e["video_key"]]
			for s, e in ((s, manifest.data["scenes"][s["id"]]) for s in scenes)
		]
		+ [intro_video.stem, spec["source"]["title"]]
	)
	assembled = STORE / "final" / f"{final_key}.mp4"
	assembled.parent.mkdir(parents=True, exist_ok=True)

	# Written whatever happens, so a cached assembly still leaves a run
	# directory that describes itself.
	chapter_file = run_dir / "chapters.txt"
	chapter_file.write_text(chapters.metadata(spec, durations, intro=intro_duration))

	if not assembled.exists():
		# Scratch, not output: these are ffmpeg inputs and full uncompressed
		# intermediates. They used to sit in the run directory the user browses.
		scratch = STORE / "tmp"
		scratch.mkdir(parents=True, exist_ok=True)
		audio_list = scratch / f"{final_key}.audio.txt"
		video_list = scratch / f"{final_key}.video.txt"
		concat_list(audio_parts, audio_list)
		concat_list(video_parts, video_list)

		track = scratch / f"{final_key}.narration.wav"
		silent = scratch / f"{final_key}.silent.mp4"
		tmp = assembled.with_name(f".{assembled.name}.partial.mp4")
		try:
			ffmpeg(
				["-f", "concat", "-safe", "0", "-i", str(audio_list), "-c", "copy", str(track)],
				"concat audio",
			)
			ffmpeg(
				["-f", "concat", "-safe", "0", "-i", str(video_list), "-c", "copy", str(silent)],
				"concat video",
			)
			# One audio encode over the whole timeline: no per-segment priming to
			# accumulate. Streams are named explicitly because the rendered video
			# carries its own silent track.
			ffmpeg(
				[
					"-i",
					str(silent),
					"-i",
					str(track),
					"-i",
					str(chapter_file),
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
		finally:
			for scratch_file in (track, silent, audio_list, video_list, tmp):
				scratch_file.unlink(missing_ok=True)

	final = run_dir / "video.mp4"
	final.unlink(missing_ok=True)
	try:
		final.hardlink_to(assembled)
	except OSError:  # different filesystem
		shutil.copy(assembled, final)

	print(f"✓ stitch: {probe_duration(final):.0f}s, {len(scenes) + 1} chapters -> {final.name}")

	write_captions(spec, manifest, run_dir, durations=durations, offset=intro_duration)
