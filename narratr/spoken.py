"""Rendering written text as the letters a forced aligner can match.

MMS_FA's vocabulary is lowercase latin plus apostrophe, so anything else is
stripped before alignment. A token that strips to nothing is dropped from the
target entirely -- and that is the problem this module exists to solve.

Chatterbox still *speaks* "36". Dropping the token means the aligner is asked to
match audio that contains a spoken number against a target that does not, so the
neighbouring words absorb that audio and their timings skew. The word also never
reaches the captions. Both failures are silent.

The expansion is a best guess at what the model said, not a transcript. That is
enough: a rough guess consumes roughly the right span of audio and protects
every neighbour, where dropping the token protects nothing.
"""

from __future__ import annotations

import re

UNITS = (
	"zero",
	"one",
	"two",
	"three",
	"four",
	"five",
	"six",
	"seven",
	"eight",
	"nine",
	"ten",
	"eleven",
	"twelve",
	"thirteen",
	"fourteen",
	"fifteen",
	"sixteen",
	"seventeen",
	"eighteen",
	"nineteen",
)
TENS = (
	"",
	"",
	"twenty",
	"thirty",
	"forty",
	"fifty",
	"sixty",
	"seventy",
	"eighty",
	"ninety",
)
SCALES = ((1_000_000_000, "billion"), (1_000_000, "million"), (1_000, "thousand"))

# Symbols a narrator reads aloud. Anything absent is simply dropped, which is
# correct: nobody speaks a bracket.
CURRENCY = {"$": "dollars", "£": "pounds", "€": "euros", "₹": "rupees"}

SYMBOLS = {
	**CURRENCY,
	"%": "percent",
	"&": "and",
	"+": "plus",
	"=": "equals",
	"@": "at",
	"°": "degrees",
	"×": "times",
}

DIGITS = re.compile(r"\d+")
DECIMAL = re.compile(r"^(\d+)\.(\d+)$")
ORDINAL = re.compile(r"^(\d+)(st|nd|rd|th)$", re.I)

ORDINALS = {
	"one": "first",
	"two": "second",
	"three": "third",
	"five": "fifth",
	"eight": "eighth",
	"nine": "ninth",
	"twelve": "twelfth",
}


def spell_integer(value: int) -> str:
	"""An integer as the words a narrator would say. Space-separated."""
	if value < 0:
		return f"minus {spell_integer(-value)}"
	if value < 20:
		return UNITS[value]
	if value < 100:
		tens, unit = divmod(value, 10)
		return TENS[tens] + (f" {UNITS[unit]}" if unit else "")
	if value < 1000:
		hundreds, rest = divmod(value, 100)
		said = f"{UNITS[hundreds]} hundred"
		return said + (f" {spell_integer(rest)}" if rest else "")
	for size, name in SCALES:
		if value >= size:
			count, rest = divmod(value, size)
			said = f"{spell_integer(count)} {name}"
			return said + (f" {spell_integer(rest)}" if rest else "")
	# Longer than the scales cover: read it digit by digit rather than fail.
	return " ".join(UNITS[int(d)] for d in str(value))


def _ordinal(value: int) -> str:
	words = spell_integer(value)
	head, _, last = words.rpartition(" ")
	if last in ORDINALS:
		last = ORDINALS[last]
	elif last.endswith("y"):
		last = last[:-1] + "ieth"
	else:
		last = last + "th"
	return f"{head} {last}".strip()


def say(token: str) -> str:
	"""One written token as the words it is spoken as.

	Returns a space-separated string, which the caller collapses. Order of
	checks matters: `2.5` is a decimal before it is two integers, and `1st` is
	an ordinal before it is the integer one.
	"""
	decimal = DECIMAL.match(token)
	if decimal:
		whole, fraction = decimal.groups()
		spoken_fraction = " ".join(UNITS[int(d)] for d in fraction)
		return f"{spell_integer(int(whole))} point {spoken_fraction}"

	ordinal = ORDINAL.match(token)
	if ordinal:
		return _ordinal(int(ordinal.group(1)))

	# A leading currency symbol is spoken after the amount: "$5" is "five
	# dollars", never "dollars five".
	if token[:1] in CURRENCY and token[1:]:
		return f"{say(token[1:])} {CURRENCY[token[:1]]}"

	parts: list[str] = []
	cursor = 0
	for match in DIGITS.finditer(token):
		parts.append(_letters_and_symbols(token[cursor : match.start()]))
		parts.append(spell_integer(int(match.group())))
		cursor = match.end()
	parts.append(_letters_and_symbols(token[cursor:]))
	return " ".join(part for part in parts if part)


def _letters_and_symbols(chunk: str) -> str:
	out: list[str] = []
	for char in chunk:
		if char.isalpha() or char == "'":
			out.append(char)
		elif char in SYMBOLS:
			out.append(f" {SYMBOLS[char]} ")
	return " ".join("".join(out).split())
