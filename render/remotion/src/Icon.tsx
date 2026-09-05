import React from "react";

/**
 * A Lucide glyph, resolved to SVG markup before the render started.
 *
 * The markup arrives in props rather than being imported here, so the renderer
 * stays synchronous and the pack stays a Python-side concern. See
 * narratr/icons.py.
 *
 * Lucide draws with `stroke="currentColor"`, so the glyph takes the colour set
 * on the wrapper. That is what lets one icon carry accent(i) and another the
 * dim of a struck bullet, with no per-icon markup.
 */

/** Sizing has to reach the inner <svg>, which inline styles cannot do. */
export const IconStyles: React.FC = () => (
	<style>{`.icon > svg { width: 100%; height: 100%; display: block; }`}</style>
);

export type IconProps = {
	markup?: string;
	size: number;
	color: string;
	/** Lucide's 2px stroke reads heavy below ~40px and thin above ~120px. */
	strokeWidth?: number;
};

export const Icon: React.FC<IconProps> = ({ markup, size, color, strokeWidth }) => {
	if (!markup) return null;
	const sized =
		strokeWidth === undefined
			? markup
			: markup.replace(/stroke-width="[^"]*"/, `stroke-width="${strokeWidth}"`);
	return (
		<span
			className="icon"
			style={{ width: size, height: size, color, flexShrink: 0 }}
			dangerouslySetInnerHTML={{ __html: sized }}
		/>
	);
};
