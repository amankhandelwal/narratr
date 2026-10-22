---
name: presentation
description: Turn a document into a slide deck a person presents - writing the speaker script, choosing the shape of each slide, applying a colour scheme, and building an editable .pptx with on-click reveals that imports into Google Slides. Use when the user asks for a presentation, a deck, slides or a talk from a Notion page, a markdown file or a doc.
---

# presentation

Turn a document into a deck the user presents themselves. You write the script
and choose each slide's shape; `narratr deck` builds the file in seconds.

It writes two files to `decks/<title>/`:

- `deck.pptx`: editable slides, reveals on click, the script in the speaker notes
- `script.md`: the same script, one section per slide, for printing

Every place the presenter should click is marked `▶️` in both.

## 1. Get the document, and the user's context

Get the document's markdown, as the narratr skill does. Also collect, if the user gave them:

- **A colour scheme or design language.** You turn it into `theme` in step 3.
- **Images.** Local PNG, JPEG or GIF files. Ask for files, not links.

## 2. Outline: same gate as the video

```sh
uv run narratr blocks <document> --json
```

That output *is* `source.block_ids`: copy it verbatim and map every id to a
scene. Deriving the list mechanically is what makes "every block is mapped"
mean anything.

**Before writing any scene, read `shapes.md` beside this file.** It is the
same guide the video skill uses: the five shapes, how to choose between them,
cues, icons and diagram sizing all apply unchanged.

## 3. Write `scenes.json`

Copy the structure of `example.scenes.json` beside this file. It uses a theme,
a section divider, a picture beside bullets and a full-slide picture.

**A person speaks the narration now, not a voice model.** Write what the
presenter will say: first person is fine, leave room for natural pauses, keep
each slide to 75–150 words. Numbers can stay as digits. Everything else from
the narratr skill holds. Each revealed element carries a `cue`: a verbatim
phrase from its scene's narration, in reveal order. **The cue is where the
presenter clicks**, so cue the phrase that introduces the element.

**Headings** are real slide titles: give every content slide one. A `prose`
scene with a heading and nothing else becomes a section divider. Use one
between parts of a longer talk.

**Theme.** From whatever the user gave you (hex codes, a brand, "navy and
coral, light and clean"), choose:

| Field | What |
|---|---|
| `background`, `text`, `muted` | `#rrggbb`. `text` must read on `background`; `muted` is for secondary lines |
| `accents` | 4–6 colours, each distinguishable from the others and readable on `background` |
| `headingFont`, `bodyFont` | Google Fonts names. Slides substitutes anything else |

With no theme, the deck uses narratr's dark palette, the same as the video.

**Images.** Paths are relative to the `scenes.json` file; absolute paths work
too.

| The user wants | Use |
|---|---|
| A screenshot or photo that is the point of the slide | an `image` scene, optional `caption` |
| A picture beside a few points | `image` on a `prose` scene; bullets go on the left |
| A picture per compared thing | `image` on each card |

An `image` scene reveals nothing, so its narration needs no cues.

**Diagrams** become native, editable boxes and arrows, one click per
`revealSteps` group. Only Mermaid flowcharts can be rebuilt; any other diagram
type is shown as one picture with no clicks, and `validate` warns about it.

## 4. Validate, then build

```sh
uv run narratr validate scenes.json
uv run narratr deck scenes.json
```

Fix everything `validate` reports and re-run until it is clean. Building takes
seconds, so it needs no confirmation. If `deck` fails because `node_modules`
is missing, tell the user to run `make setup` and stop.

## 5. Hand it over

Give the user both paths, and how to get the deck into Google Slides:

> Upload `deck.pptx` to Google Drive, open it with Google Slides, then choose
> *File → Save as Google Slides*. The animations and speaker notes come across.

Do not upload it for them unless they ask.
