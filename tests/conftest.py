"""Shared test setup.

The suite has one dependency that is not a Python package: the Lucide icon
pack, installed by `npm ci` into render/remotion/node_modules. `narratr
validate` checks every icon name against it, so any test that validates a real
example spec needs it too.

Without it those tests fail on "icons: pack not installed", which is a true
statement about the machine and a confusing one to meet as fourteen assertion
errors. This says it once, up front, and names the fix.
"""

from __future__ import annotations

import pytest

from narratr import icons


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
	"""Explain the failures, after the reader has seen them.

	Reported at the end rather than in `pytest_configure`, which runs before
	the terminal reporter writes anything and is suppressed under -q.
	"""
	if icons.installed():
		return
	terminalreporter.write_sep("=", "icon pack missing", red=True)
	terminalreporter.write_line(
		"Every failure above is 'icons: pack not installed', not a real defect.\n"
		"narratr validate checks icon names against the Lucide pack, so the\n"
		"tests that validate an example spec need it installed:\n"
		"\n"
		"  make setup          (or: npm ci --prefix render/remotion)"
	)
