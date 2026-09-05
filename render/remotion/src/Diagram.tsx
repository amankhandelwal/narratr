import React from "react";
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
// The trailing index is unpredictable, so a node is matched on the dash
// prefix; an edge's data-id is lifted out of this very SVG, so it can be
// matched whole.
//
// The node class is deliberately NOT matched. Mermaid writes "node default"
// for a plain node and "icon-shape default" for one carrying an icon, so a
// `g.node` selector silently stops animating the moment a diagram uses icons
// -- and an unmatched node falls back to visible, which every structural check
// passes. The id pattern is the part that holds across both.
// If either changes, edges and nodes fall back to visible rather than
// vanishing for the whole scene.
const EDGE_ID = /data-id="(L_[^"]*)"/g;

/**
 * Every distinct edge id mermaid wrote into this SVG, in document order.
 *
 * Deduplicated because each id appears twice in real output: once on the
 * `<path class="flowchart-link">` and again on the `<g class="label">` that
 * holds the edge's caption. Only the path is styled below, so the second
 * occurrence would just emit the same rule again.
 */
export const edgeIds = (svg: string) =>
	[...new Set([...svg.matchAll(EDGE_ID)].map(([, dataId]) => dataId))];

/**
 * Ids arrive from the scene file and are interpolated straight into CSS
 * selectors, where a stray quote or brace would end the rule and start
 * another. Anything outside mermaid's own id alphabet is refused, and the
 * node then simply has no rule -- which is the same way an unknown id already
 * degrades: visible, for the whole scene.
 */
export const isSafeId = (id: string) => /^[A-Za-z0-9_-]+$/.test(id);

/**
 * The beat an edge belongs to: the later of the two nodes it joins.
 *
 * Mermaid names an edge `L_<from>_<to>_<n>` and permits underscores in node
 * ids, so the name has no seam a regex can find. Verified: the lazy
 * /L_(.+?)_(.+?)_\d+/ this replaced read `L_step_one_step_two_0` as
 * from="step", to="one_step_two" -- neither of which is a node, so the edge
 * silently landed on beat 0. The known ids are matched against the name
 * instead, longest first so `step_one` wins wherever `step` also exists.
 *
 * An edge naming nothing we know falls back to beat 0, i.e. visible from the
 * start, matching how an unmatched node degrades.
 */
export const edgeBeat = (dataId: string, revealSteps: string[][]) => {
	const body = dataId.replace(/^L_/, "").replace(/_\d+$/, "");
	const known = revealSteps
		.flatMap((group, beat) => group.map((id) => ({ id, beat })))
		.sort((a, b) => b.id.length - a.id.length);
	const from = known.find(({ id }) => body === id || body.startsWith(`${id}_`));
	const to = known.find(({ id }) => body === id || body.endsWith(`_${id}`));
	if (!from && !to) return 0;
	return Math.max(from?.beat ?? 0, to?.beat ?? 0);
};

export const Diagram: React.FC<DiagramProps> = ({ heading, svg, revealSteps }) => {
	const frame = useCurrentFrame();
	const { durationInFrames } = useVideoConfig();

	// One more beat than there are groups, and the first group starts on beat
	// one -- the same offset prose, cards and flow use, so a diagram's opening
	// group settles in rather than being on screen before the narration is.
	const opacityAt = (beat: number) => {
		const start = beatAt(beat + 1, revealSteps.length + 1, durationInFrames);
		return interpolate(frame, [start, start + 14], [0, 1], {
			extrapolateLeft: "clamp",
			extrapolateRight: "clamp",
		});
	};

	// Mermaid stamps an inline `max-width: <n>px` on the root svg, capping it
	// at its natural size — a few hundred pixels in a 1920px frame. Only
	// !important beats an inline style. Size is importance: the diagram is the
	// message, so it gets the frame. The container below gives it a definite
	// box, so preserveAspectRatio letterboxes instead of overflowing.
	const lines: string[] = [
		".diagram svg { max-width: none !important; width: 100% !important;" +
			" height: 100% !important; }",
		// Nothing here may change the glyph's size or spacing: Mermaid
		// measured the label before this stylesheet existed and clips the
		// foreignObject to that width. Layout lives inline, in icons.py.
	];

	revealSteps.forEach((group, beat) => {
		for (const id of group) {
			if (!isSafeId(id)) continue;
			const node = `.diagram g[id*="flowchart-${id}-"]`;
			lines.push(`${node} { opacity: ${opacityAt(beat)} }`);
			// Colour follows the reveal, so each beat is visually distinct
			// and the eye can tell which nodes arrived together.
			// What may be tinted: the node's own outline, and every shape in
			// the glyph inside an icon node -- a Lucide glyph is not all
			// paths, so matching only `path` left `image` (a rect, a circle
			// and a path) two-thirds in the theme colour. Two things must be
			// left alone.
			//
			// `stroke="none"` paths are fill and hit-test layers, not
			// outlines. An icon node has both, sitting slightly proud of the
			// tile, so stroking them drew two offset rectangles over the
			// label. `.label` holds the text's background rect, which is not
			// a border either.
			const paintable =
				`${node} > rect, ${node} > polygon, ${node} > circle, ` +
				`${node} > path:not([stroke="none"]), ` +
				`${node} > g:not(.label) :is(path, rect, circle, ellipse, line, polyline, polygon):not([stroke="none"])`;
			lines.push(`${paintable} { stroke: ${accent(beat)} !important }`);
			// The label's glyph is excluded from `paintable` along with the
			// rest of `.label`, so it takes the beat colour through
			// `currentColor` instead of a stroke override.
			// Mermaid's own stylesheet carries `.node path { stroke: nodeBorder }`,
			// which reaches inside the label and greys the glyph. `paintable`
			// excludes `.label`, so the glyph needs saying explicitly.
			lines.push(
				`${node} .narratr-icon svg, ${node} .narratr-icon svg * ` +
					`{ stroke: ${accent(beat)} !important }`,
			);
			// Weight belongs to the outline only. The glyph lives in its own
			// nested <svg> on a 24-unit viewBox, where 2.5px is a slab.
			lines.push(
				`${node} > rect, ${node} > polygon, ${node} > circle, ` +
					`${node} > path:not([stroke="none"]), ` +
					`${node} > g:not(.label) > path:not([stroke="none"]) ` +
					`{ stroke-width: 2.5px !important }`,
			);
		}
	});

	// An edge belongs to the later of the two nodes it joins. The data-id is
	// taken verbatim from the SVG we are about to inline, so the selector can
	// match it exactly rather than guessing at the trailing index.
	for (const dataId of edgeIds(svg)) {
		if (!isSafeId(dataId)) continue;
		const beat = edgeBeat(dataId, revealSteps);
		// Not `path[data-id=...]`: Mermaid stamps the same id on the edge's
		// label group as well as its path. Qualifying by tag faded the line and
		// left its caption on screen from frame 0, which is the same
		// "unmatched falls back to visible" failure the node selector avoids.
		lines.push(`.diagram [data-id="${dataId}"] { opacity: ${opacityAt(beat)} }`);
	}

	const rules = lines.join("\n");

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
