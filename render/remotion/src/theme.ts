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
export const ACCENTS = [
	"#22d3ee", // cyan
	"#34d399", // emerald
	"#a78bfa", // violet
	"#fbbf24", // amber
	"#fb7185", // rose
	"#fb923c", // orange
] as const;

export const accent = (i: number) => ACCENTS[i % ACCENTS.length];

/** Reveal beats across the scene, leaving a beat of settle at the end. */
export const beatAt = (index: number, total: number, durationInFrames: number) => {
	const usable = durationInFrames * 0.6;
	return (usable / Math.max(total, 1)) * index;
};
