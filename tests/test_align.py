"""Captions are derived data, so the derivation is what needs testing."""

from __future__ import annotations

from narratr.align import _timestamp, normalise, to_cues, to_srt


def words(*spans):
	return [{"word": w, "start": s, "end": e, "score": 1.0} for w, s, e in spans]


def test_normalise_strips_punctuation_and_case():
	assert normalise("Every") == "every"
	assert normalise("again.") == "again"
	assert normalise("don't") == "don't"


def test_normalise_empties_unspeakable_tokens():
	assert normalise("—") == ""
	assert normalise("36") == ""


def test_timestamp_is_srt_format():
	assert _timestamp(0) == "00:00:00,000"
	assert _timestamp(1.234) == "00:00:01,234"
	assert _timestamp(3661.5) == "01:01:01,500"


def test_cue_breaks_on_word_count():
	cues = to_cues(words(*[(f"w{i}", i * 0.2, i * 0.2 + 0.1) for i in range(12)]))
	assert len(cues) == 2
	assert len(cues[0]["text"].split()) == 8


def test_cue_breaks_on_duration():
	cues = to_cues(words(("a", 0.0, 0.5), ("b", 0.5, 1.0), ("c", 1.0, 5.0)))
	assert len(cues) == 2


def test_cue_spans_first_start_to_last_end():
	cue = to_cues(words(("a", 0.5, 0.9), ("b", 1.0, 1.4)))[0]
	assert cue["start"] == 0.5
	assert cue["end"] == 1.4


def test_srt_is_numbered_from_one():
	srt = to_srt(to_cues(words(("hello", 0.0, 0.4), ("there", 0.5, 0.9))))
	assert srt.startswith("1\n00:00:00,000 --> 00:00:00,900\nhello there")


def test_empty_input_yields_no_cues():
	assert to_cues([]) == []
	assert to_srt([]) == ""
