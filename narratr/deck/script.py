"""What the presenter says, and where they click.

The narration is already written for the ear, and every reveal already carries
a cue: the verbatim phrase it appears on. So the click goes exactly where the
video would reveal, and `narratr validate` has already proved every cue is in
its narration and in order. Nothing here can drift from the deck, because the
deck's click groups are checked against the same `reveals`.
"""

from __future__ import annotations

import re
from typing import Any

from narratr import cues
from narratr.align import normalise
from narratr.spec import is_flowchart

MARKER = "▶️"


def reveals(scene: dict[str, Any]) -> list[str | None]:
	"""One entry per click on this slide, in order.

	A non-flowchart diagram is one static picture, so it has no clicks even
	though its spec carries cues: a marker with no animation behind it would
	have the presenter clicking straight to the next slide.
	"""
	if scene["type"] == "diagram" and not is_flowchart(scene.get("mermaid", "")):
		return []
	return cues.cue_list(scene)


def marked(scene: dict[str, Any]) -> str:
	narration: str = scene["narration"]
	# Character offset of each word the cue matcher counts. `cues.find`
	# indexes `cues.speakable`, which is `split()` minus words that normalise
	# to nothing; `\S+` yields exactly `split()`'s tokens, with their offsets.
	starts = [m.start() for m in re.finditer(r"\S+", narration) if normalise(m.group())]
	at: list[int] = []
	for cue in reveals(scene):
		index = cues.find(narration, cue) if cue else None
		if index is not None:
			at.append(starts[index])
	for offset in sorted(at, reverse=True):
		narration = narration[:offset] + MARKER + " " + narration[offset:]
	return narration


def document(spec: dict[str, Any]) -> str:
	"""script.md: one section per slide, printable from any viewer."""
	parts = [f"# {spec['source']['title']}\n"]
	for number, scene in enumerate(spec["scenes"], 1):
		heading = scene.get("heading") or scene["id"]
		parts.append(f"\n## {number}. {heading}\n")
		clicks = len(reveals(scene))
		if clicks:
			parts.append(f"\n*{clicks} click{'s' if clicks != 1 else ''}*\n")
		parts.append(f"\n{marked(scene)}\n")
	return "".join(parts)
