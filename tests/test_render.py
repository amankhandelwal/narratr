"""Props are the whole interface to the renderer, so test what gets sent."""

from __future__ import annotations

from pathlib import Path

from narratr.render import _props_for

ASSETS = Path("/tmp/narratr-test-assets")


def test_prose_carries_bullets_and_duration():
	scene = {"id": "s", "type": "prose", "heading": "H", "bullets": ["a", "b"], "narration": "..."}
	props = _props_for(scene, 12.5, ASSETS)
	assert props["type"] == "prose"
	assert props["durationInSeconds"] == 12.5
	assert props["bullets"] == ["a", "b"]
	assert "svg" not in props


def test_code_carries_source_not_bullets(tmp_path, monkeypatch):
	monkeypatch.setattr("narratr.render.highlight", lambda code, lang, out: "<pre/>")
	scene = {"id": "s", "type": "code", "code": "echo hi", "lang": "sh", "narration": "..."}
	props = _props_for(scene, 4.0, tmp_path)
	assert props["code"] == "echo hi"
	assert props["lang"] == "sh"
	assert "bullets" not in props


def test_prose_without_bullets_still_renders():
	props = _props_for({"id": "s", "type": "prose", "narration": "..."}, 3.0, ASSETS)
	assert props["bullets"] == []


def test_duration_is_passed_through_unrounded():
	# The renderer does the frame rounding; the contract passes real seconds.
	props = _props_for({"id": "s", "type": "prose", "narration": "..."}, 11.837, ASSETS)
	assert props["durationInSeconds"] == 11.837


def test_mux_names_both_streams_explicitly():
	"""Remotion writes a silent AAC track into every scene at a higher bitrate
	than our narration. Without explicit -map, ffmpeg picks that as the "best"
	audio and the video comes out silent with no warning."""
	from pathlib import Path

	from narratr.stitch import mux_args

	args = mux_args(Path("v.mp4"), Path("a.wav"), Path("o.mp4"))
	assert "-map" in args
	assert args[args.index("-map") + 1] == "0:v:0"
	rest = args[args.index("-map") + 2 :]
	assert rest[rest.index("-map") + 1] == "1:a:0"


def test_code_props_carry_highlighted_html(tmp_path, monkeypatch):
	"""The html prop went missing once: Scene.tsx did not forward it and Code
	silently fell back to plain text. Nothing failed, it just looked wrong."""
	monkeypatch.setattr("narratr.render.highlight", lambda code, lang, out: "<pre>hl</pre>")
	scene = {"id": "s", "type": "code", "code": "echo hi", "lang": "sh", "narration": "..."}
	props = _props_for(scene, 4.0, tmp_path)
	assert props["html"] == "<pre>hl</pre>"


def test_highlight_is_cached_by_path(tmp_path):
	from narratr.render import highlight

	out = tmp_path / "s.html"
	out.write_text("<pre>already here</pre>")
	# An existing file must be reused rather than shelling out to node again.
	assert highlight("ignored", "sh", out) == "<pre>already here</pre>"
