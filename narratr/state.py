"""Run state: content addressing and a checkpointed manifest.

A run is hours long and must survive a closed lid, a killed process, or the
session that started it going away. Two mechanisms carry that: every artifact
is content-addressed, and the manifest is committed after every scene.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


def atomic_write(path: Path, payload: str) -> None:
	"""Write via tmp + rename. A half-written file must never look complete."""
	tmp = path.with_suffix(path.suffix + ".tmp")
	with open(tmp, "w") as fh:
		fh.write(payload)
		fh.flush()
		os.fsync(fh.fileno())
	tmp.rename(path)


def _digest(material: Any) -> str:
	return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()[:16]


def audio_key(scene: dict[str, Any], spec: dict[str, Any]) -> str:
	"""What the narration depends on. Changing the picture must not re-narrate."""
	voice = spec.get("voice", {})
	return _digest(
		[scene["narration"], voice.get("reference"), voice.get("seed"), "chatterbox-turbo"]
	)


# Everything that changes what a frame looks like. Narration is in here via the
# audio key, because the scene's length comes from it.
VISUAL_FIELDS = ("type", "heading", "bullets", "mermaid", "revealSteps", "code", "lang")


def video_key(scene: dict[str, Any], spec: dict[str, Any]) -> str:
	"""What the picture depends on.

	Keyed separately from audio so editing a diagram re-renders the video and
	reuses the narration, and editing narration does both.
	"""
	return _digest([audio_key(scene, spec)] + [scene.get(field) for field in VISUAL_FIELDS])


def run_id_for(spec: dict[str, Any]) -> str:
	"""Stable id for a spec, so re-running the same input resumes it."""
	return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:12]


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
					"video_key": video_key(s, spec),
					"audio": None,
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
		for scene in spec["scenes"]:
			entry = self.data["scenes"].setdefault(
				scene["id"], {"audio": None, "aligned": None, "video": None}
			)
			fresh_audio = audio_key(scene, spec)
			fresh_video = video_key(scene, spec)
			if entry.get("audio_key") != fresh_audio:
				entry["audio_key"] = fresh_audio
				entry["audio"] = None
				entry["aligned"] = None
			if entry.get("video_key") != fresh_video:
				entry["video_key"] = fresh_video
				entry["video"] = None
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
