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


# ---------------------------------------------------------------- mermaid


def test_finds_icons_inside_mermaid_source():
	scene = {
		"id": "d",
		"type": "diagram",
		"mermaid": 'flowchart LR\n A@{ icon: "lucide:mic", label: "x" }\n'
		' B@{ icon: "lucide:laptop", label: "y" }',
	}
	assert icons.mermaid_names_in(scene) == ["mic", "laptop"]


def test_a_diagram_without_icons_contributes_nothing():
	assert icons.mermaid_names_in({"mermaid": "flowchart LR\n A --> B"}) == []
	assert icons.mermaid_names_in({}) == []


def test_a_bad_diagram_icon_name_is_rejected():
	scene = {
		"id": "d",
		"type": "diagram",
		"narration": "n",
		"mermaid": 'flowchart LR\n A@{ icon: "lucide:microphone", label: "x" }',
	}
	problems = icons.problems(spec_with(scene))
	assert len(problems) == 1
	assert "microphone" in problems[0]


def test_component_icons_are_kept_apart_from_diagram_icons():
	"""Diagram icons are baked into the SVG; they must not be inlined as props."""
	scene = {
		"id": "d",
		"mermaid": 'A@{ icon: "lucide:mic" }',
		"bullets": [{"text": "x", "icon": "laptop"}],
	}
	assert icons.names_in(scene) == ["laptop"]
	assert icons.mermaid_names_in(scene) == ["mic"]


# ---------------------------------------------------------------- inlining


def _real_pack_only():
	if not icons.ICONS.is_dir():
		pytest.skip("icon pack not installed")


def test_inline_markup_carries_no_double_quotes():
	"""A double quote would end the Mermaid label it is embedded in."""
	_real_pack_only()
	assert '"' not in icons.inline_markup("file-text")


def test_inline_markup_keeps_currentcolor_so_the_beat_can_tint_it():
	_real_pack_only()
	assert "currentColor" in icons.inline_markup("file-text")


def test_inline_markup_is_sized_in_em_not_pixels():
	_real_pack_only()
	out = icons.inline_markup("file-text")
	assert "width='1.15em'" in out and "height='1.15em'" in out
	assert "width='24'" not in out


def test_an_icon_node_becomes_a_box_with_the_glyph_in_its_label():
	_real_pack_only()
	from narratr.render import inline_mermaid_icons

	out = inline_mermaid_icons('A@{ icon: "lucide:file-text", form: "square", label: "doc.md" }')
	assert out.startswith('A["')
	assert "narratr-icon" in out
	assert out.rstrip().endswith('doc.md"]')
	# Mermaid's own icon syntax must be gone, or it renders a bare glyph.
	assert "@{" not in out


def test_a_node_without_a_label_falls_back_to_its_id():
	_real_pack_only()
	from narratr.render import inline_mermaid_icons

	assert 'A["' in inline_mermaid_icons('A@{ icon: "lucide:mic" }')
	assert inline_mermaid_icons('A@{ icon: "lucide:mic" }').rstrip().endswith('A"]')


def test_plain_nodes_and_other_shapes_are_left_alone():
	from narratr.render import inline_mermaid_icons

	src = 'flowchart LR\n  A["Plain"]\n  B@{ shape: "cyl", label: "Store" }\n  A --> B'
	assert inline_mermaid_icons(src) == src


def test_the_guard_rejects_an_svg_that_lost_its_icons():
	_real_pack_only()
	from narratr.render import RenderError, check_icons_landed

	with pytest.raises(RenderError, match="without its icons"):
		check_icons_landed("<svg><rect/></svg>", ["file-text"])


def test_the_guard_passes_when_the_glyph_is_present():
	_real_pack_only()
	from narratr.render import check_icons_landed

	check_icons_landed(icons.inline_markup("file-text"), ["file-text"])
