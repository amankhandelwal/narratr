import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Icon, IconStyles } from "./Icon";
import { accent, revealFrames, theme } from "./theme";

export type Card = { icon?: string; title: string; detail?: string };

export type CardsProps = {
	heading?: string;
	cards: Card[];
	icons?: Record<string, string>;
	/** Seconds into the scene at which each card appears. */
	beats?: number[];
};

/**
 * Parallel things, side by side, revealed one at a time.
 *
 * For comparisons and for a set of options with their costs -- content that is
 * genuinely of the same kind. A list of unrelated properties in cards is
 * furniture around nothing, and the skill says so.
 */
export const Cards: React.FC<CardsProps> = ({ heading, cards, icons, beats }) => {
	const frame = useCurrentFrame();
	const { durationInFrames, fps } = useVideoConfig();
	const starts = revealFrames(cards.length, durationInFrames, fps, beats);

	const fade = (start: number) =>
		interpolate(frame, [start, start + 12], [0, 1], {
			extrapolateLeft: "clamp",
			extrapolateRight: "clamp",
		});

	const lift = (start: number) =>
		interpolate(frame, [start, start + 14], [26, 0], {
			extrapolateLeft: "clamp",
			extrapolateRight: "clamp",
			easing: Easing.out(Easing.cubic),
		});

	// Four cards across 1920 need less air than two do.
	const wide = cards.length <= 2;

	return (
		<AbsoluteFill
			style={{
				backgroundColor: theme.bg,
				fontFamily: theme.font,
				padding: 96,
				justifyContent: "center",
				gap: 64,
			}}
		>
			<IconStyles />
			{heading && (
				<div style={{ color: theme.muted, fontSize: 34, opacity: fade(0) }}>{heading}</div>
			)}
			<div
				style={{
					display: "flex",
					gap: wide ? 48 : 34,
					alignItems: "stretch",
					justifyContent: "center",
				}}
			>
				{cards.map((card, i) => {
					const start = starts[i];
					return (
						<div
							key={`${i}-${card.title}`}
							style={{
								flex: 1,
								display: "flex",
								flexDirection: "column",
								gap: 26,
								padding: wide ? 56 : 42,
								borderRadius: 26,
								backgroundColor: theme.panel,
								border: `2px solid ${theme.panelBorder}`,
								opacity: fade(start),
								transform: `translateY(${lift(start)}px)`,
							}}
						>
							<Icon
								markup={card.icon ? icons?.[card.icon] : undefined}
								size={wide ? 76 : 64}
								color={accent(i)}
								strokeWidth={1.6}
							/>
							<span
								style={{
									color: theme.fg,
									fontSize: wide ? 60 : 46,
									lineHeight: 1.25,
								}}
							>
								{card.title}
							</span>
							{card.detail && (
								<span
									style={{
										color: theme.muted,
										fontSize: wide ? 36 : 30,
										lineHeight: 1.4,
									}}
								>
									{card.detail}
								</span>
							)}
						</div>
					);
				})}
			</div>
		</AbsoluteFill>
	);
};
