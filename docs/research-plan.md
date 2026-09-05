---
tags:
  - narratr
  - research
  - plan
---
# narratr — Research & Build Plan

**Date:** 2026-09-05 · **Status:** narration built and benchmarked; render pipeline not started · **Scope:** personal tool, local, macOS on Apple Silicon

---

## BLUF

A Claude skill plus a local CLI. Claude reads a document and writes the script; your laptop does the rest, unattended.

**The stack:**

| Layer | Choice | Verdict |
|---|---|---|
| **Script + scene planning** | Claude, in-session, via the narratr skill | Build as a skill |
| **Narration** | Chatterbox Turbo, local | Build on OSS |
| **Word timings** | torchaudio forced alignment, local | Build on OSS |
| **Slides + diagram animation** | Remotion (React → video) | Build on OSS |
| **Diagram source** | Mermaid, rendered to SVG, revealed step-by-step | Build (~150 LOC) |
| **Assembly** | FFmpeg concat demuxer | Buy (OSS) |

**Cost per video: $0.** Claude runs on the subscription that already powers your session. Everything else is local.

**The budget is wall clock:** about twice the video's length, most of it TTS. A two-minute clip costs about four minutes.

**Three decisions carry the design:**

1. **Audio-first.** Narration is generated first; the video timeline is derived from measured audio durations.
2. **Skill writes, CLI renders.** Claude produces `scenes.json` and stops. A 2.5-hour compute job does not belong in a conversation.
3. **Every stage is resumable.** A run must survive a closed lid and the session that started it.

---

## The Core Insight: Audio-First

Every doc-to-video project fails the same way — you build slides, then try to make narration fit them. Timing drift is unfixable and every edit re-breaks it.

Invert it. Narration is the master clock.

1. Claude writes the script, split into scenes.
2. TTS renders each scene and reports its exact duration.
3. The renderer is *told* the duration. It fits its animation into whatever it is given.

Sync becomes a non-problem, not a problem you solve.

It also makes local TTS viable. Chatterbox drifts over long single passes and holds together over short ones. Scene-sized chunks are the natural unit of both the timeline and the model's competence.

---

## The Boundary That Matters

`scenes.json` is the contract. Everything before it needs judgment; everything after is deterministic compute that never touches a model.

```mermaid
flowchart TD
    A["Notion page<br/>or markdown"] --> B["Claude session"]
    B --> C["scenes.json"]
    C --> D{"Validate"}
    D -- "problems" --> B
    D -- "clean" --> E["Human confirms"]
    E --> F["narratr render<br/>--detach"]
    F --> G["video.mp4"]

    classDef human fill:#D6E4F0,stroke:#7BA7CC,color:#1A1A1A
    classDef brain fill:#E3DAF0,stroke:#9B85C4,color:#1A1A1A
    classDef check fill:#F5D9D9,stroke:#C98A8A,color:#1A1A1A
    classDef work fill:#D9EAD3,stroke:#85B87A,color:#1A1A1A
    classDef out fill:#FCF0C8,stroke:#D4B44A,color:#1A1A1A

    class A,E human
    class B,C brain
    class D check
    class F work
    class G out
```

**Claude does not run the pipeline.** It launches a detached process and reports a run id. Streaming forty scenes of TTS progress into a conversation burns context to say what one `status` call answers in a line.

**The source is whatever Claude can read.** A Notion page via MCP, a local file, pasted text. narratr has no Notion integration and needs none.

---

## Stage 1 — The Script Engine

Where "covers everything" is won or lost. Two passes, not one.

```mermaid
flowchart TD
    A["Markdown"] --> B["Pass 1: Outline"]
    B --> C["Coverage ledger"]
    C --> D{"All mapped?"}
    D -- "no" --> B
    D -- "yes" --> E["Pass 2: Write scenes"]
    E --> F["scenes.json"]

    classDef parse fill:#D6E4F0,stroke:#7BA7CC,color:#1A1A1A
    classDef brain fill:#E3DAF0,stroke:#9B85C4,color:#1A1A1A
    classDef check fill:#F5D9D9,stroke:#C98A8A,color:#1A1A1A

    class A,C parse
    class B,E,F brain
    class D check
```

