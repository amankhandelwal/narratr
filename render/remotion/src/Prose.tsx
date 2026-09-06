import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Icon, IconStyles } from "./Icon";
import { accent, revealFrames, theme } from "./theme";

/** A bullet is a plain string, or a fragment carrying an icon and a state. */
export type Bullet = { text: string; icon?: string; state?: "struck" };

export type ProseProps = {
	heading: string;
	bullets: Bullet[];
	icons?: Record<string, string>;
	/** Seconds into the scene at which each bullet appears. */
	beats?: number[];
};

/** Heading plus up to six fragments, revealed one beat at a time. */
export const Prose: React.FC<ProseProps> = ({ heading, bullets, icons, beats }) => {
	const frame = useCurrentFrame();
	const { durationInFrames, fps } = useVideoConfig();
	const starts = revealFrames(bullets.length, durationInFrames, fps, beats);

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

	// One bullet without an icon must not pull its text left of the others, so
	// the gutter is reserved for the whole list as soon as any bullet uses it.
	const gutter = bullets.some((bullet) => bullet.icon) ? 62 : 0;

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
			<IconStyles />
			{/* Headline small, content big: the headline is rarely the point. */}
			<div style={{ color: theme.muted, fontSize: 34, opacity: fade(0), marginBottom: 44 }}>
				{heading}
			</div>
			{bullets.map((bullet, i) => {
				const { text, icon, state } = bullet;
				const start = starts[i];
				// Struck fragments are the approach being rejected. Everything
				// about them recedes -- glyph included -- so the live lines read
				// first and the rejected ones read as history.
				const struck = state === "struck";
				return (
					<div
						key={`${i}-${text}`}
						style={{
							display: "flex",
							alignItems: "center",
							gap: gutter ? 30 : 0,
							opacity: fade(start),
							transform: `translateY(${rise(start)}px)`,
						}}
					>
						{gutter > 0 && (
							<span
								style={{
									width: gutter,
									height: gutter,
									flexShrink: 0,
									display: "flex",
									alignItems: "center",
								}}
							>
								<Icon
									markup={icon ? icons?.[icon] : undefined}
									size={gutter}
									color={struck ? theme.dim : accent(i)}
									strokeWidth={1.75}
								/>
							</span>
						)}
						<span
							style={{
								color: struck ? theme.dim : theme.fg,
								fontSize: 76,
								lineHeight: 1.35,
								textDecoration: struck ? "line-through" : undefined,
								textDecorationThickness: struck ? 3 : undefined,
							}}
						>
							{text}
						</span>
					</div>
				);
			})}
		</AbsoluteFill>
	);
};
