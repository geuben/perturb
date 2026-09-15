# 02 — Model

The full design model. For an introduction to using perturb, see [concepts](../concepts.md).

## Nodes

Every node has a stable **ref** string. Refs are how events, edges and CLI arguments name things.

| Kind | Ref | Source of truth | Identity |
|---|---|---|---|
| issue | `#31` | GitHub | issue number in this repo |
| plan | `plan:fare-schema` | repo `tasks/<slug>.md` by default (`paths.plan`) | file slug; joins to issue via `closes:` |
| adr | `adr:0002` | repo `docs/adr/0002-*.md` | four-digit number |
| friction | `friction:fare-schema` | repo `tasks/friction-logs/<slug>-friction.md` by default (`paths.friction_log`) | plan slug; joins to plan, run number inside the file |
| audit | `audit:fare-schema` | repo `tasks/friction-audits/<slug>-audit.md` by default (`paths.audit`) | plan slug |
| area | `area:fares` | repo `perturb/areas.yaml` | declared slug with path globs |

**Area** is the only node type this layer invents. It exists because friction findings and ADRs
usually talk about *code* ("the rollup layer", `src/core/money/`), while issues talk about
*outcomes*. Without an intermediate, a friction finding about `src/core/fares/` can only reach an
issue somebody remembered to link. With areas, every open issue whose plan or label names
`area:fares` is a candidate target. Areas are declared, never inferred: a small YAML file, edited
by hand, with globs. Under ten entries for a mid-sized repo.

## Edges

Two families. **Structural** edges come from GitHub or from existing front-matter and are derived,
never stored by this tool. **Ledger** edges are the events, stored by this tool.

Structural (derived on every read, cached):

| Edge | From → To | Derived from |
|---|---|---|
| `parent` | issue → issue | GitHub sub-issues |
| `blocks` | issue → issue | GitHub `blocking` / `blockedBy` |
| `planned_by` | issue → plan | plan front-matter `closes:` |
| `executed_as` | plan → friction | friction log title line |
| `audited_as` | friction → audit | audit file `Friction Log Source:` line |
| `touches` | plan/friction → area | cycle `files` and commit file lists matched against area globs |
| `in_area` | issue → area | label `area:<slug>` on the issue, or `areas:` in its plan's front-matter |
| `in_area` | adr → area | `areas:` in the ADR's front-matter, see [adr-format.md](../adr-format.md) |
| `affects` | adr consequence → issue/area | `affects:` on a consequence; the primary ADR edge |
| `mentions` | adr/audit → issue | `#NNN` in the body. Low confidence; only ever a proposal input |

Only `parent`, `blocks` and `planned_by` are materialised in `.perturb/graph.json`. The others
are computed by `propose` from the source artefact each time it runs.

## Events

An event is a message from a source node to a target node.

```yaml
id: 01J9Q7K2M4X8            # ULID. Sortable, collision-free across branches
at: '2026-09-08T16:02:11Z'
source: adr:0002#refund-grain
target: "#13"
kind: decision               # see table
summary: "Refunds carry a grain column; a year-grain row must not be spread across months"
detail: docs/adr/0002-per-trip-grain.md#consequences
proposed_by: perturb propose  # or a person / agent
reason: affects               # why this target was proposed: affects | mentions | area | blocks | manual
status: pending               # proposed | pending | acknowledged | dismissed. affects → born pending
ack:                          # present once status is acknowledged or dismissed
  at: '2026-09-20T10:14:00Z'
  by: plan-issue
  plan: tasks/refund-backfill.md
  plan_blob: 4ef5700046bc1340bbca16f4baceae14c47c8703
  note: "Locked as design decision 3; backfill writes grain=year"
```

| Kind | Typical source | Meaning for the target's planner |
|---|---|---|
| `decision` | adr, plan | a locked decision constrains this issue's design |
| `scope` | plan, issue | this issue's scope moved: something was cut from or pushed into it |
| `friction` | friction, audit | run evidence about code this issue will touch |
| `supersede` | adr, issue | the source replaces or invalidates part of the target |
| `unblock` | issue | a blocker closed; informational, generated on `sync` so `inbox` is complete |

### Lifecycle

```
propose ──▶ proposed ──confirm──▶ pending ──ack──▶ acknowledged
                │                    │
                └──dismiss───────────┴──dismiss──▶ dismissed
```

- **proposed**: a tool found a plausible target. Not shown in `inbox` by default. Shown by
  `inbox --include proposed` and `propose --review`.
- **pending**: a person or the planning agent agreed the target should see this. Shown in `inbox`.
  Counts toward `stale`.
- **acknowledged**: the target's planner read it and recorded what they did. The `ack.plan_blob`
  pins which version of the plan absorbed it.
- **dismissed**: irrelevant to the target. Kept, so the same proposal is not re-raised.

An event created by hand (`perturb push`) is born `pending`: a human deciding the target *is* the
confirmation. So is the event `propose audit: --review` writes when the auditor accepts creating an issue for
a no-target CRITICAL item. An event created by `propose` from an explicit `affects:` list in ADR front-matter is
also born `pending` for the same reason. Everything else is born `proposed`.

### Idempotence

`(source, target, kind, summary-hash)` is unique. Re-running `propose adr:0002` after a dismissal
produces nothing new. Editing the ADR so a consequence's text changes produces a new event with a
new summary hash, which is correct: the decision changed.

## Derived states

These are queries, not stored fields:

- **ready(issue)**: open, every `blockedBy` closed, not itself an epic (the `epic` label, or
  `labels.epic` in `perturb/config.yaml`).
- **planned(issue)**: has a `planned_by` plan and the ready-to-implement label (`ready-to-implement`,
  or `labels.ready_to_implement` in `perturb/config.yaml`).
- **stale(issue)**: planned, and at least one `pending` event whose `at` is later than the plan
  file's last commit. Also: planned, and any acknowledged event's `ack.plan_blob` no longer matches
  the plan's current blob (the plan was revised; the ack is for an old version).
- **next(issue)**: ready and not planned, ordered by the number of open issues it transitively
  unblocks (desc), then issue number.

## Worked example: epic #3

Current state, from GitHub:

| Issue | Blocked by (open) | Ready | Note |
|---|---|---|---|
| #29 backfill daily rides | none | yes | unblocks #33 |
| #30 backfill memberships | none | yes | unblocks #33 |
| #31 backfill fares | #12 | no | |
| #32 backfill refunds | #13 #14 #15 | no | ADR 0002 mentions #13 |
| #33 reconciliation report | #29 #30 #31 #32 | no | |

With ADR 0002 in the structured format (consequences `refund-grain`, `band-windows`,
`backfill-grain` carrying `affects`), `perturb propose adr:0002` would emit:

- `adr:0002#refund-grain → #13`, `→ #32` (reason: affects) born `pending`
- `adr:0002#band-windows → #35`, `→ #31` (reason: affects) born `pending`
- `adr:0002#backfill-grain → #29`, `→ #30` (reason: affects) born `pending`
- `adr:0002#reprice → #33` (reason: area, `area:rollup`) born `proposed`

A reviewer dismisses `#35` as already implemented and confirms the `reprice` proposal. `perturb
next` now shows #29 and #30 with #29 carrying one pending event. `plan-issue 29` Phase A prints the
inbox; the plan's locked decisions cite it; `ack` records the plan blob. Later, planning #31 locks
"fare periods are half-open"; the planner runs `push --to '#32'` because refunds reference fare
periods. #32 now has one pending event before anyone has opened it.
