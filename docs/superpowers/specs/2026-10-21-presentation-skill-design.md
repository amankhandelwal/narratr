# Presentation skill — design

**Date:** 2026-10-21
**Status:** approved in conversation, pending spec review

## Goal

A second skill, `presentation`, that turns a document into a slide deck a
person presents, using every rule the video skill already follows. The same
script engine, the same five shapes, the same coverage gate — but the output is
a deck and a speaker script instead of a narrated video.

## Requirements

1. Slides stay slides. Nothing is rendered to video.
2. Reveals become on-click animations inside the slide.
3. The narration becomes text a person speaks: in each slide's speaker notes
   and in a separate, printable `script.md`.
4. Wherever a reveal happens, the script carries a fixed marker, `▶️`, so the
   presenter knows to click.
5. Headings are real headings at presentation size, not the video's small
   heading.
6. The user may pass a colour scheme / design language as context.
7. The user may supply their own images for the deck.
8. The file is generated locally and imports into Google Slides with its
   animations intact.
9. The deck stays editable by hand afterwards, without Claude.

## Format: .pptx — verified

Google Slides imports `.pptx` natively. Verified on 2026-10-21 with a
throwaway three-slide deck built by python-pptx with hand-written
`p:timing` XML, uploaded to Drive and converted with *File → Save as Google
Slides*. The Motion panel after conversion showed:

| Built | After conversion |
|---|---|
| Appear, one shape per click | 3 × Appear (On click) |
| Fade on an autoshape, a group (picture + shape), a lone picture | 3 × Fade in (On click) |
| Fly in; a connector and a shape on one click | On click + **With previous**, connector included |
| Speaker notes containing `▶️` | intact |

Rejected alternatives: the Google Slides API (builds in the cloud, needs
OAuth, not a local file); ODP or HTML decks (Slides does not import their
animations).

## Architecture

```
document ─► presentation skill (Claude) ─► scenes.json ─► narratr validate ─► narratr deck ─► decks/<title>/deck.pptx
                                                                                             decks/<title>/script.md
```

- **One spec, two outputs.** The presentation skill writes the same
  `scenes.json` as the video skill. Coverage gate, cues, icons and shapes are
  shared unchanged. A document scripted once can become either output.
- **Schema additions (optional, shared):**
  - top-level `theme` — `background`, `text`, `muted`, `accents` (4–6),
    `headingFont`, `bodyFont`. Colours are `#rrggbb`. Fonts must be Google
    Fonts so Slides does not substitute them.
  - scene type `image` — `image` (path), optional `caption`, optional `heading`.
  - optional `image` (path) on `prose` scenes and on individual `cards`.
- **The video pipeline is unchanged.** `narratr render` rejects a spec using
  `image` scenes or `image` fields with a clear message, and ignores `theme`.
  Video support is a later PR.
- **`narratr deck` is plain Python.** No TTS, no Remotion, no Chrome beyond
  `mmdc`'s own. Seconds, not minutes: no `--detach`, no run manifest, no cache.
- **Builder:** python-pptx for shapes; `p:timing` XML written directly for
  animations (python-pptx has no animation API). PptxGenJS was rejected: it
  has no animation support either, so it would need the same XML work in a
  second language.

### Modules — `narratr/deck/`

