import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { accent, theme } from "./theme";

export type CodeProps = {
	heading?: string;
	code: string;
	lang?: string;
	/** Shiki output, highlighted ahead of render time. */
	html?: string;
};

export const Code: React.FC<CodeProps> = ({ heading, code, html }) => {
	const frame = useCurrentFrame();
	const opacity = interpolate(frame, [0, 14], [0, 1], {
		extrapolateLeft: "clamp",
		extrapolateRight: "clamp",
	});

	const panel: React.CSSProperties = {
		opacity,
		margin: 0,
		padding: 40,
		borderRadius: 16,
		backgroundColor: theme.panel,
		border: `1px solid ${theme.panelBorder}`,
		borderLeft: `6px solid ${accent(1)}`,
		color: theme.fg,
		fontFamily: theme.mono,
		fontSize: 42,
		lineHeight: 1.5,
		whiteSpace: "pre-wrap",
		overflow: "hidden",
	};

	return (
		<AbsoluteFill
			style={{
				backgroundColor: theme.bg,
				fontFamily: theme.font,
				padding: 96,
				justifyContent: "center",
			}}
		>
			{heading ? (
				<div style={{ color: theme.muted, fontSize: 34, marginBottom: 40 }}>{heading}</div>
			) : null}
			{/* Shiki emits its own <pre>, so the panel styling is applied to a
			    wrapper and the inner element is flattened. */}
			<style>{`
				.code pre { margin: 0; background: transparent !important; }
				.code code { font-family: inherit; font-size: inherit; }
			`}</style>
			{html ? (
				<div className="code" style={panel} dangerouslySetInnerHTML={{ __html: html }} />
			) : (
				<pre style={panel}>{code}</pre>
			)}
		</AbsoluteFill>
	);
};
