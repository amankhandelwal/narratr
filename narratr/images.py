"""User-supplied images: where they are and whether a deck can use them.

Kept apart from the deck builder so `narratr validate` can check them without
importing python-pptx. A missing or mistyped image is the user's file, not
Claude's, and is cheapest to report before anything is built.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# What Google Slides accepts in an imported deck.
SUPPORTED_FORMATS = {"PNG", "JPEG", "GIF"}


def resolve(raw: str, base: Path) -> Path:
	"""Relative paths are relative to the spec file, not the shell."""
	path = Path(raw).expanduser()
	return path if path.is_absolute() else base / path


def paths_in(scene: dict[str, Any]) -> list[str]:
	found = [scene["image"]] if scene.get("image") else []
	for card in scene.get("cards") or []:
		if isinstance(card, dict) and card.get("image"):
			found.append(card["image"])
	return found


def problems(spec: dict[str, Any], base: Path) -> list[str]:
	from PIL import Image, UnidentifiedImageError

	found: list[str] = []
	for scene in spec.get("scenes", []):
		sid = scene.get("id", "?")
		for raw in paths_in(scene):
			path = resolve(raw, base)
			if not path.is_file():
				found.append(f"images: scene '{sid}' image '{raw}' not found (looked at {path})")
				continue
			# The suffix is a claim; the bytes are the fact. A renamed file
			# validates by name and fails inside Slides.
			try:
				with Image.open(path) as img:
					kind = img.format
			except (UnidentifiedImageError, OSError):
				kind = None
			if kind not in SUPPORTED_FORMATS:
				found.append(
					f"images: scene '{sid}' image '{raw}' is {kind or 'not an image'} "
					"-- decks take PNG, JPEG or GIF"
				)
	return found
