import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { theme } from "./theme";

export type IntroProps = {
	durationInSeconds: number;
	title: string;
};

/**
 * The title card: the mark, then the document's title, over the intro sting.
 *
 * The ground is pure black rather than `theme.bg`. The logo card carries its
 * own near-black ground baked in, so #020617 would draw a visible seam along
 * the letterbox edge where the two meet.
 *
 * `public/narratr-mark.png` is `assets/Narratr.png` with the generator's
 * sparkle watermark painted out of the bottom-right corner.
 */
export const Intro: React.FC<IntroProps> = ({ title }) => {
	const frame = useCurrentFrame();
	const { durationInFrames } = useVideoConfig();

	const markIn = interpolate(frame, [0, 14], [0, 1], {
		extrapolateLeft: "clamp",
		extrapolateRight: "clamp",
	});

	// Settles rather than zooms: the card arrives already almost in place.
	const settle = interpolate(frame, [0, 22], [1.03, 1], {
		extrapolateLeft: "clamp",
		extrapolateRight: "clamp",
		easing: Easing.out(Easing.cubic),
	});

	const titleIn = interpolate(frame, [40, 56], [0, 1], {
		extrapolateLeft: "clamp",
		extrapolateRight: "clamp",
	});

	// Out to black before the cut, so the first scene starts from the same
	// ground the card ended on rather than being jumped into.
	const out = interpolate(frame, [durationInFrames - 12, durationInFrames], [1, 0], {
		extrapolateLeft: "clamp",
		extrapolateRight: "clamp",
	});

	return (
		<AbsoluteFill style={{ backgroundColor: "#000000", opacity: out }}>
			<Img
				src={staticFile("narratr-mark.png")}
				style={{
					width: "100%",
					height: "100%",
					objectFit: "contain",
					opacity: markIn,
					transform: `scale(${settle})`,
				}}
			/>
			{/* Sits in the clear space below the wordmark, which ends at ~71% of
			    the frame once the card is letterboxed into 16:9. */}
			<AbsoluteFill
				style={{
					fontFamily: theme.font,
					justifyContent: "flex-end",
					alignItems: "center",
					paddingBottom: 196,
				}}
			>
				<div
					style={{
						color: theme.muted,
						fontSize: 34,
						letterSpacing: 6,
						textTransform: "uppercase",
						opacity: titleIn,
					}}
				>
					{title}
				</div>
			</AbsoluteFill>
		</AbsoluteFill>
	);
};
