"""The presentation skill's own example is what Claude copies for a deck."""

from __future__ import annotations

import json

from pptx import Presentation

from narratr.deck.build import build, is_section
from narratr.paths import ROOT
from narratr.spec import validate

SKILL = ROOT / "skills" / "presentation"
EXAMPLE = SKILL / "example.scenes.json"


def test_the_guide_is_shared_not_copied():
	guide = SKILL / "shapes.md"
	assert guide.is_symlink()
	assert guide.resolve() == (ROOT / "skills" / "narratr" / "shapes.md").resolve()


def test_the_example_validates_with_its_images():
	spec = json.loads(EXAMPLE.read_text())
	assert validate(spec, base=SKILL) == []


def test_the_example_shows_a_theme_a_divider_and_both_image_uses():
	spec = json.loads(EXAMPLE.read_text())
	assert spec.get("theme")
	assert any(is_section(s) for s in spec["scenes"])
	assert any(s["type"] == "image" for s in spec["scenes"])
	assert any(s["type"] == "prose" and s.get("image") for s in spec["scenes"])


def test_the_example_builds(tmp_path):
	spec = json.loads(EXAMPLE.read_text())
	deck, doc = build(spec, SKILL, tmp_path)
	assert len(Presentation(str(deck)).slides) == len(spec["scenes"])
	assert doc.read_text().startswith(f"# {spec['source']['title']}\n")


def test_the_skill_sends_the_reader_to_the_guide_and_example():
	body = (SKILL / "SKILL.md").read_text()
	assert "shapes.md" in body
	assert "example.scenes.json" in body
	assert "narratr deck" in body
