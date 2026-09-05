import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { accent, beatAt, theme } from "./theme";

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
				gap: 26,
				justifyContent: "center",
			}}
		>
			{/* Headline small, content big: the headline is rarely the point. */}
			<div style={{ color: theme.muted, fontSize: 34, opacity: fade(0), marginBottom: 44 }}>
				{heading}
			</div>
			{bullets.map((text, i) => {
				const start = beatAt(i + 1, bullets.length + 1, durationInFrames);
				return (
					<div
						key={text}
						style={{
							display: "flex",
							alignItems: "center",
							gap: 28,
							opacity: fade(start),
							transform: `translateY(${rise(start)}px)`,
						}}
					>
						{/* A short accent rule rather than a bullet glyph: it marks
						    the line without competing with the words. */}
						<span
							style={{
								width: 10,
								height: 54,
								borderRadius: 5,
								backgroundColor: accent(i),
								flexShrink: 0,
							}}
						/>
						<span style={{ color: theme.fg, fontSize: 76, lineHeight: 1.35 }}>
							{text}
						</span>
					</div>
				);
			})}
		</AbsoluteFill>
	);
};
