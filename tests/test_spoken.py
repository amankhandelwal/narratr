"""Numbers have to reach the aligner as something it can match.

MMS_FA's vocabulary is lowercase latin plus apostrophe. A token that reduces to
nothing is dropped from the alignment target while Chatterbox goes on speaking
it, so the neighbouring words absorb that audio and their timings skew -- and
the word never reaches the captions.
"""

from __future__ import annotations

import pytest

from narratr.align import normalise
from narratr.spoken import say, spell_integer

INTEGERS = [
	(0, "zero"),
	(7, "seven"),
	(13, "thirteen"),
	(20, "twenty"),
	(36, "thirty six"),
	(99, "ninety nine"),
	(100, "one hundred"),
	(101, "one hundred one"),
	(999, "nine hundred ninety nine"),
	(1000, "one thousand"),
	(2026, "two thousand twenty six"),
	(1_000_000, "one million"),
]


@pytest.mark.parametrize("value,words", INTEGERS)
def test_integers_are_spelled(value, words):
	assert spell_integer(value) == words


def test_very_large_numbers_degrade_to_digits_rather_than_fail():
	assert say("1" + "0" * 15).startswith("one")


@pytest.mark.parametrize(
	"token,words",
	[
		("2.5", "two point five"),
		("0.92", "zero point nine two"),
		("1st", "first"),
		("2nd", "second"),
		("3rd", "third"),
		("20th", "twentieth"),
		("50%", "fifty percent"),
		("$5", "five dollars"),
		("16:9", "sixteen nine"),
		("A/B", "AB"),
	],
)
def test_written_forms_are_spoken(token, words):
	assert say(token) == words


@pytest.mark.parametrize("token", ["36", "2.5", "1st", "50%", "16:9", "1990", "$5", "n8n"])
def test_no_numeric_token_normalises_away(token):
	assert normalise(token), f"{token!r} would be dropped from the alignment target"


@pytest.mark.parametrize("token", ["—", "(", ")", "...", "•"])
def test_tokens_nobody_speaks_still_normalise_away(token):
	assert normalise(token) == ""


def test_normalisation_stays_in_the_aligner_vocabulary():
	"""Whatever `say` produces, `normalise` must emit only [a-z'] -- anything
	else is not in MMS_FA's vocabulary and the tokenizer would reject it."""
	for token in ["36", "2.5", "$5", "50%", "Café", "don't", "16:9", "1st"]:
		assert set(normalise(token)) <= set("abcdefghijklmnopqrstuvwxyz'")


def test_a_sentence_of_numbers_keeps_every_token():
	sentence = "It renders 3 scenes at 0.92 speed in 45 seconds, a 2.5x saving"
	assert all(normalise(w) for w in sentence.split())
