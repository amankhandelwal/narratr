"""A silent video shipped once. This is the check that would have caught it."""

from __future__ import annotations

from pathlib import Path

import pytest

from narratr.stitch import SILENCE_DB, StitchError, check_audible, parse_mean_volume

REAL = "[Parsed_volumedetect_0 @ 0x7f8] mean_volume: -27.1 dB\nmax_volume: -2.3 dB"
SILENT = "[Parsed_volumedetect_0 @ 0x7f8] mean_volume: -91.0 dB\nmax_volume: -91.0 dB"


def test_parses_narration_level():
	assert parse_mean_volume(REAL) == -27.1


def test_parses_digital_silence():
	assert parse_mean_volume(SILENT) == -91.0


def test_returns_none_when_ffmpeg_said_nothing():
	assert parse_mean_volume("some unrelated ffmpeg output") is None


def test_threshold_separates_the_two_cases():
	# Both real values sit far from the threshold, so it needs no tuning.
	assert parse_mean_volume(SILENT) < SILENCE_DB < parse_mean_volume(REAL)


def test_check_raises_on_silence(monkeypatch):
	monkeypatch.setattr("narratr.stitch.mean_volume", lambda _: -91.0)
	with pytest.raises(StitchError, match="silent"):
		check_audible(Path("scene.mp4"), "the-flow")


def test_check_passes_on_real_audio(monkeypatch):
	monkeypatch.setattr("narratr.stitch.mean_volume", lambda _: -27.1)
	check_audible(Path("scene.mp4"), "the-flow")


def test_check_raises_when_unmeasurable(monkeypatch):
	monkeypatch.setattr("narratr.stitch.mean_volume", lambda _: None)
	with pytest.raises(StitchError, match="could not measure"):
		check_audible(Path("scene.mp4"), "the-flow")
