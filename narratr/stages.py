"""Stages that are planned but not built.

They raise rather than no-op so a run stops visibly at the edge of what works,
instead of producing a silently incomplete video.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from narratr.state import Manifest


def align(spec: dict[str, Any], manifest: Manifest, run_dir: Path) -> None:
	raise NotImplementedError(
		"align: not built yet. Planned: WhisperX forced alignment over "
		"runs/<id>/audio/*.wav, producing word timings and captions.srt"
	)


def render(spec: dict[str, Any], manifest: Manifest, run_dir: Path) -> None:
	raise NotImplementedError(
		"render: not built yet. Planned: render/remotion takes one scene plus its "
		"measured audio duration and writes one mp4. See render/CONTRACT.md"
	)
