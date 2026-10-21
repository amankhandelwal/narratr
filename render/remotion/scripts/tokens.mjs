// Shiki tokens as JSON, for the deck builder.
//
// The deck writes code as coloured text runs so it stays editable, which
// needs tokens rather than HTML. A separate file from highlight.mjs on
// purpose: that one is a renderer source, and touching it re-renders video.
//
// Reads {"code": "...", "lang": "...", "theme": "..."} on stdin, writes
// [[[content, colour], ...], ...] -- one array per line -- on stdout.
import { codeToTokens } from "shiki";

const input = JSON.parse(await new Response(process.stdin).text());

const { tokens } = await codeToTokens(input.code ?? "", {
	lang: input.lang || "text",
	theme: input.theme || "night-owl",
});

process.stdout.write(JSON.stringify(tokens.map((line) => line.map((t) => [t.content, t.color]))));
