# ADR format

The ADR is the main source of events, so its format decides how good the proposals are. The
ADRs it replaces are prose with a title line, a status line and three headings. The
useful information for propagation is already in them, in the **Consequences** section, as
bullets that name issues in passing (`#13`, `#35`). The structured format keeps the prose and
makes each consequence addressable.

## The unit of propagation is a consequence, not the ADR

One ADR produces several events with different targets. ADR 0002 has one consequence for refunds
(`#13`, `#32`), one for peak-band classification (`#35`), one for backfilled days (`#29`). Proposing
"ADR 0002 → #29" with the whole ADR as the summary makes the planner of #29 reread the ADR and
guess which part applies. Proposing "consequence 5 of ADR 0002 → #29" with the bullet as the
summary is what they actually need.

## Format

````markdown
---
id: 0002
title: Store rides at per-trip grain, price them at rollup
status: accepted            # proposed | accepted | superseded | deprecated
date: 2026-09-08
supersedes: []              # ["adr:0001"], or one consequence: ["adr:0001#refund-grain"]
amends: []                  # ["adr:0003"] or ["adr:0003#consequence-id"] — earlier ADR still stands
amended_by: []              # ["adr:0021"] — whole-ADR refs; set on the earlier record
areas: [rides, fares, rollup]
# no-propagation: true           # only when no consequence binds another issue or area
# no-propagation-reason: "..."
---

## Context
(prose, unchanged)

## Decision
(prose, unchanged)

## Consequences

```yaml
- id: volume
  text: ~40,000 rides per dock per year. Trivial for any engine; rollups can be rebuilt.

- id: reprice
  text: Re-pricing any period against any fare plan is the same function with a different rate set.
  affects: [area:rollup]

- id: dst
  text: Local days have 23, 24 or 25 hours; `hours_expected` on `daily_summary` carries that.
  affects: ["#27"]

- id: backfill-grain
  text: Backfilled days from the logbook remain daily-grain with a pre-computed split, marked
    `source='logbook-backfill'`, and are never re-priced as if recorded per trip.
  affects: ["#29", "#30"]

- id: refund-grain
  text: Refunds carry a `grain` column. A `year`-grain row must not be spread across months.
  affects: ["#13", "#32"]

- id: band-windows
  text: "`peak_band` windows never wrap midnight; a crossing window is stored as two rows."
  affects: ["#35", "#31"]
```
````

Consequences are a YAML list inside a fenced `yaml` block; `adr migrate` writes that
form. An unfenced list of the same shape also parses, but the fence keeps GitHub from rendering
it as prose bullets. It is real YAML: a `text` that starts with a backtick or other YAML
indicator must be quoted.

Fields per consequence:

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | stable slug; the event's `detail` anchor is `docs/adr/0002-*.md#refund-grain` |
| `text` | yes | the consequence, one to three sentences. Becomes the event summary verbatim |
| `affects` | no | issue refs → events born `pending`; area refs → proposals for open issues in the area |
| `kind` | no | `decision` (default), `scope`, `supersede` |

A consequence with no `affects` produces no event unless the ADR's `areas` list matches an open
issue, in which case it is proposed at low confidence. This is deliberate: a consequence the
author could not attach to anything is either general knowledge or not yet actionable.

## What changes for `propose adr:`

| Input | Born as | Reason recorded |
|---|---|---|
| consequence `affects: ["#N"]` | pending | `affects` |
| consequence `affects: [area:x]` → open issues in x | proposed | `area` |
| ADR `areas:` ∩ open issues, consequence without `affects` | proposed | `adr-area` |
| `#N` mentioned in consequence text, not in `affects` | proposed | `mentions` |
| ADR `supersedes: [adr:M]` → issues that acknowledged any event from `adr:M` | pending, kind `supersede` | `supersedes` |
| ADR `supersedes: [adr:M#id]` → issues that acknowledged an event from consequence `id` of `adr:M` | pending, kind `supersede` | `supersedes` |
| ADR `amends: [adr:M]` → issues that acknowledged any event from `adr:M` | pending, kind `amend` | `amends` |
| ADR `amends: [adr:M#id]` → issues that acknowledged an event from consequence `id` of `adr:M` | pending, kind `amend` | `amends` |
| `status` changed to `deprecated` | pending, kind `supersede`, to every acknowledger | `deprecated` |

Editing a consequence's `text` changes the summary hash, so the next `propose` writes new events
by the rules above: `pending` for `affects` issues, `proposed` for area and mention targets. The
old events keep their status; a new `pending` event on a planned issue makes it stale. Editing
anything else re-raises nothing.

## Superseding part of an ADR

A decision sometimes replaces one consequence of an earlier ADR while the rest still stands.
Name that consequence instead of the whole ADR:

```yaml
supersedes: ["adr:0003#postgres-over-sqlite"]
```

`perturb propose` then raises `supersede` events only to the issues that acknowledged an event from
that consequence; issues that absorbed the ADR's other consequences hear nothing. The earlier ADR
keeps `status: accepted`, since most of it is still in force. Supersede a whole ADR with
`supersedes: ["adr:0003"]`, and give the old ADR `status: superseded` and `superseded_by`.

## Amending an ADR

A decision sometimes changes a premise or a clause of an earlier ADR while both records stay in
force. Use `amends` on the new ADR and `amended_by` on the earlier one:

