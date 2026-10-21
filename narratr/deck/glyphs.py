"""Lucide icons as PNG.

Google Slides drops SVG from an imported deck, so each glyph is recoloured and
rasterised here. 192 px is 4x a 0.5 in icon at 96 dpi: sharp on a projector.
"""

from __future__ import annotations

from functools import lru_cache

import resvg_py

from narratr import icons

PIXELS = 192


@lru_cache(maxsize=512)
def png(name: str, colour: str) -> bytes:
	svg = icons.markup(name).replace("currentColor", colour)
	return bytes(resvg_py.svg_to_bytes(svg_string=svg, width=PIXELS, height=PIXELS))
