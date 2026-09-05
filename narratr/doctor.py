"""Environment checks.

Runs before anything expensive, and names the fix rather than just the fault.
Imports are deliberately lazy so a broken install still reports usefully
instead of failing at import time.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import warnings

from narratr.paths import ROOT, VOICES

Check = tuple[str, bool, str]


def _node_major() -> int | None:
	node = shutil.which("node")
	if not node:
		return None
	try:
		out = subprocess.run(
			[node, "--version"], capture_output=True, text=True, timeout=10, check=False
		)
		return int(out.stdout.strip().lstrip("v").split(".")[0])
	except (OSError, ValueError, subprocess.TimeoutExpired):
		return None


def collect() -> list[Check]:
	checks: list[Check] = []

	checks.append(("python", sys.version_info >= (3, 11), sys.version.split()[0]))

	try:
		import torch

		checks.append(("torch", True, torch.__version__))
		mps = torch.backends.mps.is_available()
		checks.append(
			("mps acceleration", mps, "available" if mps else "CPU only, expect ~5x slower")
		)
	except ImportError:
		checks.append(("torch", False, "not installed, run 'make setup'"))
		checks.append(("mps acceleration", False, "unknown"))

	try:
		# perth imports pkg_resources, which warns on every invocation. The
		# whole point of doctor is a clean readable table.
		with warnings.catch_warnings():
			warnings.simplefilter("ignore", UserWarning)
			import perth

		ok = perth.PerthImplicitWatermarker is not None
		checks.append(
			(
				"chatterbox watermarker",
				ok,
				"ok" if ok else "None, pin setuptools<81 and re-run 'make reset'",
			)
		)
	except ImportError:
		checks.append(("chatterbox watermarker", False, "perth not installed"))

	# Every binary the pipeline actually shells out to. ffprobe was missing:
	# it is a separate executable from ffmpeg and stitch and intro both need
	# it. So was npx, which runs both mmdc and the renderer.
	for binary, fix in (
		("ffmpeg", "brew install ffmpeg"),
		("ffprobe", "brew install ffmpeg"),
		("node", "brew install node"),
		("npx", "brew install node"),
	):
		found = shutil.which(binary)
		checks.append((binary, found is not None, found or f"not found, run '{fix}'"))

	# Node 20+ per the README. An older one fails deep inside Remotion.
	node_version = _node_major()
	checks.append(
		(
			"node 20+",
			node_version is not None and node_version >= 20,
			f"v{node_version}" if node_version else "unknown",
		)
	)

	# The renderer's own dependencies. Without this check a fresh clone gets a
	# green doctor, spends the whole narration stage, and only then learns the
	# renderer was never installed.
	from narratr import icons

	node_modules = ROOT / "render" / "remotion" / "node_modules"
	checks.append(
		(
			"renderer deps",
			node_modules.is_dir(),
			"installed" if node_modules.is_dir() else "missing, run 'make setup'",
		)
	)
	pack = icons.installed()
	checks.append(
		(
			"icon pack",
			pack,
			f"{len(icons.available())} icons" if pack else "missing, run 'make setup'",
		)
	)

	free_gb = shutil.disk_usage(ROOT).free / 1e9
	checks.append(
		(
			"disk space",
			free_gb >= 5,
			f"{free_gb:.0f} GB free" if free_gb >= 5 else f"{free_gb:.0f} GB free, want 5+",
		)
	)

	voices = sorted(VOICES.glob("*.wav"))
	checks.append(
		(
			"voice reference",
			bool(voices),
			f"{len(voices)} sample(s)" if voices else "none, add a 10s clip to assets/voices/",
		)
	)

	return checks


def report() -> int:
	checks = collect()
	width = max(len(name) for name, _, _ in checks)
	for name, ok, detail in checks:
		mark = "✓" if ok else "❌"
		print(f"  {mark} {name.ljust(width)}  {detail}")

	if any(not ok for _, ok, _ in checks):
		print("\n❌ Not ready. Run 'make setup'")
		return 1
	print("\n✓ Ready")
	return 0
