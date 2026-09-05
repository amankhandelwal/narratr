import React, { useMemo } from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { accent, beatAt, theme } from "./theme";

export type DiagramProps = {
	heading?: string;
	/** Mermaid's rendered SVG, produced ahead of time by mmdc. */
	svg: string;
	/** Groups of mermaid node ids, each revealed as one beat. */
	revealSteps: string[][];
};

// Mermaid's SVG structure is not a public API. Two shapes are load-bearing
// here, both verified against mermaid-cli output:
//   nodes: <g id="<prefix>-flowchart-<ID>-<n>">
//   edges: <path class="... flowchart-link" data-id="L_<from>_<to>_<n>">
// The trailing index is unpredictable, hence prefix matching on the dash.
//
// The node class is deliberately NOT matched. Mermaid writes "node default"
// for a plain node and "icon-shape default" for one carrying an icon, so a
// `g.node` selector silently stops animating the moment a diagram uses icons
// -- and an unmatched node falls back to visible, which every structural check
// passes. The id pattern is the part that holds across both.
// If either changes, edges and nodes fall back to visible rather than
// vanishing for the whole scene.
const EDGE_ID = /data-id="L_(.+?)_(.+?)_\d+"/g;

const beatOf = (id: string, steps: string[][]) => {
	const found = steps.findIndex((group) => group.includes(id));
	return found === -1 ? 0 : found;
};

export const Diagram: React.FC<DiagramProps> = ({ heading, svg, revealSteps }) => {
	const frame = useCurrentFrame();
	const { durationInFrames } = useVideoConfig();

	const rules = useMemo(() => {
		const opacityAt = (beat: number) =>
			interpolate(
				frame,
				[beatAt(beat, revealSteps.length, durationInFrames), beatAt(beat, revealSteps.length, durationInFrames) + 14],
				[0, 1],
				{ extrapolateLeft: "clamp", extrapolateRight: "clamp" },
			);

		// Mermaid stamps an inline `max-width: <n>px` on the root svg, which caps
		// it at its natural size — a few hundred pixels in a 1920px frame. Only
		// !important beats an inline style. Size is importance: the diagram is
		// the message, so it gets the frame.
		// Mermaid stamps an inline `max-width: <n>px` on the root svg, capping it
		// at its natural size — a few hundred pixels in a 1920px frame. Only
		// !important beats an inline style. The container below gives it a
		// definite box, so preserveAspectRatio letterboxes instead of overflowing.
		const lines: string[] = [
			".diagram svg { max-width: none !important; width: 100% !important;" +
				" height: 100% !important; }",
		];

		revealSteps.forEach((group, beat) => {
			for (const id of group) {
				const node = `.diagram g[id*="flowchart-${id}-"]`;
				lines.push(`${node} { opacity: ${opacityAt(beat)} }`);
				// Colour follows the reveal, so each beat is visually distinct
				// and the eye can tell which nodes arrived together.
				lines.push(
					`${node} rect, ${node} polygon, ${node} circle, ${node} path ` +
						`{ stroke: ${accent(beat)} !important; stroke-width: 2.5px !important }`,
				);
			}
		});

		// An edge belongs to the later of the two nodes it joins.
		for (const match of svg.matchAll(EDGE_ID)) {
			const [, from, to] = match;
			const beat = Math.max(beatOf(from, revealSteps), beatOf(to, revealSteps));
			lines.push(
				`.diagram [data-id="${match[1]}_${match[2]}_0"], ` +
					`.diagram path[data-id^="L_${from}_${to}_"] { opacity: ${opacityAt(beat)} }`,
			);
		}

		return lines.join("\n");
	}, [frame, durationInFrames, revealSteps, svg]);

	return (
		<AbsoluteFill
			style={{ backgroundColor: theme.bg, fontFamily: theme.font, padding: 96 }}
		>
			{heading ? (
				<div style={{ color: theme.muted, fontSize: 34, marginBottom: 24 }}>{heading}</div>
			) : null}
			<style>{rules}</style>
			<div
				className="diagram"
				style={{
					position: "absolute",
					top: heading ? 170 : 96,
					right: 96,
					bottom: 96,
					left: 96,
					overflow: "hidden",
				}}
				dangerouslySetInnerHTML={{ __html: svg }}
			/>
		</AbsoluteFill>
	);
};
