"""Run state: content addressing and a checkpointed manifest.

A run is hours long and must survive a closed lid, a killed process, or the
session that started it going away. Two mechanisms carry that: every artifact
is content-addressed, and the manifest is committed after every scene.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from narratr.paths import ROOT, STORE


def atomic_write(path: Path, payload: str) -> None:
	"""Write via tmp + rename. A half-written file must never look complete.

	mkstemp rather than a predictable `<name>.tmp`: the old name could be
	pre-created as a symlink by anything else on the machine, and this function
	is presented as a safety primitive.
	"""
	handle, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
	tmp = Path(name)
	try:
		with os.fdopen(handle, "w") as fh:
			fh.write(payload)
			fh.flush()
			os.fsync(fh.fileno())
		os.chmod(tmp, 0o644)  # mkstemp is 0600; these are ordinary artifacts
		tmp.replace(path)
	except BaseException:
		tmp.unlink(missing_ok=True)
		raise


def digest(material: Any) -> str:
	return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()[:16]


def file_digest(path: Path) -> str:
	"""Content hash of a binary asset. Voice clips and marks are not text."""
	return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _voice_fingerprint(reference: str | None) -> str | None:
	"""Hash the reference clip's *contents*, not the path that names it.

	Keying on the path meant replacing `assets/voices/sample-01.wav` in place
	reused every narration ever made from the old clip -- the same class of
	stale-cache bug as a renderer source left out of the render key. Falls back
	to the path when the file is missing, so an unresolvable reference still
	produces a stable key and the real error surfaces in `narrate`.
	"""
	if not reference:
		return None
	path = Path(reference)
	if not path.is_absolute():
		path = ROOT / path
	try:
		return file_digest(path)
	except OSError:
		return reference


def audio_key(scene: dict[str, Any], spec: dict[str, Any]) -> str:
	"""What the narration depends on. Changing the picture must not re-narrate."""
	voice = spec.get("voice", {})
	return digest(
		[
			scene["narration"],
			_voice_fingerprint(voice.get("reference")),
			voice.get("seed"),
			"chatterbox-turbo-chunked",
		]
	)


# Everything that changes what a frame looks like. Narration is in here via the
# audio key, because the scene's length comes from it.
VISUAL_FIELDS = (
	"type",
	"heading",
	"bullets",
	"mermaid",
	"revealSteps",
	"revealCues",
	"code",
	"lang",
	"steps",
	"footer",
	"cards",
)

# The renderer's own source counts as an input. Without this, changing a colour
# or a layout leaves every cached video stale and the pipeline reports nothing
# to do -- which is exactly what happened when the palette changed.
# The Python side builds the render command (codec, preset, props), so it is
# just as much a renderer input as the components are. Leaving it out meant an
# encoder flag change silently reused the old videos.
RENDERER_SOURCES = (
	"render/remotion/src",
	"render/remotion/mermaid.config.json",
	"narratr/render.py",
	# The renderer's npm dependencies shape frames as surely as its components
	# do -- Lucide draws the icons, Mermaid draws the diagrams. Without this,
	# bumping either leaves every cached video holding the old glyphs and the
	# pipeline reporting nothing to do.
	#
	# package.json carries the *ranges*; the lockfile carries what actually
	# installs. `^4.0.0` can move Remotion under a package.json that never
	# changed, so the lockfile is the file that decides what draws a frame.
	"render/remotion/package.json",
	"render/remotion/package-lock.json",
	# Both of these were created after the rule above was written, and both
	# were missed by it. icons.py resolves every glyph and rewrites Mermaid's
	# icon nodes; highlight.mjs picks the Shiki theme and strips backgrounds.
	# Neither is optional to how a frame looks.
	"narratr/icons.py",
	"render/remotion/scripts/highlight.mjs",
)


@lru_cache(maxsize=1)
def renderer_digest() -> str:
	parts: list[str] = []
	for entry in RENDERER_SOURCES:
		path = ROOT / entry
		files = sorted(path.rglob("*")) if path.is_dir() else [path]
		for file in files:
			if file.is_file():
				parts.append(f"{file.relative_to(ROOT)}:{file.read_text()}")
	return digest(parts)


def speech_key(scene: dict[str, Any], spec: dict[str, Any]) -> str:
	"""Narration plus playback speed.

	Separate from audio_key so changing the speed resamples what already exists
	instead of re-narrating it.
	"""
	from narratr.speed import DEFAULT_SPEED

	return digest([audio_key(scene, spec), spec.get("voice", {}).get("speed", DEFAULT_SPEED)])


# The aligner's own source decides where every word lands, exactly as the
# renderer's source decides what a frame looks like. Without this, changing how
# text is normalised leaves every cached timings file stale while the pipeline
# reports nothing to do -- the same bug as RENDERER_SOURCES, one stage over.
ALIGNER_SOURCES = ("narratr/align.py", "narratr/spoken.py")


@lru_cache(maxsize=1)
def aligner_digest() -> str:
	return digest([f"{name}:{(ROOT / name).read_text()}" for name in ALIGNER_SOURCES])


def align_key(scene: dict[str, Any], spec: dict[str, Any]) -> str:
	"""Narration timings: the audio that ships, plus how it is aligned."""
	return digest([speech_key(scene, spec), aligner_digest()])


def video_key(scene: dict[str, Any], spec: dict[str, Any]) -> str:
	"""What the picture depends on.

	Keyed separately from audio so editing a diagram re-renders the video and
	reuses the narration, and editing narration does both.
	"""
	# The align key is in here because reveal beats are read from the aligned
	# narration: re-aligning a scene moves when its elements appear, so the
	# frames have to be redrawn even though nothing about the slide changed.
	return digest(
		[speech_key(scene, spec), align_key(scene, spec), renderer_digest()]
		+ [scene.get(field) for field in VISUAL_FIELDS]
	)


# A run directory is named for a human reading `ls`, not for a machine. It no
# longer needs to be derived from the spec: artifacts live in the content-keyed
# store, so a fresh directory still reuses everything already made.
UNSAFE = re.compile(r"[/\\:\x00-\x1f]+")


def safe_name(raw: str) -> str:
	"""A string that cannot escape or nest the directory it names."""
	# A slash would be read as a path separator and silently nest the
	# directory; `..` would climb out of runs/. Collapse whitespace first: a
	# newline is whitespace, and substituting it as an unsafe character would
	# leave a dash mid-title.
	cleaned = UNSAFE.sub("-", " ".join(str(raw).split()))[:60].strip(" .")
	return cleaned or "untitled"


def run_dir_name(spec: dict[str, Any], when: datetime | None = None) -> str:
	"""`<title> [DD-MM HH:MM AM/PM]`.

	A slash would be read as a path separator and silently nest the directory,
	so the date is dash-separated.
	"""
	title = safe_name(spec.get("source", {}).get("title", "untitled"))
	stamp = (when or datetime.now()).strftime("%d-%m %I:%M %p")
	return f"{title} [{stamp}]"


class Manifest:
	"""Per-run ledger. Committed after every scene, not every stage."""

	def __init__(self, path: Path, data: dict[str, Any]) -> None:
		self.path = path
		self.data = data
		# When set, stages act on this subset only. The manifest still holds
		# every scene, so a later full run reuses whatever was already done.
		self._only: set[str] | None = None

	def restrict(self, scene_ids: list[str] | None) -> None:
		self._only = set(scene_ids) if scene_ids else None

	@classmethod
	def load_or_create(cls, run_dir: Path, spec: dict[str, Any], run_id: str) -> Manifest:
		path = run_dir / "manifest.json"
		if path.exists():
			manifest = cls(path, json.loads(path.read_text()))
			manifest.refresh(spec)
			return manifest
		data = {
			"run_id": run_id,
			"created": time.time(),
			"title": spec["source"]["title"],
			"voice": spec.get("voice", {}),
			"scenes": {
				s["id"]: {
					"audio_key": audio_key(s, spec),
					"speech_key": speech_key(s, spec),
					"align_key": align_key(s, spec),
					"video_key": video_key(s, spec),
					"audio": None,
					"speech": None,
					"aligned": None,
					"video": None,
				}
				for s in spec["scenes"]
			},
		}
		manifest = cls(path, data)
		manifest.commit()
		return manifest

	def refresh(self, spec: dict[str, Any]) -> None:
		"""Re-key against the current spec, clearing whatever it invalidates.

		A stage's output is only still valid if the key it was made from has not
		moved. Editing narration invalidates audio, timings and video; editing a
		diagram invalidates only the video.
		"""
		# Drop scenes the spec no longer has. `pending()` reads the manifest,
		# not the spec, so a scene deleted from scenes.json stayed queued
		# forever and every stage died on `by_id[scene_id]` with a bare
		# KeyError -- which `cli.main` does not catch. Editing a spec and
		# re-running is the core workflow, so this crashed on the common path.
		# The artifacts stay in the content store; only the ledger entry goes.
		live = {scene["id"] for scene in spec["scenes"]}
		for stale in [sid for sid in self.data["scenes"] if sid not in live]:
			del self.data["scenes"][stale]

		for scene in spec["scenes"]:
			entry = self.data["scenes"].setdefault(
				scene["id"],
				{"audio": None, "speech": None, "aligned": None, "video": None},
			)
			fresh_audio = audio_key(scene, spec)
			fresh_speech = speech_key(scene, spec)
			fresh_align = align_key(scene, spec)
			fresh_video = video_key(scene, spec)
			if entry.get("audio_key") != fresh_audio:
				entry["audio_key"] = fresh_audio
				entry["audio"] = None
			if entry.get("speech_key") != fresh_speech:
				# The picture is measured from the sped audio, so a speed
				# change invalidates it -- but never the narration.
				entry["speech_key"] = fresh_speech
				entry["speech"] = None
			if entry.get("align_key") != fresh_align:
				entry["align_key"] = fresh_align
				entry["aligned"] = None
			if entry.get("video_key") != fresh_video:
				entry["video_key"] = fresh_video
				entry["video"] = None

			# A manifest that claims work is done while the artifact is gone
			# leaves the pipeline reporting "nothing to do" and producing a
			# stale video. Trust the filesystem over the record.
			for stage, folder in (
				("audio", "audio"),
				("speech", "speech"),
				("aligned", "timings"),
				("video", "video"),
			):
				name = entry.get(stage)
				if name and not (STORE / folder / name).exists():
					entry[stage] = None
		self.commit()

	def commit(self) -> None:
		atomic_write(self.path, json.dumps(self.data, indent=2))

	def pending(self, stage: str) -> list[str]:
		return [
			sid
			for sid, s in self.data["scenes"].items()
			if not s.get(stage) and (self._only is None or sid in self._only)
		]

	def mark(self, scene_id: str, stage: str, value: str) -> None:
		self.data["scenes"][scene_id][stage] = value
		self.commit()