| File | One job |
|---|---|
| `theme.py` | Resolve `theme` against defaults (narratr's dark slate palette) |
| `layout.py` | One geometry function per shape; returns shapes plus their click groups |
| `animate.py` | Click groups → `p:timing` XML (Fade, On click / With previous) |
| `diagram.py` | Mermaid SVG layout → native nodes and glued connectors |
| `icons.py` | Lucide SVG → recoloured PNG via `resvg-py` |
| `script.py` | Narration + cues → notes text and `script.md` |
| `build.py` | Orchestrates; writes `deck.pptx` and `script.md` |

Reused as-is: `narratr/spec.py` validation, `narratr/icons.py` lookup,
`render.mermaid_to_svg` (mmdc remains the layout engine), and
`render/remotion/scripts/highlight.mjs` for code colours.

### Skills layout

- `skill/` → `skills/narratr/`; new `skills/presentation/`.
- `skill/presentation.md` → `skills/narratr/shapes.md` (the old name now
  collides with the new skill). `skills/presentation/shapes.md` is a symlink
  to it, so both skills read one guide.
- `example.scenes.json` stays with the narratr skill; the presentation skill
  gets its own example using `theme` and an `image` scene.
- Update every reference: `README.md` (install `ln -s` lines, now two),
  `LICENSE`, `Makefile` validate loop, `tests/test_skill_example.py`,
  `skills/narratr/SKILL.md`. Historical docs (`docs/research-plan.md`,
  checkpoints) are left as written.

## The slides

**Every slide**

- 16:9, 13.333 × 7.5 in, on a generated minimal master with a real **Title
  placeholder** — headings appear in Slides' outline and restyle from the master.
- Heading: 40 pt bold, heading font, top-left. A section card (`prose` with a
  heading and no bullets) sets it at 60 pt, centred.
- Body text 24–28 pt, never below 20 pt. Autofit off, fixed box sizes, so a
  manual edit does not reflow everything.
- Background colour set on the master. Accent rotation colours bullets,
  steps, cards and diagram nodes, as in the video.
- Every revealed element appears on click with **Fade**.

**Per shape**

| Shape | Layout | Clicks |
|---|---|---|
| `prose` | Icon + text rows; `struck` is dimmed with strikethrough; optional image fills the right half | one per bullet |
| `flow` | Icon tiles joined by arrows; footer as a static band | one per step (arrow into a step fades with it) |
| `cards` | Each card a group: accent bar, icon, title, body, optional image | one per card |
| `diagram` | Flowcharts rebuilt as native boxes and glued connectors at Mermaid's coordinates, scaled to the body area | one per `revealSteps` group; first element On click, rest With previous; an edge fades with the group that reveals its later endpoint |
| `code` | One monospace text box of coloured runs from Shiki; editable | none |
| `image` | Image fit to the body area, aspect preserved, optional caption | none |

Non-flowchart Mermaid (sequence, class, etc.) falls back to a single PNG
picture of the diagram that fades in on one click; `validate` warns.

**Icons:** Lucide SVG recoloured to the element's accent (`currentColor` →
hex) and rasterised to PNG at 4× display size with `resvg-py`. Slides drops
SVG on import.

**User images:** PNG, JPEG or GIF only. `validate` fails on a missing path or
another type. Images over 2 MB are downscaled into the deck; the source file
is never modified. Paths are resolved relative to the spec file.

## The spoken script

- The scene's `narration` is the script, verbatim.
- `▶️ ` is inserted immediately before each cue phrase. Cues are already
  verbatim, unique-enough, ordered, and checked by `validate`, so the click
  lands where the video would reveal. A diagram step's marker sits before its
  `revealCues` entry.
- Speaker notes: each slide's script with markers inline.
- `script.md`, one section per slide:

  ```markdown
  ## 3. Narration is the clock
  *3 clicks*

  Every project like this fails the same way. ▶️ You build the slides first, ...
  ```

  Plain markdown, no tables, so it prints from any viewer.
- The presentation skill tells Claude narration is now spoken by a person:
  first person is fine, write for natural pauses, no TTS workarounds. Shapes,
  cues, coverage and icon rules are unchanged.

## CLI

- `narratr deck <scenes.json> [--out DIR]` → `DIR/deck.pptx`, `DIR/script.md`.
  Default `DIR` is `decks/<safe_name(title)>/` beside `runs/`, using
  `narratr.state.safe_name`; `decks/` is gitignored like `runs/`.
- `narratr validate` adds: `theme` schema, image paths and types, the
  non-flowchart diagram warning.
- New dependencies: `python-pptx`, `resvg-py`. `doctor` already checks
  `node_modules`, which covers mmdc, Shiki and Lucide.

## Testing

Each test asserts a property over every slide, not one example:

- **Clicks agree three ways:** for every slide of every bundled example, the
  count of click groups in `p:timing` = the number of reveals in the spec =
  the count of `▶️` in that slide's notes.
- **Targets exist:** every `spTgt/@spid` in a slide's timing names a shape on
  that slide.
- **Diagrams:** each Mermaid node id becomes exactly one shape; each edge one
  connector whose begin/end are glued to the two right shapes.
- **Script fidelity:** notes with `▶️ ` removed equal the narration exactly;
  `script.md` carries the same text per slide.
- **Rejections:** missing image, unsupported image type, malformed theme
  colour, and a video render of an image scene each fail with a named error.
- **Round trip:** the written file reopens in python-pptx.
- **Manual, once per PR:** upload `examples/brief.scenes.json`'s deck to Google Slides, convert,
  check the Motion panel on every slide; user deletes the test files after.

## Out of scope

- Corporate `.pptx`/`.potx` templates.
- `theme` and images in the video renderer.
- Slide transitions.

## Risks

- **Connector gluing in Slides.** The spike showed a glued straight connector
  survives conversion; elbow connectors routed around nodes did not get
  tested. If they convert badly, edges are straight connectors only.
- **Mermaid SVG structure.** `diagram.py` reads node positions from mmdc's
  output; a mermaid-cli upgrade can change it. The diagram test over the
  bundled examples is the guard, and `mermaid-cli` is already pinned through
  `package-lock.json`.
