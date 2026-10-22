"""Colours and fonts for a deck.

The default is the video's palette (render/remotion/src/theme.ts), so a deck
and a video of one document look like the same thing. Fonts are Google Fonts:
Slides substitutes anything else on import.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pptx.dml.color import RGBColor

DEFAULT: dict[str, Any] = {
	"background": "#020617",
	"text": "#ffffff",
	"muted": "#94a3b8",
	"accents": ["#22d3ee", "#34d399", "#a78bfa", "#fbbf24", "#fb7185", "#fb923c"],
	"headingFont": "Inter",
	"bodyFont": "Inter",
}


def _channels(colour: str) -> tuple[int, int, int]:
	value = colour.lstrip("#")
	return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def blend(a: str, b: str, amount: float) -> str:
	"""`amount` of the way from a to b."""
	mixed = (round(x + (y - x) * amount) for x, y in zip(_channels(a), _channels(b), strict=True))
	return "#" + "".join(f"{c:02x}" for c in mixed)


def rgb(colour: str) -> RGBColor:
	return RGBColor(*_channels(colour))


@dataclass(frozen=True)
class Theme:
	background: str
	text: str
	muted: str
	accents: tuple[str, ...]
	heading_font: str
	body_font: str
	mono_font: str = "Roboto Mono"

	def accent(self, i: int) -> str:
		return self.accents[i % len(self.accents)]

	@property
	def panel(self) -> str:
		"""Card and node fill: a step off the background, toward the text."""
		return blend(self.background, self.text, 0.07)

	@property
	def line(self) -> str:
		return blend(self.background, self.text, 0.35)

	@property
	def is_light(self) -> bool:
		r, g, b = _channels(self.background)
		return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 > 0.5


def resolve(spec: dict[str, Any]) -> Theme:
	given = {**DEFAULT, **(spec.get("theme") or {})}
	return Theme(
		background=given["background"],
		text=given["text"],
		muted=given["muted"],
		accents=tuple(given["accents"]),
		heading_font=given["headingFont"],
		body_font=given["bodyFont"],
	)
