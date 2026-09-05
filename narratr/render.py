"""Scene rendering: one mp4 per scene, fitted to its measured audio.

The renderer is told how long it has and never asks for more. Everything it
needs arrives as props; it does not read scenes.json. See render/CONTRACT.md.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from narratr import icons, media, speed
from narratr.errors import PipelineError
from narratr.paths import ROOT, STORE
from narratr.state import Manifest, atomic_write

REMOTION = ROOT / "render" / "remotion"

# Frame rate is owned by media.py so it is defined once for the whole pipeline.
FPS = media.FPS

# A long scene legitimately renders for minutes; this is a hang detector.
TIMEOUT = 30 * 60


class RenderError(PipelineError):
	"""Rendering cannot proceed."""


def run_remotion(cmd: list[str], cwd: Path, what: str) -> None:
	"""Run a node CLI, with a timeout.

	Unbounded, a wedged Puppeteer inside `mmdc` blocks the run forever -- and
	under `--detach` it does so in an orphaned session with no handle to kill.
	`--no-install` matters as much: `npx` falls back to fetching a package from
	the registry when the local one is absent, and `mmdc` is not a name this
	project owns.
	"""
	try:
		result = subprocess.run(
			cmd, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT, check=False
		)
	except subprocess.TimeoutExpired:
		raise RenderError(f"{what} timed out after {TIMEOUT // 60} min")
	except FileNotFoundError:
		raise RenderError(f"{what} failed: {cmd[0]} not found. Run 'narratr doctor'")
	if result.returncode != 0:
		tail = (result.stderr or result.stdout).strip().splitlines()[-6:]
		raise RenderError(f"{what} failed:\n  " + "\n  ".join(tail))


# `ID@{ icon: "lucide:name", form: "square", label: "text" }` -- Mermaid's own
# icon-node syntax, which it renders as a bare glyph with the label underneath.
ICON_NODE = re.compile(r"(?P<id>[A-Za-z0-9_-]+)@\{(?P<body>[^{}]*)\}")
ICON_FIELD = re.compile(r"""icon:\s*["']lucide:(?P<name>[a-z0-9-]+)["']""")
LABEL_FIELD = re.compile(r"""label:\s*["'](?P<text>[^"']*)["']""")


def inline_mermaid_icons(source: str) -> str:
	"""Rewrite Mermaid icon nodes as labelled boxes with the glyph inside.

	Mermaid's `@{ icon: ... }` shape *replaces* the box: you get a bare glyph
	with the text beneath it. That reads well for five nodes and falls apart for
	an engineering diagram, where the box is what carries the structure.

	So the node becomes an ordinary one whose label is `<icon> text`. Mermaid
	measures the rendered label to size the box, so the glyph is laid out for
	free and every node stays a `g.node` with a `rect` -- which is what the
	reveal animation and the edge routing already understand.

	Inlining the glyph also means Mermaid is never asked to load an icon pack.
	Its loader only takes a URL and fetches from unpkg.com, so this is what
	keeps the network off the render path.
	"""

	def rewrite(match: re.Match[str]) -> str:
		icon = ICON_FIELD.search(match.group("body"))
		if not icon:
			return match.group(0)  # some other @{} node; leave it alone
		label = LABEL_FIELD.search(match.group("body"))
		text = label.group("text") if label else match.group("id")
		glyph = icons.inline_markup(icon.group("name"))
		return f'{match.group("id")}["{glyph}{text}"]'

	return ICON_NODE.sub(rewrite, source)


def check_icons_landed(svg: str, names: list[str]) -> None:
	"""Refuse a diagram that came back without the icons it asked for.

	The glyph is inlined into the label, so a failure here means Mermaid's
	sanitiser dropped it -- which it does silently, leaving a diagram that
	renders, exits zero and is simply missing its icons. Every structural check
	passes that. This is the one that does not.

	The test is the glyph's own path data, which survives into the output
	verbatim.
	"""
	for name in dict.fromkeys(names):
		paths = re.findall(r"\sd='([^']{16,})'", icons.inline_markup(name))
		if not paths:
			continue  # nothing distinctive to look for; do not invent a failure
		if not any(fragment in svg for fragment in paths):
			raise RenderError(
				f"diagram rendered without its icons: '{name}' is missing from the SVG."
			)


def mermaid_to_svg(source: str, out: Path) -> str:
	"""Render a Mermaid diagram to SVG, cached by content address.

	Pinning matters: node ids and class names are not a public API, and the
	Diagram component matches on them.
	"""
	if not out.exists():
		wanted = icons.mermaid_names_in({"mermaid": source})
		# Scratch, deleted on the way out. It used to be written beside the SVG
		# and never read back or removed, so store/assets grew one per diagram.
		mmd = out.with_name(f".{out.name}.partial.mmd")
		mmd.write_text(inline_mermaid_icons(source))
		tmp = out.with_name(f".{out.name}.partial.svg")
		try:
			run_remotion(
				[
					"npx",
					"--no-install",
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
			check_icons_landed(tmp.read_text(), wanted)
			tmp.rename(out)
		finally:
			mmd.unlink(missing_ok=True)
			tmp.unlink(missing_ok=True)
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
		try:
			tmp.write_text(result.stdout)
			tmp.rename(out)
		finally:
			tmp.unlink(missing_ok=True)
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

	# `scene_duration` reads the *speech* artifact, not the narration, so that
	# is what has to exist. Guarding on `audio` let a None speech through and
	# died with a TypeError two frames deeper, under a message naming the wrong
	# stage.
	missing = [sid for sid in todo if not manifest.data["scenes"][sid].get("speech")]
	if missing:
		raise RenderError(
			f"no timed audio yet for {', '.join(missing[:3])}; run narration and speed first"
		)

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
		atomic_write(props_file, json.dumps(props))

		tmp = out.with_name(f".{out.name}.partial.mp4")
		started = time.perf_counter()
		try:
			run_remotion(
				[
					"npx",
					"--no-install",
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
		finally:
			tmp.unlink(missing_ok=True)
		manifest.mark(scene_id, "video", out.name)

		rendered += duration
		elapsed += took
		print(
			f"  [{n}/{len(todo)}] {scene_id}: {duration:5.1f}s video in {took:5.1f}s "
			f"(rtf {took / duration:.2f})"
		)

	if rendered:
		print(f"✓ render: {rendered:.0f}s video in {elapsed:.0f}s (rtf {elapsed / rendered:.2f})")
