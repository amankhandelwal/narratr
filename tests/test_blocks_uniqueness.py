"""Block ids must be unique by construction, not by luck.

`test_ids_are_unique` in test_blocks.py reads one document and asserts its 75
ids do not collide. That document happens not to contain a colliding heading,
so the test asserted a sample rather than the property -- the same shape as
measuring "has an audio stream" and calling it "contains audio".

The coverage gate compares sets. A duplicate id hides a whole unmapped block
behind one that is mapped, and validation still reports full coverage.
"""

from __future__ import annotations

from narratr.blocks import extract

CASES = {
	"identical headings": "## Notes\nalpha\n\n## Notes\nbeta\n",
	"identical past the 28-char truncation": (
		"## A very long heading indeed about alpha\none\n\n"
		"## A very long heading indeed about beta\ntwo\n"
	),
	"a heading that looks like another's block id": "## Notes 1\na\n\nb\n\n## Notes\nc\n\nd\n",
	"three of the same": "## Same\na\n\n## Same\nb\n\n## Same\nc\n",
	"headings that slug to nothing": "## ---\na\n\n## ***\nb\n",
	"unicode headings sharing a slug": "## Café\na\n\n## Cafe!\nb\n",
}


def test_ids_are_unique_for_every_colliding_shape():
	for label, document in CASES.items():
		ids = [b["id"] for b in extract(document)]
		assert len(ids) == len(set(ids)), f"{label}: {ids}"


def test_every_block_still_gets_an_id():
	for label, document in CASES.items():
		blocks = extract(document)
		assert blocks, label
		assert all(b["id"] for b in blocks), label


def test_extraction_stays_deterministic_under_collisions():
	for document in CASES.values():
		assert extract(document) == extract(document)


def test_a_collision_does_not_renumber_the_section_before_it():
	"""Ids are section-scoped so an edit in one section leaves the others alone.
	Disambiguation must not break that for the section that was already fine."""
	first = [b["id"] for b in extract("## Notes\na\n\nb\n")]
	both = [b["id"] for b in extract("## Notes\na\n\nb\n\n## Notes\nc\n")]
	assert both[: len(first)] == first
