# Presentation language

How a scene should look, and how to choose. `SKILL.md` covers the workflow;
this covers the picture. Read it before writing `scenes.json`, and read
`example.scenes.json` beside it for a complete spec using every shape.

The rule underneath all of it: **a shape separates things, it never
decorates.** An icon that names nothing, or a layout the content does not
have, is worse than the plain version.

---

## Pick the shape from the content

Five scene types. Choose by what the content *is*, not for variety:

| The content is | Use | Carries |
|---|---|---|
| Ordered steps, a pipeline | `flow` | `steps` (2–5), optional `footer` |
| Parallel things being compared | `cards` | `cards` (2–4) |
| Structure or relationships | `diagram` | `mermaid` + `revealSteps` |
| Source code | `code` | `code` + `lang` |
| Anything else — properties, claims | `prose` | `bullets` (≤6) |

`prose` is the default. Reaching for `flow` when the content is not a sequence,
or `cards` when the things are not parallel, makes the shape fight the words.

**The shuffle test.** Before writing `bullets`, reorder them in your head. If
the slide still reads, it is a list — use `prose`. If it does not, the order is
carrying meaning and the content is a sequence: use `flow`.

Ordinal words are the giveaway. *First, then, next, after, becomes, feeds,
turns into* — or bullets that are numbered, or that each name a stage. "Script
first / Then audio / Then pictures" fails the shuffle test three times over. It
is a flow, not a list.

**`flow` or `diagram`?** `flow` is for a straight line: one path, every step
following the last. `diagram` is for shape — branching, merging, clusters,
labelled edges, anything you would need to draw rather than list. A linear
pipeline in Mermaid renders as a narrow column of small boxes with the frame
empty either side; the same steps as a `flow` fill the frame and reveal one at
a time.

**Diagrams are drawn into a 16:9 frame.** Pick the direction to suit it:
`flowchart LR` for a chain, `flowchart TD` only for something genuinely deep.
The same five-node pipeline measures 114×756 as `TD` and 606×124 as `LR` — one
is a sliver down the middle of the screen, the other fills it.

**Give diagram nodes icons.** Same as bullets, steps and cards — a node names
a thing, and the glyph says which thing at a glance:

```
flowchart LR
    A@{ icon: "lucide:file-text", label: "doc.md" }
    B@{ icon: "lucide:file-pen", label: "Script" }
    A --> B
```

narratr renders these as ordinary labelled boxes with the glyph inside the box,
not as Mermaid's bare icon shapes — the box is what carries structure once a
diagram has more than a handful of nodes. Write `icon` and `label` and nothing
else; `form` and the other icon-shape fields are ignored.

All the nodes or none of them: a half-iconised diagram reads as a mistake. If
several nodes are abstract enough that no icon names them, leave the whole
diagram plain rather than icon some and not others. Node ids stay whatever
`revealSteps` refers to.

**Never downgrade a shape to avoid repeating one.** If two scenes in a row both
want to be a `flow`, the problem is the script, not the layout — they are
almost certainly the same content at two levels of detail. Merge them, or give
each a distinct job: one carries the principle, the other the mechanism. Making
the second one a bulleted list hides the duplication instead of fixing it, and
leaves a sequence rendered as a list.

## Icons

Every bullet, step, card and diagram node takes a Lucide icon, kebab-case, in
`icon`. Icons are the default everywhere, not a decoration you add if there is
room.

- **Name the object under discussion.** "Runs resume" is `rotate-ccw`, not
  `sparkles`. An icon that decorates rather than names is worse than none.
- **Omit it if nothing fits.** An approximate icon reads as a mistake.
- **Look the name up, do not guess twice:**

  ```sh
  uv run narratr icons <word>
  ```

  Searches ~2,000 names and Lucide's own keywords. An icon name that does not
  exist fails `narratr validate` before any compute is spent, with near misses.

## Rejecting something

A bullet describing the approach being *rejected* takes `"state": "struck"`.
It renders dimmed with a line through it. Use it for the wrong way, usually
before the right way; do not strike a consequence, only a choice.

## The rules the schema enforces

- One message per scene
- Fragments on screen, never sentences — detail lives in the narration
- Six bullets maximum, 2–5 flow steps, 2–4 cards
- Diagram scenes carry `mermaid` plus `revealSteps` grouping node ids into beats
