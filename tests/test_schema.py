"""The schema is the gate, and scenes.json is untrusted input.

It is written by an LLM from a document nobody in this project controls, so
everything downstream -- a CSS selector in the renderer, a filesystem path, a
subprocess handed a diagram source, a TTS model handed a paragraph -- reads
values this file is the only thing standing in front of. These tests pin the
two properties that matter: every value the project itself ships still passes,
and the shapes that would break a later stage are refused here, before any
compute is spent.

Validation goes through `narratr.spec.validate` rather than `jsonschema`
directly, so a test exercises the real gate a run goes through.
"""

from __future__ import annotations

import copy
import json

import pytest

from narratr.paths import ROOT
from narratr.spec import validate

EXAMPLES = [
	ROOT / "examples" / "brief.scenes.json",
	ROOT / "examples" / "code.scenes.json",
	ROOT / "skill" / "example.scenes.json",
]


@pytest.fixture
def spec() -> dict:
	"""A known-good spec, fresh per test so mutations do not leak."""
	return json.loads((ROOT / "examples" / "brief.scenes.json").read_text())


def schema_problems(spec: dict) -> list[str]:
	return [p for p in validate(spec) if p.startswith("schema:")]


# ------------------------------------------------------- the bundled examples


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_every_bundled_example_still_validates(path):
	"""Caps are only useful if they are set above what the project itself ships."""
	assert path.is_file(), path
	assert validate(json.loads(path.read_text())) == []


# ------------------------------------------------------------- revealSteps ids


def test_reveal_step_id_with_a_quote_is_rejected(spec):
	"""The renderer interpolates these into g[id*="flowchart-<id>-"].

	A quote closes the selector, so the id is held to Mermaid's own node-id
	charset here rather than being sanitised on the way to the browser.
	"""
	scene = next(s for s in spec["scenes"] if s["type"] == "diagram")
	scene["revealSteps"] = [['A"] { display: none } .diagram g[id*="']]
	problems = schema_problems(spec)
	assert problems, "a quoted reveal id passed the gate"
	assert "revealSteps" in problems[0]


def test_reveal_step_id_with_a_space_is_rejected(spec):
	scene = next(s for s in spec["scenes"] if s["type"] == "diagram")
	scene["revealSteps"] = [["A B"]]
	assert schema_problems(spec)


def test_an_ordinary_reveal_id_is_accepted(spec):
	scene = next(s for s in spec["scenes"] if s["type"] == "diagram")
	scene["revealSteps"] = [["A", "node_2", "Step-3"]]
	recue(scene)
	assert validate(spec) == []


def recue(scene: dict, narration: str | None = None) -> None:
	"""Re-point a scene's cues after a test rewrites its narration or reveals.

	Cues are a hard gate, so a test that replaces the words or the reveal
	groups has to keep them consistent -- the same way one that adds a block
	has to map it. The phrase is the narration's opening, which every scene
	has and which always resolves.
	"""
	if narration is not None:
		scene["narration"] = narration
	opening = " ".join(scene["narration"].split()[:3])
	for field in ("bullets", "steps", "cards"):
		for element in scene.get(field, []):
			element["cue"] = opening
	if "revealSteps" in scene:
		scene["revealCues"] = [opening] * len(scene["revealSteps"])


# --------------------------------------------------------------------- caps


def test_over_long_narration_is_rejected(spec):
	spec["scenes"][0]["narration"] = "word " * 2000
	problems = schema_problems(spec)
	assert problems
	assert "narration" in problems[0]


def test_narration_of_a_normal_length_is_accepted(spec):
	"""A minute of speech is roughly 900 characters; the cap is 5000."""
	recue(spec["scenes"][0], "This is a sentence of narration. " * 27)
	assert len(spec["scenes"][0]["narration"]) > 850
	assert validate(spec) == []


def test_over_long_code_is_rejected(spec):
	scene = next(s for s in spec["scenes"] if s["type"] == "diagram")
	scene["type"] = "code"
	del scene["mermaid"]
	del scene["revealSteps"]
	scene["code"] = "x = 1\n" * 5000
	problems = schema_problems(spec)
	assert problems
	assert "code" in problems[0]


def test_code_of_a_normal_length_is_accepted(spec):
	scene = next(s for s in spec["scenes"] if s["type"] == "diagram")
	scene["type"] = "code"
	del scene["mermaid"]
	del scene["revealSteps"]
	scene["code"] = "def f(n):\n\treturn n * 2\n" * 20
	scene["lang"] = "python"
	assert validate(spec) == []


