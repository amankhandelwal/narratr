"""The coverage gate is the whole point, so test that it actually fails."""

from __future__ import annotations

import json
from pathlib import Path

from narratr.spec import summarise, validate
from narratr.state import audio_key, run_id_for, video_key

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "scenes.json"


def load() -> dict:
	return json.loads(EXAMPLE.read_text())


def test_example_is_valid():
	assert validate(load()) == []


def test_unmapped_block_is_rejected():
	spec = load()
	spec["source"]["block_ids"].append("orphan-block")
	problems = validate(spec)
	assert any("orphan-block" in p for p in problems)


def test_coverage_pointing_at_unknown_scene_is_rejected():
	spec = load()
	spec["coverage"]["intro-p1"] = "no-such-scene"
	problems = validate(spec)
	assert any("no-such-scene" in p for p in problems)


def test_schema_rejects_more_than_six_bullets():
	spec = load()
	spec["scenes"][0]["bullets"] = [f"b{i}" for i in range(7)]
	assert validate(spec)


def test_audio_key_changes_with_narration():
	spec = load()
	scene = spec["scenes"][0]
	before = audio_key(scene, spec)
	scene["narration"] += " One more sentence."
	assert audio_key(scene, spec) != before


def test_audio_key_changes_with_voice():
	spec = load()
	scene = spec["scenes"][0]
	before = audio_key(scene, spec)
	spec["voice"]["reference"] = "assets/voices/other.wav"
	assert audio_key(scene, spec) != before


def test_editing_the_picture_does_not_renarrate():
	"""A diagram edit must not invalidate audio that costs 100x more to make."""
	spec = load()
	scene = next(s for s in spec["scenes"] if s["type"] == "diagram")
	audio_before = audio_key(scene, spec)
	video_before = video_key(scene, spec)
	scene["mermaid"] = scene["mermaid"] + '\n    E --> F["extra"]'
	assert audio_key(scene, spec) == audio_before
	assert video_key(scene, spec) != video_before


def test_editing_bullets_invalidates_only_the_video():
	spec = load()
	scene = spec["scenes"][0]
	audio_before = audio_key(scene, spec)
	video_before = video_key(scene, spec)
	scene["bullets"] = ["something", "different"]
	assert audio_key(scene, spec) == audio_before
	assert video_key(scene, spec) != video_before


def test_editing_narration_invalidates_both():
	spec = load()
	scene = spec["scenes"][0]
	video_before = video_key(scene, spec)
	scene["narration"] += " Another sentence."
	assert video_key(scene, spec) != video_before


def test_run_id_is_stable():
	assert run_id_for(load()) == run_id_for(load())


def test_summarise_mentions_scene_count():
	assert "3 scenes" in summarise(load())
