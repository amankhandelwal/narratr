"""Reveals land on the words that introduce them.

The failure this replaces: elements spaced across the first 60% of the scene
regardless of narration, which put the last step of a 40s scene nine seconds
ahead of the phrase that introduces it.
"""

from __future__ import annotations

import pytest

from narratr import cues
from narratr.align import normalise

NARRATION = (
	"So here is the list. Zero unaccounted balance incidents needing manual "
	"forensics, against several days each. A new liquidity provider queryable "
	"the same day, against weeks."
)


def timings(narration: str, per_word: float = 0.5) -> list[dict[str, float]]:
	"""One entry per speakable word, evenly spaced -- what the aligner emits."""
	return [
		{"word": w, "start": i * per_word, "end": (i + 1) * per_word}
		for i, w in enumerate(cues.speakable(narration))
	]


class TestSpeakable:
	def test_matches_the_aligners_filter(self):
		# align.word_timings keeps exactly the words with a normalised form.
		narration = "A dash -- and a word."
		assert cues.speakable(narration) == [w for w in narration.split() if normalise(w)]

	def test_drops_unspeakable_tokens(self):
		assert "--" not in cues.speakable("A dash -- here.")


class TestFind:
	def test_finds_a_phrase(self):
		assert cues.find(NARRATION, "Zero unaccounted balance") == 5

	def test_index_addresses_the_aligned_words(self):
		words = timings(NARRATION)
		index = cues.find(NARRATION, "A new liquidity provider")
		assert words[index]["word"] == "A"
		assert words[index + 2]["word"] == "liquidity"

	def test_ignores_case_and_punctuation(self):
		assert cues.find(NARRATION, "manual forensics") == cues.find(NARRATION, "MANUAL FORENSICS,")

	def test_matches_spelled_out_numbers(self):
		# The aligner spells numbers out, so a cue may be written either way.
		assert cues.find("We booked 25 million dirhams.", "25 million") is not None
		assert cues.find("We booked 25 million dirhams.", "twenty five million") is not None

	def test_missing_phrase_returns_none(self):
		assert cues.find(NARRATION, "nowhere in this text") is None

	def test_empty_cue_returns_none(self):
		assert cues.find(NARRATION, "   ") is None

	def test_cue_longer_than_narration_returns_none(self):
		assert cues.find("Two words", "far more words than exist here") is None

	def test_first_occurrence_wins(self):
		assert cues.find("one two one two", "one two") == 0


class TestCueList:
	def test_prose_reads_bullet_cues(self):
		scene = {"type": "prose", "bullets": [{"text": "a", "cue": "x"}, "plain string"]}
		assert cues.cue_list(scene) == ["x", None]

	def test_flow_reads_step_cues(self):
		scene = {
			"type": "flow",
			"steps": [{"icon": "i", "label": "l", "cue": "x"}, {"icon": "i", "label": "l"}],
		}
		assert cues.cue_list(scene) == ["x", None]

	def test_cards_read_card_cues(self):
		scene = {"type": "cards", "cards": [{"title": "t", "cue": "x"}]}
		assert cues.cue_list(scene) == ["x"]

	def test_diagram_pads_missing_reveal_cues(self):
		scene = {"type": "diagram", "revealSteps": [["A"], ["B"], ["C"]], "revealCues": ["x"]}
		assert cues.cue_list(scene) == ["x", None, None]

	def test_code_reveals_nothing(self):
		assert cues.cue_list({"type": "code", "code": "x"}) == []


