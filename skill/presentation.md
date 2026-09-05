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

### Size a diagram for the frame

A diagram is scaled whole to fit an 1728x814 box. Nothing reflows and the font
never shrinks on its own — the picture just gets smaller, text included. Padding
and node spacing are fixed pixels, so **shrinking the font makes text smaller on
screen, not larger.** The lever is the other way round.

Count the nodes and set the config in the `mermaid` string itself:

| Nodes | Add |
|---|---|
| up to 4 | nothing |
| 5 to 9 | `fontSize: 28px`, `padding: 10` |
| 10 or more | `fontSize: 36px`, `padding: 6` |

```
---
config:
  themeVariables:
    fontSize: 36px
  flowchart:
    padding: 6
---
flowchart LR
    A@{ icon: "lucide:file-text", label: "doc.md" }
```

Only the keys named are overridden; the palette is untouched.

**A straight chain past about ten nodes cannot be rescued this way** — it ends
up 20:1 against a 2:1 frame and wastes all the height. Break it into rows or
subgraphs. Shape beats font size: 25 branching nodes read larger than 9 in a
line.

### When the config runs out: split the diagram

Only when a diagram is genuinely too dense to read at the largest setting —
roughly a dozen nodes in a line, or twenty-five in total. Not a habit. A
diagram that fits is better shown whole.

When it does not fit, show the system once and then open one component at a
time:

1. **The high-level diagram**, components only, no internals.
2. **For each component worth opening:** the same high-level diagram again with
   that component highlighted and the rest dimmed, then a second scene with its
   internals.

The recap is what makes it digestible — it says where you are before it goes
deep. Dim with a class, and list **only** the highlighted node in
`revealSteps`; the reveal styling overrides whatever it is given, so a dimmed
node named there comes back undimmed.

```
flowchart LR
    A@{ icon: "lucide:inbox", label: "Ingest" }
    B@{ icon: "lucide:mic", label: "Narrate" }
    C@{ icon: "lucide:film", label: "Assemble" }
    A --> B --> C
    classDef dim fill:#0b1220,stroke:#1e293b,color:#475569
    class A,C dim
```

A recap scene introduces no new source blocks. That is fine; the coverage gate
maps blocks to scenes, not scenes to blocks.

### Give diagram nodes icons

Same as bullets, steps and cards — a node names a thing, and the glyph says
which thing at a glance:

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
