"""The presenter's script: the narration, with a marker wherever to click."""

from __future__ import annotations

import json

import pytest

from narratr.deck import script
from narratr.paths import ROOT

SPECS = [
	ROOT / "examples" / "brief.scenes.json",
	ROOT / "examples" / "code.scenes.json",
	ROOT / "skills" / "narratr" / "example.scenes.json",
]
SCENES = [
	pytest.param(scene, id=f"{path.stem}:{scene['id']}")
	for path in SPECS
	for scene in json.loads(path.read_text())["scenes"]
]
MARK = script.MARKER + " "


@pytest.mark.parametrize("scene", SCENES)
def test_one_marker_per_reveal(scene):
	assert script.marked(scene).count(script.MARKER) == len(script.reveals(scene))


@pytest.mark.parametrize("scene", SCENES)
def test_removing_the_markers_gives_back_the_narration(scene):
	assert script.marked(scene).replace(MARK, "") == scene["narration"]


@pytest.mark.parametrize("scene", SCENES)
def test_each_marker_sits_right_before_its_cue(scene):
	text = script.marked(scene)
	for cue in script.reveals(scene):
		assert MARK + cue.split()[0] in text


def test_a_sequence_diagram_has_no_clicks():
	scene = {
		"id": "s",
		"type": "diagram",
		"mermaid": "sequenceDiagram\n A->>B: hi",
		"revealSteps": [["A"]],
		"revealCues": ["hello"],
		"narration": "hello there",
	}
	assert script.reveals(scene) == []
	assert script.marked(scene) == "hello there"


def test_two_cues_on_one_word_get_two_markers():
	scene = {
		"id": "s",
		"type": "prose",
		"bullets": [{"text": "a", "cue": "start here"}, {"text": "b", "cue": "start here now"}],
		"narration": "We start here now.",
	}
	assert script.marked(scene) == f"We {MARK}{MARK}start here now."


def test_document_has_a_section_per_slide_with_its_click_count():
	spec = json.loads(SPECS[0].read_text())
	doc = script.document(spec)
	assert doc.startswith(f"# {spec['source']['title']}\n")
	for number, scene in enumerate(spec["scenes"], 1):
		clicks = len(script.reveals(scene))
		assert f"## {number}. " in doc
		assert script.marked(scene) in doc
		if clicks:
			assert f"*{clicks} click{'s' if clicks != 1 else ''}*" in doc
