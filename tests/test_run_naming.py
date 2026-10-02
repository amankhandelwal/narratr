"""Run directories are named for people, so resolution has to be forgiving."""

from __future__ import annotations

from datetime import datetime

import pytest

from narratr.state import run_dir_name, safe_name

SPEC = {"source": {"title": "narratr in brief"}}


def test_format_is_title_then_stamp():
	assert run_dir_name(SPEC, datetime(2026, 9, 5, 13, 22)) == "narratr in brief [05-09 01.22 PM]"


def test_midnight_and_noon_are_not_confused():
	assert "12.05 AM" in run_dir_name(SPEC, datetime(2026, 9, 5, 0, 5))
	assert "12.05 PM" in run_dir_name(SPEC, datetime(2026, 9, 5, 12, 5))


def test_slashes_are_replaced_not_nested():
	name = run_dir_name({"source": {"title": "reports/q3"}})
	assert "/" not in name


def test_colon_in_a_title_does_not_reach_the_name():
	assert ":" not in run_dir_name({"source": {"title": "draft: v2"}}).split("[")[0]


def test_whitespace_is_collapsed():
	assert run_dir_name({"source": {"title": "a   b\n c"}}).startswith("a b c [")


def test_long_titles_are_capped():
	name = run_dir_name({"source": {"title": "x" * 200}})
	assert len(name.split(" [")[0]) <= 60


def test_missing_title_falls_back():
	assert run_dir_name({}).startswith("untitled [")


@pytest.mark.parametrize("title", ["narratr in brief", "x" * 200, "draft: v2", "a/b\\c"])
@pytest.mark.parametrize("when", [datetime(2026, 9, 5, 0, 5), datetime(2026, 9, 5, 13, 22)])
def test_a_run_name_survives_being_passed_back(title: str, when: datetime):
	# A detached child receives the name as --run-name and sanitises it again.
	# If that changed it, the child would write to a second directory.
	name = run_dir_name({"source": {"title": title}}, when)
	assert safe_name(name, limit=None) == name
