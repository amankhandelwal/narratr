# Renderer contract

The renderer is isolated behind this contract so it can be replaced without
touching the rest of the pipeline.

Today it is Remotion. Remotion is free for individuals and teams up to 3
people; above that it needs a paid Company License, counted by headcount rather
than by whether anything is sold. If that becomes a problem, the swap target is
Motion Canvas (MIT) — and this boundary is what keeps that from being a rewrite
of everything upstream.

## What a renderer receives

```json
{
  "scene":    { "...": "one entry from scenes.json" },
  "duration": 47.3,
  "out":      "runs/<run-id>/video/<scene-id>.mp4"
}
```

`duration` is measured from the rendered audio, never estimated. The renderer
fits its animation into the time it is given; it does not get to ask for more.

## What it must guarantee

- Write to `out.tmp` and rename. A half-written mp4 must never look complete.
- Be deterministic: same scene plus same duration produces the same frames.
- Exit non-zero on failure and write nothing.

## What it must not do

- Read `scenes.json` directly — it sees one scene at a time.
- Know anything about TTS, alignment, or stitching.
- Depend on scene order. Scenes render independently and concat afterwards.
