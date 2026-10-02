"""The coverage gate is the whole point, so test that it actually fails."""

from __future__ import annotations

import json
from pathlib import Path

from narratr.spec import summarise, validate
from narratr.state import audio_key, run_dir_name, video_key

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "brief.scenes.json"


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


def test_run_dir_name_reads_like_a_folder_a_person_named():
	"""The format is the subject, so the title is stated here rather than
	borrowed from whichever example happens to be bundled."""
	from datetime import datetime

	spec = {"source": {"title": "Audio-first video generation"}}
	name = run_dir_name(spec, datetime(2026, 9, 5, 13, 22))
	assert name == "Audio-first video generation [05-09 01.22 PM]"


def test_run_dir_name_never_contains_a_path_separator():
	"""A slash is a path separator: mkdir would silently nest the directory
	instead of failing, which is how this was nearly shipped."""
	spec = {"source": {"title": "reports/2026: draft"}}
	assert "/" not in run_dir_name(spec)
	assert ":" not in run_dir_name(spec).split("[")[0]


def test_run_dir_name_falls_back_when_the_title_is_empty():
	assert run_dir_name({"source": {"title": "   "}}).startswith("untitled [")


def test_summarise_mentions_scene_count():
	spec = load()
	assert f"{len(spec['scenes'])} scenes" in summarise(spec)


def test_renderer_source_is_part_of_the_video_key(monkeypatch, tmp_path):
	"""Changing a colour or a layout must invalidate cached videos.

	Without this the pipeline reports "nothing to do" and ships the old look —
	which happened, and cost a confusing debugging round.
	"""
	from narratr import state

	spec = load()
	scene = spec["scenes"][0]
	before = state.video_key(scene, spec)

	monkeypatch.setattr(state, "RENDERER_SOURCES", ())
	state.renderer_digest.cache_clear()
	after = state.video_key(scene, spec)
	state.renderer_digest.cache_clear()

	assert before != after
