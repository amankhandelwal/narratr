# Presentation Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `narratr deck scenes.json` builds an editable, Google-Slides-importable `deck.pptx` with on-click reveals, plus a printable `script.md`, from the same `scenes.json` the video uses; a `presentation` skill drives it.

**Architecture:** A new `narratr/deck/` package turns a validated spec into slides with python-pptx. Each shape has a layout function that draws the slide and returns its click groups (lists of shape ids); `animate.py` writes those as `p:timing` XML; `script.py` inserts `▶️` before each cue for the notes and `script.md`. Diagrams reuse `render.mermaid_to_svg` for layout and are rebuilt as native shapes.

**Tech Stack:** Python 3.11, python-pptx 1.0, resvg-py (SVG→PNG), Pillow (via python-pptx), lxml, mermaid-cli and Shiki via the existing `render/remotion/node_modules`.

**Spec:** `docs/superpowers/specs/2026-10-21-presentation-skill-design.md`

## Global Constraints

- All work on branch `presentation-skill`; finish with a PR. Never commit to `main`.
- Tabs for indentation, double quotes, line length 100 (`ruff.toml`).
- Every new error type subclasses `narratr.errors.PipelineError`.
- Do **not** modify any file in `RENDERER_SOURCES` (`narratr/state.py:109`): `render/remotion/src`, `mermaid.config.json`, `narratr/render.py`, `package.json`, `package-lock.json`, `narratr/icons.py`, `scripts/highlight.mjs`. Changing them re-renders every cached video.
- Slide 13.333 × 7.5 in. Headings 40 pt bold; section cards 60 pt centred; body 24–28 pt, never below 20 pt (code alone may go to 12 pt).
- Marker is exactly `▶️` followed by one space, inserted immediately before the cue phrase.
- Reveal effect is Fade, 500 ms. First element of a click group `clickEffect`, the rest `withEffect`.
- Images: PNG, JPEG, GIF only; >2 MB downscaled into the deck, source untouched; paths relative to the spec file.
- Theme colours `#rrggbb`; 4–6 accents; fonts are Google Fonts names. Default theme = narratr dark slate, font `Inter`, mono `Roboto Mono`.
- Output defaults to `decks/<safe_name(title)>/` (gitignored).
- Tests assert properties over every slide of every bundled example, not single samples.

---

## File map

| Path | Responsibility |
|---|---|
| `skills/narratr/` (moved from `skill/`) | Video skill; `shapes.md` (renamed from `presentation.md`) |
| `skills/presentation/SKILL.md` | Presentation workflow |
| `skills/presentation/shapes.md` | Symlink → `../narratr/shapes.md` |
| `skills/presentation/example.scenes.json`, `example-image.png` | Reference spec using `theme` and images |
| `schemas/scenes.schema.json` | `theme`, `image` scene, `image`/`caption` fields |
| `narratr/spec.py` | Shape ownership for new fields, `is_flowchart`, `warnings`, `video_problems`, `validate(spec, base)` |
| `narratr/images.py` | Image path resolution and validation (no pptx import) |
| `narratr/paths.py` | `DECKS` |
| `narratr/deck/theme.py` | `Theme`, `resolve(spec)` |
| `narratr/deck/draw.py` | Low-level drawing helpers shared by layouts |
| `narratr/deck/glyphs.py` | Lucide → recoloured PNG |
| `narratr/deck/script.py` | `reveals`, `marked`, `document` |
| `narratr/deck/animate.py` | `timing_xml`, `apply` |
| `narratr/deck/layout.py` | `prose`, `flow`, `cards`, `code`, `image` layouts |
| `narratr/deck/diagram.py` | SVG parse → native diagram; fallback picture |
| `narratr/deck/build.py` | Master setup, slide loop, save |
| `render/remotion/scripts/tokens.mjs` | Shiki tokens as JSON (new file, not a renderer source) |
| `narratr/cli.py` | `deck` subcommand; validate passes base; render refuses image specs |
| `tests/test_images.py`, `tests/test_theme.py`, `tests/test_script.py`, `tests/test_animate.py`, `tests/test_deck_build.py`, `tests/test_deck_diagram.py` | Tests |

---

### Task 1: Move the skill to `skills/narratr/` and rename the shape guide

**Files:**
- Move: `skill/` → `skills/narratr/`; `skills/narratr/presentation.md` → `skills/narratr/shapes.md`
- Modify: `skills/narratr/SKILL.md`, `skills/narratr/shapes.md` (self-references), `tests/test_skill_example.py`, `Makefile:48`, `README.md:52-62,175`, `LICENSE:8`

**Interfaces:** Produces `skills/narratr/shapes.md`, the guide path later tasks symlink to.

- [ ] **Step 1: Update the test to the new paths (failing)**

In `tests/test_skill_example.py` replace the module docstring's path and the constants:

```python
EXAMPLE = ROOT / "skills" / "narratr" / "example.scenes.json"
GUIDE = ROOT / "skills" / "narratr" / "shapes.md"
```

and the last test:

```python
def test_the_skill_sends_the_reader_to_both():
	body = (ROOT / "skills" / "narratr" / "SKILL.md").read_text()
	assert "shapes.md" in body
	assert "example.scenes.json" in body
```

Docstring first paragraph becomes: "`skills/narratr/example.scenes.json` travels with the skill directory, so a session loading the skill from `~/.claude/skills/narratr` reads it without knowing where the checkout lives."

- [ ] **Step 2: Run it, expect failure**

Run: `uv run pytest tests/test_skill_example.py -q`
Expected: FAIL — `skills/narratr/example.scenes.json` missing.

- [ ] **Step 3: Move and rename**

```bash
mkdir -p skills
git mv skill skills/narratr
git mv skills/narratr/presentation.md skills/narratr/shapes.md
grep -rl "presentation.md" skills/narratr | xargs sed -i '' 's/presentation\.md/shapes.md/g'
sed -i '' 's#examples/\*.json skill/example.scenes.json#examples/*.json skills/*/example.scenes.json#' Makefile
sed -i '' 's#(the `skill/` directory)#(the `skills/` directory)#' LICENSE
```

README: replace the install block and paragraph (lines 52–62) with:

````markdown
Then let Claude see the skills:

```sh
ln -s "$PWD/skills/narratr" ~/.claude/skills/narratr
ln -s "$PWD/skills/presentation" ~/.claude/skills/presentation
```

