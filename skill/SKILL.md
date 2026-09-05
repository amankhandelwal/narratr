---
name: narratr
description: Turn a document into a narrated video - writing the scene script, choosing the shape of each slide, and launching a local render. Use when the user points at a Notion page, a markdown file, or a doc and asks for a video, a walkthrough, a narrated deck, a slide deck, or a screencast of it.
---

# narratr

Turn a document into a narrated video. You write the script; a local pipeline
does the rest.

Your job is the part that needs judgment: reading the document and turning it
into `scenes.json`. Everything after that is deterministic compute you kick off
and walk away from.

## Before anything else

```sh
uv run narratr doctor
```

If it reports "not ready", tell the user to run `make setup` and stop. Do not
try to work around a missing dependency.

## 1. Get the document

Whatever the user pointed at — a Notion URL via MCP, a local file, a pasted
blob. You need its markdown and nothing else. narratr has no Notion
integration and does not need one.

## 2. Pass 1 — outline

**Get the block ids from the tool, never by hand:**

```sh
uv run narratr blocks <document> --json
```

That output *is* `source.block_ids`. Copy it verbatim.

This matters more than it looks. If you decide both what counts as a block and
which blocks are covered, the gate is circular — anything you skip can simply be
left off the list, and validation still passes. Deriving the list mechanically is
the only thing that makes "every block is mapped" mean anything.

Then map **every** id to a scene. A script that reads well but silently dropped a
third of the document is the failure mode this whole design exists to prevent.

Scenes run 30–60 seconds of narration, roughly 75–150 words. Longer drifts,
shorter feels choppy.

## 3. Pass 2 — write the scenes

One `scenes.json` conforming to `schemas/scenes.schema.json`.

Narration is spoken prose. Write for the ear: short sentences, no bullet
syntax, no markdown, no "as you can see". It is the master clock — its measured
duration sets how long the scene lasts, so never write narration to fit a
slide.

### Pick the shape from the content

Five scene types. Choose by what the content *is*, not for variety:

| The content is | Use | Carries |
|---|---|---|
| Ordered steps, a pipeline | `flow` | `steps` (2–5), optional `footer` |
| Parallel things being compared | `cards` | `cards` (2–4) |
| Structure or relationships | `diagram` | `mermaid` + `revealSteps` |
| Source code | `code` | `code` + `lang` |
| Anything else — properties, claims | `prose` | `bullets` (≤6) |

`prose` is the default. Reaching for `flow` when the content is not a sequence,
or `cards` when the things are not parallel, makes the shape fight the words.

### Icons

Every bullet, step and card takes a Lucide icon, kebab-case, in `icon`.

- **Name the object under discussion.** "Runs resume" is `rotate-ccw`, not
  `sparkles`. An icon that decorates rather than names is worse than none.
- **Omit it if nothing fits.** An approximate icon reads as a mistake.
- **Look the name up, do not guess twice:**

  ```sh
  uv run narratr icons <word>
  ```

  Searches ~2,000 names and Lucide's own keywords. An icon name that does not
  exist fails `narratr validate` before any compute is spent, with near misses.

### Rejecting something

A bullet describing the approach being *rejected* takes `"state": "struck"`.
It renders dimmed with a line through it. Use it for the wrong way, usually
before the right way; do not strike a consequence, only a choice.

### The rules the schema enforces

- One message per scene
- Fragments on screen, never sentences — detail lives in the narration
- Six bullets maximum, 2–5 flow steps, 2–4 cards
- Diagram scenes carry `mermaid` plus `revealSteps` grouping node ids into beats

## 4. Validate before spending anything

```sh
uv run narratr validate scenes.json
```

This is free and catches dropped blocks, bad schema, and scenes referenced by
coverage that do not exist. Fix and re-validate until clean.

## 5. Confirm, then launch

Show the user the coverage report, the scene count, and the estimated runtime.
**Wait for them to say go.** A full run is hours of compute — this is the last
cheap moment to catch a bad script.

Then:

```sh
uv run narratr render scenes.json --detach
```

It returns a run id in about a second and keeps running after this session
ends. Report the id and stop.

## 6. Afterwards

Only when asked:

```sh
uv run narratr status <run-id>
```

Never poll the render. Streaming forty scenes of TTS progress into the
conversation burns context to say what one status call answers in a line.
