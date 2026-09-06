"""Captions ship inside the mp4.

QuickTime cannot load a sidecar .srt, so a run whose subtitles live only beside
the video has no subtitles as far as the player is concerned.
"""

from __future__ import annotations

import pytest

from narratr.media import MediaError
from narratr.stitch import _deliver, caption_args


@pytest.fixture
def parts(tmp_path):
	assembled = tmp_path / "assembled.mp4"
	assembled.write_bytes(b"mp4")
	captions = tmp_path / "captions.srt"
	captions.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n")
	return assembled, captions, tmp_path / "video.mp4"


def test_subtitle_track_is_mov_text(parts):
	args = caption_args(*parts)
	assert args[args.index("-c:s") + 1] == "mov_text"


def test_video_and_audio_are_stream_copied(parts):
	args = caption_args(*parts)
	assert args[args.index("-c:v") + 1] == "copy"
	assert args[args.index("-c:a") + 1] == "copy"


def test_streams_are_mapped_explicitly(parts):
	# A bare -map 0 hands the assembly's data stream to the subtitle encoder.
	args = caption_args(*parts)
	assert [args[i + 1] for i, a in enumerate(args) if a == "-map"] == ["0:v:0", "0:a:0", "1:0"]


def test_chapters_survive(parts):
	args = caption_args(*parts)
	assert args[args.index("-map_chapters") + 1] == "0"


def test_delivers_with_captions(parts, monkeypatch):
	assembled, captions, final = parts
	seen = {}

	def fake(args, label):
		seen["label"] = label
		# ffmpeg writes the temp file the caller then renames.
		next(p for p in map(str, args) if p.endswith(".partial.mp4"))
		final.with_name(f".{final.name}.partial.mp4").write_bytes(b"muxed")

	monkeypatch.setattr("narratr.stitch.ffmpeg", fake)
	assert _deliver(assembled, captions, final) is True
	assert final.read_bytes() == b"muxed"
	assert seen["label"] == "mux captions"


def test_empty_captions_still_ship_a_video(parts, monkeypatch):
	assembled, captions, final = parts
	captions.write_text("   \n")
	monkeypatch.setattr(
		"narratr.stitch.ffmpeg",
		lambda *a, **k: pytest.fail("must not mux an empty srt"),
	)
	assert _deliver(assembled, captions, final) is False
	assert final.read_bytes() == b"mp4"


def test_missing_captions_still_ship_a_video(parts, monkeypatch):
	assembled, captions, final = parts
	captions.unlink()
	monkeypatch.setattr(
		"narratr.stitch.ffmpeg",
		lambda *a, **k: pytest.fail("must not mux a missing srt"),
	)
	assert _deliver(assembled, captions, final) is False
	assert final.read_bytes() == b"mp4"


def test_failed_mux_leaves_no_partial(parts, monkeypatch):
	assembled, captions, final = parts

	def boom(args, label):
		final.with_name(f".{final.name}.partial.mp4").write_bytes(b"junk")
		raise MediaError("ffmpeg said no")

	monkeypatch.setattr("narratr.stitch.ffmpeg", boom)
	with pytest.raises(MediaError):
		_deliver(assembled, captions, final)
	assert not final.with_name(f".{final.name}.partial.mp4").exists()


def test_stale_output_is_replaced(parts, monkeypatch):
	assembled, captions, final = parts
	final.write_bytes(b"an older render")
	monkeypatch.setattr(
		"narratr.stitch.ffmpeg",
		lambda args, label: final.with_name(f".{final.name}.partial.mp4").write_bytes(b"muxed"),
	)
	_deliver(assembled, captions, final)
	assert final.read_bytes() == b"muxed"
