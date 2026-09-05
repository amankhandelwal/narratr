"""Restricting a run must not lose track of the scenes it skipped."""

from __future__ import annotations

from pathlib import Path

from narratr.state import Manifest


def manifest() -> Manifest:
	return Manifest(
		Path("/tmp/unused.json"),
		{
			"scenes": {
				"one": {"audio_key": "k", "audio": None},
				"two": {"audio_key": "k", "audio": None},
				"three": {"audio_key": "k", "audio": "three.wav"},
			}
		},
	)


def test_unrestricted_lists_every_pending_scene():
	assert manifest().pending("audio") == ["one", "two"]


def test_restriction_narrows_to_the_named_scene():
	m = manifest()
	m.restrict(["two"])
	assert m.pending("audio") == ["two"]


def test_restriction_still_skips_completed_work():
	m = manifest()
	m.restrict(["three"])
	assert m.pending("audio") == []


def test_restriction_ignores_stages_already_done():
	m = manifest()
	m.restrict(["one", "three"])
	assert m.pending("audio") == ["one"]


def test_empty_restriction_means_no_restriction():
	# argparse gives None when --only is absent; [] should behave the same.
	for value in (None, []):
		m = manifest()
		m.restrict(value)
		assert m.pending("audio") == ["one", "two"]


def test_manifest_still_holds_every_scene_when_restricted():
	m = manifest()
	m.restrict(["one"])
	assert set(m.data["scenes"]) == {"one", "two", "three"}
