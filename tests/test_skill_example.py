"""The spec bundled with the skill is what Claude copies. It must not go stale.

`skill/example.scenes.json` travels with the skill directory, so a session
loading the skill from `~/.claude/skills/narratr` reads it without knowing where
the checkout lives. That makes it the most-copied file in the project and the
one most worth pinning: a reference that quietly stops matching the schema
teaches the wrong shape to every future video.
"""

from __future__ import annotations

import json

import pytest

from narratr.paths import ROOT
from narratr.spec import validate

EXAMPLE = ROOT / "skill" / "example.scenes.json"
GUIDE = ROOT / "skill" / "presentation.md"


@pytest.fixture(scope="module")
def spec() -> dict:
	return json.loads(EXAMPLE.read_text())


def test_the_skill_carries_its_own_example():
	assert EXAMPLE.is_file(), EXAMPLE


def test_it_validates_exactly_as_a_real_spec_would(spec):
	"""Schema, coverage ledger and every icon name."""
	assert validate(spec) == []


def test_it_uses_every_scene_shape(spec):
	"""A reference that omits a shape is how a shape stops being used."""
	shapes = {scene["type"] for scene in spec["scenes"]}
	assert shapes == {"prose", "flow", "cards", "diagram", "code"}


def test_it_demonstrates_the_struck_state(spec):
	struck = [
		bullet
		for scene in spec["scenes"]
		for bullet in scene.get("bullets", [])
		if isinstance(bullet, dict) and bullet.get("state") == "struck"
	]
	assert struck, "nothing shows how to reject an approach"


def test_its_bullets_are_objects_with_icons_not_bare_strings(spec):
	"""Icons are the default; the example must not teach the old style."""
	bullets = [b for scene in spec["scenes"] for b in scene.get("bullets", [])]
	assert bullets
	assert all(isinstance(b, dict) and b.get("icon") for b in bullets)


def test_its_diagram_nodes_carry_icons(spec):
	from narratr.icons import mermaid_names_in

	diagrams = [s for s in spec["scenes"] if s["type"] == "diagram"]
	assert diagrams
	for scene in diagrams:
		assert mermaid_names_in(scene), f"{scene['id']} has no node icons"


def test_the_diagram_actually_branches(spec):
	"""Otherwise it is a flow, and the example would contradict the guide."""
	scene = next(s for s in spec["scenes"] if s["type"] == "diagram")
	sources = [
		line.split("-->")[0].strip() for line in scene["mermaid"].splitlines() if "-->" in line
	]
	assert len(sources) != len(set(sources)), "no node fans out; this is a straight line"


def test_the_guide_travels_with_the_skill():
	assert GUIDE.is_file(), GUIDE


def test_the_skill_sends_the_reader_to_both():
	body = (ROOT / "skill" / "SKILL.md").read_text()
	assert "presentation.md" in body
	assert "example.scenes.json" in body
