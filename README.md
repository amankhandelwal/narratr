<p align="center">
  <img src="assets/Narratr.png" alt="narratr" width="520">
</p>

<p align="center">
  <strong>Turn a document into a narrated video, locally.</strong><br>
  No API bills, nothing uploaded.
</p>

Point a Claude session at a Notion page or a markdown file and ask for a video.
Claude writes the script; your laptop renders it while you do something else.

---

## Requirements

- **macOS on Apple Silicon** — narration runs on MPS
- **[uv](https://docs.astral.sh/uv/)**, **ffmpeg**, **Node 20+**
- **Python 3.11.9–3.12** (uv installs it if missing)
- **~7 GB free** — 3.8 GB of model weights, 1.2 GB of Python environment,
  1.1 GB of Node packages

```sh
brew install uv ffmpeg node
```

## Setup

```sh
git clone <this-repo> && cd narratr
make setup
npm install --prefix render/remotion
```

`make setup` covers the Python side only: it syncs the environment from
`pyproject.toml`, downloads the Chatterbox Turbo weights into the shared
HuggingFace cache, installs the pre-commit hook, and finishes by running
`doctor`. First run takes a few minutes, mostly the weights.

**The Node packages are the second command, and nothing before it complains.**
Remotion draws the frames, Mermaid the diagrams, Shiki the code and Lucide the
icons — all four live in `render/remotion/node_modules`. Skip it and the run
gets all the way through narration before `render` refuses with "renderer not
installed".

A green `doctor` means the machine can render. It walks the Python and torch
versions, MPS acceleration, the Chatterbox watermarker, `ffmpeg`, `node` and the
voice reference, one line each, and each failing line names its own fix. It ends
in `✓ Ready`, or in `❌ Not ready` and a non-zero exit — the skill checks it
before spending anything.

Then let Claude see the skill:

```sh
ln -s "$PWD/skill" ~/.claude/skills/narratr
```

Start a new Claude session for it to load. The link covers the whole directory,
so three files travel with it: `SKILL.md` (the workflow), `presentation.md` (how
to choose a scene's shape) and `example.scenes.json` (a complete spec using
every shape). A session reads all three without needing to know where this
checkout lives.

## Use

**From Claude** — point it at a document and ask for a video. It writes
`scenes.json`, validates it, shows you a coverage report, and waits for your go
before spending any compute.

**Directly:**

```sh
uv run narratr doctor                        # is this machine ready
uv run narratr validate scenes.json          # schema + coverage, costs nothing
uv run narratr render scenes.json --detach   # returns a run id in ~1s
uv run narratr status                        # progress of the newest run
uv run narratr blocks <doc> --json           # leaf block ids for the ledger
uv run narratr icons <word>                  # search Lucide icon names
```

Edits are cheap. Artifacts are content-addressed in a shared `store/`, keyed
separately for audio and picture, so a re-run only redoes what actually changed:

| Change | Cost |
|---|---|
| Nothing | ~1s |
| A diagram or some bullets | ~7s |
| One scene's narration | ~45s |
| Everything (cold) | ~2.5 min |

To iterate on a single scene without touching the rest:

```sh
uv run narratr render scenes.json --only the-flow
```

Repeatable, and it skips stitching so `video.mp4` is never left partial.

Runs land in `runs/<title> [DD-MM HH.MM AM/PM]/`. `narratr status` takes a name
or any prefix of one, and defaults to the most recent run.

`--detach` survives the terminal closing, the parent shell exiting, and the
Claude session ending. It re-invokes itself with `--run-name`, which is what
keeps the detached child writing into the directory the parent just announced
instead of minting a second one a moment later.

**Re-running the same command starts a new run rather than resuming the old
one.** The directory name carries the clock, so a second `narratr render` mints
`runs/<title> [DD-MM HH.MM AM/PM]/` afresh with an empty manifest — three goes
at one spec leave three directories. Recovery comes from `store/`, not from the
manifest: every scene the interrupted run finished is already sitting there
under its content address, so the new run reuses it and only redoes the scene it
died on. The outcome is the same and it is just as fast, but the mechanism is
worth knowing the first time you go looking for a manifest to resume.

Try it against the bundled example — six scenes using every slide shape:

```sh
uv run narratr render examples/brief.scenes.json
```

## Voice

`assets/voices/sample-01.wav` is the project voice. Point `voice.reference`
somewhere else to change it.

```json
"voice": { "reference": "assets/voices/sample-01.wav", "seed": 7, "speed": 0.92 }
```

**Speed defaults to 0.92** — a little slower than Chatterbox's natural pace,
which suits narration you follow rather than skim. Below 1 is slower; pitch is
unchanged either way.

Speed is keyed apart from narration, so trying a different one resamples what
already exists instead of regenerating it: about 40s for a six-scene clip
against two and a half minutes.

Chatterbox Turbo has no built-in voice of its own — it speaks only as the
reference clip, so that clip sets the character of every video.

## Slides

Five scene shapes, chosen by what the content is rather than for variety:

| The content is | Scene type |
|---|---|
| Ordered steps, a pipeline | `flow` — icons and labels, revealed left to right |
| Parallel things compared | `cards` — two to four, side by side |
| Structure or relationships | `diagram` — Mermaid, revealed in beats |
| Source code | `code` — Shiki, highlighted ahead of render |
| Anything else | `prose` — up to six fragments |

Bullets, flow steps, cards and diagram nodes carry a
[Lucide](https://lucide.dev) icon by name. A bullet describing the approach
being rejected takes `"state": "struck"` and renders dimmed with a line through
it.

Diagram icons use Mermaid's node syntax and render as labelled boxes with the
glyph inside. The glyph is inlined into the label before Mermaid sees it, so
nothing is fetched at render time:

```
flowchart LR
    A@{ icon: "lucide:file-text", label: "doc.md" }
```

```sh
uv run narratr icons clapper     # clapperboard
```

An icon name that does not exist fails `narratr validate` before any compute,
with near misses — the same gate that catches a dropped source block.

`skill/SKILL.md` is what actually chooses between the shapes; the renderer only
makes each one possible.

## The title card

Every video opens with a four-second card: the mark, the document's title, and
`assets/intro.mp3`. It is built like a scene — rendered against a duration it is
told, audio padded to a whole number of frames — so assembly does not treat it
as a special case.

**The card is required.** The [licence](LICENSE) requires every video made
with narratr, or with anything built from it, to open with this card unchanged
and the narratr name visible — forks included. `assets/intro.mp3` sets the
length of the card, and `render/remotion/public/narratr-mark.png` is the image.
The sting is
attenuated 8 dB on the way in, because it is mastered about eleven decibels
louder than the narration that follows it.

The card is keyed apart from the scenes, so changing it rebuilds four seconds
rather than the whole video.

## What it costs

**Nothing per video.** Claude runs on your existing subscription; everything
else is local.

The budget is wall clock, at roughly **twice the video's length** on an M4 Pro.
The bundled 6-scene example runs cold in about two and a half minutes. Narration dominates
at rtf 1.33; rendering is 0.55, and speed, alignment and assembly are close to
free.

To keep the machine awake through a long run:

```sh
caffeinate -is uv run narratr render scenes.json
```

Note that `caffeinate` prevents idle sleep but **not lid-close sleep** unless an
external display is attached.

## Development

```sh
make test    # ruff format + lint, mypy, pytest
make fix     # auto-fix formatting and lint
make clean   # drop caches
make reset   # rebuild the environment from scratch (weights survive)
```

Run `make` on its own for the full target list.

## Status

Every stage works end to end. A run produces `runs/<id>/video.mp4` and
`captions.srt`.

| Stage | Measured on an M4 Pro |
|---|---|
| Script engine (Claude skill) | conversational |
| Narration (Chatterbox Turbo) | rtf 1.33 |
| Speed (ffmpeg atempo) | rtf 0.02 |
| Alignment (torchaudio forced) | rtf 0.03 |
| Scene render (Remotion) | rtf 0.55 |
| Assembly (FFmpeg) | ~1s |

The finished video opens on the title card and carries chapters — the card
first, then one per scene heading — with `captions.srt` beside it.

**Audio and picture are frame-exact.** Each scene's audio is padded to a whole
number of frames and the whole narration is encoded once, so scene boundaries
land within 0 ms of each other however long the video is.

## Troubleshooting

**`'NoneType' object is not callable` on model load** — `setuptools` 81 removed
`pkg_resources`, which Chatterbox's watermarker imports and whose ImportError it
swallows. The pin in `pyproject.toml` prevents this; `make reset` restores it.

**`doctor` reports `mps acceleration: CPU only`** — narration will be roughly 5×
slower. Check you are on Apple Silicon and that torch installed correctly.

**Weights re-downloading** — they live in `~/.cache/huggingface`, outside the
project. `make reset` does not touch them.

**A change to the renderer seems to do nothing** — video is keyed on the React
components, `mermaid.config.json`, `narratr/render.py` and
`render/remotion/package.json`. Editing anything else that affects the picture
will reuse the cached video. Add the file to `RENDERER_SOURCES` in
`narratr/state.py`.

**Everything re-renders after an edit** — expected if you changed narration:
that invalidates the audio, its timings, and the picture, because a scene's
length comes from its audio. Changing only bullets or a diagram re-renders just
the video.

## Licence

narratr is free to use, and the videos it makes are yours to publish — including
commercially — under the [narratr License](LICENSE). In short:

- **Every video opens with the narratr title card, unmodified.** That holds for
  forks and modified copies too.
- **Credit the work.** Anything built from narratr says so, names its author and
  links back here.
- **Keep it free.** narratr and anything built from it may not be sold or
  offered as a paid service, and is shared under the same licence.

It is source-available rather than OSI open source, because of those
conditions. The [LICENSE](LICENSE) file is the authoritative text.

**Third-party parts keep their own terms.** Remotion, which renders the scenes,
is free for individuals, non-profits and companies of up to 3 people, even for
commercial videos; a larger for-profit company needs a paid
[Company License](https://www.remotion.pro/license) — counted by headcount, and
internal use counts. `render/CONTRACT.md` isolates the renderer so Motion Canvas
(MIT) can replace it if that becomes a problem. The intro music is royalty-free
from [Pixabay](https://pixabay.com/service/license-summary/), and the sample
voice is Chatterbox's default audio (MIT).

## Design

See [docs/research-plan.md](docs/research-plan.md) for why each piece was chosen,
what was measured, and what is still uncertain.
