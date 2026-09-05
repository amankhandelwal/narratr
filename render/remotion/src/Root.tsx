import React from "react";
import { Composition } from "remotion";
import { Intro, type IntroProps } from "./Intro";
import { Scene, type SceneProps } from "./Scene";

// The frame clock and the frame. Both compositions share them, and the Python
// side assumes the same numbers when it measures audio, so they are stated
// once here and exported as the renderer's public constants.
export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

/**
 * Seconds of measured audio to frames.
 *
 * Rounds rather than truncating, so a scene is never a frame short of its
 * narration, and floors at one frame: Remotion refuses a zero-length
 * composition, and a clip can legitimately measure a few milliseconds.
 */
export const framesFor = (seconds: number) => Math.max(1, Math.round(seconds * FPS));

const DEFAULTS: SceneProps = {
	type: "prose",
	durationInSeconds: 12,
	heading: "The usual failure",
	bullets: ["Slides first", "Narration second", "Drift forever"],
};

const INTRO_DEFAULTS: IntroProps = {
	durationInSeconds: 4.1,
	title: "narratr in brief",
};

// Duration comes from the measured audio, never from a guess. This is the
// audio-first clock reaching the renderer -- for the title card that clock is
// the intro sting rather than narration, but the rule is the same.
const framesFromProps = ({ props }: { props: { durationInSeconds: number } }) => ({
	durationInFrames: framesFor(props.durationInSeconds),
});

export const Root: React.FC = () => (
	<>
		<Composition
			id="Scene"
			component={Scene}
			fps={FPS}
			width={WIDTH}
			height={HEIGHT}
			defaultProps={DEFAULTS}
			calculateMetadata={framesFromProps}
		/>
		<Composition
			id="Intro"
			component={Intro}
			fps={FPS}
			width={WIDTH}
			height={HEIGHT}
			defaultProps={INTRO_DEFAULTS}
			calculateMetadata={framesFromProps}
		/>
	</>
);
