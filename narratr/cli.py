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

from narratr import align, blocks, doctor, narrate, stages
from narratr.paths import RUNS
from narratr.spec import SpecError, load_spec, summarise, validate
from narratr.state import Manifest, run_id_for


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

	run_id = run_id_for(spec)
	run_dir = RUNS / run_id
	run_dir.mkdir(parents=True, exist_ok=True)

	if args.detach:
		# Daemonize so the run outlives the session that started it. Popen dups
		# the descriptor, so closing our handle here does not affect the child.
		with open(run_dir / "run.log", "a") as log:
			subprocess.Popen(
				[sys.executable, "-m", "narratr.cli", "render", str(args.scenes.resolve())],
				stdout=log,
				stderr=subprocess.STDOUT,
				start_new_session=True,
			)
		print(f"✓ Run {run_id} started in background")
		print(f"  narratr status {run_id}")
		return 0

	shutil.copy(args.scenes, run_dir / "scenes.json")
	manifest = Manifest.load_or_create(run_dir, spec, run_id)
	print(f"run {run_id}: {spec['source']['title']}")

	narrate.run(spec, manifest, run_dir)
	for stage in (align.run, stages.render):
		try:
			stage(spec, manifest, run_dir)
		except NotImplementedError as exc:
			print(f"\n⚠️  Stopped: {exc}")
			print(f"  Audio is complete in {run_dir / 'audio'}")
			return 2
	return 0


def cmd_status(args: argparse.Namespace) -> int:
	manifest_path = RUNS / args.run_id / "manifest.json"
	if not manifest_path.exists():
		print(f"❌ No such run: {args.run_id}", file=sys.stderr)
		return 1

	data = json.loads(manifest_path.read_text())
	scenes = data["scenes"]
	done = sum(1 for s in scenes.values() if s.get("audio"))

	print(f"run {data['run_id']}: {data['title']}")
	print(f"  audio   {done}/{len(scenes)} scenes")
	if done < len(scenes):
		pending = sorted(sid for sid, s in scenes.items() if not s.get("audio"))
		print(f"  pending {', '.join(pending[:5])}")

	log = RUNS / args.run_id / "run.log"
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

	status_cmd = sub.add_parser("status", help="progress of a run")
	status_cmd.add_argument("run_id")

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
	except (SpecError, narrate.NarrationError, align.AlignmentError) as exc:
		print(f"❌ {exc}", file=sys.stderr)
		return 1


if __name__ == "__main__":
	sys.exit(main())
