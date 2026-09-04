import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { beatAt, theme } from "./theme";

export type ProseProps = {
	heading: string;
	bullets: string[];
};

/** Heading plus up to six fragments, revealed one beat at a time. */
export const Prose: React.FC<ProseProps> = ({ heading, bullets }) => {
	const frame = useCurrentFrame();
	const { durationInFrames } = useVideoConfig();

	const fade = (start: number) =>
		interpolate(frame, [start, start + 12], [0, 1], {
			extrapolateLeft: "clamp",
			extrapolateRight: "clamp",
		});

	const rise = (start: number) =>
		interpolate(frame, [start, start + 12], [18, 0], {
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
			{/* Headline small, content big: the headline is rarely the point. */}
			<div style={{ color: theme.dim, fontSize: 34, opacity: fade(0), marginBottom: 40 }}>
				{heading}
			</div>
			{bullets.map((text, i) => {
				const start = beatAt(i + 1, bullets.length + 1, durationInFrames);
				return (
					<div
						key={text}
						style={{
							color: theme.fg,
							fontSize: 76,
							lineHeight: 1.35,
							opacity: fade(start),
							transform: `translateY(${rise(start)}px)`,
						}}
					>
						{text}
					</div>
				);
			})}
		</AbsoluteFill>
	);
};