class TestBeats:
	def test_cued_element_lands_on_its_phrase(self):
		scene = {
			"type": "cards",
			"narration": NARRATION,
			"cards": [{"title": "a", "cue": "Zero unaccounted balance"}],
		}
		words = timings(NARRATION)
		index = cues.find(NARRATION, "Zero unaccounted balance")
		assert cues.beats(scene, words, 30.0) == [words[index]["start"]]

	def test_uncued_element_follows_the_narration_timeline(self):
		scene = {"type": "cards", "narration": NARRATION, "cards": [{"title": "a"}, {"title": "b"}]}
		beats = cues.beats(scene, timings(NARRATION), 30.0)
		assert beats == sorted(beats)
		# Spread through the speech, not crammed into the front 60%.
		assert beats[-1] > timings(NARRATION)[-1]["start"] * 0.4

	def test_beats_never_go_backwards(self):
		scene = {
			"type": "cards",
			"narration": NARRATION,
			"cards": [
				{"title": "a", "cue": "against weeks"},
				{"title": "b", "cue": "Zero unaccounted"},
			],
		}
		beats = cues.beats(scene, timings(NARRATION), 60.0)
		assert beats == sorted(beats)

	def test_settle_is_left_at_the_end(self):
		scene = {
			"type": "cards",
			"narration": NARRATION,
			"cards": [{"title": "a", "cue": "against weeks"}],
		}
		duration = 5.0
		assert cues.beats(scene, timings(NARRATION), duration)[0] <= duration - cues.SETTLE

	def test_no_elements_no_beats(self):
		assert cues.beats({"type": "code", "narration": NARRATION}, timings(NARRATION), 10.0) == []

	def test_no_timings_no_beats(self):
		scene = {"type": "cards", "narration": NARRATION, "cards": [{"title": "a"}]}
		assert cues.beats(scene, [], 10.0) == []

	def test_one_beat_per_element(self):
		scene = {
			"type": "flow",
			"narration": NARRATION,
			"steps": [{"icon": "i", "label": str(n)} for n in range(5)],
		}
		assert len(cues.beats(scene, timings(NARRATION), 30.0)) == 5


@pytest.mark.parametrize(
	"kind,field,items",
	[
		("prose", "bullets", [{"text": "a"}, {"text": "b"}]),
		("flow", "steps", [{"icon": "i", "label": "a"}, {"icon": "i", "label": "b"}]),
		("cards", "cards", [{"title": "a"}, {"title": "b"}]),
	],
)
def test_every_revealing_type_gets_beats(kind, field, items):
	scene = {"type": kind, "narration": NARRATION, field: items}
	assert len(cues.beats(scene, timings(NARRATION), 30.0)) == 2


class TestBoundaries:
	def test_half_a_word_does_not_match(self):
		# "twenty" alone is half of the normalised "twentyfive".
		assert cues.find("We booked 25 million.", "twenty") is None

	def test_spoken_and_written_forms_both_match(self):
		narration = "We booked 25 million dirhams."
		assert cues.find(narration, "25 million") == cues.find(narration, "twenty five million")

	def test_match_must_start_on_a_word(self):
		assert cues.find("Reconciliation matters.", "conciliation") is None


class TestGate:
	"""Cues are validated like coverage: a hard gate, before any compute."""

	def scene(self, **over):
		base = {
			"id": "s",
			"type": "cards",
			"narration": NARRATION,
			"cards": [{"title": "a", "cue": "Zero unaccounted balance"}],
		}
		return {**base, **over}

	def test_a_clean_scene_has_no_problems(self):
		assert cues.problems(self.scene()) == []

	def test_an_element_without_a_cue_is_rejected(self):
		problems = cues.problems(self.scene(cards=[{"title": "Coverage"}]))
		assert len(problems) == 1
		assert "has no cue" in problems[0]
		assert "'Coverage'" in problems[0]

	def test_a_phrase_not_in_the_narration_is_rejected(self):
		problems = cues.problems(self.scene(cards=[{"title": "a", "cue": "not in there"}]))
		assert "is not a phrase in this scene's narration" in problems[0]

	def test_out_of_order_cues_are_rejected(self):
		problems = cues.problems(
			self.scene(
				cards=[
					{"title": "a", "cue": "against weeks"},
					{"title": "b", "cue": "Zero unaccounted"},
				]
			)
		)
		assert "is spoken before the element above it" in problems[0]

	def test_in_order_cues_are_accepted(self):
		assert (
			cues.problems(
				self.scene(
					cards=[
						{"title": "a", "cue": "Zero unaccounted"},
						{"title": "b", "cue": "against weeks"},
					]
				)
			)
			== []
		)

	def test_more_reveal_cues_than_groups_is_rejected(self):
		problems = cues.problems(
			{
				"id": "d",
				"type": "diagram",
				"narration": NARRATION,
				"revealSteps": [["A"]],
				"revealCues": ["So here is", "against weeks"],
			}
		)
		assert "2 revealCues for 1 revealSteps" in problems[0]

	def test_a_code_scene_needs_no_cues(self):
		assert cues.problems({"id": "c", "type": "code", "narration": NARRATION, "code": "x"}) == []

	def test_the_scene_is_named_in_every_problem(self):
		for problem in cues.problems(self.scene(id="the-scoreboard", cards=[{"title": "a"}])):
			assert "the-scoreboard" in problem
