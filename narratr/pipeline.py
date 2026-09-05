"""The stage sequence, and the rules about running part of it.

This lived inside an argparse handler, which is why none of it was testable and
none of it was tested. The CLI parses arguments; this decides what runs.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from narratr import align, narrate, render, speed, stitch
from narratr.state import Manifest


class Stage(Protocol):
	def __call__(self, spec: dict[str, Any], manifest: Manifest, run_dir: Path) -> None: ...


# Order is a dependency chain, not a preference: speed reads narration, align
# measures whatever audio ships, render is fitted to the sped audio, and stitch
# needs all three.
STAGES: tuple[tuple[str, Stage], ...] = (
	("narrate", narrate.run),
	("speed", speed.run),
	("align", align.run),
	("render", render.run),
	("stitch", stitch.run),
)

# Stitching a subset would overwrite video.mp4 with a partial video, so a
# restricted run stops after the per-scene files.
WHOLE_RUN_ONLY = frozenset({"stitch"})


def stages_for(only: list[str] | None) -> tuple[tuple[str, Stage], ...]:
	if not only:
		return STAGES
	return tuple((name, fn) for name, fn in STAGES if name not in WHOLE_RUN_ONLY)


def unknown_scenes(spec: dict[str, Any], only: list[str] | None) -> list[str]:
	known = {scene["id"] for scene in spec["scenes"]}
	return [sid for sid in (only or []) if sid not in known]


def execute(
	spec: dict[str, Any],
	manifest: Manifest,
	run_dir: Path,
	only: list[str] | None = None,
	on_stage: Callable[[str], None] | None = None,
) -> None:
	manifest.restrict(only)
	for name, stage in stages_for(only):
		if on_stage:
			on_stage(name)
		stage(spec, manifest, run_dir)
