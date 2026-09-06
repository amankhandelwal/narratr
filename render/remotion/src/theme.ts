// Palette from archify (github.com/tt-a1i/archify), dark theme. Slate ground
// with 400-level accents, which stay legible on near-black without glaring.
//
// Colour is used to separate things, never to decorate: one accent per bullet
// so the eye can track the reveal, and a rotation across diagram nodes so the
// stages of a flow are distinguishable at a glance.
export const theme = {
	bg: "#020617",
	panel: "#0f172a",
	panelBorder: "#1e293b",
	fg: "#ffffff",
	muted: "#94a3b8",
	dim: "#475569",
	line: "#64748b",
	font: '"Helvetica Neue", Helvetica, Arial, sans-serif',
	mono: 'Menlo, Monaco, "Courier New", monospace',
} as const;

/** Accent rotation. Ordered so adjacent entries stay distinguishable. */
const ACCENTS = [
	"#22d3ee", // cyan
	"#34d399", // emerald
	"#a78bfa", // violet
	"#fbbf24", // amber
	"#fb7185", // rose
	"#fb923c", // orange
] as const;

export const accent = (i: number) => ACCENTS[i % ACCENTS.length];

/**
 * Even spacing across the first 60% of the scene.
 *
 * The fallback only. It knows nothing about the narration, so on a long scene
 * it put the last element nine seconds ahead of the words introducing it and
 * left the final third playing against a finished slide. `revealFrames` uses
 * the cued beats instead wherever they exist; this is what is left for the
 * preview, which has no audio to align against.
 */
export const beatAt = (index: number, total: number, durationInFrames: number) => {
	const usable = durationInFrames * 0.6;
	return (usable / Math.max(total, 1)) * index;
};

/**
 * The frame each element is revealed on.
 *
 * `beats` are seconds into the scene, resolved in Python from the cue phrases
 * against the aligned narration -- so an element appears exactly as the words
 * that introduce it are spoken. Absent, the even spacing above stands in.
 */
export const revealFrames = (
	count: number,
	durationInFrames: number,
	fps: number,
	beats?: number[],
): number[] =>
	Array.from({ length: count }, (_, i) =>
		beats?.[i] != null
			? Math.min(Math.round(beats[i] * fps), durationInFrames - 1)
			: beatAt(i + 1, count + 1, durationInFrames),
	);
