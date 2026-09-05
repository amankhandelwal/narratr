// Highlights code to HTML ahead of render time.
//
// Doing this here rather than inside the Remotion component keeps the renderer
// synchronous: highlighting in the component would need delayRender, and every
// frame would pay for it.
//
// Reads {"code": "...", "lang": "..."} on stdin, writes HTML on stdout.
import { codeToHtml } from "shiki";

const input = JSON.parse(await new Response(process.stdin).text());

const html = await codeToHtml(input.code ?? "", {
	lang: input.lang || "text",
	theme: "night-owl",
});

// Shiki paints its own background; the scene already has one, and the panel
// styling belongs to the component.
process.stdout.write(html.replace(/background-color:[^;"]*;?/g, ""));
