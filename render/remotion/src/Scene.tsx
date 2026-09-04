import React from "react";
import { Code } from "./Code";
import { Diagram } from "./Diagram";
import { Prose } from "./Prose";

/**
 * One scene from scenes.json, plus the duration measured from its audio.
 *
 * The renderer is told how long it has and fits its animation into that; it
 * never asks for more. See ../CONTRACT.md.
 */
export type SceneProps = {
	type: "prose" | "diagram" | "code";
	durationInSeconds: number;
	heading?: string;
	bullets?: string[];
	svg?: string;
	revealSteps?: string[][];
	code?: string;
	lang?: string;
};

export const Scene: React.FC<SceneProps> = (props) => {
	if (props.type === "diagram") {
		return (
			<Diagram
				heading={props.heading}
				svg={props.svg ?? ""}
				revealSteps={props.revealSteps ?? []}
			/>
		);
	}
	if (props.type === "code") {
		return <Code heading={props.heading} code={props.code ?? ""} lang={props.lang} />;
	}
	return <Prose heading={props.heading ?? ""} bullets={props.bullets ?? []} />;
};
