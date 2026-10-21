"""A deck's colours and fonts: the video's palette unless the spec says otherwise."""

from __future__ import annotations

from narratr.deck import glyphs
from narratr.deck.theme import DEFAULT, resolve


def test_no_theme_is_the_video_palette():
	theme = resolve({})
	assert theme.background == DEFAULT["background"] == "#020617"
	assert not theme.is_light


def test_a_partial_theme_keeps_the_other_defaults():
	theme = resolve({"theme": {"background": "#ffffff", "text": "#111827"}})
	assert theme.is_light
	assert theme.muted == DEFAULT["muted"]
	assert theme.heading_font == "Inter"


def test_accents_rotate():
	theme = resolve({"theme": {"accents": ["#000001", "#000002", "#000003", "#000004"]}})
	assert theme.accent(5) == "#000002"


def test_panel_sits_between_background_and_text():
	theme = resolve({"theme": {"background": "#000000", "text": "#ffffff"}})
	assert theme.panel not in {"#000000", "#ffffff"}


def test_glyph_is_a_png_in_the_given_colour():
	data = glyphs.png("mic", "#22d3ee")
	assert data.startswith(b"\x89PNG")
	assert glyphs.png("mic", "#ff0000") != data
