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


def scene_key(scene: dict[str, Any], spec: dict[str, Any]) -> str:
	"""Content address: same inputs -> same file -> skip.

	This is what gives resume and incremental re-render from one mechanism.
	Edit one scene's narration and only that scene re-runs.
	"""
	voice = spec.get("voice", {})
	material = json.dumps(
		[scene["narration"], voice.get("reference"), voice.get("seed"), "chatterbox-turbo"],
		sort_keys=True,
	)
	return hashlib.sha256(material.encode()).hexdigest()[:16]


def run_id_for(spec: dict[str, Any]) -> str:
	"""Stable id for a spec, so re-running the same input resumes it."""
	return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:12]


class Manifest:
	"""Per-run ledger. Committed after every scene, not every stage."""

	def __init__(self, path: Path, data: dict[str, Any]) -> None:
		self.path = path
		self.data = data

	@classmethod
	def load_or_create(cls, run_dir: Path, spec: dict[str, Any], run_id: str) -> Manifest:
		path = run_dir / "manifest.json"
		if path.exists():
			return cls(path, json.loads(path.read_text()))
		data = {
			"run_id": run_id,
			"created": time.time(),
			"title": spec["source"]["title"],
			"voice": spec.get("voice", {}),
			"scenes": {
				s["id"]: {"key": scene_key(s, spec), "audio": None, "video": None}
				for s in spec["scenes"]
			},
		}
		manifest = cls(path, data)
		manifest.commit()
		return manifest

	def commit(self) -> None:
		atomic_write(self.path, json.dumps(self.data, indent=2))

	def pending(self, stage: str) -> list[str]:
		return [sid for sid, s in self.data["scenes"].items() if not s.get(stage)]

	def mark(self, scene_id: str, stage: str, value: str) -> None:
		self.data["scenes"][scene_id][stage] = value
		self.commit()
