import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Icon, IconStyles } from "./Icon";
import { accent, beatAt, theme } from "./theme";

export type Step = { icon: string; label: string };

export type FlowProps = {
	heading?: string;
	steps: Step[];
	/** The condition holding across every step, shown below the chain. */
	footer?: Step;
	icons?: Record<string, string>;
};

/**
 * Two steps across 1920px is a different problem from five. Fixed tiles left a
 * short chain marooned in the middle of the frame, so the scale follows the
 * count and the chain fills a comparable width either way.
 */
const SCALE = {
	2: { tile: 248, icon: 124, label: 46, connector: 150 },
	3: { tile: 212, icon: 106, label: 42, connector: 116 },
	4: { tile: 184, icon: 92, label: 37, connector: 92 },
	5: { tile: 160, icon: 80, label: 33, connector: 72 },
} as const;

const scaleFor = (count: number) =>
	SCALE[Math.min(Math.max(count, 2), 5) as keyof typeof SCALE];

/**
 * A sequence: icon above label, joined left to right, revealed a step at a
 * time. The connector into a step draws before the step it points at, so the
 * eye is led rather than surprised.
 *
 * Three to five steps. Past that it is a diagram, and the skill says so.
 */
export const Flow: React.FC<FlowProps> = ({ heading, steps, footer, icons }) => {
	const frame = useCurrentFrame();
	const { durationInFrames } = useVideoConfig();
	const size = scaleFor(steps.length);

	// The footer is one more beat after the chain, so the chain lands first.
	const beats = steps.length + (footer ? 1 : 0) + 1;
	const at = (index: number) => beatAt(index, beats, durationInFrames);

	const fade = (start: number, over = 12) =>
		interpolate(frame, [start, start + over], [0, 1], {
			extrapolateLeft: "clamp",
			extrapolateRight: "clamp",
		});

	const lift = (start: number) =>
		interpolate(frame, [start, start + 14], [22, 0], {
			extrapolateLeft: "clamp",
			extrapolateRight: "clamp",
			easing: Easing.out(Easing.cubic),
		});

	const tile = (step: Step, index: number, start: number) => (
		<div
			key={`${step.icon}-${step.label}`}
			style={{
				display: "flex",
				flexDirection: "column",
				alignItems: "center",
				gap: 22,
				width: size.tile + 60,
				opacity: fade(start),
				transform: `translateY(${lift(start)}px)`,
			}}
		>
			<div
				style={{
					width: size.tile,
					height: size.tile,
					borderRadius: 28,
					backgroundColor: theme.panel,
					border: `2px solid ${theme.panelBorder}`,
					display: "flex",
					alignItems: "center",
					justifyContent: "center",
				}}
			>
				<Icon
					markup={icons?.[step.icon]}
					size={size.icon}
					color={accent(index)}
					strokeWidth={1.6}
				/>
			</div>
			<span
				style={{
					color: theme.fg,
					fontSize: size.label,
					lineHeight: 1.3,
					textAlign: "center",
				}}
			>
				{step.label}
			</span>
		</div>
	);

	return (
		<AbsoluteFill
			style={{
				backgroundColor: theme.bg,
				fontFamily: theme.font,
				padding: 96,
				justifyContent: "center",
				alignItems: "center",
				gap: 76,
			}}
		>
			<IconStyles />
			{heading && (
				<div
					style={{
						color: theme.muted,
						fontSize: 34,
						opacity: fade(0),
						alignSelf: "flex-start",
					}}
				>
					{heading}
				</div>
			)}

			<div style={{ display: "flex", alignItems: "flex-start", justifyContent: "center" }}>
				{steps.map((step, i) => (
					<React.Fragment key={`${step.icon}-${step.label}-${i}`}>
						{i > 0 && (
							<div
								style={{
									width: size.connector,
									height: size.tile,
									display: "flex",
									alignItems: "center",
									justifyContent: "center",
									// Drawn on the beat before the step it feeds.
									opacity: fade(at(i) - 6, 10),
								}}
							>
								<div
									style={{
										width: "100%",
										height: 3,
										backgroundColor: theme.line,
										position: "relative",
									}}
								>
									<div
										style={{
											position: "absolute",
											right: -2,
											top: -8,
											width: 0,
											height: 0,
											borderTop: "9px solid transparent",
											borderBottom: "9px solid transparent",
											borderLeft: `14px solid ${theme.line}`,
										}}
									/>
								</div>
							</div>
						)}
						{tile(step, i, at(i + 1))}
					</React.Fragment>
				))}
			</div>

			{footer && (
				<div
					style={{
						display: "flex",
						alignItems: "center",
						gap: 22,
						padding: "22px 40px",
						borderRadius: 20,
						backgroundColor: theme.panel,
						border: `2px solid ${theme.panelBorder}`,
						opacity: fade(at(steps.length + 1)),
						transform: `translateY(${lift(at(steps.length + 1))}px)`,
					}}
				>
					<Icon
						markup={icons?.[footer.icon]}
						size={52}
						color={theme.muted}
						strokeWidth={1.7}
					/>
					<span style={{ color: theme.muted, fontSize: 36 }}>{footer.label}</span>
				</div>
			)}
		</AbsoluteFill>
	);
};
