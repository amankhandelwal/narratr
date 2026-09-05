"""Chapter markers, as an ffmpeg metadata file.

Split out of `stitch.py`: generating a text format is a different job from
assembling a video, and it is the part with an escaping rule to get right.
"""

from __future__ import annotations

import re
from typing import Any

# FFMETADATA1 is a text format with real syntax. `=`, `;`, `#`, `\` and a
# newline all mean something in it, and a scene heading comes from an
# LLM-written scenes.json. Unescaped, a heading containing a newline could
# inject arbitrary chapters or metadata keys into the shipped mp4 -- and a
# heading containing a plain `=` silently truncated the title.
SPECIAL = re.compile(r"([=;#\\])")


def escape(value: str) -> str:
	"""Escape a value for FFMETADATA1, collapsing newlines."""
	# A newline cannot be escaped into a value; ffmpeg reads it as a line
	# break. Collapse whitespace first so a multi-line heading stays one title.
	collapsed = " ".join(str(value).split())
	return SPECIAL.sub(r"\\\1", collapsed)


def metadata(spec: dict[str, Any], durations: dict[str, float], intro: float = 0.0) -> str:
	"""An ffmpeg metadata file marking each scene as a chapter.

	The title card is a chapter of its own, so scrubbing to the first scene
	means the first scene rather than four seconds of music.
	"""
	lines = [";FFMETADATA1"]
	start = 0.0

	def chapter(begin: float, end: float, title: str) -> list[str]:
		return [
			"[CHAPTER]",
			"TIMEBASE=1/1000",
			f"START={round(begin * 1000)}",
			# One millisecond short so chapters do not overlap by a tick.
			f"END={max(round(end * 1000) - 1, round(begin * 1000))}",
			f"title={escape(title)}",
		]

	if intro > 0:
		lines += chapter(0.0, intro, spec["source"]["title"])
		start = intro

	for scene in spec["scenes"]:
		end = start + durations[scene["id"]]
		lines += chapter(start, end, scene.get("heading") or scene["id"])
		start = end
	return "\n".join(lines) + "\n"
