---
name: perturb
description: Answer questions about the planning ledger and issue graph by running one perturb verb and rendering its JSON. Use when the user asks "what's next", "what's ready", "what changed for 31", "is 29 still valid", "show 29", "what's in the inbox", "is the ledger clean", or names a perturb verb. Not for planning, implementing or reviewing an issue.
---

## Purpose

Make the `perturb` verbs discoverable by name. This skill has no logic of its own: each question
maps to exactly one verb, run with `--json`, and the envelope is rendered for the user.

Run from the repository root. Every read verb syncs from GitHub first (through `gh`, or the command in
`PERTURB_GH`); if the
envelope comes back `ok: false`, show its `reason` and `detail` and stop. Never answer from memory
or from an earlier result.

## Phrase → verb

| The user asks | Run |
|---|---|
| "what's next", "what should I plan next" | `perturb next --json` (add `--epic N` if they name an epic) |
| "what's ready", "what can be started" | `perturb ready --json` (`--all` to include planned issues) |
| "what changed for N", "what's in N's inbox" | `perturb inbox N --json --include proposed` |
| "is N still valid", "is N's plan stale" | `perturb stale N --json` |
| "is anything stale" | `perturb stale --json` |
| "show N", "tell me about N" | `perturb show N --json` |
| "draw the epic", "graph of N" | `perturb graph --epic N --format mermaid` |
| "is the ledger clean", "will CI pass" | `perturb check --json` |

A question that maps to none of these is not for this skill: say which verb is closest, or that
none fits.

## Rendering

- **Lists** (`next`, `ready`): one line per issue — `#N title` plus its state — in the order the
  verb returned. The order is the priority; never re-sort.
- **`inbox`**: group by status (`pending` first, then `proposed`); each event as
  `kind — summary (source, id)`, with `detail` as a link when present.
- **`stale`**: empty `data` → "N is current". Otherwise list each stale event and say the plan
  needs re-planning; do not re-plan here.
- **`show`**: title, state, labels, epic, `ready`/`planned`, plan path, `blocked_by` (with each
  blocker's state) and `blocking`. For its events, run `inbox` as a second question.
- **`check`**: `ok: true` → "clean". Otherwise one line per finding — `kind ref: detail` — followed
  by its `fix` command verbatim.
- **`graph`**: print the mermaid block as is.

## Write verbs are out of scope

Do not run `push`, `ack`, `propose`, `confirm`, `dismiss` or `init` from this skill. When the
answer suggests one (a `check` fix, an unacked inbox), quote the command and let the user run it.
