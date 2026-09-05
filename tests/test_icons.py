"""Icon names are Claude's to invent, so they are checked before compute."""

from __future__ import annotations

import pytest

from narratr import icons
from narratr.spec import validate


@pytest.fixture(autouse=True)
def _pack(monkeypatch):
	"""A small stand-in pack, so tests do not depend on node_modules."""
	monkeypatch.setattr(icons, "available", lambda: frozenset({"file-text", "mic", "laptop"}))


def scene(**overrides):
	base = {"id": "one", "type": "prose", "narration": "n"}
	return {**base, **overrides}


def spec_with(*scenes):
	return {
		"version": 1,
		"source": {"title": "t", "block_ids": ["b1"]},
		"coverage": {"b1": "one"},
		"scenes": list(scenes),
	}


# ---------------------------------------------------------------- collecting


def test_finds_icons_on_bullets():
	found = icons.names_in(scene(bullets=["plain", {"text": "x", "icon": "mic"}]))
	assert found == ["mic"]


def test_finds_icons_on_flow_steps_and_footer():
	found = icons.names_in(
		scene(
			type="flow",
			steps=[{"icon": "file-text", "label": "Doc"}],
			footer={"icon": "laptop", "label": "Local"},
		)
	)
	assert found == ["file-text", "laptop"]


def test_finds_icons_on_cards():
	found = icons.names_in(scene(type="cards", cards=[{"icon": "mic", "title": "T"}]))
	assert found == ["mic"]


def test_a_bullet_without_an_icon_contributes_nothing():
	assert icons.names_in(scene(bullets=["just text"])) == []


# ---------------------------------------------------------------- validation


def test_a_known_icon_passes():
	assert icons.problems(spec_with(scene(bullets=[{"text": "x", "icon": "mic"}]))) == []


def test_an_unknown_icon_is_rejected():
	problems = icons.problems(spec_with(scene(bullets=[{"text": "x", "icon": "microphone"}])))
	assert len(problems) == 1
	assert "microphone" in problems[0]
	assert "one" in problems[0]


def test_the_rejection_suggests_a_near_miss():
	problems = icons.problems(spec_with(scene(bullets=[{"text": "x", "icon": "laptopp"}])))
	assert "did you mean" in problems[0]
	assert "laptop" in problems[0]


def test_a_missing_pack_reports_itself_once(monkeypatch):
	"""Not as two thousand unknown icon names."""
	monkeypatch.setattr(icons, "available", lambda: frozenset())
	problems = icons.problems(spec_with(scene(bullets=[{"text": "x", "icon": "mic"}])))
	assert len(problems) == 1
	assert "not installed" in problems[0]


def test_a_spec_with_no_icons_never_touches_the_pack(monkeypatch):
	def boom():
		raise AssertionError("should not have been consulted")

	monkeypatch.setattr(icons, "available", boom)
	assert icons.problems(spec_with(scene(bullets=["plain"]))) == []


def test_validate_reports_bad_icons_alongside_coverage():
	problems = validate(spec_with(scene(bullets=[{"text": "x", "icon": "nope"}])))
	assert any("nope" in p for p in problems)


# ---------------------------------------------------------------- markup


def test_markup_strips_the_licence_comment_and_keeps_currentcolor():
	if not icons.ICONS.is_dir():
		pytest.skip("icon pack not installed")
	svg = icons.markup("file-text")
	assert svg.startswith("<svg")
	assert "currentColor" in svg


def test_an_unknown_name_raises_rather_than_returning_nothing():
	with pytest.raises(icons.IconError, match="no such icon"):
		icons.markup("definitely-not-an-icon")