**Why two passes** — a single "turn this doc into a video" call silently drops material. Long docs get summarized, not covered. Splitting outline from prose lets you assert coverage mechanically.

**The coverage ledger is the FOMO cure.** Every leaf block gets an id. Pass 1 must map each one to a scene. `narratr validate` fails on any unmapped block, any mapping to a scene that does not exist, and any block that was invented. This runs before compute is spent and costs nothing.

**The block list must come from the document, not the author.** `narratr blocks <doc> --json` extracts it mechanically. If the same pass decides both what counts as a block and which blocks are covered, the gate is circular — anything skipped can simply be left off the list and validation still passes. This was a real hole, found by running the skill on this document.

Running the script engine inside the live session — rather than shelling out to `claude -p` — removes a whole category of problem. There is no subprocess to authenticate, no ambient config to pin, and no exposure to `--bare` becoming the default for `-p`. Claude is already the script engine.

---

## Stage 2 — Narration

**Chatterbox Turbo**, 350M params, MIT licence, on MPS.

### Measured on this machine

M4 Pro / 24 GB, real runs:

| Model | Load | Sustained rtf |
|---|---|---|
| Standard (0.5B) | 15–17s | 2.9–3.5 |
| **Turbo (350M)** | 75s | **1.0–1.35** |

`rtf` is seconds of compute per second of audio. Measured over a six-scene run, which matters: an earlier two-scene benchmark reported 1.59 and hid a 4× regression that only appears once memory pressure builds. **Benchmark six scenes or more, never two.**

### What this constrains

- **Turbo has no built-in voice.** It speaks only as the reference clip it is given. That clip's quality caps every video you make.
- **Pin the reference clip and the seed.** Both are conditioning inputs, and cross-scene consistency is the quality risk that matters.
- **Pin `setuptools<81`.** Chatterbox's watermarker imports `pkg_resources`, swallows the ImportError, and dies far away with `'NoneType' object is not callable`.
- **Weights are ~3.8 GB**, pulled once into the shared HuggingFace cache.
- **Release the MPS allocator cache between scenes.** Left alone it reserves 14.6 GB against 2.9 GB live, which over-commits a 24 GB machine and drives ~1M page-ins per generation. One `torch.mps.empty_cache()` per scene holds it near 3.6 GB and keeps rtf flat. Any future stage running a model on MPS needs the same.

### Captions

Forced alignment, not transcription. The text is known exactly — it is what we asked Chatterbox to say — so `torchaudio`'s CTC aligner and the MMS_FA bundle line the words up against the audio directly.

That replaced WhisperX, which would have brought faster-whisper and CTranslate2 to transcribe speech we already have the script for. torchaudio was already a dependency. Measured at **rtf 0.03** — 73 seconds of audio aligned in 2 seconds, essentially free.

`torchaudio::forced_align` has no MPS kernel, so the emission is moved to CPU explicitly for that one call rather than setting `PYTORCH_ENABLE_MPS_FALLBACK`, which would silently send any unimplemented op to the CPU and hide the cost.

---

## Stage 3 — The Scene Renderer

```mermaid
flowchart TD
    A["scene + duration"] --> B{"Type?"}
    B -- "diagram" --> C["Mermaid → SVG"]
    B -- "prose" --> D["Slide"]
    B -- "code" --> E["Shiki"]
    C --> F["Tag reveal steps"]
    F --> G["Interpolate<br/>over timeline"]
    D --> G
    E --> G
    G --> H["scene_N.mp4"]

    classDef visual fill:#FBE0D0,stroke:#D9945F,color:#1A1A1A
    classDef check fill:#F5D9D9,stroke:#C98A8A,color:#1A1A1A
    classDef out fill:#FCF0C8,stroke:#D4B44A,color:#1A1A1A

    class A,C,D,E,F,G visual
    class B check
    class H out
```

