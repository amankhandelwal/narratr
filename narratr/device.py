"""Device selection and the MPS memory discipline every stage needs."""

from __future__ import annotations


def select() -> str:
	"""Prefer Apple's Metal backend, fall back to CPU."""
	import torch

	return "mps" if torch.backends.mps.is_available() else "cpu"


def release_cache(device: str) -> None:
	"""Hand freed MPS blocks back to the system between scenes.

	The MPS caching allocator keeps blocks it has finished with. Measured on a
	24 GB M4 Pro, that grew the driver reservation to 14.6 GB while only 2.9 GB
	was live. Combined with the rest of the desktop that over-commits memory,
	and every later scene thrashes: ~1M page-ins and page-outs per generation,
	pushing rtf from ~1.0 to 4-6.

	Releasing the cache each scene holds the reservation near 3.6 GB and keeps
	rtf flat. Costs a negligible amount of re-allocation.

	Every stage that runs a model on MPS needs this, not just narration.
	"""
	if device != "mps":
		return
	# Imported here so `narratr doctor` does not pay for loading torch.
	import torch

	torch.mps.empty_cache()
