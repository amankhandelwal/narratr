"""Images are the user's files, so validate catches a bad one before a build."""

from __future__ import annotations

import copy
import json

import pytest
from PIL import Image

from narratr.paths import ROOT
from narratr.spec import validate, video_problems

BRIEF = ROOT / "examples" / "brief.scenes.json"


@pytest.fixture
def spec() -> dict:
	return json.loads(BRIEF.read_text())


def with_image_scene(spec: dict, path: str) -> dict:
	out = copy.deepcopy(spec)
	out["scenes"].append(
		{"id": "picture", "type": "image", "image": path, "narration": "Here it is."}
	)
	return out


def test_a_png_beside_the_spec_is_accepted(spec, tmp_path):
	Image.new("RGB", (8, 8)).save(tmp_path / "shot.png")
	assert validate(with_image_scene(spec, "shot.png"), base=tmp_path) == []


def test_a_missing_image_is_rejected(spec, tmp_path):
	problems = validate(with_image_scene(spec, "nope.png"), base=tmp_path)
	assert any("nope.png" in p and "not found" in p for p in problems)


def test_a_renamed_non_image_is_rejected(spec, tmp_path):
	(tmp_path / "fake.png").write_text("not an image")
	problems = validate(with_image_scene(spec, "fake.png"), base=tmp_path)
	assert any("fake.png" in p for p in problems)


def test_an_unsupported_format_is_rejected(spec, tmp_path):
	Image.new("RGB", (8, 8)).save(tmp_path / "shot.bmp")
	problems = validate(with_image_scene(spec, "shot.bmp"), base=tmp_path)
	assert any("shot.bmp" in p and "PNG, JPEG or GIF" in p for p in problems)


def test_an_image_scene_needs_its_image(spec):
	broken = copy.deepcopy(spec)
	broken["scenes"].append({"id": "picture", "type": "image", "narration": "x"})
	assert any("'picture'" in p and "'image'" in p for p in validate(broken))


def test_card_images_are_checked_too(spec, tmp_path):
	broken = copy.deepcopy(spec)
	cards = next(s for s in broken["scenes"] if s["type"] == "cards")
	cards["cards"][0]["image"] = "gone.jpg"
	assert any("gone.jpg" in p for p in validate(broken, base=tmp_path))


def test_an_image_on_a_flow_is_rejected(spec, tmp_path):
	"""Only prose and image scenes draw a scene-level image."""
	Image.new("RGB", (8, 8)).save(tmp_path / "shot.png")
	broken = copy.deepcopy(spec)
	flow = next(s for s in broken["scenes"] if s["type"] == "flow")
	flow["image"] = "shot.png"
	assert any(f"'{flow['id']}'" in p and "'image'" in p for p in validate(broken, base=tmp_path))


def test_the_video_refuses_images(spec, tmp_path):
	Image.new("RGB", (8, 8)).save(tmp_path / "shot.png")
	assert video_problems(with_image_scene(spec, "shot.png"))
	assert video_problems(spec) == []
