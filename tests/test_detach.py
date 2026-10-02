"""A detached render must keep everything in the one directory it announced.

The parent creates the run directory, opens run.log in it, and hands the name
to a background child with --run-name. The child used to sanitise that name a
second time: the colon in the timestamp became a dash and a long title was cut
to sixty characters, so the log stayed in one directory and the video, manifest
and captions went to another.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

from narratr import cli, pipeline

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "brief.scenes.json"


class FakePopen:
	"""Records the child's command line instead of starting it."""

	calls: ClassVar[list[list[str]]] = []

	def __init__(self, argv: list[str], **kwargs: Any) -> None:
		FakePopen.calls.append(argv)


@pytest.fixture
def runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
	runs = tmp_path / "runs"
	monkeypatch.setattr(cli, "RUNS", runs)
	monkeypatch.setattr(cli.subprocess, "Popen", FakePopen)
	# The child's real work is not the point here; where it writes is.
	monkeypatch.setattr(pipeline, "execute", lambda *args, **kwargs: None)
	FakePopen.calls = []
	return runs


def spec_titled(tmp_path: Path, title: str) -> Path:
	spec = json.loads(EXAMPLE.read_text())
	spec["source"]["title"] = title
	path = tmp_path / "scenes.json"
	path.write_text(json.dumps(spec))
	return path


def detach_then_run_child(scenes: Path) -> None:
	parser = cli.build_parser()
	assert cli.cmd_render(parser.parse_args(["render", str(scenes), "--detach"])) == 0
	(argv,) = FakePopen.calls
	# argv is [python, -m, narratr.cli, render, ...]; parse what the child would.
	child = parser.parse_args(argv[argv.index("render") :])
	assert cli.cmd_render(child) == 0


@pytest.mark.parametrize(
	"title",
	[
		"narratr in brief",
		"How the payments reconciliation pipeline handles refunds end to end",
		"draft: v2 / final",
	],
)
def test_log_and_outputs_share_one_directory(runs: Path, tmp_path: Path, title: str):
	detach_then_run_child(spec_titled(tmp_path, title))

	(run_dir,) = list(runs.iterdir())
	assert {"run.log", "scenes.json", "manifest.json"} <= {p.name for p in run_dir.iterdir()}


def test_child_writes_where_the_parent_announced(
	runs: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
	detach_then_run_child(spec_titled(tmp_path, "narratr in brief"))

	announced = capsys.readouterr().out.split("Run started in background: ")[1].splitlines()[0]
	assert (runs / announced / "manifest.json").exists()


def test_run_name_still_cannot_escape_runs(runs: Path, tmp_path: Path):
	scenes = spec_titled(tmp_path, "narratr in brief")
	args = cli.build_parser().parse_args(["render", str(scenes), "--run-name", "../../escape"])
	assert cli.cmd_render(args) == 0

	assert not (tmp_path / "escape").exists()
	(run_dir,) = list(runs.iterdir())
	assert run_dir.parent == runs
