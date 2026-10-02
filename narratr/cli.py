"""Command line entry point.

Claude produces scenes.json; everything here is deterministic.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from narratr import blocks, doctor, icons, pipeline, stitch
from narratr.errors import PipelineError
from narratr.paths import RUNS, STORE
from narratr.spec import load_spec, summarise, validate
from narratr.state import Manifest, run_dir_name, safe_name


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


def cmd_icons(args: argparse.Namespace) -> int:
	"""Search the installed Lucide names.

	The pack has ~2,000 icons. Carrying that list in a skill would cost more
	context than it is worth, so the skill looks a name up instead of guessing
	twice.
	"""
	if not icons.installed():
		print(f"❌ Icon pack not installed: run 'npm install' in {icons.PACK.parent.parent}")
		return 1
	found = icons.search(args.query)
	if not found:
		near = icons.suggest(args.query)
		print(
			f"No icon matches '{args.query}'" + (f" -- closest: {', '.join(near)}" if near else "")
		)
		return 1
	for name in found:
		print(f"  {name}")
	print(f"\n{len(found)} match(es) of {len(icons.available())} icons")
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

	unknown = pipeline.unknown_scenes(spec, args.only)
	if unknown:
		known = sorted(scene["id"] for scene in spec["scenes"])
		print(f"❌ No such scene: {', '.join(unknown)}")
		print(f"  available: {', '.join(known)}")
		return 1

	# --run-name is internal, but it still names a directory. run_dir_name
	# sanitises; this used to not, so `--run-name ../../tmp/x` wrote outside
	# runs/ and was forwarded verbatim to the detached child. No length cap:
	# the name was capped when the parent made it, and re-capping it here sent
	# a long-titled run's output to a different directory from its run.log.
	run_id = safe_name(args.run_name, limit=None) if args.run_name else run_dir_name(spec)
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
		print(f"  narratr status {run_id!r}")
		return 0

	shutil.copy(args.scenes, run_dir / "scenes.json")
	manifest = Manifest.load_or_create(run_dir, spec, run_id)
	print(f"run: {run_id}")
	if args.only:
		print(f"  only: {', '.join(args.only)}")

	pipeline.execute(spec, manifest, run_dir, only=args.only)

	if args.only:
		# A rendered scene carries Remotion's silent track, so the file the old
		# code pointed at could not be listened to -- and it pointed into
		# run_dir/video/, which has not existed since artifacts moved to store/.
		for scene_id in args.only:
			playable = stitch.preview(manifest, scene_id, run_dir)
			if playable:
				print(f"→ {playable}")
		print("  Run without --only to stitch the finished video.")
	return 0


def cmd_gc(args: argparse.Namespace) -> int:
	"""Delete store artifacts no run still refers to.

	The store is append-only by design -- that is what makes an edit cheap --
	but nothing ever removed anything, so every renderer change orphaned a full
	set of videos and the directory only grew.
	"""
	live: set[str] = set()
	for manifest_path in RUNS.glob("*/manifest.json"):
		try:
			data = json.loads(manifest_path.read_text())
		except json.JSONDecodeError:
			print(f"⚠️  skipping unreadable manifest: {manifest_path.parent.name}")
			continue
		for entry in data.get("scenes", {}).values():
			for stage in ("audio", "speech", "aligned", "video"):
				name = entry.get(stage)
				if name:
					live.add(Path(name).stem)
			for key in ("audio_key", "speech_key", "video_key"):
				if entry.get(key):
					live.add(entry[key])

	orphans: list[Path] = []
	freed = 0
	for path in STORE.rglob("*"):
		if not path.is_file():
			continue
		# Keys are the stem, but padded files are "<key>.30.wav" and intro
		# props are "intro.<key>.props.json", so match on any dot-separated part.
		if live.isdisjoint(path.name.split(".")):
			orphans.append(path)
			freed += path.stat().st_size

	if not orphans:
		print("✓ gc: nothing to remove")
		return 0

	# Deleting is the one irreversible thing this tool does, so it says what
	# it would do and needs to be told to do it.
	print(f"gc: {len(orphans)} orphaned file(s), {freed / 1e6:.0f} MB")
	if not args.delete:
		for path in sorted(orphans)[:10]:
			print(f"  {path.relative_to(STORE)}")
		if len(orphans) > 10:
			print(f"  ... and {len(orphans) - 10} more")
		print("\n  Re-run with --delete to remove them.")
		return 0
	for path in orphans:
		path.unlink(missing_ok=True)
	print(f"✓ gc: freed {freed / 1e6:.0f} MB")
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
	total = len(scenes)

	print(f"run {run_dir.name}")
	# Every stage, not just narration. A run twenty minutes into rendering used
	# to report "audio 6/6" and nothing else, which is the whole of what a
	# detached run can tell you about itself.
	for stage, label in (
		("audio", "narrate"),
		("speech", "speed"),
		("aligned", "align"),
		("video", "render"),
	):
		done = sum(1 for s in scenes.values() if s.get(stage))
		bar = "█" * round(12 * done / total) if total else ""
		print(f"  {label:8} {done:>3}/{total} {bar}")

	incomplete = [
		(label, sorted(sid for sid, s in scenes.items() if not s.get(stage)))
		for stage, label in (
			("audio", "narrate"),
			("speech", "speed"),
			("aligned", "align"),
			("video", "render"),
		)
	]
	for label, pending in incomplete:
		if pending:
			shown = ", ".join(pending[:5])
			more = f" (+{len(pending) - 5})" if len(pending) > 5 else ""
			print(f"\n  {label} pending: {shown}{more}")
			break

	final = run_dir / "video.mp4"
	if final.exists():
		print(f"\n  ✓ {final}")

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

	icons_cmd = sub.add_parser("icons", help="search Lucide icon names")
	icons_cmd.add_argument("query", help="word to match against names and Lucide's tags")

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

	gc_cmd = sub.add_parser("gc", help="remove store artifacts no run refers to")
	gc_cmd.add_argument(
		"--delete", action="store_true", help="actually remove them; otherwise just reports"
	)

	status_cmd = sub.add_parser("status", help="progress of a run")
	status_cmd.add_argument("run_id", nargs="?", help="name or prefix; defaults to the newest")

	return parser


def main() -> int:
	args = build_parser().parse_args()
	handlers: dict[str, Callable[[argparse.Namespace], int]] = {
		"doctor": cmd_doctor,
		"blocks": cmd_blocks,
		"icons": cmd_icons,
		"validate": cmd_validate,
		"render": cmd_render,
		"status": cmd_status,
		"gc": cmd_gc,
	}
	try:
		return handlers[args.cmd](args)
	except PipelineError as exc:
		# One base class rather than a list that has to be kept in step with
		# every module. IconError and IntroError were both missing from the old
		# tuple and reached the user as tracebacks from inside a render.
		print(f"❌ {exc}", file=sys.stderr)
		return 1
	except json.JSONDecodeError as exc:
		print(f"❌ unreadable JSON: {exc}", file=sys.stderr)
		return 1
	except KeyboardInterrupt:
		# Checkpointed per scene, so say what was kept rather than dumping a
		# traceback from wherever the interrupt landed.
		print("\n⚠️  Interrupted. Finished scenes are kept; re-run to continue.", file=sys.stderr)
		return 130


if __name__ == "__main__":
	sys.exit(main())
