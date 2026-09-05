import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { edgeBeat, edgeIds, isSafeId } from "../Diagram";

// A real mmdc output, copied out of store/assets. Mermaid's SVG shape is not a
// public API, so the parsing is checked against something mermaid actually
// wrote rather than against a hand-typed idea of it.
const svg = readFileSync(new URL("./fixtures/flowchart.svg", import.meta.url), "utf8");

describe("edgeIds", () => {
	it("finds every edge in a real mermaid SVG, once each", () => {
		// Mermaid stamps the id on both the link path and the edge's label
		// group, so the raw match count is double the number of edges.
		expect(edgeIds(svg)).toEqual(["L_A_B_0", "L_B_C_0", "L_C_D_0", "L_D_E_0"]);
	});

	it("returns nothing for a diagram with no edges", () => {
		expect(edgeIds("<svg><g id='my-svg-flowchart-A-0'></g></svg>")).toEqual([]);
	});
});

describe("edgeBeat", () => {
	// The nodes of the fixture, split across three beats.
	const steps = [["A", "B"], ["C"], ["D", "E"]];

	it("gives an edge the beat of the later node it joins", () => {
		expect(edgeBeat("L_A_B_0", steps)).toBe(0);
		expect(edgeBeat("L_B_C_0", steps)).toBe(1);
		expect(edgeBeat("L_C_D_0", steps)).toBe(2);
		expect(edgeBeat("L_D_E_0", steps)).toBe(2);
	});

	it("covers every edge the fixture actually contains", () => {
		expect(edgeIds(svg).map((id) => edgeBeat(id, steps))).toEqual([0, 1, 2, 2]);
	});

	it("reads underscored node ids correctly", () => {
		// The lazy /L_(.+?)_(.+?)_\d+/ this replaced split
		// `L_step_one_step_two_0` into from="step", to="one_step_two" -- two
		// ids that do not exist, so the edge fell back to beat 0 and appeared
		// before either of the nodes it joins.
		const underscored = [["step_one"], ["step_two"]];
		expect(edgeBeat("L_step_one_step_two_0", underscored)).toBe(1);
		expect(edgeBeat("L_step_two_step_one_0", underscored)).toBe(1);
	});

	it("prefers the longest matching id when one is a prefix of another", () => {
		// With both `step_one` and `step` known, `L_step_one_two_0` starts
		// with either. Matching the short one first would credit the edge to
		// beat 1 instead of beat 0 and hold it back a beat too long.
		const ambiguous = [["step_one"], ["step"]];
		expect(edgeBeat("L_step_one_two_0", ambiguous)).toBe(0);
	});

	it("falls back to beat 0 when it recognises neither end", () => {
		// Same degradation as an unmatched node: on screen for the whole
		// scene, rather than never.
		expect(edgeBeat("L_X_Y_0", steps)).toBe(0);
		expect(edgeBeat("L_A_B_0", [])).toBe(0);
	});

	it("credits an edge to the one end it does recognise", () => {
		expect(edgeBeat("L_unknown_D_0", steps)).toBe(2);
		expect(edgeBeat("L_D_unknown_0", steps)).toBe(2);
	});
});

describe("isSafeId", () => {
	it("accepts the ids mermaid itself emits", () => {
		for (const id of ["A", "step_one", "node-2", "L_A_B_0"]) {
			expect(isSafeId(id)).toBe(true);
		}
	});

	it("refuses anything that could close a selector or a rule", () => {
		// These reach a CSS selector by string interpolation, so a quote or a
		// brace would end our rule and start the author's.
		for (const id of ['a"] { opacity: 1 } *', "a{}", "a b", "a.b", ""]) {
			expect(isSafeId(id)).toBe(false);
		}
	});
});
