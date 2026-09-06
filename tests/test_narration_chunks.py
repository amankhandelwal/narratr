"""Chatterbox compresses rather than truncates past its generation ceiling, so
narration has to reach it in pieces. These pin the split."""

import re

import pytest

from narratr.narrate import BUDGET, split_narration


def _words(text: str) -> list[str]:
	return re.findall(r"[\w']+", text)


SCENE = (
	"So here is the list, and the right hand column is where we are today. "
	"Zero unaccounted balance incidents needing manual forensics, against "
	"recurring incidents costing several days each. A new liquidity provider "
	"queryable the same day, against weeks."
)


def test_every_chunk_fits_the_budget():
	assert all(len(c) <= BUDGET for c in split_narration(SCENE))


def test_no_words_are_lost():
	assert _words(" ".join(split_narration(SCENE))) == _words(SCENE)


def test_splits_on_sentences():
	chunks = split_narration("One two three. Four five six.", budget=20)
	assert chunks == ["One two three.", "Four five six."]


def test_short_sentences_are_packed_together():
	assert split_narration("A cat. A dog. A bird.") == ["A cat. A dog. A bird."]


def test_long_sentence_falls_back_to_clauses():
	sentence = "alpha bravo charlie, delta echo foxtrot, golf hotel india"
	chunks = split_narration(sentence, budget=30)
	assert all(len(c) <= 30 for c in chunks)
	assert _words(" ".join(chunks)) == _words(sentence)


def test_unpunctuated_run_is_split_on_words():
	sentence = " ".join(["word"] * 40) + "."
	chunks = split_narration(sentence, budget=30)
	assert all(len(c) <= 30 for c in chunks)
	assert _words(" ".join(chunks)) == _words(sentence)


def test_empty_narration_yields_nothing():
	assert split_narration("   ") == []


@pytest.mark.parametrize("text", [SCENE, "One. Two. Three.", "No trailing period"])
def test_split_is_stable(text):
	assert split_narration(text) == split_narration(text)
