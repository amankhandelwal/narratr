# Renderer contract

The renderer is isolated behind this contract so it can be replaced without
touching the rest of the pipeline.

Today it is Remotion. Remotion is free for individuals and teams up to 3
people; above that it needs a paid Company License, counted by headcount rather
than by whether anything is sold. If that becomes a problem, the swap target is
Motion Canvas (MIT) — and this boundary is what keeps that from being a rewrite
of everything upstream.

## What a renderer receives

One flat props object per scene, written to
`store/assets/<video-key>.props.json` and passed by path, plus the output file
to write. For Remotion that is:

```sh
npx remotion render src/index.ts Scene <out.mp4> --props=<props.json> --codec=h264
```

Props are flat, not a nested scene. The renderer never sees a `scenes.json`
entry, a scene id, or a run directory.

**Always present:**

| Field | Meaning |
|---|---|
| `type` | `prose` \| `flow` \| `cards` \| `diagram` \| `code` |
| `durationInSeconds` | measured from the rendered audio, never estimated |
| `heading` | the scene's heading, or `null` |

**Per type, exactly one set:**

| `type` | Fields |
|---|---|
| `prose` | `bullets` — strings, or `{text, icon?, state?}` |
| `flow` | `steps` — `{icon, label}`; `footer` — one more of the same, or `null` |
| `cards` | `cards` — `{title, detail?, icon?}` |
| `diagram` | `svg` — Mermaid output as markup; `revealSteps` — node ids grouped into beats |
| `code` | `code`, `lang`, `html` — Shiki output as markup |

**`icons`**, when the scene names any: a map of Lucide name → SVG markup. Keyed
by name because one scene may use the same icon twice.

### Everything is resolved before the renderer starts

`svg`, `html` and `icons` arrive as finished markup. The Python side runs
Mermaid, Shiki and the Lucide lookup itself and hands over the result.

This is deliberate, and it is part of the contract: **the renderer stays
synchronous.** Highlighting or diagramming inside a component would need
`delayRender`, and would be paid on every frame of the scene rather than once.
A replacement renderer inherits the same deal — it draws, it does not fetch.

`durationInSeconds` is the audio-first clock reaching the picture. The renderer
fits its animation into the time it is given; it does not get to ask for more.
Frames are `round(durationInSeconds × 30)` at 1920×1080.

## What it must guarantee

- Be deterministic: same props produce the same frames. Cache keys assume it.
- Exit non-zero on failure. The caller renders to `.<name>.partial.mp4` and
  renames only on a zero exit, so a half-written file must never exit zero.
- Write only the file it was given.

## The title card

A second entry point, `Intro`, renders the card that opens every video. It
takes `{ durationInSeconds, title }` and nothing else, and lands in
`store/intro/<intro-key>.mp4`. The duration is the intro sting's own length
rather than a scene's narration, but the rule is unchanged: the renderer is
told how long it has.

## What it must not do

- Read `scenes.json` directly — it sees one scene's props at a time.
- Know anything about TTS, alignment, or stitching.
- Depend on scene order. Scenes render independently and concat afterwards.
- Reach the network, or read anything outside its props.

## Where the output goes

`store/video/<video-key>.mp4`, not the run directory. The name is a content
address over the scene's picture-affecting fields and `renderer_digest()`, so
an unchanged scene is never re-rendered and a renderer change re-renders
everything. **Anything that can change a pixel belongs in `RENDERER_SOURCES`**
(`narratr/state.py`) before it ships — a source the digest misses silently
serves stale video. That has bitten three times.
