import React from "react";
import { Cards, type Card } from "./Cards";
import { Code } from "./Code";
import { Diagram } from "./Diagram";
import { Flow, type Step } from "./Flow";
import { Prose, type Bullet } from "./Prose";

/**
 * One scene from scenes.json, plus the duration measured from its audio.
 *
 * The renderer is told how long it has and fits its animation into that; it
 * never asks for more. See ../CONTRACT.md.
 */
export type SceneProps = {
	type: "prose" | "diagram" | "code" | "flow" | "cards";
	durationInSeconds: number;
	heading?: string;
	bullets?: Bullet[];
	svg?: string;
	revealSteps?: string[][];
	code?: string;
	lang?: string;
	/** Shiki output for code scenes, highlighted ahead of render time. */
	html?: string;
	steps?: Step[];
	footer?: Step;
	cards?: Card[];
	/** Lucide markup by name, resolved ahead of render time. */
	icons?: Record<string, string>;
	/**
	 * Seconds into the scene at which each revealed element appears, resolved
	 * in Python from the scene's cue phrases against the aligned narration.
	 * Absent under `narratr preview`, which has no audio to align.
	 */
	beats?: number[];
};

export const Scene: React.FC<SceneProps> = (props) => {
	if (props.type === "diagram") {
		return (
			<Diagram
				heading={props.heading}
				svg={props.svg ?? ""}
				revealSteps={props.revealSteps ?? []}
				beats={props.beats}
			/>
		);
	}
	if (props.type === "code") {
		return (
			<Code
				heading={props.heading}
				code={props.code ?? ""}
				lang={props.lang}
				html={props.html}
			/>
		);
	}
	if (props.type === "flow") {
		return (
			<Flow
				heading={props.heading}
				steps={props.steps ?? []}
				footer={props.footer}
				icons={props.icons}
				beats={props.beats}
			/>
		);
	}
	if (props.type === "cards") {
		return (
			<Cards
				heading={props.heading}
				cards={props.cards ?? []}
				icons={props.icons}
				beats={props.beats}
			/>
		);
	}
	return (
		<Prose
			heading={props.heading ?? ""}
			bullets={props.bullets ?? []}
			icons={props.icons}
			beats={props.beats}
		/>
	);
};
