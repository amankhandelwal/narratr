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

from narratr.errors import PipelineError
from narratr.paths import ROOT

PACK = ROOT / "render" / "remotion" / "node_modules" / "lucide-static"
ICONS = PACK / "icons"
TAGS = PACK / "tags.json"

# lucide-static prefixes every file with a licence comment. It is the same on
# all 2,000 of them, so it is stripped rather than repeated into every prop.
LICENCE = re.compile(r"^<!--.*?-->\s*", re.DOTALL)


class IconError(PipelineError):
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


# ------------------------------------------------------------------ mermaid

# Mermaid node syntax: A@{ icon: "lucide:file-text", form: "square", ... }
MERMAID_ICON = re.compile(r"""icon:\s*["']lucide:([a-z0-9-]+)["']""")


def inline_markup(name: str, size_em: float = 1.15) -> str:
	"""An icon sized and quoted for embedding in a Mermaid HTML node label.

	Mermaid measures the rendered label to size the box, so an inline glyph is
	laid out correctly without anyone computing geometry. Two details make it
	work: the attributes are single-quoted, because a double quote would end the
	Mermaid label; and the glyph keeps `stroke="currentColor"`, so the CSS that
	colours a node on its reveal beat colours the icon with it.
	"""
	svg = markup(name)
	svg = re.sub(r'\swidth="[^"]*"', f" width='{size_em}em'", svg, count=1)
	svg = re.sub(r'\sheight="[^"]*"', f" height='{size_em}em'", svg, count=1)
	svg = re.sub(r"\s+", " ", svg).replace('"', "'")
	# Spacing is inline, not in the renderer's stylesheet. Mermaid measures the
	# rendered label to size the box and then clips the foreignObject to that
	# width, so anything CSS adds afterwards pushes the text out of view.
	style = "display:inline-flex;align-items:center;vertical-align:-0.22em;margin-right:0.45em"
	return f"<span class='narratr-icon' style='{style}'>{svg}</span>"


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


def mermaid_names_in(scene: dict[str, Any]) -> list[str]:
	"""Icons a diagram scene asks for, read out of its Mermaid source.

	Kept apart from `names_in` because these never reach a React component --
	they are baked into the SVG by Mermaid itself. They still have to be
	validated, or diagram icons become the one place a typo escapes the gate.
	"""
	return MERMAID_ICON.findall(scene.get("mermaid") or "")


def problems(spec: dict[str, Any]) -> list[str]:
	"""Icon names that do not exist, with near misses.

	Runs inside `narratr validate`, before any compute is spent. A name that
	silently fell back to no icon would degrade one slide in a long video and
	be found on playback, which is the failure this whole design avoids.
	"""
	# Keyed by name but collecting every scene that asks for it. Keying to a
	# single id meant three scenes sharing a typo reported only the last one,
	# so the user fixed it and re-ran into the same error twice more.
	wanted: dict[str, list[str]] = {}
	for scene in spec.get("scenes", []):
		for name in [*names_in(scene), *mermaid_names_in(scene)]:
			where = wanted.setdefault(name, [])
			if scene["id"] not in where:
				where.append(scene["id"])
	if not wanted:
		return []

	if not installed():
		return [f"icons: pack not installed -- run 'npm install' in {PACK.parent.parent}"]

	found: list[str] = []
	for name, scene_ids in sorted(wanted.items()):
		if name in available():
			continue
		near = suggest(name)
		hint = f" -- did you mean {', '.join(near)}?" if near else ""
		named = ", ".join(f"'{sid}'" for sid in scene_ids)
		found.append(f"icons: '{name}' in scene {named} is not a Lucide icon{hint}")
	return found
