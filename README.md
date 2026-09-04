# narratr

Turn a document into a narrated video, locally. No API bills, nothing uploaded.

Point a Claude session at a Notion page or a markdown file and ask for a video.
Claude writes the script; your laptop renders it while you do something else.

---

## Requirements

- **macOS on Apple Silicon** — narration runs on MPS
- **[uv](https://docs.astral.sh/uv/)**, **ffmpeg**, **Node 20+**
- **Python 3.11.9–3.12** (uv installs it if missing)
- **~6 GB free** — 3.8 GB of model weights, 1.1 GB of Python environment

```sh
brew install uv ffmpeg node
```

## Setup

```sh
git clone <this-repo> && cd narratr
make setup
```

`make setup` syncs the environment from `pyproject.toml`, downloads the
Chatterbox Turbo weights into the shared HuggingFace cache, installs the
pre-commit hook, and finishes by running `doctor`. First run takes a few
minutes, mostly the weights.

A green `doctor` means the machine can render:

```
  ✓ python                  3.11.9
  ✓ torch                   2.6.0
  ✓ mps acceleration        available
  ✓ chatterbox watermarker  ok
  ✓ ffmpeg                  /opt/homebrew/bin/ffmpeg
  ✓ node                    /Users/you/.nvm/versions/node/v22.16.0/bin/node
  ✓ voice reference         1 sample(s)

  ✓ Ready
```

Then let Claude see the skill:

```sh
ln -s "$PWD/skill" ~/.claude/skills/narratr
```

Start a new Claude session for it to load.

## Use

**From Claude** — point it at a document and ask for a video. It writes
`scenes.json`, validates it, shows you a coverage report, and waits for your go
before spending any compute.

**Directly:**

```sh
uv run narratr doctor                        # is this machine ready
uv run narratr validate scenes.json          # schema + coverage, costs nothing
uv run narratr render scenes.json --detach   # returns a run id in ~1s
uv run narratr status <run-id>               # progress
```

`--detach` survives the terminal closing, the parent shell exiting, and the
Claude session ending. Runs are checkpointed per scene, so an interruption
costs one scene rather than the run — re-run the same command to resume.

Try it against the bundled example:

```sh
uv run narratr render examples/scenes.json
```

## Voice

Chatterbox Turbo has **no built-in voice**. It speaks only as the reference clip
you give it, and that clip's quality caps every video you make.

`assets/voices/` ships a sample so a fresh clone renders immediately. Record ten
clean seconds of yourself and point `voice.reference` at it when you want it to
sound like you.

## What it costs

**Nothing per video.** Claude runs on your existing subscription; everything
else is local.

The budget is wall clock: roughly **2.5 hours** for a 36-minute video on an
M4 Pro, most of it narration at a measured real-time factor of 1.59.

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

| Stage | State |
|---|---|
| Script engine (Claude skill) | written, unexercised on a real document |
| Schema + coverage gate | working |
| Narration (Chatterbox Turbo) | **working**, benchmarked |
| Detached, resumable runs | **working** |
| Alignment (WhisperX) | not built |
| Scene render (Remotion) | not built |
| Stitch (FFmpeg) | not built |

`render` runs narration then stops visibly at the first unbuilt stage, leaving
completed audio in `runs/<id>/audio/`.

## Troubleshooting

**`'NoneType' object is not callable` on model load** — `setuptools` 81 removed
`pkg_resources`, which Chatterbox's watermarker imports and whose ImportError it
swallows. The pin in `pyproject.toml` prevents this; `make reset` restores it.

**`doctor` reports `mps acceleration: CPU only`** — narration will be roughly 5×
slower. Check you are on Apple Silicon and that torch installed correctly.

**Weights re-downloading** — they live in `~/.cache/huggingface`, outside the
project. `make reset` does not touch them.

## Licence note

Remotion, used by the (unbuilt) scene renderer, is free for individuals and
organizations of up to 3 people. Above that it requires a paid Company License,
counted by headcount rather than by whether anything is sold — internal use at a
company counts. No account or licence key is needed for free use.

`render/CONTRACT.md` isolates the renderer so Motion Canvas (MIT) can replace it
if that becomes a problem.

## Design

See [docs/research-plan.md](docs/research-plan.md) for why each piece was chosen,
what was measured, and what is still uncertain.
