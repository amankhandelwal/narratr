"""Scene rendering: one mp4 per scene, fitted to its measured audio.

The renderer is told how long it has and never asks for more. Everything it
needs arrives as props; it does not read scenes.json. See render/CONTRACT.md.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from narratr import icons, speed
from narratr.paths import ROOT, STORE
from narratr.state import Manifest

REMOTION = ROOT / "render" / "remotion"
FPS = 30


class RenderError(Exception):
	"""Rendering cannot proceed."""


def run_remotion(cmd: list[str], cwd: Path, what: str) -> None:
	result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
	if result.returncode != 0:
		tail = (result.stderr or result.stdout).strip().splitlines()[-6:]
		raise RenderError(f"{what} failed:\n  " + "\n  ".join(tail))


def mermaid_to_svg(source: str, out: Path) -> str:
	"""Render a Mermaid diagram to SVG, cached by content address.

	Pinning matters: node ids and class names are not a public API, and the
	Diagram component matches on them.
	"""
	if not out.exists():
		mmd = out.with_suffix(".mmd")
		mmd.write_text(source)
		tmp = out.with_name(f".{out.name}.partial.svg")
		run_remotion(
			[
				"npx",
				"mmdc",
				"-i",
				str(mmd),
				"-o",
				str(tmp),
				"-b",
				"transparent",
				"-c",
				"mermaid.config.json",
			],
			REMOTION,
			"mermaid",
		)
		tmp.rename(out)
	return out.read_text()


def highlight(code: str, lang: str | None, out: Path) -> str:
	"""Syntax-highlight to HTML, cached by content address.

	Done here rather than in the Remotion component so the renderer stays
	synchronous — highlighting in the component would need delayRender and
	would be paid for on every frame.
	"""
	if not out.exists():
		payload = json.dumps({"code": code, "lang": lang or "text"})
		result = subprocess.run(
			["node", "scripts/highlight.mjs"],
			cwd=REMOTION,
			input=payload,
			capture_output=True,
			text=True,
		)
		if result.returncode != 0:
			tail = (result.stderr or result.stdout).strip().splitlines()[-4:]
			raise RenderError("highlight failed:\n  " + "\n  ".join(tail))
		tmp = out.with_name(f".{out.name}.partial.html")
		tmp.write_text(result.stdout)
		tmp.rename(out)
	return out.read_text()


def _props_for(
	scene: dict[str, Any], duration: float, assets: Path, key: str = "k"
) -> dict[str, Any]:
	props: dict[str, Any] = {
		"type": scene["type"],
		"durationInSeconds": duration,
		"heading": scene.get("heading"),
	}
	# Icons resolve here, like Mermaid and Shiki, so the component stays
	# synchronous. Keyed by name because a scene may use one twice.
	wanted = icons.names_in(scene)
	if wanted:
		props["icons"] = {name: icons.markup(name) for name in dict.fromkeys(wanted)}
	if scene["type"] == "prose":
		props["bullets"] = scene.get("bullets", [])
	elif scene["type"] == "flow":
		props["steps"] = scene.get("steps", [])
		props["footer"] = scene.get("footer")
	elif scene["type"] == "cards":
		props["cards"] = scene.get("cards", [])
	elif scene["type"] == "diagram":
		svg_path = assets / f"{key}.svg"
		props["svg"] = mermaid_to_svg(scene["mermaid"], svg_path)
		props["revealSteps"] = scene.get("revealSteps", [])
	elif scene["type"] == "code":
		code = scene.get("code", "")
		props["code"] = code
		props["lang"] = scene.get("lang")
		props["html"] = highlight(code, scene.get("lang"), assets / f"{key}.html")
	return props


def scene_duration(entry: dict[str, Any]) -> float:
	"""Duration measured from the rendered audio, never estimated."""
	import torchaudio

	info = torchaudio.info(str(speed.path_for(entry)))
	return info.num_frames / info.sample_rate


def run(spec: dict[str, Any], manifest: Manifest, run_dir: Path) -> None:
	todo = manifest.pending("video")
	if not todo:
		print("render: nothing to do")
		return

	missing = [sid for sid in todo if not manifest.data["scenes"][sid].get("audio")]
	if missing:
		raise RenderError(f"no audio yet for {', '.join(missing[:3])}; run narration first")

	if not (REMOTION / "node_modules").exists():
		raise RenderError(f"renderer not installed: run 'npm install' in {REMOTION}")

	video_dir = STORE / "video"
	video_dir.mkdir(parents=True, exist_ok=True)

	remaining = []
	for scene_id in todo:
		cached = video_dir / f"{manifest.data['scenes'][scene_id]['video_key']}.mp4"
		if cached.exists():
			manifest.mark(scene_id, "video", cached.name)
		else:
			remaining.append(scene_id)
	todo = remaining
	if not todo:
		print("render: nothing to do")
		return

	assets = STORE / "assets"
	assets.mkdir(parents=True, exist_ok=True)

	by_id = {s["id"]: s for s in spec["scenes"]}
	print(f"render: {len(todo)} scene(s) at {FPS}fps")
	rendered = 0.0
	elapsed = 0.0

	for n, scene_id in enumerate(todo, 1):
		entry = manifest.data["scenes"][scene_id]
		out = video_dir / f"{entry['video_key']}.mp4"
		duration = scene_duration(entry)
		props = _props_for(by_id[scene_id], duration, assets, entry["video_key"])
		props_file = assets / f"{entry['video_key']}.props.json"
		props_file.write_text(json.dumps(props))

		tmp = out.with_name(f".{out.name}.partial.mp4")
		started = time.perf_counter()
		run_remotion(
			[
				"npx",
				"remotion",
				"render",
				"src/index.ts",
				"Scene",
				str(tmp),
				f"--props={props_file}",
				"--codec=h264",
				"--log=error",
			],
			REMOTION,
			f"render {scene_id}",
		)
		took = time.perf_counter() - started
		tmp.rename(out)
		manifest.mark(scene_id, "video", out.name)

		rendered += duration
		elapsed += took
		print(
			f"  [{n}/{len(todo)}] {scene_id}: {duration:5.1f}s video in {took:5.1f}s "
			f"(rtf {took / duration:.2f})"
		)

	if rendered:
		print(f"✓ render: {rendered:.0f}s video in {elapsed:.0f}s (rtf {elapsed / rendered:.2f})")
