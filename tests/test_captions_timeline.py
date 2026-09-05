"""Captions must follow the video's timeline, not the raw audio's.

Frame rounding shifts each scene slightly. Over dozens of scenes that drift
would be visible against the subtitles, so stitch re-derives them from the
measured segment durations.
"""

from __future__ import annotations

import json
from pathlib import Path

from narratr.align import write_captions
from narratr.state import Manifest


def _fixture(tmp_path: Path, monkeypatch):
	# Timings live in the shared store, not under the run directory.
	monkeypatch.setattr("narratr.align.STORE", tmp_path)
	spec = {
		"scenes": [
			{"id": "one", "type": "prose", "narration": "a"},
			{"id": "two", "type": "prose", "narration": "b"},
		]
	}
	timings = tmp_path / "timings"
	timings.mkdir(exist_ok=True)
	for name in ("one", "two"):
		(timings / f"{name}.k.json").write_text(
			json.dumps(
				{
					"duration": 10.0,
					"words": [{"word": name, "start": 0.0, "end": 1.0, "score": 1.0}],
				}
			)
		)
	manifest = Manifest(
		tmp_path / "m.json",
		{
			"scenes": {
				"one": {"audio_key": "k", "aligned": "one.k.json"},
				"two": {"audio_key": "k", "aligned": "two.k.json"},
			}
		},
	)
	return spec, manifest


def test_second_scene_is_offset_by_the_first(tmp_path, monkeypatch):
	spec, manifest = _fixture(tmp_path, monkeypatch)
	write_captions(spec, manifest, tmp_path)
	srt = (tmp_path / "captions.srt").read_text()
	assert "00:00:10,000 --> 00:00:11,000" in srt


def test_measured_durations_override_audio_length(tmp_path, monkeypatch):
	spec, manifest = _fixture(tmp_path, monkeypatch)
	write_captions(spec, manifest, tmp_path, durations={"one": 10.5, "two": 10.5})
	srt = (tmp_path / "captions.srt").read_text()
	assert "00:00:10,500 --> 00:00:11,500" in srt
	assert "00:00:10,000 --> 00:00:11,000" not in srt
