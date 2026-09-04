import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { theme } from "./theme";

export type CodeProps = {
	heading?: string;
	code: string;
	lang?: string;
};

/** Plain monospace for now. Shiki highlighting is a later refinement. */
export const Code: React.FC<CodeProps> = ({ heading, code }) => {
	const frame = useCurrentFrame();
	const opacity = interpolate(frame, [0, 14], [0, 1], {
		extrapolateLeft: "clamp",
		extrapolateRight: "clamp",
	});

	return (
		<AbsoluteFill
			style={{
				backgroundColor: theme.bg,
				fontFamily: theme.font,
				padding: 96,
				justifyContent: "center",
			}}
		>
			{heading ? (
				<div style={{ color: theme.dim, fontSize: 34, marginBottom: 40 }}>{heading}</div>
			) : null}
			<pre
				style={{
					opacity,
					margin: 0,
					padding: 40,
					borderRadius: 16,
					backgroundColor: "#1E2229",
					border: `2px solid ${theme.accent}`,
					color: theme.fg,
					fontFamily: 'Menlo, Monaco, "Courier New", monospace',
					fontSize: 42,
					lineHeight: 1.5,
					whiteSpace: "pre-wrap",
				}}
			>
				{code}
			</pre>
		</AbsoluteFill>
	);
};
