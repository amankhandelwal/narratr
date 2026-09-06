"""Reveal beats tied to the narration.

A slide's elements used to appear on a wall-clock rhythm: evenly spaced across
the first 60% of the scene, with no reference to when anything was said. On a
40-second scene the last step landed nine seconds before the words that
introduce it, and the final third played against a finished slide.

The narration is already aligned word by word for captions, so the timings
exist. What was missing was a way to say *which* word an element belongs to.
That is `cue`: a verbatim phrase from the scene's own narration. The element
appears as that phrase begins.

An element with no cue falls back to a proportional position, but measured
along the narration's timeline rather than the clock -- so even an uncued
slide follows the speech instead of drifting away from it.

The index returned by `find` is an index into the aligned word timings. That
holds because `speakable` applies exactly the filter `align.word_timings`
applies before handing words to the aligner; the two must stay in step.
"""

from __future__ import annotations

from typing import Any

from narratr.align import normalise

# Seconds an element must be on screen before the scene ends. A cue that
# resolves to the last word would otherwise flash in on the final frame.
SETTLE = 0.4


def speakable(narration: str) -> list[str]:
	"""The display words the aligner emits, in order.

	`align.word_timings` drops words whose normalised form is empty -- a lone
	dash, say -- so an index into this list is an index into its output.
	"""
	return [word for word in narration.split() if normalise(word)]


def find(narration: str, cue: str) -> int | None:
	"""Index of the cue's first word among the narration's speakable words.

	Matching is on the normalised character stream rather than token by token,
	because normalising spells numbers out and glues the result: "25" becomes
	"twentyfive", one token where the cue may well have written two. Comparing
	the streams lets a cue be written either as it appears in the narration or
	as it is spoken, and anchoring both ends of the match to token boundaries
	keeps that from matching half a word.

	Returns None if the phrase is not in the narration, which is an authoring
	error `narratr validate` reports before any compute is spent.
	"""
	tokens = [normalise(word) for word in speakable(narration)]
	wanted = "".join(n for n in (normalise(word) for word in cue.split()) if n)
	if not wanted or not tokens:
		return None

	# Character offset where each token starts, plus the end of the stream, so
	# a match can be checked against both edges.
	starts: list[int] = []
	position = 0
	for token in tokens:
		starts.append(position)
		position += len(token)
	boundaries = set(starts) | {position}

	stream = "".join(tokens)
	at = stream.find(wanted)
	while at != -1:
		if at in boundaries and at + len(wanted) in boundaries:
			return starts.index(at)
		at = stream.find(wanted, at + 1)
	return None


def cue_list(scene: dict[str, Any]) -> list[str | None]:
	"""One entry per revealed element, in reveal order.

	Every scene type that reveals anything is here, so validation and rendering
	agree on what the elements are. A `code` scene reveals nothing.
	"""
	kind = scene["type"]
	if kind == "prose":
		return [b.get("cue") if isinstance(b, dict) else None for b in scene.get("bullets", [])]
	if kind == "flow":
		return [step.get("cue") for step in scene.get("steps", [])]
	if kind == "cards":
		return [card.get("cue") for card in scene.get("cards", [])]
	if kind == "diagram":
		written = scene.get("revealCues", [])
		groups = scene.get("revealSteps", [])
		return [written[i] if i < len(written) else None for i in range(len(groups))]
	return []


def labels(scene: dict[str, Any]) -> list[str]:
	"""A short name per revealed element, for naming one in an error."""
	kind = scene["type"]
	if kind == "prose":
		return [b if isinstance(b, str) else b.get("text", "") for b in scene.get("bullets", [])]
	if kind == "flow":
		return [step.get("label", "") for step in scene.get("steps", [])]
	if kind == "cards":
		return [card.get("title", "") for card in scene.get("cards", [])]
	if kind == "diagram":
		return [", ".join(group) for group in scene.get("revealSteps", [])]
	return []


def problems(scene: dict[str, Any]) -> list[str]:
	"""Why this scene's cues would not produce correct reveals.

	A hard gate, like coverage: an element with no cue, or a cue that is not in
	the narration, is an authoring mistake that costs nothing to catch here and
	produces a visibly wrong video if it is not. Reveals were unsynced for as
	long as cueing was optional, so it is not optional.
	"""
	found: list[str] = []
	sid = scene.get("id", "?")
	written = scene.get("revealCues", [])
	groups = scene.get("revealSteps", [])
	if scene.get("type") == "diagram" and len(written) > len(groups):
		found.append(
			f"cues: scene '{sid}' has {len(written)} revealCues for {len(groups)} revealSteps"
		)

	narration = scene.get("narration", "")
	previous = -1
	for position, (cue, label) in enumerate(zip(cue_list(scene), labels(scene), strict=True), 1):
		where = f"scene '{sid}' element {position}" + (f" ({label!r})" if label else "")
		if not cue:
			found.append(f"cues: {where} has no cue -- add the narration phrase it appears on")
			continue
		index = find(narration, cue)
		if index is None:
			found.append(f"cues: {where} cue {cue!r} is not a phrase in this scene's narration")
			continue
		if index < previous:
			found.append(f"cues: {where} cue {cue!r} is spoken before the element above it")
		previous = index
	return found


def indices(scene: dict[str, Any]) -> list[int | None]:
	"""Where each element's cue lands in the narration, None where uncued."""
	narration = scene.get("narration", "")
	return [find(narration, cue) if cue else None for cue in cue_list(scene)]


def beats(scene: dict[str, Any], words: list[dict[str, Any]], duration: float) -> list[float]:
	"""Seconds into the scene at which each element appears.

	Cued elements land on their phrase. Uncued ones are spread along the
	narration's own timeline, which keeps the old rhythm without the old drift.
	Results are non-decreasing and leave `SETTLE` at the end, so a late or
	out-of-order cue degrades into a tight reveal rather than a missing one.
	"""
	resolved = indices(scene)
	if not resolved or not words:
		return []

	total = len(resolved) + 1
	raw: list[float] = []
	for position, index in enumerate(resolved, start=1):
		if index is None or index >= len(words):
			index = min(len(words) - 1, round(position * len(words) / total))
		raw.append(float(words[index]["start"]))

	limit = max(0.0, duration - SETTLE)
	out: list[float] = []
	previous = 0.0
	for value in raw:
		previous = min(max(value, previous), limit)
		out.append(round(previous, 3))
	return out
