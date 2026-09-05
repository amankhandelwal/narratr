"""The title card that opens every video.

A fixed four-second card: the mark, the document's title, and the intro sting.
It is built exactly like a scene -- rendered by Remotion against a duration it
is told, audio padded to a whole number of frames -- so assembly does not have
to treat it as a special case. The only difference is where the clock comes
from: a scene is as long as its narration, the card is as long as its music.

Keyed separately from the scenes on purpose. Changing the sting or the mark
must not invalidate six scene videos, and re-narrating a scene must not rebuild
the card.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from narratr import stitch
from narratr.paths import ROOT, STORE
from narratr.state import digest, renderer_digest

MUSIC = ROOT / "assets" / "intro.mp3"
MARK = ROOT / "render" / "remotion" / "public" / "narratr-mark.png"

# The sting peaks at -0.1 dB and averages -15.8 dB; narration sits near -27 dB.
# Straight in, it would open the video roughly eleven decibels above everything
# that follows. This lands it a little above the narration, which is where a
# title sting belongs, rather than on top of it.
GAIN_DB = -8


class IntroError(Exception):
	"""The title card cannot be built."""


def file_digest(path: Path) -> str:
	"""Content hash of a binary asset. The mark and the sting are not text."""
	return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def audio_layout(reference: Path) -> tuple[int, int]:
	"""The sample rate and channel count of an already-padded scene.

	The card's audio is concatenated with the narration under `-c copy`, which
	refuses streams whose parameters differ. Rather than hardcode Chatterbox's
	24 kHz mono, take it from what the narration actually turned out to be.
	"""
	out = subprocess.run(
		[
			"ffprobe",
			"-v",
			"error",
			"-select_streams",
			"a:0",
			"-show_entries",
			"stream=sample_rate,channels",
			"-of",
			"csv=p=0",
			str(reference),
		],
		capture_output=True,
		text=True,
		check=True,
	)
	rate, channels = out.stdout.strip().split(",")
	return int(rate), int(channels)


def key(title: str, rate: int, channels: int) -> str:
	return digest(
		[
			title,
			renderer_digest(),
			file_digest(MUSIC),
			file_digest(MARK),
			GAIN_DB,
			stitch.FPS,
			rate,
			channels,
			# This module builds the ffmpeg and Remotion commands, so its own
			# source shapes the result the same way narratr/render.py does.
			file_digest(Path(__file__)),
		]
	)


def duration() -> float:
	"""How long the card runs: the sting's own length, rounded to a frame."""
	return stitch.frame_aligned(stitch.probe_duration(MUSIC))


def build(title: str, reference: Path) -> tuple[Path, Path, float]:
	"""Render the card and prepare its audio. Returns (video, audio, seconds)."""
	for asset in (MUSIC, MARK):
		if not asset.exists():
			raise IntroError(f"missing intro asset: {asset.relative_to(ROOT)}")

	rate, channels = audio_layout(reference)
	seconds = duration()
	intro_key = key(title, rate, channels)

	out_dir = STORE / "intro"
	out_dir.mkdir(parents=True, exist_ok=True)
	video = out_dir / f"{intro_key}.mp4"
	audio = out_dir / f"{intro_key}.wav"

	if not audio.exists():
		tmp = audio.with_name(f".{audio.name}.partial.wav")
		# apad then -t: the sting decays to silence on its own by 3.8s, so what
		# this adds is padding to the frame boundary, not a fade.
		stitch.ffmpeg(
			[
				"-i",
				str(MUSIC),
				"-af",
				f"volume={GAIN_DB}dB,apad",
				"-t",
				f"{seconds:.6f}",
				"-ar",
				str(rate),
				"-ac",
				str(channels),
				"-c:a",
				"pcm_f32le",
				str(tmp),
			],
			"intro audio",
		)
		tmp.rename(audio)

	if not video.exists():
		from narratr.render import REMOTION, run_remotion

		props = STORE / "assets" / f"intro.{intro_key}.props.json"
		props.parent.mkdir(parents=True, exist_ok=True)
		props.write_text(json.dumps({"durationInSeconds": seconds, "title": title}))

		rendered = out_dir / f".{intro_key}.rendered.mp4"
		run_remotion(
			[
				"npx",
				"remotion",
				"render",
				"src/index.ts",
				"Intro",
				str(rendered),
				f"--props={props}",
				"--codec=h264",
				"--log=error",
			],
			REMOTION,
			"render intro",
		)
		# Same reason as every scene: Remotion writes a silent AAC track whose
		# encoder padding makes it longer than its own picture, and concat
		# advances by container duration.
		stitch.strip_audio(rendered, video)
		rendered.unlink(missing_ok=True)

	return video, audio, seconds
