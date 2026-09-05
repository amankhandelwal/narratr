"""One base class for everything the pipeline raises on purpose.

`cli.main` used to catch a hand-written tuple of six exception types. Two more
existed -- `icons.IconError`, raised mid-render, and `intro.IntroError` -- and
neither was in it, so both reached the user as a traceback. A list that has to
be kept in step with every module will drift; a base class will not.
"""

from __future__ import annotations


class PipelineError(Exception):
	"""Something the pipeline knows how to explain."""
