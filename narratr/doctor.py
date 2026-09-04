"""Environment checks.

Runs before anything expensive, and names the fix rather than just the fault.
Imports are deliberately lazy so a broken install still reports usefully
instead of failing at import time.
"""

from __future__ import annotations

import shutil
import sys

from narratr.paths import VOICES

Check = tuple[str, bool, str]


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

	ffmpeg = shutil.which("ffmpeg")
	checks.append(("ffmpeg", ffmpeg is not None, ffmpeg or "not found"))

	node = shutil.which("node")
	checks.append(("node", node is not None, node or "not found"))

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
