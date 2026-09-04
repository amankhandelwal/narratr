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


def validate(spec: dict[str, Any]) -> list[str]:
	"""Schema plus the coverage gate. Returns a list of problems, empty if clean."""
	problems: list[str] = []

	try:
		jsonschema.validate(spec, json.loads(SCHEMA.read_text()))
	except jsonschema.ValidationError as exc:
		location = "/".join(str(p) for p in exc.path) or "(root)"
		problems.append(f"schema: {exc.message} at {location}")

	blocks = set(spec.get("source", {}).get("block_ids", []))
	coverage = spec.get("coverage", {})
	scene_ids = {s["id"] for s in spec.get("scenes", [])}

	for missing in sorted(blocks - set(coverage)):
		problems.append(f"coverage: source block '{missing}' is not mapped to any scene")
	for unknown in sorted(set(coverage) - blocks):
		problems.append(f"coverage: '{unknown}' is mapped but not in source.block_ids")
	for block, sid in sorted(coverage.items()):
		if sid not in scene_ids:
			problems.append(f"coverage: block '{block}' maps to unknown scene '{sid}'")

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