Start a new Claude session for them to load. Each link covers a whole
directory, so the files travel with it: `SKILL.md` (the workflow), `shapes.md`
(how to choose a scene's shape, shared by both skills) and
`example.scenes.json` (a complete spec). A session reads them without needing
to know where this checkout lives.
````

and on line 175 replace `skill/SKILL.md` with `skills/narratr/SKILL.md`.

- [ ] **Step 4: Run tests and validate**

Run: `uv run pytest tests/test_skill_example.py -q && make validate`
Expected: all pass; `make validate` prints `✓ All specs valid` (the glob currently matches only `skills/narratr/example.scenes.json`).

- [ ] **Step 5: Commit**

```bash
git add -A skills skill Makefile README.md LICENSE tests/test_skill_example.py
git commit -m "Move the video skill to skills/narratr and name its guide shapes.md

Room for a second skill beside it; presentation.md would collide with it."
```

---

### Task 2: Schema and validation for themes and images

**Files:**
- Modify: `schemas/scenes.schema.json`, `narratr/spec.py`, `narratr/cli.py` (`cmd_validate`, `cmd_render`)
- Create: `narratr/images.py`, `tests/test_images.py`
- Modify test: `tests/test_spec.py` (append)

**Interfaces:**
- Produces: `spec.validate(spec, base: Path | None = None) -> list[str]`; `spec.warnings(spec) -> list[str]`; `spec.video_problems(spec) -> list[str]`; `spec.is_flowchart(source: str) -> bool`; `images.resolve(raw: str, base: Path) -> Path`; `images.paths_in(scene) -> list[str]`; `images.problems(spec, base) -> list[str]`; `images.SUPPORTED_FORMATS = {"PNG", "JPEG", "GIF"}`.

- [ ] **Step 1: Write failing tests**

`tests/test_images.py`:

```python
"""Images are the user's files, so validate catches a bad one before a build."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from PIL import Image

from narratr.paths import ROOT
from narratr.spec import validate, video_problems

BRIEF = ROOT / "examples" / "brief.scenes.json"


@pytest.fixture
def spec() -> dict:
	return json.loads(BRIEF.read_text())


def with_image_scene(spec: dict, path: str) -> dict:
	out = copy.deepcopy(spec)
	out["scenes"].append(
		{"id": "picture", "type": "image", "image": path, "narration": "Here it is."}
	)
	return out


def test_a_png_beside_the_spec_is_accepted(spec, tmp_path):
	Image.new("RGB", (8, 8)).save(tmp_path / "shot.png")
	assert validate(with_image_scene(spec, "shot.png"), base=tmp_path) == []


def test_a_missing_image_is_rejected(spec, tmp_path):
	problems = validate(with_image_scene(spec, "nope.png"), base=tmp_path)
	assert any("nope.png" in p and "not found" in p for p in problems)


def test_a_renamed_non_image_is_rejected(spec, tmp_path):
	(tmp_path / "fake.png").write_text("not an image")
	problems = validate(with_image_scene(spec, "fake.png"), base=tmp_path)
	assert any("fake.png" in p for p in problems)


def test_an_unsupported_format_is_rejected(spec, tmp_path):
	Image.new("RGB", (8, 8)).save(tmp_path / "shot.bmp")
	problems = validate(with_image_scene(spec, "shot.bmp"), base=tmp_path)
	assert any("shot.bmp" in p and "PNG, JPEG or GIF" in p for p in problems)


def test_an_image_scene_needs_its_image(spec):
	broken = copy.deepcopy(spec)
	broken["scenes"].append({"id": "picture", "type": "image", "narration": "x"})
	assert any("'picture'" in p and "'image'" in p for p in validate(broken))


def test_card_images_are_checked_too(spec, tmp_path):
	broken = copy.deepcopy(spec)
	cards = next(s for s in broken["scenes"] if s["type"] == "cards")
	cards["cards"][0]["image"] = "gone.jpg"
	assert any("gone.jpg" in p for p in validate(broken, base=tmp_path))


def test_the_video_refuses_images(spec, tmp_path):
	Image.new("RGB", (8, 8)).save(tmp_path / "shot.png")
	assert video_problems(with_image_scene(spec, "shot.png"))
	assert video_problems(spec) == []
```

Append to `tests/test_spec.py`:

```python
def test_theme_colours_must_be_hex():
	spec = load()
	spec["theme"] = {"background": "navy"}
	assert any("theme" in p for p in validate(spec))


def test_a_full_theme_is_accepted():
	spec = load()
	spec["theme"] = {
		"background": "#ffffff",
		"text": "#111827",
		"muted": "#6b7280",
		"accents": ["#2563eb", "#db2777", "#059669", "#d97706"],
		"headingFont": "Poppins",
		"bodyFont": "Inter",
	}
	assert validate(spec) == []


def test_non_flowchart_diagrams_warn_but_pass():
	from narratr.spec import warnings

	spec = load()
	diagram = next(s for s in spec["scenes"] if s["type"] == "diagram")
	diagram["mermaid"] = "sequenceDiagram\n    A->>B: hi"
	assert any(diagram["id"] in w for w in warnings(spec))


def test_is_flowchart_skips_frontmatter_and_comments():
	from narratr.spec import is_flowchart

	assert is_flowchart("---\nconfig:\n  x: 1\n---\n%% note\nflowchart LR\n A-->B")
	assert is_flowchart("graph TD\n A-->B")
	assert not is_flowchart("sequenceDiagram\n A->>B: hi")
```

- [ ] **Step 2: Run, expect failures**

Run: `uv run pytest tests/test_images.py tests/test_spec.py -q`
Expected: FAIL — `video_problems` cannot be imported; `validate()` takes no `base`.

- [ ] **Step 3: Schema**

In `schemas/scenes.schema.json`, add under top-level `properties` (after `voice`):

```json
"theme": {
  "type": "object",
  "additionalProperties": false,
  "description": "Deck colours and fonts. Ignored by the video renderer. Fonts should be Google Fonts so Google Slides does not substitute them.",
  "properties": {
    "background": { "$ref": "#/$defs/colour" },
    "text": { "$ref": "#/$defs/colour" },
    "muted": { "$ref": "#/$defs/colour" },
    "accents": { "type": "array", "minItems": 4, "maxItems": 6, "items": { "$ref": "#/$defs/colour" } },
    "headingFont": { "type": "string", "minLength": 1, "maxLength": 100 },
    "bodyFont": { "type": "string", "minLength": 1, "maxLength": 100 }
  }
},
```

Add at the schema root (sibling of `properties`):

```json
"$defs": {
  "colour": { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
  "image": {
    "type": "string",
    "minLength": 1,
    "maxLength": 1000,
    "description": "Path to a PNG, JPEG or GIF, relative to this spec file. Decks only."
  }
}
```

Add `"image"` to the scene `type` enum. Add scene properties `"image": { "$ref": "#/$defs/image" }` and `"caption": { "type": "string", "maxLength": 300 }`, and inside `cards.items.properties` add `"image": { "$ref": "#/$defs/image" }`. Extend the `type` description with: "'image' needs 'image' and is decks only."

- [ ] **Step 4: `narratr/images.py`**

```python
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
```

- [ ] **Step 5: `narratr/spec.py` changes**

Change `REQUIRED_BY_TYPE` to add `"image": ("image",),`.

Replace `OWNED_BY_TYPE` with tuple owners and update `_shape_problems`:

```python
OWNED_BY_TYPE: dict[str, tuple[str, ...]] = {
	"mermaid": ("diagram",),
	"revealSteps": ("diagram",),
	"code": ("code",),
	"lang": ("code",),
	"steps": ("flow",),
	"footer": ("flow",),
	"cards": ("cards",),
	"bullets": ("prose",),
	# A picture beside the bullets, or the whole slide.
	"image": ("prose", "image"),
	"caption": ("image",),
}

KINDS = {kind for owners in OWNED_BY_TYPE.values() for kind in owners}
```

In `_shape_problems` replace the kind guard with `if not isinstance(kind, str) or kind not in KINDS:` and the ownership loop with:

```python
		for field, owners in OWNED_BY_TYPE.items():
			if kind not in owners and scene.get(field):
				found.append(
					f"scenes: '{sid}' is type '{kind}' and carries '{field}', "
					f"which only {' or '.join(repr(o) for o in owners)} renders"
				)
```

Add imports `import re` and `from narratr import cues, icons, images`. Change `validate`'s signature and add the image check after the icon check:

```python
def validate(spec: dict[str, Any], base: Path | None = None) -> list[str]:
	"""Schema plus the coverage gate. Returns a list of problems, empty if clean.

	`base` is the directory image paths are relative to: the spec file's own.
	"""
```

```python
	problems += images.problems(spec, base or Path.cwd())
```

Add below `validate`:

```python
FRONTMATTER = re.compile(r"\A\s*---\n.*?\n---\n", re.DOTALL)


def is_flowchart(source: str) -> bool:
	"""Whether a deck can rebuild this diagram as native shapes."""
	for line in FRONTMATTER.sub("", source).splitlines():
		stripped = line.strip()
		if stripped and not stripped.startswith("%%"):
			return stripped.split()[0] in {"flowchart", "graph"}
	return False


def warnings(spec: dict[str, Any]) -> list[str]:
	"""Things that build, but not the way the author may expect."""
	return [
		f"diagram: '{s['id']}' is not a flowchart -- the deck shows it as one picture, "
		"with no clicks"
		for s in spec.get("scenes", [])
		if s.get("type") == "diagram" and not is_flowchart(s.get("mermaid", ""))
	]


def video_problems(spec: dict[str, Any]) -> list[str]:
	"""What the video renderer cannot draw yet. Images are decks-only for now."""
	return [
		f"render: scene '{s['id']}' uses images, which only 'narratr deck' renders"
		for s in spec.get("scenes", [])
		if s.get("type") == "image" or images.paths_in(s)
	]
```

- [ ] **Step 6: CLI wiring**

In `narratr/cli.py`: `from narratr.spec import load_spec, summarise, validate, video_problems, warnings`.
`cmd_validate`: `problems = validate(spec, base=args.scenes.resolve().parent)`, and after the ✓ line print each warning: `for warning in warnings(spec): print(f"⚠️  {warning}")`.
`cmd_render`: `problems = validate(spec, base=args.scenes.resolve().parent) + video_problems(spec)`.

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/ -q -x && make validate`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add schemas/scenes.schema.json narratr/spec.py narratr/images.py narratr/cli.py tests/test_images.py tests/test_spec.py
git commit -m "Let a spec carry a theme and images, checked before anything builds"
```

---

### Task 3: Dependencies, theme and icon PNGs

**Files:**
- Modify: `pyproject.toml`, `narratr/paths.py`, `.gitignore`
- Create: `narratr/deck/__init__.py`, `narratr/deck/theme.py`, `narratr/deck/glyphs.py`, `tests/test_theme.py`

**Interfaces:**
- Produces: `Theme` (frozen dataclass: `background, text, muted, accents: tuple[str, ...], heading_font, body_font, mono_font`; methods `accent(i) -> str`, properties `panel -> str`, `line -> str`, `is_light -> bool`); `theme.resolve(spec) -> Theme`; `theme.rgb(hex: str) -> RGBColor`; `glyphs.png(name: str, colour: str) -> bytes`; `paths.DECKS`.

- [ ] **Step 1: Dependencies**

```bash
uv add "python-pptx>=1.0.2" "resvg-py>=0.5.0"
```

Add to `narratr/paths.py`: `DECKS = ROOT / "decks"` (with comment `# narratr deck output, one directory per deck title.`). Add `decks/` to `.gitignore` under `runs/`.

- [ ] **Step 2: Failing test `tests/test_theme.py`**

```python
from __future__ import annotations

from narratr.deck import glyphs
from narratr.deck.theme import DEFAULT, resolve


def test_no_theme_is_the_video_palette():
	theme = resolve({})
	assert theme.background == DEFAULT["background"] == "#020617"
	assert not theme.is_light


def test_a_partial_theme_keeps_the_other_defaults():
	theme = resolve({"theme": {"background": "#ffffff", "text": "#111827"}})
	assert theme.is_light
	assert theme.muted == DEFAULT["muted"]
	assert theme.heading_font == "Inter"


def test_accents_rotate():
	theme = resolve({"theme": {"accents": ["#000001", "#000002", "#000003", "#000004"]}})
	assert theme.accent(5) == "#000002"


def test_panel_sits_between_background_and_text():
	theme = resolve({"theme": {"background": "#000000", "text": "#ffffff"}})
	assert theme.panel not in {"#000000", "#ffffff"}


def test_glyph_is_a_png_in_the_given_colour():
	data = glyphs.png("mic", "#22d3ee")
	assert data.startswith(b"\x89PNG")
	assert glyphs.png("mic", "#ff0000") != data
```

Run: `uv run pytest tests/test_theme.py -q` — Expected: FAIL, `narratr.deck` missing.

- [ ] **Step 3: Implement**

`narratr/deck/__init__.py`:

```python
"""Slide decks: the same scenes.json, presented by a person instead of narrated."""
```

`narratr/deck/theme.py`:

```python
"""Colours and fonts for a deck.

The default is the video's palette (render/remotion/src/theme.ts), so a deck
and a video of one document look like the same thing. Fonts are Google Fonts:
Slides substitutes anything else on import.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pptx.dml.color import RGBColor

DEFAULT: dict[str, Any] = {
	"background": "#020617",
	"text": "#ffffff",
	"muted": "#94a3b8",
	"accents": ["#22d3ee", "#34d399", "#a78bfa", "#fbbf24", "#fb7185", "#fb923c"],
	"headingFont": "Inter",
	"bodyFont": "Inter",
}


def _channels(colour: str) -> tuple[int, int, int]:
	value = colour.lstrip("#")
	return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def blend(a: str, b: str, amount: float) -> str:
	"""`amount` of the way from a to b."""
	mixed = (round(x + (y - x) * amount) for x, y in zip(_channels(a), _channels(b), strict=True))
	return "#" + "".join(f"{c:02x}" for c in mixed)


def rgb(colour: str) -> RGBColor:
	return RGBColor(*_channels(colour))


@dataclass(frozen=True)
class Theme:
	background: str
	text: str
	muted: str
	accents: tuple[str, ...]
	heading_font: str
	body_font: str
	mono_font: str = "Roboto Mono"

	def accent(self, i: int) -> str:
		return self.accents[i % len(self.accents)]

	@property
	def panel(self) -> str:
		"""Card and node fill: a step off the background, toward the text."""
		return blend(self.background, self.text, 0.07)

	@property
	def line(self) -> str:
		return blend(self.background, self.text, 0.35)

	@property
	def is_light(self) -> bool:
		r, g, b = _channels(self.background)
		return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 > 0.5


def resolve(spec: dict[str, Any]) -> Theme:
	given = {**DEFAULT, **(spec.get("theme") or {})}
	return Theme(
		background=given["background"],
		text=given["text"],
		muted=given["muted"],
		accents=tuple(given["accents"]),
		heading_font=given["headingFont"],
		body_font=given["bodyFont"],
	)
```

`narratr/deck/glyphs.py`:

```python
"""Lucide icons as PNG.

Google Slides drops SVG from an imported deck, so each glyph is recoloured and
rasterised here. 192 px is 4x a 0.5 in icon at 96 dpi: sharp on a projector.
"""

from __future__ import annotations

from functools import lru_cache

import resvg_py

from narratr import icons

PIXELS = 192


@lru_cache(maxsize=512)
def png(name: str, colour: str) -> bytes:
	svg = icons.markup(name).replace("currentColor", colour)
	return bytes(resvg_py.svg_to_bytes(svg_string=svg, width=PIXELS, height=PIXELS))
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_theme.py -q && uv run mypy narratr/`
Expected: PASS, mypy clean.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock narratr/paths.py .gitignore narratr/deck tests/test_theme.py
git commit -m "Add deck theme resolution and PNG icons for Slides"
```

---

### Task 4: The spoken script

**Files:**
- Create: `narratr/deck/script.py`, `tests/test_script.py`

**Interfaces:**
- Consumes: `cues.cue_list`, `cues.find`, `spec.is_flowchart`.
- Produces: `script.MARKER = "▶️"`; `script.reveals(scene) -> list[str | None]` (the cues the deck animates; `[]` for a non-flowchart diagram); `script.marked(scene) -> str`; `script.document(spec) -> str`.

- [ ] **Step 1: Failing tests `tests/test_script.py`**

```python
"""The presenter's script: the narration, with a marker wherever to click."""

from __future__ import annotations

import json

import pytest

from narratr.deck import script
from narratr.paths import ROOT

SPECS = [
	ROOT / "examples" / "brief.scenes.json",
	ROOT / "examples" / "code.scenes.json",
	ROOT / "skills" / "narratr" / "example.scenes.json",
]
SCENES = [
	pytest.param(scene, id=f"{path.stem}:{scene['id']}")
	for path in SPECS
	for scene in json.loads(path.read_text())["scenes"]
]
MARK = script.MARKER + " "


@pytest.mark.parametrize("scene", SCENES)
def test_one_marker_per_reveal(scene):
	assert script.marked(scene).count(script.MARKER) == len(script.reveals(scene))


@pytest.mark.parametrize("scene", SCENES)
def test_removing_the_markers_gives_back_the_narration(scene):
	assert script.marked(scene).replace(MARK, "") == scene["narration"]


@pytest.mark.parametrize("scene", SCENES)
def test_each_marker_sits_right_before_its_cue(scene):
	text = script.marked(scene)
	for cue in script.reveals(scene):
		assert MARK + cue.split()[0] in text


def test_a_sequence_diagram_has_no_clicks():
	scene = {
		"id": "s",
		"type": "diagram",
		"mermaid": "sequenceDiagram\n A->>B: hi",
		"revealSteps": [["A"]],
		"revealCues": ["hello"],
		"narration": "hello there",
	}
	assert script.reveals(scene) == []
	assert script.marked(scene) == "hello there"


def test_document_has_a_section_per_slide_with_its_click_count():
	spec = json.loads(SPECS[0].read_text())
	doc = script.document(spec)
	assert doc.startswith(f"# {spec['source']['title']}\n")
	for number, scene in enumerate(spec["scenes"], 1):
		clicks = len(script.reveals(scene))
		assert f"## {number}. " in doc
		assert script.marked(scene) in doc
		if clicks:
			assert f"*{clicks} click{'s' if clicks != 1 else ''}*" in doc
```

Run: `uv run pytest tests/test_script.py -q` — Expected: FAIL, module missing.

- [ ] **Step 2: Implement `narratr/deck/script.py`**

```python
"""What the presenter says, and where they click.

The narration is already written for the ear, and every reveal already carries
a cue: the verbatim phrase it appears on. So the click goes exactly where the
video would reveal, and `narratr validate` has already proved every cue is in
its narration and in order. Nothing here can drift from the deck, because the
deck's click groups come from the same `reveals`.
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
	# to nothing; `\S+` yields exactly `split()`'s tokens with their offsets.
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
			parts.append(f"*{clicks} click{'s' if clicks != 1 else ''}*\n")
		parts.append(f"\n{marked(scene)}\n")
	return "".join(parts)
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_script.py -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add narratr/deck/script.py tests/test_script.py
git commit -m "Write the presenter's script with a click marker on every cue"
```

---

### Task 5: Animation timing XML

**Files:**
- Create: `narratr/deck/animate.py`, `tests/test_animate.py`

**Interfaces:**
- Produces: `animate.timing_xml(groups: list[list[int]]) -> str`; `animate.apply(slide, groups: list[list[int]]) -> None`; `animate.click_groups(slide_element) -> list[list[int]]` (reads back; used by tests and the build's self-check).

- [ ] **Step 1: Failing tests `tests/test_animate.py`**

```python
from __future__ import annotations

from pptx import Presentation
from pptx.util import Inches

from narratr.deck import animate


def slide_with(n: int):
	prs = Presentation()
	slide = prs.slides.add_slide(prs.slide_layouts[6])
	ids = [
		slide.shapes.add_textbox(Inches(i), Inches(1), Inches(1), Inches(1)).shape_id
		for i in range(n)
	]
	return prs, slide, ids


def test_groups_round_trip():
	_, slide, ids = slide_with(4)
	groups = [[ids[0]], [ids[1], ids[2]], [ids[3]]]
	animate.apply(slide, groups)
	assert animate.click_groups(slide._element) == groups


def test_first_of_a_group_is_on_click_the_rest_with_previous():
	xml = animate.timing_xml([[5, 6, 7]])
	assert xml.count('nodeType="clickEffect"') == 1
	assert xml.count('nodeType="withEffect"') == 2


def test_every_effect_is_a_fade():
	xml = animate.timing_xml([[5], [6]])
	assert xml.count('presetID="10" presetClass="entr"') == 2
	assert xml.count('filter="fade"') == 2


def test_no_groups_writes_no_timing():
	_, slide, _ = slide_with(1)
	animate.apply(slide, [])
	assert animate.click_groups(slide._element) == []
	assert slide._element.find(animate.qn("p:timing")) is None


def test_timing_ids_are_unique():
	import re

	xml = animate.timing_xml([[1, 2], [3], [4, 5, 6]])
	ids = re.findall(r'<p:cTn id="(\d+)"', xml)
	assert len(ids) == len(set(ids))


def test_saved_file_reopens(tmp_path):
	prs, slide, ids = slide_with(2)
	animate.apply(slide, [[ids[0]], [ids[1]]])
	prs.save(tmp_path / "x.pptx")
	again = Presentation(tmp_path / "x.pptx")
	assert animate.click_groups(again.slides[0]._element) == [[ids[0]], [ids[1]]]
```

Run: `uv run pytest tests/test_animate.py -q` — Expected: FAIL.

- [ ] **Step 2: Implement `narratr/deck/animate.py`**

```python
"""On-click reveals, as PowerPoint timing XML.

python-pptx has no animation API, so this writes `p:timing` directly. The shape
is the one verified to survive Google Slides' import (see the spec): a main
sequence of click groups, each holding Fade entrance effects -- the first
On click, the rest With previous.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import count
from typing import Any

from lxml import etree
from pptx.oxml.ns import qn

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
FADE_MS = 500


def _fade(ids: Iterator[int], spid: int, node_type: str) -> str:
	target = f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>'
	return (
		f'<p:par><p:cTn id="{next(ids)}" presetID="10" presetClass="entr" presetSubtype="0" '
		f'fill="hold" nodeType="{node_type}"><p:stCondLst><p:cond delay="0"/></p:stCondLst>'
		"<p:childTnLst>"
		f'<p:set><p:cBhvr><p:cTn id="{next(ids)}" dur="1" fill="hold"><p:stCondLst>'
		f'<p:cond delay="0"/></p:stCondLst></p:cTn>{target}<p:attrNameLst>'
		"<p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>"
		'<p:to><p:strVal val="visible"/></p:to></p:set>'
		f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{next(ids)}" '
		f'dur="{FADE_MS}"/>{target}</p:cBhvr></p:animEffect>'
		"</p:childTnLst></p:cTn></p:par>"
	)


def timing_xml(groups: list[list[int]]) -> str:
	ids = count(3)  # 1 and 2 are the root and the main sequence
	clicks = ""
	for group in groups:
		effects = "".join(
			_fade(ids, spid, "clickEffect" if i == 0 else "withEffect")
			for i, spid in enumerate(group)
		)
		clicks += (
			f'<p:par><p:cTn id="{next(ids)}" fill="hold"><p:stCondLst>'
			'<p:cond delay="indefinite"/></p:stCondLst><p:childTnLst>'
			f'<p:par><p:cTn id="{next(ids)}" fill="hold"><p:stCondLst><p:cond delay="0"/>'
			f"</p:stCondLst><p:childTnLst>{effects}</p:childTnLst></p:cTn></p:par>"
			"</p:childTnLst></p:cTn></p:par>"
		)
	return (
		f'<p:timing xmlns:p="{P}"><p:tnLst><p:par><p:cTn id="1" dur="indefinite" '
		'restart="never" nodeType="tmRoot"><p:childTnLst><p:seq concurrent="1" '
		'nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
		f"{clicks}</p:childTnLst></p:cTn>"
		'<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl>'
		"</p:cond></p:prevCondLst>"
		'<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl>'
		"</p:cond></p:nextCondLst>"
		"</p:seq></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>"
	)


def apply(slide: Any, groups: list[list[int]]) -> None:
	groups = [g for g in groups if g]
	if not groups:
		return
	element = slide._element
	timing = etree.fromstring(timing_xml(groups))
	# Schema order: cSld, clrMapOvr, transition, timing, extLst.
	ext = element.find(qn("p:extLst"))
	if ext is not None:
		ext.addprevious(timing)
	else:
		element.append(timing)


def click_groups(element: Any) -> list[list[int]]:
	"""Read the click groups back out of a slide's XML."""
	seq = element.find(f".//{qn('p:cTn')}[@nodeType='mainSeq']")
	if seq is None:
		return []
	groups: list[list[int]] = []
	for click in seq.find(qn("p:childTnLst")):
		groups.append(
			[
				int(t.get("spid"))
				for effect in click.iter(qn("p:cTn"))
				if effect.get("presetClass") == "entr"
				for t in effect.iter(qn("p:spTgt"))
			][::2]  # each effect targets its shape twice: set + animEffect
		)
	return groups
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_animate.py -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add narratr/deck/animate.py tests/test_animate.py
git commit -m "Write on-click Fade reveals as slide timing XML"
```

---

### Task 6: Deck builder, master, prose/section/image/code slides, and `narratr deck`

**Files:**
- Create: `narratr/deck/draw.py`, `narratr/deck/layout.py`, `narratr/deck/build.py`, `render/remotion/scripts/tokens.mjs`, `tests/test_deck_build.py`
- Modify: `narratr/cli.py`

**Interfaces:**
- Consumes: `Theme`, `glyphs.png`, `script.reveals/marked/document`, `animate.apply/click_groups`, `images.resolve`.
- Produces: `layout.Ctx` (dataclass `theme: Theme, base: Path, tmp: Path`); `layout.LAYOUTS: dict[str, Callable[[Any, dict, Ctx], list[list[int]]]]` (flow/cards added in Task 7, diagram in Task 8); `build.build(spec, base: Path, out_dir: Path) -> tuple[Path, Path]`; `build.DeckError(PipelineError)`; geometry constants in `draw`: `SLIDE_W=13.333, SLIDE_H=7.5, MARGIN=0.6, BODY_TOP=1.6, BODY_W=SLIDE_W-2*MARGIN, BODY_H=SLIDE_H-BODY_TOP-0.5`.

- [ ] **Step 1: Failing tests `tests/test_deck_build.py`**

```python
"""Properties of a built deck, over every slide of every bundled example."""

from __future__ import annotations

import json

import pytest
from pptx import Presentation

from narratr.deck import animate, script
from narratr.deck.build import build
from narratr.paths import ROOT

SPECS = {
	"brief": ROOT / "examples" / "brief.scenes.json",
	"code": ROOT / "examples" / "code.scenes.json",
	"skill": ROOT / "skills" / "narratr" / "example.scenes.json",
}


@pytest.fixture(scope="module", params=sorted(SPECS))
def built(request, tmp_path_factory):
	path = SPECS[request.param]
	spec = json.loads(path.read_text())
	deck, doc = build(spec, path.parent, tmp_path_factory.mktemp(request.param))
	return spec, Presentation(deck), doc.read_text()


def shape_ids(slide) -> set[int]:
	return {int(e.get("id")) for e in slide._element.iter() if e.tag.endswith("}cNvPr")}


def test_one_slide_per_scene(built):
	spec, prs, _ = built
	assert len(prs.slides) == len(spec["scenes"])


def test_clicks_agree_three_ways(built):
	"""Timing groups, spec reveals and notes markers are the same count."""
	spec, prs, _ = built
	for scene, slide in zip(spec["scenes"], prs.slides, strict=True):
		groups = animate.click_groups(slide._element)
		notes = slide.notes_slide.notes_text_frame.text
		assert len(groups) == len(script.reveals(scene)), scene["id"]
		assert notes.count(script.MARKER) == len(groups), scene["id"]


def test_every_animation_targets_a_shape_on_its_slide(built):
	_, prs, _ = built
	for slide in prs.slides:
		ids = shape_ids(slide)
		for group in animate.click_groups(slide._element):
			assert set(group) <= ids


def test_notes_are_the_narration_with_markers(built):
	spec, prs, _ = built
	for scene, slide in zip(spec["scenes"], prs.slides, strict=True):
		notes = slide.notes_slide.notes_text_frame.text
		assert notes.replace(script.MARKER + " ", "") == scene["narration"]


def test_script_md_matches_the_notes(built):
	spec, prs, doc = built
	for slide in prs.slides:
		assert slide.notes_slide.notes_text_frame.text in doc


def test_headings_are_title_placeholders(built):
	spec, prs, _ = built
	for scene, slide in zip(spec["scenes"], prs.slides, strict=True):
		if scene.get("heading"):
			assert slide.shapes.title is not None, scene["id"]
			assert slide.shapes.title.text_frame.text == scene["heading"]


def test_no_body_text_below_twenty_points(built):
	spec, prs, _ = built
	for scene, slide in zip(spec["scenes"], prs.slides, strict=True):
		if scene["type"] in {"code", "diagram"}:
			continue
		for shape in slide.shapes:
			for e in shape._element.iter():
				if e.tag.endswith("}rPr") and e.get("sz"):
					assert int(e.get("sz")) >= 2000, scene["id"]
```

Run: `uv run pytest tests/test_deck_build.py -q` — Expected: FAIL, `narratr.deck.build` missing.

(Flow, cards and diagram scenes exist in these examples; until Tasks 7–8 land, `build` raises for them. To keep this task's cycle green, Step 6 temporarily runs the tests against a filtered spec — see there.)

- [ ] **Step 2: `render/remotion/scripts/tokens.mjs`**

```js
// Shiki tokens as JSON, for the deck builder.
//
// The deck writes code as coloured text runs so it stays editable, which
// needs tokens rather than HTML. A separate file from highlight.mjs on
// purpose: that one is a renderer source, and touching it re-renders video.
//
// Reads {"code": "...", "lang": "...", "theme": "..."} on stdin, writes
// [[[content, colour], ...], ...] -- one array per line -- on stdout.
import { codeToTokens } from "shiki";

const input = JSON.parse(await new Response(process.stdin).text());

const { tokens } = await codeToTokens(input.code ?? "", {
	lang: input.lang || "text",
	theme: input.theme || "night-owl",
});

process.stdout.write(JSON.stringify(tokens.map((line) => line.map((t) => [t.content, t.color]))));
```

- [ ] **Step 3: `narratr/deck/draw.py`**

```python
"""Drawing primitives shared by every layout. Positions are in inches."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from narratr.deck.theme import rgb

SLIDE_W = 13.333
SLIDE_H = 7.5
MARGIN = 0.6
BODY_TOP = 1.6
BODY_W = SLIDE_W - 2 * MARGIN
BODY_H = SLIDE_H - BODY_TOP - 0.5


def text(
	shapes: Any,
	x: float,
	y: float,
	w: float,
	h: float,
	content: str,
	*,
	size: float,
	colour: str,
	font: str,
	bold: bool = False,
	align: PP_ALIGN = PP_ALIGN.LEFT,
	anchor: MSO_ANCHOR = MSO_ANCHOR.MIDDLE,
	strike: bool = False,
) -> Any:
	box = shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
	frame = box.text_frame
	frame.word_wrap = True
	frame.auto_size = None
	frame.vertical_anchor = anchor
	for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
		setattr(frame, side, Emu(0))
	para = frame.paragraphs[0]
	para.alignment = align
	run = para.add_run()
	run.text = content
	style(run, size=size, colour=colour, font=font, bold=bold, strike=strike)
	return box


def style(
	run: Any, *, size: float, colour: str, font: str, bold: bool = False, strike: bool = False
) -> None:
	run.font.size = Pt(size)
	run.font.bold = bold
	run.font.name = font
	run.font.color.rgb = rgb(colour)
	if strike:
		run.font._rPr.set("strike", "sngStrike")


def panel(
	shapes: Any,
	x: float,
	y: float,
	w: float,
	h: float,
	*,
	fill: str,
	border: str | None = None,
	shape: MSO_SHAPE = MSO_SHAPE.ROUNDED_RECTANGLE,
) -> Any:
	box = shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
	box.fill.solid()
	box.fill.fore_color.rgb = rgb(fill)
	if border:
		box.line.color.rgb = rgb(border)
		box.line.width = Pt(1.5)
	else:
		box.line.fill.background()
	box.shadow.inherit = False
	if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
		box.adjustments[0] = 0.08
	return box


def picture(shapes: Any, data: bytes, x: float, y: float, w: float, h: float) -> Any:
	return shapes.add_picture(BytesIO(data), Inches(x), Inches(y), Inches(w), Inches(h))


def arrow(shapes: Any, x1: float, y1: float, x2: float, y2: float, *, colour: str) -> Any:
	from pptx.enum.shapes import MSO_CONNECTOR

	line = shapes.add_connector(
		MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
	)
	arrowhead(line, colour)
	return line


def arrowhead(connector: Any, colour: str) -> None:
	connector.line.color.rgb = rgb(colour)
	connector.line.width = Pt(2)
	ln = connector.line._get_or_add_ln()
	tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
	ln.append(tail)


def fit(img_w: int, img_h: int, x: float, y: float, w: float, h: float) -> tuple[float, ...]:
	"""Largest box of the image's aspect inside (x, y, w, h), centred."""
	scale = min(w / img_w, h / img_h)
	fw, fh = img_w * scale, img_h * scale
	return x + (w - fw) / 2, y + (h - fh) / 2, fw, fh
```

- [ ] **Step 4: `narratr/deck/layout.py` (prose, section, code, image)**

```python
"""One function per scene shape. Each draws its slide and returns the click
groups: lists of shape ids, one list per reveal, in reveal order."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

from narratr import images
from narratr.deck import glyphs
from narratr.deck.draw import BODY_H, BODY_TOP, BODY_W, MARGIN, fit, panel, picture, style, text
from narratr.deck.theme import Theme
from narratr.errors import PipelineError
from narratr.render import REMOTION

# Slides rejects very large images on import.
MAX_IMAGE_BYTES = 2 * 1024 * 1024


class LayoutError(PipelineError):
	"""A slide could not be drawn."""


@dataclass(frozen=True)
class Ctx:
	theme: Theme
	base: Path
	tmp: Path


Layout = Callable[[Any, dict[str, Any], Ctx], list[list[int]]]


def image_bytes(raw: str, base: Path) -> tuple[bytes, int, int]:
	"""The image as it goes into the deck, plus its pixel size.

	Over 2 MB it is downscaled to 2560 px on the long side, and if that is not
	enough and it has no transparency, re-encoded as JPEG. GIFs pass through:
	resizing one drops every frame but the first. The source is never touched.
	"""
	path = images.resolve(raw, base)
	data = path.read_bytes()
	with Image.open(path) as img:
		size = img.size
		if len(data) <= MAX_IMAGE_BYTES or img.format == "GIF":
			return data, *size
		img.thumbnail((2560, 2560))
		out = BytesIO()
		img.save(out, format=img.format)
		if out.tell() > MAX_IMAGE_BYTES and img.mode in {"RGB", "L"}:
			out = BytesIO()
			img.convert("RGB").save(out, format="JPEG", quality=85)
		return out.getvalue(), *img.size


def prose(slide: Any, scene: dict[str, Any], ctx: Ctx) -> list[list[int]]:
	theme = ctx.theme
	bullets = scene.get("bullets") or []
	width = BODY_W
	if scene.get("image"):
		width = BODY_W * 0.55
		data, iw, ih = image_bytes(scene["image"], ctx.base)
		x0 = MARGIN + width + 0.4
		picture(slide.shapes, data, *fit(iw, ih, x0, BODY_TOP, BODY_W - width - 0.4, BODY_H))
	if not bullets:
		return []
	row = min(0.95, BODY_H / len(bullets))
	top = BODY_TOP + (BODY_H - row * len(bullets)) / 2
	groups: list[list[int]] = []
	for i, bullet in enumerate(bullets):
		struck = bullet.get("state") == "struck"
		y = top + i * row
		group = slide.shapes.add_group_shape()
		indent = 0.0
		if bullet.get("icon"):
			colour = theme.muted if struck else theme.accent(i)
			picture(
				group.shapes,
				glyphs.png(bullet["icon"], colour),
				MARGIN,
				y + (row - 0.5) / 2,
				0.5,
				0.5,
			)
			indent = 0.75
		text(
			group.shapes,
			MARGIN + indent,
			y,
			width - indent,
			row,
			bullet["text"],
			size=26,
			colour=theme.muted if struck else theme.text,
			font=theme.body_font,
			strike=struck,
		)
		groups.append([group.shape_id])
	return groups


def code(slide: Any, scene: dict[str, Any], ctx: Ctx) -> list[list[int]]:
	theme = ctx.theme
	payload = json.dumps(
		{
			"code": scene["code"],
			"lang": scene.get("lang") or "text",
			"theme": "github-light" if theme.is_light else "night-owl",
		}
	)
	result = subprocess.run(
		["node", "scripts/tokens.mjs"],
		cwd=REMOTION,
		input=payload,
		capture_output=True,
		text=True,
		timeout=120,
	)
	if result.returncode != 0:
		tail = (result.stderr or result.stdout).strip().splitlines()[-4:]
		raise LayoutError("code highlighting failed:\n  " + "\n  ".join(tail))
	lines: list[list[list[str]]] = json.loads(result.stdout)
	longest = max((sum(len(t[0]) for t in line) for line in lines), default=1) or 1
	pad = 0.3
	size = max(
		12.0,
		min(
			24.0,
			(BODY_H - 2 * pad) * 72 / (len(lines) * 1.25),
			(BODY_W - 2 * pad) * 72 / (longest * 0.62),
		),
	)
	panel(slide.shapes, MARGIN, BODY_TOP, BODY_W, BODY_H, fill=theme.panel)
	box = text(
		slide.shapes,
		MARGIN + pad,
		BODY_TOP + pad,
		BODY_W - 2 * pad,
		BODY_H - 2 * pad,
		"",
		size=size,
		colour=theme.text,
		font=theme.mono_font,
		anchor=MSO_ANCHOR.TOP,
	)
	frame = box.text_frame
	for n, line in enumerate(lines):
		para = frame.paragraphs[0] if n == 0 else frame.add_paragraph()
		for content, colour in line or [[" ", theme.text]]:
			run = para.add_run()
			run.text = content
			style(run, size=size, colour=colour or theme.text, font=theme.mono_font)
	return []


def image(slide: Any, scene: dict[str, Any], ctx: Ctx) -> list[list[int]]:
	data, iw, ih = image_bytes(scene["image"], ctx.base)
	caption = scene.get("caption")
	height = BODY_H - (0.7 if caption else 0)
	picture(slide.shapes, data, *fit(iw, ih, MARGIN, BODY_TOP, BODY_W, height))
	if caption:
		text(
			slide.shapes,
			MARGIN,
			BODY_TOP + height + 0.1,
			BODY_W,
			0.6,
			caption,
			size=20,
			colour=ctx.theme.muted,
			font=ctx.theme.body_font,
			align=PP_ALIGN.CENTER,
		)
	return []


LAYOUTS: dict[str, Layout] = {"prose": prose, "code": code, "image": image}
```

Note: the `code` scene's `text(...)` creates one empty run first; `frame.paragraphs[0]` already holds it. Clear it before adding token runs: after `frame = box.text_frame`, add `frame.paragraphs[0].runs[0]._r.getparent().remove(frame.paragraphs[0].runs[0]._r)`.

- [ ] **Step 5: `narratr/deck/build.py`**

```python
"""scenes.json -> deck.pptx + script.md."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from lxml import etree
from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from narratr.deck import animate, script
from narratr.deck.draw import MARGIN, SLIDE_H, SLIDE_W
from narratr.deck.layout import LAYOUTS, Ctx
from narratr.deck.theme import Theme, resolve, rgb
from narratr.errors import PipelineError

# python-pptx's default template: 0 is "Title Slide", 5 is "Title Only".
SECTION_LAYOUT = 0
CONTENT_LAYOUT = 5


class DeckError(PipelineError):
	"""The deck could not be built."""


def _theme_fonts(prs: Any, theme: Theme) -> None:
	"""Point the theme's major/minor fonts at ours, so new text a person adds
	by hand in Slides or PowerPoint matches what was generated."""
	part = prs.slide_master.part.part_related_by(RT.THEME)
	root = etree.fromstring(part.blob)
	for which, font in (("a:majorFont", theme.heading_font), ("a:minorFont", theme.body_font)):
		latin = root.find(f".//{qn(which)}/{qn('a:latin')}")
		if latin is not None:
			latin.set("typeface", font)
	part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _master(prs: Any, theme: Theme) -> None:
	prs.slide_width, prs.slide_height = Inches(SLIDE_W), Inches(SLIDE_H)
	master = prs.slide_master
	master.background.fill.solid()
	master.background.fill.fore_color.rgb = rgb(theme.background)
	_theme_fonts(prs, theme)


def _heading(slide: Any, scene: dict[str, Any], theme: Theme, section: bool) -> None:
	title = slide.shapes.title
	heading = scene.get("heading")
	# Unused placeholders show "Click to add title" in an editor.
	for ph in list(slide.placeholders):
		if ph is not title or not heading:
			ph._element.getparent().remove(ph._element)
	if not heading:
		return
	if section:
		title.left, title.top, title.width, title.height = (
			Inches(MARGIN),
			Inches(2.5),
			Inches(SLIDE_W - 2 * MARGIN),
			Inches(2.5),
		)
	else:
		title.left, title.top, title.width, title.height = (
			Inches(MARGIN),
			Inches(0.4),
			Inches(SLIDE_W - 2 * MARGIN),
			Inches(1.0),
		)
	frame = title.text_frame
	frame.text = heading
	para = frame.paragraphs[0]
	para.alignment = PP_ALIGN.CENTER if section else PP_ALIGN.LEFT
	run = para.runs[0]
	run.font.size = Pt(60 if section else 40)
	run.font.bold = True
	run.font.name = theme.heading_font
	run.font.color.rgb = rgb(theme.text)


def is_section(scene: dict[str, Any]) -> bool:
	return scene["type"] == "prose" and not scene.get("bullets") and not scene.get("image")


def build(spec: dict[str, Any], base: Path, out_dir: Path) -> tuple[Path, Path]:
	theme = resolve(spec)
	prs = Presentation()
	_master(prs, theme)
	with tempfile.TemporaryDirectory() as tmp:
		ctx = Ctx(theme=theme, base=base, tmp=Path(tmp))
		for scene in spec["scenes"]:
			section = is_section(scene)
			slide = prs.slides.add_slide(
				prs.slide_layouts[SECTION_LAYOUT if section else CONTENT_LAYOUT]
			)
			_heading(slide, scene, theme, section)
			draw = LAYOUTS.get(scene["type"])
			if draw is None:
				raise DeckError(f"scene '{scene['id']}': no deck layout for '{scene['type']}'")
			groups = draw(slide, scene, ctx)
			# The invariant every test leans on, checked on every build rather
			# than only on the examples.
			if len(groups) != len(script.reveals(scene)):
				raise DeckError(
					f"scene '{scene['id']}': {len(groups)} click groups for "
					f"{len(script.reveals(scene))} cues"
				)
			animate.apply(slide, groups)
			slide.notes_slide.notes_text_frame.text = script.marked(scene)
	out_dir.mkdir(parents=True, exist_ok=True)
	deck, doc = out_dir / "deck.pptx", out_dir / "script.md"
	prs.save(deck)
	doc.write_text(script.document(spec))
	return deck, doc
```

- [ ] **Step 6: CLI**

In `narratr/cli.py`: import `DECKS` from `narratr.paths`. Add:

```python
def cmd_deck(args: argparse.Namespace) -> int:
	"""Build a presentation. Seconds, not minutes: no detach, no manifest."""
	from narratr.deck.build import build  # python-pptx is not needed to render video

	spec = load_spec(args.scenes)
	base = args.scenes.resolve().parent
	problems = validate(spec, base=base)
	if problems:
		print("❌ Refusing to build an invalid spec:")
		for problem in problems:
			print(f"  - {problem}")
		return 1
	for warning in warnings(spec):
		print(f"⚠️  {warning}")
	out = args.out or DECKS / safe_name(spec["source"]["title"])
	deck, doc = build(spec, base, out)
	print(f"✓ {deck}")
	print(f"✓ {doc}")
	return 0
```

Parser: `deck_cmd = sub.add_parser("deck", help="build a .pptx deck and speaker script")`, `deck_cmd.add_argument("scenes", type=Path)`, `deck_cmd.add_argument("--out", type=Path, help="output directory; default decks/<title>")`. Add `"deck": cmd_deck` to `handlers`.

To keep this task green before flow/cards/diagram exist, temporarily add at the top of `tests/test_deck_build.py`'s `built` fixture: `spec["scenes"] = [s for s in spec["scenes"] if s["type"] in LAYOUTS]` with `from narratr.deck.layout import LAYOUTS`, and remove that line in Task 8. Also gate `test_one_slide_per_scene` accordingly (it compares against the filtered `spec`, so it holds).

- [ ] **Step 7: Run tests and a real build**

Run: `uv run pytest tests/test_deck_build.py -q && uv run mypy narratr/ && uv run narratr deck examples/code.scenes.json --out /tmp/narratr-code-deck`
Expected: tests PASS; CLI prints two ✓ paths. Open the pptx in Keynote (`open -a Keynote ...`) and look at the code and prose slides.

- [ ] **Step 8: Commit**

```bash
git add narratr/deck render/remotion/scripts/tokens.mjs narratr/cli.py tests/test_deck_build.py
git commit -m "Build decks: master, headings, prose, code and image slides, narratr deck"
```

---

### Task 7: Flow and cards slides

**Files:**
- Modify: `narratr/deck/layout.py`

**Interfaces:** Adds `layout.flow`, `layout.cards`; `LAYOUTS` gains `"flow"`, `"cards"`.

- [ ] **Step 1: Failing test — extend `tests/test_deck_build.py`**

```python
def test_cards_and_steps_are_one_group_each(built):
	"""A card or step fades in whole, so each click targets one group shape."""
	spec, prs, _ = built
	for scene, slide in zip(spec["scenes"], prs.slides, strict=True):
		if scene["type"] not in {"flow", "cards"}:
			continue
		groups = animate.click_groups(slide._element)
		by_id = {s.shape_id: s for s in slide.shapes}
		for group in groups:
			kinds = {by_id[i].shape_type for i in group}
			from pptx.enum.shapes import MSO_SHAPE_TYPE

			assert MSO_SHAPE_TYPE.GROUP in kinds, scene["id"]
```

Run: `uv run pytest tests/test_deck_build.py -q` — Expected: no flow/cards slides yet (filtered), so the test is vacuous; it must fail once the filter allows them. Add `"flow"` and `"cards"` to `LAYOUTS` as `None` placeholders? No — instead implement Step 2 directly and confirm the test then exercises real slides (assert at least one flow and one cards slide was checked across params by adding a module-level counter is overkill; check by running `-k cards -v` and seeing the brief/skill params execute assertions).

- [ ] **Step 2: Implement in `layout.py`**

```python
def flow(slide: Any, scene: dict[str, Any], ctx: Ctx) -> list[list[int]]:
	theme = ctx.theme
	steps = scene["steps"]
	n = len(steps)
	gap = 0.7
	tile_w = min(2.4, (BODY_W - gap * (n - 1)) / n)
	tile_h = 2.4
	total = tile_w * n + gap * (n - 1)
	left = MARGIN + (BODY_W - total) / 2
	footer_h = 0.9 if scene.get("footer") else 0
	top = BODY_TOP + (BODY_H - footer_h - tile_h) / 2
	groups: list[list[int]] = []
	for i, step in enumerate(steps):
		x = left + i * (tile_w + gap)
		group = slide.shapes.add_group_shape()
		panel(group.shapes, x, top, tile_w, tile_h, fill=theme.panel, border=theme.accent(i))
		picture(
			group.shapes,
			glyphs.png(step["icon"], theme.accent(i)),
			x + (tile_w - 0.9) / 2,
			top + 0.35,
			0.9,
			0.9,
		)
		text(
			group.shapes,
			x + 0.1,
			top + 1.35,
			tile_w - 0.2,
			tile_h - 1.45,
			step["label"],
			size=24,
			colour=theme.text,
			font=theme.body_font,
			bold=True,
			align=PP_ALIGN.CENTER,
			anchor=MSO_ANCHOR.TOP,
		)
		ids = [group.shape_id]
		if i:
			line = arrow(
				slide.shapes,
				x - gap + 0.1,
				top + tile_h / 2,
				x - 0.1,
				top + tile_h / 2,
				colour=theme.line,
			)
			ids.append(line.shape_id)
		groups.append(ids)
	footer = scene.get("footer")
	if footer:
		y = BODY_TOP + BODY_H - footer_h
		panel(slide.shapes, left, y, total, footer_h - 0.1, fill=theme.panel)
		picture(
			slide.shapes, glyphs.png(footer["icon"], theme.muted), left + 0.25, y + 0.15, 0.5, 0.5
		)
		text(
			slide.shapes,
			left + 0.95,
			y,
			total - 1.2,
			footer_h - 0.1,
			footer["label"],
			size=22,
			colour=theme.muted,
			font=theme.body_font,
		)
	return groups


def cards(slide: Any, scene: dict[str, Any], ctx: Ctx) -> list[list[int]]:
	theme = ctx.theme
	items = scene["cards"]
	n = len(items)
	gap = 0.4
	w = (BODY_W - gap * (n - 1)) / n
	h = BODY_H
	groups: list[list[int]] = []
	for i, card in enumerate(items):
		x = MARGIN + i * (w + gap)
		y = BODY_TOP
		group = slide.shapes.add_group_shape()
		panel(group.shapes, x, y, w, h, fill=theme.panel)
		panel(group.shapes, x, y, w, 0.08, fill=theme.accent(i), shape=MSO_SHAPE.RECTANGLE)
		cursor = y + 0.4
		if card.get("icon"):
			picture(
				group.shapes, glyphs.png(card["icon"], theme.accent(i)), x + 0.35, cursor, 0.7, 0.7
			)
			cursor += 0.95
		text(
			group.shapes,
			x + 0.35,
			cursor,
			w - 0.7,
			1.1,
			card["title"],
			size=26,
			colour=theme.text,
			font=theme.heading_font,
			bold=True,
			anchor=MSO_ANCHOR.TOP,
		)
		cursor += 1.15
		if card.get("detail"):
			text(
				group.shapes,
				x + 0.35,
				cursor,
				w - 0.7,
				1.0,
				card["detail"],
				size=20,
				colour=theme.muted,
				font=theme.body_font,
				anchor=MSO_ANCHOR.TOP,
			)
			cursor += 1.05
		if card.get("image"):
			data, iw, ih = image_bytes(card["image"], ctx.base)
			picture(
				group.shapes, data, *fit(iw, ih, x + 0.25, cursor, w - 0.5, y + h - 0.25 - cursor)
			)
		groups.append([group.shape_id])
	return groups
```

Add imports: `from pptx.enum.shapes import MSO_SHAPE` and `arrow` from `draw`. Extend `LAYOUTS` with `"flow": flow, "cards": cards`.

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_deck_build.py -q -k "cards or clicks or targets" -v && uv run mypy narratr/`
Expected: PASS, with brief and skill params running against real flow/cards slides.

- [ ] **Step 4: Commit**

```bash
git add narratr/deck/layout.py tests/test_deck_build.py
git commit -m "Draw flow and cards slides, one fading group per step or card"
```

---

### Task 8: Native diagrams

**Files:**
- Create: `narratr/deck/diagram.py`, `tests/test_deck_diagram.py`
- Modify: `narratr/deck/layout.py` (register), `tests/test_deck_build.py` (drop the temporary filter)

**Interfaces:**
- Consumes: `render.mermaid_to_svg(source, out) -> str`, `render.inline_mermaid_icons`, `render.run_remotion`, `render.REMOTION`, `spec.is_flowchart`, `icons.mermaid_names_in` regex `render.ICON_NODE`/`ICON_FIELD`.
- Produces: `diagram.parse(svg: str) -> Layout` with dataclasses `Node(id, cx, cy, w, h, label, kind, dim)`, `Edge(src, dst, label, label_box: tuple[float, float, float, float] | None)`, `Cluster(label, x, y, w, h)`, `Layout(width, height, nodes: dict[str, Node], edges: list[Edge], clusters: list[Cluster])`; `diagram.draw(slide, scene, ctx) -> list[list[int]]`. Native shapes are named `node:<id>` and `edge:<src>-><dst>`.

- [ ] **Step 1: Failing tests `tests/test_deck_diagram.py`**

```python
"""A flowchart becomes native shapes: one per node, one glued connector per edge."""

from __future__ import annotations

import json
import re

import pytest
from pptx import Presentation

from narratr.deck import animate
from narratr.deck.build import build
from narratr.paths import ROOT
from narratr.spec import is_flowchart

SPECS = [
	ROOT / "examples" / "brief.scenes.json",
	ROOT / "skills" / "narratr" / "example.scenes.json",
]
EDGE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*-->(?:\|[^|]*\|)?\s*([A-Za-z0-9_]+)", re.M)


def diagram_slides():
	for path in SPECS:
		spec = json.loads(path.read_text())
		for index, scene in enumerate(spec["scenes"]):
			if scene["type"] == "diagram" and is_flowchart(scene["mermaid"]):
				yield pytest.param(path, index, id=f"{path.stem}:{scene['id']}")


@pytest.fixture(scope="module")
def decks(tmp_path_factory):
	out = {}
	for path in SPECS:
		spec = json.loads(path.read_text())
		deck, _ = build(spec, path.parent, tmp_path_factory.mktemp(path.stem))
		out[path] = (spec, Presentation(deck))
	return out


@pytest.mark.parametrize(("path", "index"), list(diagram_slides()))
def test_every_node_is_exactly_one_shape(decks, path, index):
	spec, prs = decks[path]
	scene, slide = spec["scenes"][index], prs.slides[index]
	ids = set(re.findall(r"^\s*([A-Za-z0-9_]+)(?:@\{|\[|\(|\{)", scene["mermaid"], re.M))
	names = [s.name for s in slide.shapes if s.name.startswith("node:")]
	assert sorted(names) == sorted(f"node:{i}" for i in ids)


@pytest.mark.parametrize(("path", "index"), list(diagram_slides()))
def test_every_edge_is_a_connector_glued_to_its_nodes(decks, path, index):
	spec, prs = decks[path]
	scene, slide = spec["scenes"][index], prs.slides[index]
	by_name = {s.name: s for s in slide.shapes}
	for src, dst in EDGE.findall(scene["mermaid"]):
		edge = by_name[f"edge:{src}->{dst}"]
		xml = edge._element
		start = xml.find(".//{*}stCxn").get("id")
		end = xml.find(".//{*}endCxn").get("id")
		assert int(start) == by_name[f"node:{src}"].shape_id
		assert int(end) == by_name[f"node:{dst}"].shape_id


@pytest.mark.parametrize(("path", "index"), list(diagram_slides()))
def test_a_reveal_step_is_one_click_and_brings_its_edges(decks, path, index):
	spec, prs = decks[path]
	scene, slide = spec["scenes"][index], prs.slides[index]
	by_id = {s.shape_id: s.name for s in slide.shapes}
	groups = animate.click_groups(slide._element)
	assert len(groups) == len(scene["revealSteps"])
	beat = {n: i for i, step in enumerate(scene["revealSteps"]) for n in step}
	for i, group in enumerate(groups):
		names = {by_id[s] for s in group}
		assert {f"node:{n}" for n in scene["revealSteps"][i]} <= names
		for src, dst in EDGE.findall(scene["mermaid"]):
			if max(beat.get(src, -1), beat.get(dst, -1)) == i:
				assert f"edge:{src}->{dst}" in names


def test_a_sequence_diagram_is_one_static_picture(tmp_path):
	spec = json.loads(SPECS[0].read_text())
	scene = next(s for s in spec["scenes"] if s["type"] == "diagram")
	scene["mermaid"] = "sequenceDiagram\n    A->>B: hello"
	deck, _ = build(spec, SPECS[0].parent, tmp_path)
	slide = Presentation(deck).slides[spec["scenes"].index(scene)]
	assert animate.click_groups(slide._element) == []
	assert any(s.shape_type == 13 for s in slide.shapes)  # PICTURE
```

Run: `uv run pytest tests/test_deck_diagram.py -q` — Expected: FAIL (`no deck layout for 'diagram'`).

- [ ] **Step 2: Implement `narratr/deck/diagram.py`**

```python
"""Mermaid flowcharts as native, editable shapes.

Mermaid still does the layout: mmdc renders the SVG exactly as the video does,
and this reads node boxes, edges and clusters back out of it. Each node becomes
a real shape, each edge a straight connector glued to the two nodes' facing
sides -- so a person can drag a node in Slides and its edges follow.

Anything that is not a flowchart is shown as one picture, with no clicks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from lxml import etree
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches

from narratr.deck import glyphs
from narratr.deck.draw import BODY_H, BODY_TOP, BODY_W, MARGIN, arrowhead, fit, panel, picture, text
from narratr.deck.layout import Ctx
from narratr.render import (
	ICON_FIELD,
	ICON_NODE,
	REMOTION,
	inline_mermaid_icons,
	mermaid_to_svg,
	run_remotion,
)
from narratr.spec import is_flowchart

SVG = "{http://www.w3.org/2000/svg}"
TRANSLATE = re.compile(r"translate\(\s*([-\d.e]+)[ ,]+([-\d.e]+)\s*\)")
# Largest scale, inches per SVG unit: Mermaid's 20px font at 0.025 in/px is
# 36 pt. Past this a two-node diagram fills the slide with giant boxes.
MAX_SCALE = 0.025


@dataclass
class Node:
	id: str
	cx: float
	cy: float
	w: float
	h: float
	label: str
	kind: str  # "rect" | "diamond"
	dim: bool


@dataclass
class Edge:
	src: str
	dst: str
	label: str
	label_box: tuple[float, float, float, float] | None  # cx, cy, w, h


@dataclass
class Cluster:
	label: str
	x: float
	y: float
	w: float
	h: float


@dataclass
class Layout:
	width: float
	height: float
	nodes: dict[str, Node]
	edges: list[Edge]
	clusters: list[Cluster]


def _offset(element: Any) -> tuple[float, float]:
	"""Sum of every translate() from the element up to the root."""
	x = y = 0.0
	while element is not None:
		match = TRANSLATE.search(element.get("transform") or "")
		if match:
			x += float(match.group(1))
			y += float(match.group(2))
		element = element.getparent()
	return x, y


def _text(element: Any) -> str:
	return " ".join("".join(element.itertext()).split())


def _classes(element: Any) -> list[str]:
	return (element.get("class") or "").split()


def _split_edge(data_id: str, known: set[str]) -> tuple[str, str] | None:
	"""`L_<from>_<to>_<n>`, where node ids may themselves contain underscores."""
	body = re.sub(r"_\d+$", "", data_id.removeprefix("L_"))
	parts = body.split("_")
	for cut in range(1, len(parts)):
		src, dst = "_".join(parts[:cut]), "_".join(parts[cut:])
		if src in known and dst in known:
			return src, dst
	return None


def parse(svg: str) -> Layout:
	root = etree.fromstring(svg.encode())
	_, _, width, height = (float(v) for v in root.get("viewBox").split())
	prefix = f"{root.get('id')}-flowchart-"

	nodes: dict[str, Node] = {}
	for g in root.iter(f"{SVG}g"):
		gid = g.get("id") or ""
		if "node" not in _classes(g) or not gid.startswith(prefix):
			continue
		node_id = gid[len(prefix) :].rsplit("-", 1)[0]
		ox, oy = _offset(g)
		shape = next((c for c in g if c.tag in {f"{SVG}rect", f"{SVG}polygon"}), None)
		kind = "rect"
		w = h = 0.0
		cx, cy = ox, oy
		if shape is not None and shape.tag == f"{SVG}rect":
			x, y = float(shape.get("x", 0)), float(shape.get("y", 0))
			w, h = float(shape.get("width", 0)), float(shape.get("height", 0))
			cx, cy = ox + x + w / 2, oy + y + h / 2
		elif shape is not None:
			points = [tuple(map(float, p.split(","))) for p in shape.get("points", "").split()]
			xs, ys = [p[0] for p in points], [p[1] for p in points]
			w, h = max(xs) - min(xs), max(ys) - min(ys)
			sx, sy = _offset(shape)
			cx, cy = sx + min(xs) + w / 2, sy + min(ys) + h / 2
			kind = "diamond" if len(points) == 4 else "rect"
		label = next((_text(s) for s in g.iter() if "nodeLabel" in _classes(s)), node_id)
		nodes[node_id] = Node(node_id, cx, cy, w, h, label, kind, "dim" in _classes(g))

	labels: dict[str, tuple[str, tuple[float, float, float, float]]] = {}
	for g in root.iter(f"{SVG}g"):
		if "label" in _classes(g) and g.get("data-id") and _text(g):
			fo = g.find(f"{SVG}foreignObject")
			ox, oy = _offset(g)
			w = float(fo.get("width", 0)) if fo is not None else 0.0
			h = float(fo.get("height", 0)) if fo is not None else 0.0
			labels[g.get("data-id")] = (_text(g), (ox + w / 2, oy + h / 2, w, h))

	edges: list[Edge] = []
	known = set(nodes)
	for path in root.iter(f"{SVG}path"):
		if "flowchart-link" not in _classes(path):
			continue
		data_id = path.get("data-id") or ""
		ends = _split_edge(data_id, known)
		if ends is None:
			continue
		text_, box = labels.get(data_id, ("", None))
		edges.append(Edge(ends[0], ends[1], text_, box))

	clusters: list[Cluster] = []
	for g in root.iter(f"{SVG}g"):
		if "cluster" not in _classes(g):
			continue
		rect = g.find(f"{SVG}rect")
		if rect is None:
			continue
		ox, oy = _offset(g)
		label = next((_text(s) for s in g.iter() if "cluster-label" in _classes(s)), "")
		clusters.append(
			Cluster(
				label,
				ox + float(rect.get("x", 0)),
				oy + float(rect.get("y", 0)),
				float(rect.get("width", 0)),
				float(rect.get("height", 0)),
			)
		)
	return Layout(width, height, nodes, edges, clusters)


def _icons(source: str) -> dict[str, str]:
	found: dict[str, str] = {}
	for match in ICON_NODE.finditer(source):
		icon = ICON_FIELD.search(match.group("body"))
		if icon:
			found[match.group("id")] = icon.group("name")
	return found


def _font_px(source: str) -> float:
	match = re.search(r"fontSize:\s*(\d+)", source)
	return float(match.group(1)) if match else 20.0


# Connection sites python-pptx knows for rectangles and diamonds.
TOP, LEFT, BOTTOM, RIGHT = 0, 1, 2, 3


def _sides(a: Node, b: Node) -> tuple[int, int]:
	dx, dy = b.cx - a.cx, b.cy - a.cy
	if abs(dx) >= abs(dy):
		return (RIGHT, LEFT) if dx >= 0 else (LEFT, RIGHT)
	return (BOTTOM, TOP) if dy >= 0 else (TOP, BOTTOM)


def _picture(slide: Any, scene: dict[str, Any], ctx: Ctx) -> list[list[int]]:
	"""Non-flowcharts: mmdc's own PNG, themed to the deck, shown whole."""
	theme = ctx.theme
	config = ctx.tmp / "deck-mermaid.json"
	config.write_text(
		json.dumps(
			{
				"theme": "base",
				"securityLevel": "strict",
				"themeVariables": {
					"darkMode": not theme.is_light,
					"background": theme.background,
					"mainBkg": theme.panel,
					"primaryColor": theme.panel,
					"primaryTextColor": theme.text,
					"primaryBorderColor": theme.line,
					"lineColor": theme.line,
					"textColor": theme.text,
					"fontFamily": theme.body_font,
					"fontSize": "20px",
				},
			}
		)
	)
	mmd = ctx.tmp / f"{scene['id']}.mmd"
	png = ctx.tmp / f"{scene['id']}.png"
	mmd.write_text(inline_mermaid_icons(scene["mermaid"]))
	run_remotion(
		[
			"npx",
			"--no-install",
			"mmdc",
			"-i",
			str(mmd),
			"-o",
			str(png),
			"-b",
			"transparent",
			"-c",
			str(config),
			"-s",
			"3",
		],
		REMOTION,
		"mermaid",
	)
	from PIL import Image

	with Image.open(png) as img:
		iw, ih = img.size
	picture(slide.shapes, png.read_bytes(), *fit(iw, ih, MARGIN, BODY_TOP, BODY_W, BODY_H))
	return []


def draw(slide: Any, scene: dict[str, Any], ctx: Ctx) -> list[list[int]]:
	source = scene["mermaid"]
	if not is_flowchart(source):
		return _picture(slide, scene, ctx)
	theme = ctx.theme
	layout = parse(mermaid_to_svg(source, ctx.tmp / f"{scene['id']}.svg"))
	scale = min(BODY_W / layout.width, BODY_H / layout.height, MAX_SCALE)
	ox = MARGIN + (BODY_W - layout.width * scale) / 2
	oy = BODY_TOP + (BODY_H - layout.height * scale) / 2
	font = max(12.0, min(32.0, _font_px(source) * scale * 72))
	icons_by_node = _icons(source)

	def at(x: float, y: float) -> tuple[float, float]:
		return ox + x * scale, oy + y * scale

	for cluster in layout.clusters:
		x, y = at(cluster.x, cluster.y)
		panel(
			slide.shapes,
			x,
			y,
			cluster.w * scale,
			cluster.h * scale,
			fill=theme.background,
			border=theme.line,
		)
		if cluster.label:
			text(
				slide.shapes,
				x + 0.1,
				y + 0.05,
				cluster.w * scale - 0.2,
				0.4,
				cluster.label,
				size=max(12.0, font * 0.8),
				colour=theme.muted,
				font=theme.body_font,
			)

	beat = {n: i for i, step in enumerate(scene.get("revealSteps", [])) for n in step}
	groups: list[list[int]] = [[] for _ in scene.get("revealSteps", [])]
	shapes: dict[str, Any] = {}
	for index, node in enumerate(layout.nodes.values()):
		x, y = at(node.cx - node.w / 2, node.cy - node.h / 2)
		w, h = node.w * scale, node.h * scale
		border = theme.line if node.dim else theme.accent(index)
		box = panel(
			slide.shapes,
			x,
			y,
			w,
			h,
			fill=theme.panel,
			border=border,
			shape=MSO_SHAPE.DIAMOND if node.kind == "diamond" else MSO_SHAPE.ROUNDED_RECTANGLE,
		)
		box.name = f"node:{node.id}"
		shapes[node.id] = box
		members = [box.shape_id]
		icon = icons_by_node.get(node.id)
		inset = 0.0
		if icon:
			size = min(h * 0.5, font / 72 * 1.2)
			glyph = picture(
				slide.shapes, glyphs.png(icon, border), x + 0.12, y + (h - size) / 2, size, size
			)
			members.append(glyph.shape_id)
			inset = size + 0.12
		label = text(
			slide.shapes,
			x + inset + 0.08,
			y,
			w - inset - 0.16,
			h,
			node.label,
			size=font,
			colour=theme.muted if node.dim else theme.text,
			font=theme.body_font,
			align=PP_ALIGN.CENTER,
		)
		members.append(label.shape_id)
		if node.id in beat:
			groups[beat[node.id]] += members

	for edge in layout.edges:
		a, b = layout.nodes[edge.src], layout.nodes[edge.dst]
		start, end = _sides(a, b)
		line = slide.shapes.add_connector(
			MSO_CONNECTOR.STRAIGHT, Inches(0), Inches(0), Inches(1), Inches(1)
		)
		line.begin_connect(shapes[edge.src], start)
		line.end_connect(shapes[edge.dst], end)
		arrowhead(line, theme.line)
		line.name = f"edge:{edge.src}->{edge.dst}"
		members = [line.shape_id]
		if edge.label and edge.label_box:
			cx, cy, w, h = edge.label_box
			x, y = at(cx - w / 2, cy - h / 2)
			caption = text(
				slide.shapes,
				x,
				y,
				w * scale,
				h * scale,
				edge.label,
				size=max(12.0, font * 0.8),
				colour=theme.muted,
				font=theme.body_font,
				align=PP_ALIGN.CENTER,
			)
			members.append(caption.shape_id)
		when = max(beat.get(edge.src, -1), beat.get(edge.dst, -1))
		if when >= 0:
			groups[when] += members
	return groups
```

In `layout.py` the diagram module imports `Ctx` from `layout`, so register it from `build.py` instead to avoid a cycle: in `build.py` after importing `LAYOUTS`, add

```python
from narratr.deck import diagram

LAYOUTS["diagram"] = diagram.draw
```

Remove the temporary scene filter from `tests/test_deck_build.py`.

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_deck_diagram.py tests/test_deck_build.py -q && uv run mypy narratr/`
Expected: PASS. If `test_every_node_is_exactly_one_shape` fails on a subgraph example, inspect the SVG (`mermaid_to_svg` output in a scratch dir) and fix the `prefix`/offset logic, not the test.

- [ ] **Step 4: Commit**

```bash
git add narratr/deck tests/test_deck_diagram.py tests/test_deck_build.py
git commit -m "Rebuild flowcharts as native nodes and glued connectors"
```

---

### Task 9: The presentation skill and its example

**Files:**
- Create: `skills/presentation/SKILL.md`, `skills/presentation/shapes.md` (symlink), `skills/presentation/example.scenes.json`, `skills/presentation/example-image.png`, `tests/test_presentation_skill.py`
- Modify: `README.md` (a "Presentations" section)

**Interfaces:** Consumes `narratr deck`, `narratr validate`, `narratr blocks`, `narratr icons`.

- [ ] **Step 1: Failing test `tests/test_presentation_skill.py`**

```python
"""The presentation skill's own example is what Claude copies for a deck."""

from __future__ import annotations

import json

from pptx import Presentation

from narratr.deck.build import build
from narratr.paths import ROOT
from narratr.spec import validate

SKILL = ROOT / "skills" / "presentation"
EXAMPLE = SKILL / "example.scenes.json"


def test_the_guide_is_shared_not_copied():
	guide = SKILL / "shapes.md"
	assert guide.is_symlink()
	assert guide.resolve() == (ROOT / "skills" / "narratr" / "shapes.md").resolve()


def test_the_example_validates_with_its_images():
	spec = json.loads(EXAMPLE.read_text())
	assert validate(spec, base=SKILL) == []


def test_the_example_shows_a_theme_and_both_image_uses():
	spec = json.loads(EXAMPLE.read_text())
	assert spec.get("theme")
	assert any(s["type"] == "image" for s in spec["scenes"])
	assert any(s["type"] == "prose" and s.get("image") for s in spec["scenes"])


def test_the_example_builds(tmp_path):
	spec = json.loads(EXAMPLE.read_text())
	deck, doc = build(spec, SKILL, tmp_path)
	assert len(Presentation(deck).slides) == len(spec["scenes"])
	assert doc.read_text().startswith("# ")


def test_the_skill_sends_the_reader_to_the_guide_and_example():
	body = (SKILL / "SKILL.md").read_text()
	assert "shapes.md" in body
	assert "example.scenes.json" in body
	assert "narratr deck" in body
```

Run: `uv run pytest tests/test_presentation_skill.py -q` — Expected: FAIL.

- [ ] **Step 2: Files**

```bash
mkdir -p skills/presentation
ln -s ../narratr/shapes.md skills/presentation/shapes.md
uv run python -c "from PIL import Image; im=Image.open('assets/Narratr.png'); im.thumbnail((800,800)); im.save('skills/presentation/example-image.png', optimize=True)"
```

`skills/presentation/example.scenes.json`: copy `skills/narratr/example.scenes.json`, then (a) drop `voice`; (b) add a light `theme`:

```json
"theme": {
  "background": "#ffffff",
  "text": "#0f172a",
  "muted": "#64748b",
  "accents": ["#2563eb", "#db2777", "#059669", "#d97706"],
  "headingFont": "Poppins",
  "bodyFont": "Inter"
}
```

(c) give its first `prose` scene that has bullets `"image": "example-image.png"`; (d) append an `image` scene — `{"id": "the-mark", "type": "image", "heading": "The mark", "image": "example-image.png", "caption": "One file in, one deck out", "narration": "This is the narratr mark. Everything you just saw came from one document."}` — and map one existing block id to it only if needed for coverage (it introduces no new block, which is allowed); (e) set `source.title` to `"narratr, presented"`. Rewrite each scene's narration only where it says "video" or addresses a listener of a recording, keeping every cue phrase verbatim present.

`skills/presentation/SKILL.md`:

````markdown
---
name: presentation
description: Turn a document into a slide deck a person presents - writing the speaker script, choosing the shape of each slide, applying a colour scheme, and building an editable .pptx with on-click reveals that imports into Google Slides. Use when the user asks for a presentation, a deck, slides, or a talk from a Notion page, markdown file or doc.
---

# presentation

Turn a document into a deck you present yourself. Claude writes the script and
chooses each slide's shape; `narratr deck` builds the file in seconds.

Output, in `decks/<title>/`:

- `deck.pptx` — editable slides, reveals on click, the script in the speaker notes
- `script.md` — the same script, one section per slide, for printing

Every place the presenter should click is marked `▶️` in both.

## 1. Get the document, and the user's context

The document's markdown, as for the narratr skill. Also collect, if given:

- **A colour scheme or design language.** Turn it into `theme` (step 3).
- **Images.** Local PNG, JPEG or GIF paths. Ask for files, not links.

## 2. Outline — same gate as the video

```sh
uv run narratr blocks <document> --json
```

Copy the output into `source.block_ids` verbatim and map every id to a scene.
Read `shapes.md` beside this file before writing any scene; it is the same
guide the video skill uses, and the same shape rules apply.

## 3. Write `scenes.json`

Copy the structure of `example.scenes.json` beside this file.

**Narration is spoken by a person now, not a voice model.** Write what the
presenter says: first person is fine, write for natural pauses, keep each
slide to 75–150 words. Numbers can stay as digits. Everything else from the
narratr skill holds — cues are verbatim phrases from the narration, in order,
and each one is where the presenter clicks.

**Headings** are real slide titles. Give every content slide one. A `prose`
scene with a heading and no bullets is a section divider.

**Theme.** From whatever the user gave — hex codes, brand names, "navy and
coral, clean, light" — choose: `background`, `text`, `muted`, 4–6 `accents`
that stay distinguishable on the background, `headingFont`, `bodyFont`. Fonts
must be Google Fonts (Slides substitutes anything else). Check contrast:
`text` and every accent must read on `background`. No theme means narratr's
dark palette.

**Images.** Paths are relative to the `scenes.json` file; absolute paths work
too. Three places they go:

| Want | Use |
|---|---|
| A screenshot or photo that is the point of the slide | `image` scene, optional `caption` |
| A picture beside a few points | `image` on a `prose` scene (bullets go left) |
| A picture per compared thing | `image` on each card |

An image scene reveals nothing, so its narration has no cues.

**Diagrams** become native, editable boxes and arrows, one click per
`revealSteps` group. Only flowcharts can do this; any other Mermaid type is
shown as one picture with no clicks, and `validate` warns.

## 4. Validate, then build

```sh
uv run narratr validate scenes.json
uv run narratr deck scenes.json
```

Fix every problem `validate` reports and re-run. Building is cheap — no
confirmation needed. If `deck` reports that `node_modules` is missing, tell the
user to run `make setup` and stop.

## 5. Hand it over

Give the user both paths, and how to get the deck into Google Slides:

> Upload `deck.pptx` to Google Drive, open it with Google Slides, then
> *File → Save as Google Slides*. Animations and speaker notes come across.

Do not upload it for them unless asked.
````

README: add after the skill install section:

````markdown
## Presentations

The same `scenes.json` also builds a deck you present yourself:

```sh
uv run narratr deck scenes.json   # → decks/<title>/deck.pptx and script.md
```

Slides are editable shapes, reveals happen on click, and the script sits in
the speaker notes with `▶️` wherever to click. A `theme` sets colours and
fonts; `image` scenes and `image` fields add your own pictures. Upload the
.pptx to Google Drive and open it with Google Slides — animations survive the
import. The `presentation` skill drives all of this from a document.
````

- [ ] **Step 3: Run tests and validate**

Run: `uv run pytest tests/test_presentation_skill.py -q && make validate`
Expected: PASS; `make validate` now also checks `skills/presentation/example.scenes.json` — it runs from the repo root, so the image path would resolve against the spec's directory (`validate` passes `args.scenes.resolve().parent`) and pass.

- [ ] **Step 4: Commit**

```bash
git add skills/presentation tests/test_presentation_skill.py README.md
git commit -m "Add the presentation skill, with a themed example that uses images"
```

---

### Task 10: Full check, Slides verification, PR

**Files:** none new.

- [ ] **Step 1: Everything green**

Run: `make test`
Expected: `✓ All checks passed!` (ruff, mypy, pytest, tsc, vitest).

- [ ] **Step 2: Build the two reference decks and look at them**

```bash
uv run narratr deck examples/brief.scenes.json --out /tmp/narratr-brief
uv run narratr deck skills/presentation/example.scenes.json --out /tmp/narratr-presentation
open -a Keynote /tmp/narratr-brief/deck.pptx
```

Check every slide by eye: headings large, nothing overflowing, diagram edges attached, theme applied on the presentation example.

- [ ] **Step 3: Google Slides verification**

Upload `/tmp/narratr-presentation/deck.pptx` to Drive (same Chrome route as the spike), *File → Save as Google Slides*, open the Motion panel on every slide with reveals and confirm the count of Fade (On click) entries equals the `▶️` count in that slide's notes. Ask the user to delete both uploaded files afterwards.

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin presentation-skill
gh pr create --title "Add a presentation skill: editable .pptx decks from scenes.json" --body "<summary, test results, Slides verification, symlink re-link note>"
```

The PR body must tell the user to re-link the moved skill: `rm ~/.claude/skills/narratr && ln -s "$PWD/skills/narratr" ~/.claude/skills/narratr`, plus the new `presentation` link.
