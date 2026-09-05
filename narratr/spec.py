"""Loading and validating scenes.json.

This is the contract between Claude and the renderer. Validation is free and
runs before any compute is spent, because the expensive failure is a script
that reads well but silently dropped a third of the document.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from narratr import icons
from narratr.paths import SCHEMA


class SpecError(Exception):
	"""The spec could not be read at all."""


def load_spec(path: Path) -> dict[str, Any]:
	try:
		return json.loads(path.read_text())
	except FileNotFoundError:
		raise SpecError(f"no such file: {path}")
	except json.JSONDecodeError as exc:
		raise SpecError(f"{path} is not valid JSON: {exc}")


# What each scene type cannot render without. The schema requires only id,
# type and narration, so a `diagram` with no `mermaid` validated clean and then
# died with a bare KeyError inside `_props_for` -- after the whole narration
# stage had been paid for. This gate is the point: catch it before compute.
# `prose` is deliberately absent: a heading with no bullets is a legitimate
# section card, and `tests/test_render.py` pins that.
REQUIRED_BY_TYPE: dict[str, tuple[str, ...]] = {
	"diagram": ("mermaid",),
	"code": ("code",),
	"flow": ("steps",),
	"cards": ("cards",),
}

# A field that belongs to another shape is dead weight: it never reaches the
# renderer, but it is in VISUAL_FIELDS, so it still moves the video key and
# re-renders a scene that cannot look any different.
OWNED_BY_TYPE = {
	"mermaid": "diagram",
	"revealSteps": "diagram",
	"code": "code",
	"lang": "code",
	"steps": "flow",
	"footer": "flow",
	"cards": "cards",
	"bullets": "prose",
}


def _shape_problems(scenes: list[dict[str, Any]]) -> list[str]:
	found: list[str] = []
	for scene in scenes:
		kind = scene.get("type")
		if not isinstance(kind, str) or kind not in set(OWNED_BY_TYPE.values()):
			continue  # the schema's enum already rejected it
		sid = scene.get("id", "?")
		for field in REQUIRED_BY_TYPE.get(kind, ()):
			if not scene.get(field):
				found.append(f"scenes: '{sid}' is type '{kind}' but has no '{field}'")
		for field, owner in OWNED_BY_TYPE.items():
			if owner != kind and scene.get(field):
				found.append(
					f"scenes: '{sid}' is type '{kind}' and carries '{field}', "
					f"which only '{owner}' renders"
				)
	return found


def validate(spec: dict[str, Any]) -> list[str]:
	"""Schema plus the coverage gate. Returns a list of problems, empty if clean."""
	problems: list[str] = []

	try:
		jsonschema.validate(spec, json.loads(SCHEMA.read_text()))
	except jsonschema.ValidationError as exc:
		location = "/".join(str(p) for p in exc.path) or "(root)"
		problems.append(f"schema: {exc.message} at {location}")

	scenes = spec.get("scenes", [])

	# Two scenes sharing an id collapse in every `by_id` dict and in the
	# manifest: one scene's video is rendered and reused for both, and the
	# other's narration is never spoken. JSON Schema cannot express uniqueness
	# over a key, so it is checked here.
	ids = [s["id"] for s in scenes if "id" in s]
	for duplicate in sorted({sid for sid in ids if ids.count(sid) > 1}):
		problems.append(f"scenes: duplicate scene id '{duplicate}'")

	problems += _shape_problems(scenes)

	# The coverage ledger is compared as sets, so a duplicate block id hides a
	# whole unmapped block behind one that is mapped. `narratr blocks` no
	# longer emits collisions, but a hand-written list still can.
	block_list = spec.get("source", {}).get("block_ids", [])
	blocks = set(block_list)
	if len(block_list) != len(blocks):
		repeated = sorted({b for b in block_list if block_list.count(b) > 1})
		problems.append(
			f"source: duplicate block_ids {', '.join(repeated)} -- "
			"regenerate with 'narratr blocks <doc> --json'"
		)

	coverage = spec.get("coverage", {})
	scene_ids = {s["id"] for s in scenes}

	for missing in sorted(blocks - set(coverage)):
		problems.append(f"coverage: source block '{missing}' is not mapped to any scene")
	for unknown in sorted(set(coverage) - blocks):
		problems.append(f"coverage: '{unknown}' is mapped but not in source.block_ids")
	for block, sid in sorted(coverage.items()):
		if sid not in scene_ids:
			problems.append(f"coverage: block '{block}' maps to unknown scene '{sid}'")

	# Icon names are Claude's to invent, so they are checked here rather than
	# discovered on playback. Same reason the coverage gate exists.
	problems += icons.problems(spec)

	return problems


def summarise(spec: dict[str, Any]) -> str:
	"""What the user sees before deciding to spend hours of compute."""
	words = sum(len(s["narration"].split()) for s in spec["scenes"])
	minutes = words / 150  # ~150 words per minute of speech
	return (
		f"{len(spec['scenes'])} scenes, {words} words of narration\n"
		f"  all {len(spec['source']['block_ids'])} source blocks covered\n"
		f"  estimated: ~{minutes:.0f} min of video, ~{minutes * 1.6:.0f} min of TTS"
	)
