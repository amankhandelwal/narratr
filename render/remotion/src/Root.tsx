import React from "react";
import { Composition } from "remotion";
import { Intro, type IntroProps } from "./Intro";
import { Scene, type SceneProps } from "./Scene";

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

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
	durationInFrames: Math.max(1, Math.round(props.durationInSeconds * FPS)),
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
