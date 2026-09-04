"""The MPS cache release is a performance fix, so guard it against removal.

Measured on a 24 GB M4 Pro: without it the driver reservation grows to 14.6 GB,
the machine swaps ~1M pages per generation, and rtf goes from ~1.0 to 4-6.
"""

from __future__ import annotations

from unittest import mock

from narratr.narrate import _release_cache


def test_releases_cache_on_mps():
	with mock.patch("torch.mps.empty_cache") as empty:
		_release_cache("mps")
	empty.assert_called_once()


def test_does_not_touch_mps_on_cpu():
	with mock.patch("torch.mps.empty_cache") as empty:
		_release_cache("cpu")
	empty.assert_not_called()
