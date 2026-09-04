"""The MPS cache release is a performance fix, so guard it against removal.

Measured on a 24 GB M4 Pro: without it the driver reservation grows to 14.6 GB,
the machine swaps ~1M pages per generation, and rtf goes from ~1.0 to 4-6.
"""

from __future__ import annotations

from unittest import mock

from narratr.device import release_cache, select


def test_releases_cache_on_mps():
	with mock.patch("torch.mps.empty_cache") as empty:
		release_cache("mps")
	empty.assert_called_once()


def test_does_not_touch_mps_on_cpu():
	with mock.patch("torch.mps.empty_cache") as empty:
		release_cache("cpu")
	empty.assert_not_called()


def test_select_returns_a_known_device():
	assert select() in {"mps", "cpu"}
