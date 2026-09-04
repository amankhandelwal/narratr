"""The coverage gate is only meaningful if block ids come from the document."""

from __future__ import annotations

from pathlib import Path

from narratr.blocks import extract, extract_file

PLAN = Path(__file__).resolve().parent.parent / "docs" / "research-plan.md"

DOC = """---
tags: [x]
---
# Title

An opening paragraph.

## First section

A paragraph here.

- a list
- of things

| a | b |
|---|---|
| 1 | 2 |

```mermaid
flowchart TD
    A --> B
```

```sh
echo hi
```

## Second section

Another paragraph.
"""


def test_kinds_are_classified():
	ids = {b["id"]: b["kind"] for b in extract(DOC)}
	assert ids["first-section-1"] == "para"
	assert ids["first-section-2"] == "list"
	assert ids["first-section-3"] == "table"
	assert ids["first-section-4"] == "diagram"
	assert ids["first-section-5"] == "code"


def test_frontmatter_is_not_a_block():
	assert not any("tags" in b["id"] for b in extract(DOC))


def test_ids_are_scoped_per_section():
	ids = [b["id"] for b in extract(DOC)]
	assert "second-section-1" in ids


def test_editing_one_section_does_not_renumber_others():
	before = [b["id"] for b in extract(DOC)]
	after = [b["id"] for b in extract(DOC.replace("A paragraph here.", "Changed text."))]
	assert before == after


def test_ids_are_unique():
	ids = [b["id"] for b in extract_file(PLAN)]
	assert len(ids) == len(set(ids))


def test_extraction_is_deterministic():
	assert extract_file(PLAN) == extract_file(PLAN)
