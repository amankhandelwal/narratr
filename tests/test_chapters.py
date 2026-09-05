"""Chapters must line up with the assembled video, not the raw audio."""

from __future__ import annotations

from narratr.stitch import chapter_metadata

SPEC = {
	"scenes": [
		{"id": "one", "heading": "First thing"},
		{"id": "two", "heading": "Second thing"},
		{"id": "three"},
	]
}
DURATIONS = {"one": 10.0, "two": 5.5, "three": 4.0}


def meta() -> str:
	return chapter_metadata(SPEC, DURATIONS)


def test_starts_with_the_ffmetadata_header():
	assert meta().startswith(";FFMETADATA1")


def test_one_chapter_per_scene():
	assert meta().count("[CHAPTER]") == 3


def test_headings_become_titles():
	assert "title=First thing" in meta()


def test_scene_without_a_heading_falls_back_to_its_id():
	assert "title=three" in meta()


def test_offsets_are_cumulative():
	body = meta()
	assert "START=0" in body
	assert "START=10000" in body  # after the 10s first scene
	assert "START=15500" in body  # after 10 + 5.5


def test_chapters_do_not_overlap():
	lines = meta().splitlines()
	starts = [int(t.split("=")[1]) for t in lines if t.startswith("START=")]
	ends = [int(t.split("=")[1]) for t in lines if t.startswith("END=")]
	for end, next_start in zip(ends, starts[1:], strict=False):
		assert end < next_start


def test_a_zero_length_scene_does_not_invert_its_chapter():
	body = chapter_metadata({"scenes": [{"id": "x"}]}, {"x": 0.0})
	assert "START=0" in body and "END=0" in body
