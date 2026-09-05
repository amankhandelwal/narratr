"""Audio and video must be the same length per scene, or drift creeps back.

The renderer rounds a scene to whole frames. Padding the audio to that same
length is what makes the offset exactly zero instead of a per-scene coin flip
that a stream copy then bakes in.
"""

from __future__ import annotations

from narratr.stitch import FPS, chapter_metadata, frame_aligned


def test_aligns_to_the_frame_grid():
	assert frame_aligned(11.400) == 342 / FPS
	assert frame_aligned(1.0) == 1.0


def test_rounds_to_nearest_not_down():
	# 0.9 of a frame past a whole second rounds up to the next frame.
	assert round(frame_aligned(1.0 + 0.9 / FPS) * FPS) == FPS + 1
	# 0.4 of a frame rounds back down.
	assert round(frame_aligned(1.0 + 0.4 / FPS) * FPS) == FPS


def test_never_returns_a_zero_length_scene():
	# Remotion clamps to one frame; a zero-frame composition cannot render.
	assert frame_aligned(0.0) == 1 / FPS
	assert frame_aligned(0.001) == 1 / FPS


def test_result_is_always_a_whole_number_of_frames():
	for seconds in (0.017, 1.234, 11.4, 13.919, 60.0):
		assert abs(frame_aligned(seconds) * FPS - round(frame_aligned(seconds) * FPS)) < 1e-9


def test_chapters_use_the_aligned_durations():
	spec = {"scenes": [{"id": "a", "heading": "A"}, {"id": "b", "heading": "B"}]}
	body = chapter_metadata(spec, {"a": frame_aligned(11.4), "b": frame_aligned(5.0)})
	assert "START=0" in body
	assert "START=11400" in body


def test_video_is_muted_before_concat(monkeypatch):
	"""The renderer writes a silent AAC track into every scene. Its encoder
	padding makes the container ~50ms longer than the picture, and concat
	advances by container duration -- so the picture drifted late, ~57ms per
	join. Stripping the track is what makes the boundaries exact."""
	from pathlib import Path

	from narratr import stitch

	captured: list[list[str]] = []
	monkeypatch.setattr(stitch, "ffmpeg", lambda args, what: captured.append(args))
	monkeypatch.setattr(Path, "rename", lambda self, target: None)

	stitch.strip_audio(Path("in.mp4"), Path("out.mp4"))

	assert "-an" in captured[0]
	assert "copy" in captured[0]
