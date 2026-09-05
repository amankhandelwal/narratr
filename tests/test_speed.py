"""Tempo is keyed apart from narration so trying a speed is cheap."""

from __future__ import annotations

import pytest

from narratr.speed import MAX_TEMPO, MIN_TEMPO, SpeedError, tempo_chain
from narratr.state import audio_key, speech_key, video_key

SPEC = {
	"voice": {"reference": "v.wav", "seed": 7},
	"scenes": [{"id": "s", "type": "prose", "narration": "hello there", "bullets": ["a"]}],
}


def scene():
	return SPEC["scenes"][0]


def at(speed):
	return {**SPEC, "voice": {**SPEC["voice"], "speed": speed}}


def test_speed_does_not_invalidate_narration():
	"""The whole point: narration costs ~100x what a resample does."""
	assert audio_key(scene(), at(0.92)) == audio_key(scene(), at(1.0))


def test_speed_does_invalidate_the_shipping_audio():
	assert speech_key(scene(), at(0.92)) != speech_key(scene(), at(1.0))


def test_speed_invalidates_the_video():
	"""Scene length comes from the sped audio, so the picture must follow."""
	assert video_key(scene(), at(0.92)) != video_key(scene(), at(1.0))


def test_default_speed_matches_an_explicit_one():
	assert speech_key(scene(), SPEC) == speech_key(scene(), at(1.0))


def test_single_filter_inside_the_valid_range():
	assert tempo_chain(0.92) == "atempo=0.920000"
	assert tempo_chain(MIN_TEMPO).count("atempo") == 1
	assert tempo_chain(MAX_TEMPO).count("atempo") == 1


def test_chains_beyond_the_valid_range():
	# atempo is undefined outside 0.5-2.0, so extremes must split, not clamp.
	assert tempo_chain(0.25).count("atempo") == 2
	assert tempo_chain(3.0).count("atempo") == 2


def test_chain_multiplies_back_to_the_requested_speed():
	import re

	for speed in (0.25, 0.4, 0.92, 1.0, 1.5, 3.0):
		factors = [float(f) for f in re.findall(r"atempo=([0-9.]+)", tempo_chain(speed))]
		product = 1.0
		for f in factors:
			product *= f
		assert abs(product - speed) < 1e-4


def test_zero_or_negative_is_rejected():
	for bad in (0, -1):
		with pytest.raises(SpeedError):
			tempo_chain(bad)