**Diagram animation, concretely.** Mermaid emits an SVG where every node is `g.node[id]` and every edge is `g.edgePath`. Claude emits a `revealSteps` array grouping those ids into beats. Remotion interpolates opacity per group across the scene's duration. No third-party service.

**Render per scene, concat after.** Remotion slows down on very long single compositions, so scene-sized renders are the safe unit regardless of total length. Per-scene output is also what makes a run resumable and what lets a single edited scene re-render alone.

**The renderer sits behind a contract** (`render/CONTRACT.md`): it receives one scene, its measured duration, and an output path. It knows nothing about TTS, alignment, or scene ordering. That boundary exists so Remotion can be replaced without touching anything upstream — see Risks.

---

## Stage 4 — Durability

Kick it off, walk away, come back to a finished video or a run that resumes exactly where it stopped.

```mermaid
flowchart TD
    A["Start run"] --> B["Hash doc + config"]
    B --> C{"Manifest?"}
    C -- "no" --> D["Create"]
    C -- "yes" --> E["Load"]
    D --> F["Next pending scene"]
    E --> F
    F --> G["Write .partial<br/>then rename"]
    G --> H["Mark done<br/>fsync"]
    H --> I{"More?"}
    I -- "yes" --> F
    I -- "no" --> J["Stitch → final.mp4"]

    classDef state fill:#D6E4F0,stroke:#7BA7CC,color:#1A1A1A
    classDef work fill:#D9EAD3,stroke:#85B87A,color:#1A1A1A
    classDef check fill:#F5D9D9,stroke:#C98A8A,color:#1A1A1A
    classDef out fill:#FCF0C8,stroke:#D4B44A,color:#1A1A1A

    class A,B,D,E,H state
    class F,G work
    class C,I check
    class J out
```

### The four rules

- **Content-address every artifact.** Each scene is keyed on `hash(narration + voice_ref + seed + model)`. A matching file means skip. Resume and incremental re-render fall out of one mechanism: edit one scene, only that scene re-runs.
- **Atomic writes only.** Write a `.partial.wav` beside the target, then `rename()`. The temp name keeps its real extension — torchaudio infers the container from it, and a `.tmp` suffix breaks the write.
- **Commit after each scene, not each stage.** `fsync` the manifest on every transition. The unit of loss is one scene, roughly 90 seconds.
- **One process, many scenes.** Turbo costs 75 seconds to load. Never spawn per scene.

### Surviving the session and the lid

`narratr render --detach` forks with `start_new_session=True`, writes a run id, and returns in under a second. The run outlives the Claude session, the terminal, and the parent shell.

Sleep is the remaining gap:

```sh
caffeinate -is uv run narratr render scenes.json
```

**Closing the lid still sleeps the machine.** `caffeinate` prevents idle sleep, not lid-close sleep, unless an external display is attached. Run lid-open on AC power, or rely on the checkpointing and lose the scene in flight.

---

## Build vs Buy

| Layer | Decision | Reasoning |
|---|---|---|
| **Script engine** | **Build** as a skill | Nothing off-the-shelf does coverage-guaranteed chunking. Running it in-session removes the auth and reproducibility problems a subprocess would add. |
| **TTS** | **Build** — Chatterbox Turbo | Quality cleared the bar on a real listen; MIT; zero marginal cost. Benchmarked above. |
| **Alignment** | **Build** — torchaudio | Already a dependency; forced alignment beats transcribing text we already have. |
| **Slides** | **Build** on Remotion — ~~MARP~~ | MARP outputs *static* artifacts. Animating them means exporting frames and panning, which kills per-element reveals. |
| **Diagram animation** | **Build** — ~~FlowGif~~ | Closed SaaS, GIF/PNG export. A GIF cannot be timed against narration. |
| **Assembly** | **Buy** — FFmpeg | `concat` demuxer with stream copy. Milliseconds, no re-encode. |

**Ruled out for TTS:** ElevenLabs and Sarvam. The recurring cost bought nothing that could not be replaced locally.

