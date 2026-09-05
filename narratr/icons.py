"""Lucide icons: resolution, validation and search.

Icons resolve here rather than in the renderer, the way Mermaid and Shiki
already do. The component receives finished SVG markup in its props and stays
synchronous -- resolving inside React would need delayRender and would be paid
for on every frame.

The pack is `lucide-static`, pinned exactly in render/remotion/package.json,
which is part of renderer_digest(). Bumping it re-renders rather than silently
keeping the old glyphs.
"""

from __future__ import annotations

import difflib
import json
import re
from functools import lru_cache
from typing import Any

from narratr.paths import ROOT

PACK = ROOT / "render" / "remotion" / "node_modules" / "lucide-static"
ICONS = PACK / "icons"
TAGS = PACK / "tags.json"

# lucide-static prefixes every file with a licence comment. It is the same on
# all 2,000 of them, so it is stripped rather than repeated into every prop.
LICENCE = re.compile(r"^<!--.*?-->\s*", re.DOTALL)


class IconError(Exception):
	"""An icon could not be resolved."""


@lru_cache(maxsize=1)
def available() -> frozenset[str]:
	"""Every icon name the installed pack provides."""
	if not ICONS.is_dir():
		return frozenset()
	return frozenset(path.stem for path in ICONS.glob("*.svg"))


def installed() -> bool:
	"""Whether the pack is present at all.

	Distinguished from "no such icon" so a missing `npm install` reports itself
	rather than being reported as 2,000 unknown icon names.
	"""
	return bool(available())


def suggest(name: str, limit: int = 3) -> list[str]:
	"""Near misses for a name that does not exist.

	Claude writes these names unprompted. Handing back the closest matches is
	the difference between one correction and a second guess.
	"""
	return difflib.get_close_matches(name, sorted(available()), n=limit, cutoff=0.6)


def markup(name: str) -> str:
	"""The icon's SVG, ready to inline.

	`stroke="currentColor"` is left as it is: the component sets a colour and
	the glyph inherits it, which is what lets one icon take accent(i).
	"""
	path = ICONS / f"{name}.svg"
	if not path.is_file():
		raise IconError(f"no such icon: {name}")
	return LICENCE.sub("", path.read_text()).strip()


@lru_cache(maxsize=1)
def _tags() -> dict[str, list[str]]:
	"""Lucide's own keyword index, used for search rather than for validation."""
	if not TAGS.is_file():
		return {}
	return json.loads(TAGS.read_text())


def search(query: str, limit: int = 20) -> list[str]:
	"""Names matching a word, by name first and then by Lucide's own tags.

	This exists so the skill can look a name up instead of guessing twice. The
	full set is too large to carry in context and too small a detail to be worth
	the tokens.
	"""
	needle = query.strip().lower()
	if not needle:
		return []

	tags = _tags()
	by_name = sorted(n for n in available() if needle in n)
	by_tag = sorted(
		name
		for name, words in tags.items()
		if name in available() and any(needle in word.lower() for word in words)
	)

	seen: list[str] = []
	for name in [*by_name, *by_tag]:
		if name not in seen:
			seen.append(name)
	return seen[:limit]


# ---------------------------------------------------------------- validation


def names_in(scene: dict[str, Any]) -> list[str]:
	"""Every icon a scene asks for, in the order they appear."""
	found: list[str] = []

	for bullet in scene.get("bullets") or []:
		if isinstance(bullet, dict) and bullet.get("icon"):
			found.append(str(bullet["icon"]))

	for step in scene.get("steps") or []:
		if isinstance(step, dict) and step.get("icon"):
			found.append(str(step["icon"]))

	footer = scene.get("footer")
	if isinstance(footer, dict) and footer.get("icon"):
		found.append(str(footer["icon"]))

	for card in scene.get("cards") or []:
		if isinstance(card, dict) and card.get("icon"):
			found.append(str(card["icon"]))

	return found


def problems(spec: dict[str, Any]) -> list[str]:
	"""Icon names that do not exist, with near misses.

	Runs inside `narratr validate`, before any compute is spent. A name that
	silently fell back to no icon would degrade one slide in a long video and
	be found on playback, which is the failure this whole design avoids.
	"""
	wanted = {name: scene["id"] for scene in spec.get("scenes", []) for name in names_in(scene)}
	if not wanted:
		return []

	if not installed():
		return [f"icons: pack not installed -- run 'npm install' in {PACK.parent.parent}"]

	found: list[str] = []
	for name, scene_id in sorted(wanted.items()):
		if name in available():
			continue
		near = suggest(name)
		hint = f" -- did you mean {', '.join(near)}?" if near else ""
		found.append(f"icons: '{name}' in scene '{scene_id}' is not a Lucide icon{hint}")
	return found