```yaml
# new ADR
amends: ["adr:0008"]               # whole ADR, or "adr:0008#shape-ownership" for one consequence
```

```yaml
# ADR 0008
amended_by: ["adr:0021"]           # whole-ADR ref only; the earlier record keeps its status
```

`perturb propose` raises `amend` events to the issues that acknowledged events from the amended ADR
(or consequence). The earlier ADR keeps `status: accepted`; the relation is informational.

`extends` on a status line is read as `amends` by `perturb adr migrate`. Use `amends:` in
front-matter — there is no separate `extends` key.

## Migration for existing ADRs

A one-off `perturb adr migrate docs/adr/0002-*.md`:

1. Parse the title line, status line and date.
2. Carry a `**Supersedes:**` line into `supersedes` when it names only whole ADRs — with or
   without the `ADR` prefix (`**Supersedes:** [0003](0003-x.md) and ADR 4`). Any other Supersedes
   line, such as "the storage half of ADR 0003", stays in the body with a warning; write the
   matching `adr:0003#<consequence-id>` entry by hand.
3. Carry status-line `amends`/`extends` and `amended by`/`extended … by` annotations that name
   only whole ADR numbers into `amends:` and `amended_by:` in the front-matter. `extends` is read
   as `amends`. Accepted forms: `amends ADR 0008`, `amends [ADR-0008](0008-shape.md)`,
   `Extends ADR:4 and 0005`, `amended by ADR 0021`, `resolution premise amended by 0021`,
   `extended to physical geometry by [0022](0022-panel-geometry.md)`. Anchored refs
   (`amends ADR-0008#shape`), reason clauses before bare refs, and unrecognized annotations are
   reported as warnings.
4. Carry `**Amends:**`, `**Extends:**`, `**Amended by:**`, and `**Extended by:**` labelled body
   lines into `amends:` and `amended_by:` (case-insensitive; `-` accepted for the space in
   two-word forms). Continuation lines — a line that is not blank and does not start with `>`
   or `**` — are joined to the preceding relation line before its refs are read.
   - A whole-ADR line (`**Amends:** ADR 0003, ADR 4`) has its refs carried and the line removed
     from the body.
   - A line with a reason clause (first ` — `, ` – `, `: `, or ` (` in the text) has its refs
     carried, keeps the whole line in the body, and warns with the clause — the author should fold
     the explanation into a consequence.
   - A line naming more than whole ADRs (`**Amends:** the storage half of ADR 0003`) keeps the
     line in the body and warns with a consequence-anchor hint
     (`amends: ["adr:0003#<consequence-id>"]`).
   - Body-line refs merge with status-line refs from step 3, status-line first, de-duplicated.
5. Keep any prose between the status line and the first heading at the top of the body. An
   annotation on the status line itself is reported as a warning.
6. Split the existing Consequences bullets into entries with generated ids from the first
   noun phrase; the author renames them.
7. Extract `#NNN` mentions in each bullet into that entry's `affects`, so nothing already in
   prose is lost.
8. Write the file back; the author reviews the diff and the warnings, fills `areas`, and runs
   `perturb propose`.

## Validation in `perturb check`

An ADR is a file in `docs/adr` named `NNNN-<title>.md` — the name `perturb propose adr:` can
resolve. Other Markdown in that directory (an index `README.md`, a template, etc.) is ignored.

- **`adr_filename`** — a Markdown file in `docs/adr` whose name starts with digits but is not
  `NNNN-<title>.md` (e.g. `2-x.md`, `0002_x.md`). Rename it to `NNNN-<title>.md`.
- front-matter `id` matches the filename number;
- every `affects` ref resolves (issue exists, area is declared);
- every consequence `id` is unique within the ADR;
- `status: superseded` has a `superseded_by` entry that is a whole-ADR ref `adr:NNNN` (no
  consequence anchor) naming an ADR in the directory; a one-element list `["adr:NNNN"]` is
  accepted and normalised to the string; anything else (malformed ref, anchored ref, unknown ADR,
  or a list of two or more entries) is `superseded_by_unresolved`; that ADR lists it in
  `supersedes`;
- every `supersedes` entry is `adr:NNNN` or `adr:NNNN#id`, the ADR exists, and so does the named
  consequence; a bare string `supersedes: adr:0001` is accepted and read as a one-element list;
  the `supersede_backlink` check compares by ADR number, so `adr:2`, `adr:0002`, and `adr:0002#id`
  are equivalent spellings when checking that a superseding ADR points back;
- every `amends` entry is `adr:NNNN` or `adr:NNNN#id`, the ADR exists, and so does the named
  consequence (`amends_invalid`, `amends_unresolved`);
- every `amended_by` entry is `adr:NNNN` naming an ADR in the directory (no consequence anchor;
  `amended_by_unresolved`);
- two-way symmetry: `amended_by: [adr:M]` on ADR N requires ADR M to list N (or N#id) in
  `amends` (`amend_backlink`), and a resolved `amends` entry on ADR M requires ADR N to list M
  in `amended_by` (`amended_by_missing`);
- an ADR with `status: accepted` has at least one event, in any status, whose source is `adr:NNNN`
  or `adr:NNNN#<consequence>`, or it carries `no-propagation: true` (a YAML boolean) with a
  non-empty `no-propagation-reason`. `no-propagation: true` without a reason is itself a finding.
