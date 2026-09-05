"""Command line entry point.

Claude produces scenes.json; everything here is deterministic.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from narratr import align, blocks, doctor, narrate, render, speed, stitch
from narratr.paths import RUNS
from narratr.spec import SpecError, load_spec, summarise, validate
from narratr.state import Manifest, run_dir_name


def cmd_doctor(args: argparse.Namespace) -> int:
	return doctor.report()


def cmd_blocks(args: argparse.Namespace) -> int:
	"""Emit the leaf blocks of a document, for the coverage ledger.

	Pass 1 must build source.block_ids from this rather than by hand. A
	hand-written list can silently omit whatever the scene plan skipped.
	"""
	found = blocks.extract_file(args.document)
	if args.json:
		print(json.dumps([b["id"] for b in found], indent=2))
	else:
		for block in found:
			print(f"  {block['id']:34} {block['kind']}")
		print(f"\n{len(found)} leaf blocks")
	return 0


def cmd_validate(args: argparse.Namespace) -> int:
	spec = load_spec(args.scenes)
	problems = validate(spec)
	if problems:
		print(f"❌ Invalid ({len(problems)} problem(s)):")
		for problem in problems:
			print(f"  - {problem}")
		return 1
	print(f"✓ Valid: {summarise(spec)}")
	return 0


def cmd_render(args: argparse.Namespace) -> int:
	spec = load_spec(args.scenes)
	problems = validate(spec)
	if problems:
		print("❌ Refusing to spend compute on an invalid spec:")
		for problem in problems:
			print(f"  - {problem}")
		return 1

	known = {scene["id"] for scene in spec["scenes"]}
	unknown = [sid for sid in (args.only or []) if sid not in known]
	if unknown:
		print(f"❌ No such scene: {', '.join(unknown)}")
		print(f"  available: {', '.join(sorted(known))}")
		return 1

	run_id = args.run_name or run_dir_name(spec)
	run_dir = RUNS / run_id
	run_dir.mkdir(parents=True, exist_ok=True)

	if args.detach:
		# Daemonize so the run outlives the session that started it. Popen dups
		# the descriptor, so closing our handle here does not affect the child.
		with open(run_dir / "run.log", "a") as log:
			forwarded = [arg for sid in (args.only or []) for arg in ("--only", sid)]
			forwarded += ["--run-name", run_id]
			subprocess.Popen(
				[
					sys.executable,
					"-m",
					"narratr.cli",
					"render",
					str(args.scenes.resolve()),
					*forwarded,
				],
				stdout=log,
				stderr=subprocess.STDOUT,
				start_new_session=True,
			)
		print(f"✓ Run started in background: {run_id}")
		print("  narratr status")
		return 0

	shutil.copy(args.scenes, run_dir / "scenes.json")
	manifest = Manifest.load_or_create(run_dir, spec, run_id)
	manifest.restrict(args.only)
	print(f"run: {run_id}")
	if args.only:
		print(f"  only: {', '.join(args.only)}")

	narrate.run(spec, manifest, run_dir)
	# Stitching a subset would overwrite video.mp4 with a partial video, so a
	# restricted run stops after the per-scene files.
	stages = (
		(speed.run, align.run, render.run)
		if args.only
		else (speed.run, align.run, render.run, stitch.run)
	)
	for stage in stages:
		try:
			stage(spec, manifest, run_dir)
		except NotImplementedError as exc:
			print(f"\n⚠️  Stopped: {exc}")
			print(f"  Audio is complete in {run_dir / 'audio'}")
			return 2

	if args.only:
		for scene_id in args.only:
			video = manifest.data["scenes"][scene_id].get("video")
			if video:
				print(f"→ {run_dir / 'video' / video}")
		print("  Run without --only to stitch the finished video.")
	return 0


def resolve_run(name: str | None) -> Path | None:
	"""Find a run by exact name, unique prefix, or default to the newest.

	Run directories are named for people now, which means they have spaces in
	them. Defaulting to the newest saves quoting one most of the time.
	"""
	runs = sorted(
		(d for d in RUNS.glob("*") if (d / "manifest.json").exists()),
		key=lambda d: d.stat().st_mtime,
		reverse=True,
	)
	if not name:
		return runs[0] if runs else None
	exact = RUNS / name
	if (exact / "manifest.json").exists():
		return exact
	# runs is newest-first, so an ambiguous prefix resolves to the latest run
	# of that name -- which is what "show me how the brief is doing" means.
	matches = [d for d in runs if d.name.startswith(name)]
	return matches[0] if matches else None


def cmd_status(args: argparse.Namespace) -> int:
	run_dir = resolve_run(args.run_id)
	if run_dir is None:
		print(
			f"❌ No such run: {args.run_id}" if args.run_id else "❌ No runs yet", file=sys.stderr
		)
		return 1
	manifest_path = run_dir / "manifest.json"

	data = json.loads(manifest_path.read_text())
	scenes = data["scenes"]
	done = sum(1 for s in scenes.values() if s.get("audio"))

	print(f"run {run_dir.name}")
	print(f"  audio   {done}/{len(scenes)} scenes")
	if done < len(scenes):
		pending = sorted(sid for sid, s in scenes.items() if not s.get("audio"))
		print(f"  pending {', '.join(pending[:5])}")

	log = run_dir / "run.log"
	if log.exists():
		tail = log.read_text().strip().splitlines()
		if tail:
			print(f"  last    {tail[-1]}")
	return 0


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(prog="narratr", description=__doc__.splitlines()[0])
	sub = parser.add_subparsers(dest="cmd", required=True)

	sub.add_parser("doctor", help="check this machine can render")

	blocks_cmd = sub.add_parser("blocks", help="list a document's leaf blocks for the ledger")
	blocks_cmd.add_argument("document", type=Path)
	blocks_cmd.add_argument("--json", action="store_true", help="emit ids as a JSON array")

	validate_cmd = sub.add_parser("validate", help="schema + coverage check, spends nothing")
	validate_cmd.add_argument("scenes", type=Path)

	render_cmd = sub.add_parser("render", help="run the pipeline")
	render_cmd.add_argument("scenes", type=Path)
	render_cmd.add_argument(
		"--detach",
		action="store_true",
		help="run in the background; survives this session ending",
	)
	render_cmd.add_argument(
		"--run-name",
		help=argparse.SUPPRESS,  # internal: keeps a detached child in one directory
	)
	render_cmd.add_argument(
		"--only",
		action="append",
		metavar="SCENE_ID",
		help="render just this scene, repeatable; skips stitching",
	)

	status_cmd = sub.add_parser("status", help="progress of a run")
	status_cmd.add_argument("run_id", nargs="?", help="name or prefix; defaults to the newest")

	return parser


def main() -> int:
	args = build_parser().parse_args()
	handlers = {
		"doctor": cmd_doctor,
		"blocks": cmd_blocks,
		"validate": cmd_validate,
		"render": cmd_render,
		"status": cmd_status,
	}
	try:
		return handlers[args.cmd](args)
	except (
		SpecError,
		narrate.NarrationError,
		align.AlignmentError,
		render.RenderError,
		stitch.StitchError,
		speed.SpeedError,
	) as exc:
		print(f"❌ {exc}", file=sys.stderr)
		return 1


if __name__ == "__main__":
	sys.exit(main())
