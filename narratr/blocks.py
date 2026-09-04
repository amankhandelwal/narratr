"""Leaf-block extraction for the coverage ledger.

This must be mechanical. If the scene author also decides what counts as a
block, the coverage gate is circular: anything skipped can simply be left off
the block list, and the check still passes. Deriving blocks from the document
independently is what makes "every block is mapped" mean something.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
SLUG = re.compile(r"[^a-z0-9]+")


def _slug(title: str) -> str:
	return SLUG.sub("-", title.lower()).strip("-")[:28] or "section"


def extract(markdown: str) -> list[dict[str, Any]]:
	"""Split markdown into leaf blocks with ids stable under re-runs.

	Ids are `<section-slug>-<n>`, so an edit inside one section does not
	renumber the rest of the document.
	"""
	body = FRONTMATTER.sub("", markdown)
	lines = body.splitlines()
	blocks: list[dict[str, Any]] = []
	section = "intro"
	n = 0
	i = 0

	while i < len(lines):
		line = lines[i]

		if line.startswith("#"):
			section = _slug(line.lstrip("#").strip())
			n = 0
			i += 1
			continue

		if not line.strip() or line.strip() == "---":
			i += 1
			continue

		if line.startswith("```"):
			opener = line
			i += 1
			while i < len(lines) and not lines[i].startswith("```"):
				i += 1
			i += 1
			n += 1
			kind = "diagram" if "mermaid" in opener else "code"
			blocks.append({"id": f"{section}-{n}", "kind": kind})
			continue

		if line.lstrip().startswith("|"):
			while i < len(lines) and lines[i].lstrip().startswith("|"):
				i += 1
			n += 1
			blocks.append({"id": f"{section}-{n}", "kind": "table"})
			continue

		start = i
		while (
			i < len(lines)
			and lines[i].strip()
			and lines[i].strip() != "---"
			and not lines[i].startswith(("#", "```"))
			and not lines[i].lstrip().startswith("|")
		):
			i += 1
		if i > start:
			n += 1
			first = lines[start].lstrip()
			kind = "list" if first.startswith(("-", "*")) or re.match(r"\d+\.", first) else "para"
			blocks.append({"id": f"{section}-{n}", "kind": kind})

	return blocks


def extract_file(path: Path) -> list[dict[str, Any]]:
	return extract(path.read_text())
