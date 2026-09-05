"""The title card: its length, its key, and what it refuses to build without."""

from __future__ import annotations

from pathlib import Path

import pytest

from narratr import intro


def test_length_is_a_whole_number_of_frames(monkeypatch):
	# The sting is 4.101219s; the card must be what the renderer can produce.
	monkeypatch.setattr(intro.stitch, "probe_duration", lambda path: 4.101219)
	# Exactly 123 frames: not 4.1s, which is not a frame boundary at all.
	assert intro.duration() == 123 / 30


def test_the_assets_it_needs_are_in_the_repo():
	assert intro.MUSIC.exists(), intro.MUSIC
	assert intro.MARK.exists(), intro.MARK


def test_the_title_is_part_of_the_key():
	assert intro.key("one", 24000, 1) != intro.key("two", 24000, 1)


def test_the_audio_layout_is_part_of_the_key():
	"""A card built for 24 kHz mono cannot be concatenated onto 48 kHz stereo."""
	assert intro.key("t", 24000, 1) != intro.key("t", 48000, 1)
	assert intro.key("t", 24000, 1) != intro.key("t", 24000, 2)


def test_the_key_is_stable_for_the_same_inputs():
	assert intro.key("t", 24000, 1) == intro.key("t", 24000, 1)


def test_a_missing_asset_is_named(monkeypatch, tmp_path):
	monkeypatch.setattr(intro, "MUSIC", intro.ROOT / "assets" / "nope.mp3")
	with pytest.raises(intro.IntroError, match=r"nope\.mp3"):
		intro.build("t", reference=tmp_path / "any.wav")


def test_the_sting_is_attenuated():
	"""It peaks at -0.1 dB against narration near -27 dB. Straight in, it shouts."""
	assert intro.GAIN_DB < 0


def test_layout_is_read_from_the_reference(monkeypatch):
	monkeypatch.setattr(
		intro.subprocess,
		"run",
		lambda *a, **k: type("R", (), {"stdout": "24000,1\n"})(),
	)
	assert intro.audio_layout(Path("whatever.wav")) == (24000, 1)
