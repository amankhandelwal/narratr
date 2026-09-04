// Dark ground so the slide never outshines the speaker's voice, per the
// presentation rules in ~/obsidian-home/Claude Rules/presentation.md.
export const theme = {
	bg: "#14161A",
	fg: "#F2F3F5",
	dim: "#8A9099",
	accent: "#D9945F",
	font: '"Helvetica Neue", Helvetica, Arial, sans-serif',
} as const;

/** Reveal beats across the scene, leaving a beat of settle at the end. */
export const beatAt = (index: number, total: number, durationInFrames: number) => {
	const usable = durationInFrames * 0.6;
	return (usable / Math.max(total, 1)) * index;
};
