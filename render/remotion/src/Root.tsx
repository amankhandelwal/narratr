import React from "react";
import { Composition } from "remotion";
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

export const Root: React.FC = () => (
	<Composition
		id="Scene"
		component={Scene}
		fps={FPS}
		width={WIDTH}
		height={HEIGHT}
		defaultProps={DEFAULTS}
		// Duration comes from the measured audio, never from a guess. This is
		// the audio-first clock reaching the renderer.
		calculateMetadata={({ props }) => ({
			durationInFrames: Math.max(1, Math.round(props.durationInSeconds * FPS)),
		})}
	/>
);
