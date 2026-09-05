import { describe, expect, it } from "vitest";
import { accent, beatAt } from "../theme";

describe("beatAt", () => {
	it("hands out beats inside the first 60% of the scene", () => {
		// The tail is settle time: the last beat must land well before the
		// narration ends, or the final item is still fading as the cut comes.
		expect(beatAt(0, 4, 300)).toBe(0);
		expect(beatAt(4, 4, 300)).toBe(180);
		expect(beatAt(2, 4, 300)).toBe(90);
	});

	it("survives a total of zero", () => {
		// A prose scene with no bullets, or a diagram with no reveal groups,
		// reaches here with total = 0. Dividing by it would put NaN into an
		// interpolate range, which Remotion throws on -- so the scene would
		// not render at all rather than simply showing nothing.
		expect(beatAt(0, 0, 300)).toBe(0);
		expect(Number.isNaN(beatAt(1, 0, 300))).toBe(false);
		expect(Number.isFinite(beatAt(1, 0, 300))).toBe(true);
	});

	it("never runs backwards as the index climbs", () => {
		for (const total of [1, 3, 6]) {
			let previous = -1;
			for (let i = 0; i <= total; i++) {
				const start = beatAt(i, total, 360);
				expect(start).toBeGreaterThan(previous);
				previous = start;
			}
		}
	});
});

describe("accent", () => {
	it("wraps past the end of the palette", () => {
		// Six accents, and nothing stops a scene from asking for a seventh.
		expect(accent(6)).toBe(accent(0));
		expect(accent(7)).toBe(accent(1));
		expect(accent(13)).toBe(accent(1));
	});

	it("keeps adjacent beats distinguishable", () => {
		for (let i = 0; i < 6; i++) expect(accent(i)).not.toBe(accent(i + 1));
	});
});