**Ruled out for the LLM:** the Anthropic Messages API. It offers explicit cache control and determinism, but needs separately purchased API credits for a tool whose calls the subscription already covers.

---

## Cost

**Dollars: $0.** Electricity for a 2.5-hour run is under two cents.

### Wall clock is the real budget

Real-time factors, which scale to whatever length you make. All measured, none estimated.

| Stage | rtf | 74s clip |
|---|---|---|
| Script | — | conversational |
| **Narration** | **1.33** | ~97s |
| Alignment | 0.03 | ~2s |
| Render | 0.55 | ~40s |
| Stitch | copy | ~1s |
| **Total** | **~1.9** | **~2.5 min** |

Rendering came in faster than realtime, against an estimate that was wrong by roughly 3×. 1080p30 has headroom; the planned fallback to 24fps and 1600×900 is not needed. Concurrency swept 4 to 12 on a 12-core machine: identical above 6, so Remotion's default needs no tuning.

**Work in short clips.** `examples/brief.scenes.json` is six scenes and runs cold in about two minutes, which is the right unit for iterating. Content addressing means a single edited scene re-renders alone.

---

## Risks

- **Script quality is the whole product.** Voice and animation are solved. Whether the narration is worth watching is decided in the Pass-1/Pass-2 prompts. Budget most of the effort there.
- **Remotion needs a paid Company License above 3 people.** The threshold is headcount, not whether anything is sold, and internal use counts. Using narratr on a work laptop triggers it. Free use needs no account or licence key — this is a terms obligation, not an enforced one. The renderer contract exists so Motion Canvas (MIT) can replace it; the swap gets more expensive with every scene component written.
- **Cross-scene voice consistency is unproven.** Longest test so far is three scenes. Whether scene 40 still sounds like scene 3 is the open quality question and the failure mode local TTS is most prone to.
- **The reference clip is a single point of failure.** Turbo has no fallback voice.
- **~~MPS performance is unexplained~~ — resolved.** The erratic figures were the MPS caching allocator over-committing memory and forcing the machine to swap. Releasing it per scene fixed it. What remains unexplained is the gap to a quoted 0.499 on a 4090, and that `PYTORCH_ENABLE_MPS_FALLBACK=1` still sends unsupported ops to CPU silently. Neither is currently costing anything.
- **Mermaid's SVG structure is not a public API.** Node ids and class names shift between versions. Pin the version and snapshot-test the selectors.

---

## Status

| Stage | State |
|---|---|
| Script engine | working; produced 34 scenes covering all 51 blocks of this document |
| Schema + coverage gate | working; verified to reject dropped blocks, ghost scenes and over-long slides |
| Block extraction | working, mechanical |
| Narration | **working**, benchmarked, resumable |
| Detached runs | **working**, verified surviving the parent process |
| Alignment | working, word timings + SRT |
| Scene render | working, rtf 0.55 |
| Stitch | working, stream copy |

A run now produces `runs/<id>/video.mp4` and `captions.srt` end to end.

---

## Next

Everything in the original plan is built. What remains is refinement:

1. **Chapter markers** in the final concat.
2. **Shiki highlighting** for code scenes, which currently render as plain monospace.
3. **Fail loudly on silent audio**, so the class of bug that shipped once cannot ship again.

---

## Sources

- Chatterbox benchmarks: measured in-session on M4 Pro / 24 GB, 2026-09-05.
- [Chatterbox repo](https://github.com/resemble-ai/chatterbox) · [Chatterbox Turbo](https://codersera.com/blog/chatterbox-turbo-run-and-install-locally-free-elevenlabs-alternative-2026/) · [Best open-source TTS 2026](https://findskill.ai/blog/best-open-source-tts-2026/)
- [Remotion licence FAQ](https://www.remotion.dev/docs/license/faq) — the 3-person threshold and the no-account-needed rule
- [Claude Code skills](https://code.claude.com/docs/en/skills) · [Plugins](https://code.claude.com/docs/en/plugins)
- [Mermaid: animated diagrams issue #3029](https://github.com/mermaid-js/mermaid/issues/3029)
