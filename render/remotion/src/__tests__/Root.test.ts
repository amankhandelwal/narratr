import { describe, expect, it } from "vitest";
import { FPS, framesFor } from "../Root";

describe("framesFor", () => {
	it("matches the rounding the Python side does at 30fps", () => {
		// Both halves of the pipeline convert the same measured duration: if
		// they disagree by a frame the audio and the video drift apart, one
		// scene at a time, over a 36-minute cut.
		expect(FPS).toBe(30);
		expect(framesFor(1.0)).toBe(30);
		expect(framesFor(11.837)).toBe(355);
		expect(framesFor(74.0)).toBe(2220);
	});

	it("never returns zero", () => {
		// Remotion refuses a composition of zero frames, and a clip can
		// genuinely measure a few milliseconds.
		expect(framesFor(0.01)).toBe(1);
		expect(framesFor(0)).toBe(1);
		expect(framesFor(-3)).toBe(1);
	});

	it("rounds rather than truncating", () => {
		// Truncating leaves a scene a frame short of its own narration.
		expect(framesFor(0.99)).toBe(30);
		expect(framesFor(2.4 / 30 + 2)).toBe(62);
	});
});
