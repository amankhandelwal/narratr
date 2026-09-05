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

**Before writing any scene, read `presentation.md` beside this file.** It
carries the five scene shapes and how to choose between them, the icon rules,
and the limits the schema enforces. `example.scenes.json`, also beside this
file, is a complete spec that uses every shape — copy its structure.

Getting the shape wrong is the most common failure: a sequence written as a
bulleted list, or a comparison written as prose. The guide exists because that
judgment is the part worth spending attention on.

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