def test_over_long_mermaid_is_rejected(spec):
	scene = next(s for s in spec["scenes"] if s["type"] == "diagram")
	scene["mermaid"] = "flowchart LR\n" + "".join(f"  n{i} --> n{i + 1}\n" for i in range(2000))
	problems = schema_problems(spec)
	assert problems
	assert "mermaid" in problems[0]


def test_mermaid_of_a_normal_length_is_accepted(spec):
	scene = next(s for s in spec["scenes"] if s["type"] == "diagram")
	scene["mermaid"] = "flowchart LR\n" + "".join(f"  n{i} --> n{i + 1}\n" for i in range(20))
	scene["revealSteps"] = [["n0", "n1"]]
	recue(scene)
	assert validate(spec) == []


def test_too_many_scenes_is_rejected(spec):
	"""200 scenes is already a two-hour video; past that it is a runaway spec."""
	first = spec["scenes"][0]
	spec["scenes"] = [dict(first, id=f"s{i}") for i in range(201)]
	spec["coverage"] = dict.fromkeys(spec["source"]["block_ids"], "s0")
	problems = schema_problems(spec)
	assert problems
	assert "scenes" in problems[0]


def test_an_over_long_heading_is_rejected(spec):
	spec["scenes"][0]["heading"] = "h" * 500
	assert schema_problems(spec)


def test_an_over_long_bullet_is_rejected(spec):
	"""Bullets are fragments. A paragraph in a bullet slot overflows the slide."""
	spec["scenes"][0]["bullets"] = ["b" * 400]
	assert schema_problems(spec)


def test_an_over_long_voice_reference_is_rejected(spec):
	spec["voice"]["reference"] = "assets/voices/" + "a" * 600 + ".wav"
	assert schema_problems(spec)


# ---------------------------------------------------------------------- lang


def test_a_lang_with_a_shell_metacharacter_is_rejected(spec):
	scene = next(s for s in spec["scenes"] if s["type"] == "diagram")
	scene["type"] = "code"
	del scene["mermaid"]
	del scene["revealSteps"]
	scene["code"] = "print(1)"
	scene["lang"] = "python; rm -rf /"
	problems = schema_problems(spec)
	assert problems
	assert "lang" in problems[0]


@pytest.mark.parametrize("lang", ["python", "c#", "objective-c", "f#", "vue-html"])
def test_real_shiki_language_ids_are_accepted(spec, lang):
	"""The pattern must not be so tight that it rejects Shiki's own ids."""
	scene = next(s for s in spec["scenes"] if s["type"] == "diagram")
	scene["type"] = "code"
	del scene["mermaid"]
	del scene["revealSteps"]
	scene["code"] = "print(1)"
	scene["lang"] = lang
	assert validate(spec) == []


# ------------------------------------------------------------------- the seed


def test_an_out_of_range_seed_is_rejected(spec):
	"""torch.manual_seed raises on this -- after the model has loaded."""
	spec["voice"]["seed"] = 2**80
	assert schema_problems(spec)


# ----------------------------------------------- the type enum documents itself


def test_the_type_enum_names_the_field_each_shape_needs():
	"""The requirement is enforced in narratr.spec, which words it better than
	JSON Schema can. The schema still has to document the contract."""
	schema = json.loads((ROOT / "schemas" / "scenes.schema.json").read_text())
	described = schema["properties"]["scenes"]["items"]["properties"]["type"]["description"]
	for shape, field in [
		("diagram", "mermaid"),
		("code", "code"),
		("flow", "steps"),
		("cards", "cards"),
	]:
		assert shape in described and field in described


def test_a_diagram_without_mermaid_reports_once_and_in_python(spec):
	"""No if/then in the schema: one problem, worded by narratr.spec."""
	scene = next(s for s in spec["scenes"] if s["type"] == "diagram")
	del scene["mermaid"]
	del scene["revealSteps"]
	problems = validate(spec)
	assert not schema_problems(spec)
	assert any("is type 'diagram' but has no 'mermaid'" in p for p in problems)


# --------------------------------------------------------------- untouched spec


def test_validate_does_not_mutate_the_spec(spec):
	before = copy.deepcopy(spec)
	validate(spec)
	assert spec == before
