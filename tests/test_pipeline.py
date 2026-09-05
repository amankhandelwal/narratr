"""The stage sequence and the rules about running part of it.

None of this was testable while it lived inside an argparse handler, and none
of it was tested. Two shipped bugs came from exactly that: the manifest was
never pruned when a scene left the spec, and `--only` printed a path that had
not existed since artifacts moved to store/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from narratr import pipeline
from narratr.state import Manifest

SPEC = {
	"version": 1,
	"source": {"title": "t", "block_ids": ["a-1"]},
	"coverage": {"a-1": "one"},
	"scenes": [
		{"id": "one", "type": "prose", "narration": "first"},
		{"id": "two", "type": "prose", "narration": "second"},
	],
}


def manifest_at(tmp_path: Path, spec=SPEC) -> Manifest:
	return Manifest.load_or_create(tmp_path, spec, "run")


def test_a_full_run_ends_in_stitch():
	assert [name for name, _ in pipeline.stages_for(None)][-1] == "stitch"


def test_a_restricted_run_stops_before_stitch():
	"""Stitching a subset would overwrite video.mp4 with a partial video."""
	names = [name for name, _ in pipeline.stages_for(["one"])]
	assert "stitch" not in names
	assert names == ["narrate", "speed", "align", "render"]


def test_stage_order_is_the_dependency_chain():
	assert [name for name, _ in pipeline.STAGES] == [
		"narrate",
		"speed",
		"align",
		"render",
		"stitch",
	]


def test_unknown_scene_ids_are_named():
	assert pipeline.unknown_scenes(SPEC, ["one", "ghost"]) == ["ghost"]
	assert pipeline.unknown_scenes(SPEC, ["one", "two"]) == []
	assert pipeline.unknown_scenes(SPEC, None) == []


def test_execute_runs_every_stage_in_order(tmp_path, monkeypatch):
	seen: list[str] = []
	monkeypatch.setattr(
		pipeline,
		"STAGES",
		tuple(
			(name, lambda spec, m, d, _n=name: seen.append(_n))
			for name in ("narrate", "speed", "align", "render", "stitch")
		),
	)
	pipeline.execute(SPEC, manifest_at(tmp_path), tmp_path)
	assert seen == ["narrate", "speed", "align", "render", "stitch"]


def test_execute_restricts_the_manifest_to_the_named_scenes(tmp_path, monkeypatch):
	pending: list[list[str]] = []
	monkeypatch.setattr(
		pipeline,
		"STAGES",
		(("narrate", lambda spec, m, d: pending.append(m.pending("audio"))),),
	)
	pipeline.execute(SPEC, manifest_at(tmp_path), tmp_path, only=["two"])
	assert pending == [["two"]]


# ---------------------------------------------------------------- manifest


def test_a_scene_removed_from_the_spec_is_pruned(tmp_path):
	"""pending() reads the manifest, not the spec. An entry left behind stayed
	queued forever and every stage died on by_id[scene_id] with a KeyError."""
	manifest_at(tmp_path)
	trimmed = {**SPEC, "scenes": [SPEC["scenes"][0]]}
	again = Manifest.load_or_create(tmp_path, trimmed, "run")
	assert sorted(again.data["scenes"]) == ["one"]
	assert again.pending("audio") == ["one"]


def test_pruning_keeps_the_scenes_that_remain(tmp_path):
	first = manifest_at(tmp_path)
	first.mark("one", "audio", "kept.wav")
	keys = dict(first.data["scenes"]["one"])
	trimmed = {**SPEC, "scenes": [SPEC["scenes"][0]]}
	again = Manifest.load_or_create(tmp_path, trimmed, "run")
	assert again.data["scenes"]["one"]["audio_key"] == keys["audio_key"]


def test_the_manifest_survives_a_round_trip(tmp_path):
	manifest_at(tmp_path).commit()
	on_disk = json.loads((tmp_path / "manifest.json").read_text())
	assert sorted(on_disk["scenes"]) == ["one", "two"]
	assert on_disk["title"] == "t"


HOSTILE = [
	"../../etc",
	"a/b",
	"..",
	".",
	"",
	"   ",
	"with\nnewline",
	"nul\x00byte",
	"C:\\Windows",
	"plain title",
	"." * 80,
]


@pytest.mark.parametrize("raw", HOSTILE)
def test_a_run_name_cannot_escape_the_runs_directory(raw):
	"""--run-name bypassed the sanitiser run_dir_name applies, so it could write
	outside runs/ -- and was forwarded verbatim to the detached child."""
	from narratr.paths import RUNS
	from narratr.state import safe_name

	name = safe_name(raw)
	assert name, f"{raw!r} produced an empty name"
	assert "/" not in name and "\\" not in name
	assert name not in {".", ".."}
	# The property that actually matters: it stays one level under runs/.
	assert (RUNS / name).resolve().parent == RUNS.resolve()


def test_a_readable_title_is_left_alone():
	from narratr.state import safe_name

	assert safe_name("narratr in brief") == "narratr in brief"
	assert safe_name("with\nnewline") == "with newline"
