# Concepts

perturb connects the things decisions are recorded in (issues, plans, ADRs, the evidence
implementation leaves behind) so that a change to one reaches the others. This page explains the
pieces. The full design model, with every edge, is in [design/02-model.md](design/02-model.md).

## Refs

Everything perturb talks about has a short name, a **ref**:

| Thing | Ref | Where it lives |
|---|---|---|
| issue | `#32` or `32` | GitHub |
| plan | `plan:backfill-refunds`, or its path `tasks/backfill-refunds.md` | `tasks/<slug>.md` by default |
| friction log | `friction:backfill-refunds` | `tasks/friction-logs/<slug>-friction.md` by default |
| audit | `audit:backfill-refunds` | `tasks/friction-audits/<slug>-audit.md` by default |
| ADR | `adr:0002` or `adr:2` | `docs/adr/0002-*.md` |
| area | `area:fares` | `perturb/areas.yaml` |

A plan, its friction log and its audit share a slug. Events name a single ADR consequence as
`adr:0002#refund-grain`. In zsh, quote `'#32'` or write `32`. `perturb ref <text>` shows how a ref
resolves.

## Ready, planned and next

perturb reads each issue's state, labels, sub-issue parent and blocked-by links from GitHub.
GitHub stays the source of truth; perturb keeps a local cache in `.perturb/`, but never answers
from it when GitHub cannot be reached.

- **Epic:** an issue with the `epic` label. Epics group work: they are never ready, and never the
  target of an event. A proposal aimed at an epic goes to its open children instead, and
  `perturb push` refuses an epic and lists its children.
- **Ready:** open, not an epic, and every issue blocking it is closed.
- **Planned:** a plan's `closes:` names the issue, and the issue carries the ready-to-implement
  label.
- **Next:** ready and not planned, ordered by how many open issues each would unblock, directly or
  further down the chain, then by issue number. This is `perturb next`.

Both labels can be changed in [configuration](configuration.md#config-perturbconfigyaml).

## Events

An **event** is a message from a source to an issue: *this changed something that may affect you*.
Each one is a YAML file in `perturb/events/`, named by a sortable unique ID and committed with the
change that caused it.

```yaml
id: 01J9Q7K2M4X8
at: '2026-09-08T16:02:11Z'
source: "#31"
target: "#32"
kind: decision
summary: Fare periods are half-open
detail: tasks/backfill-fares.md#design-decisions-locked
proposed_by: sam
reason: manual
status: pending
```

`detail` optionally points at the text behind the event, which `perturb inbox` quotes.

| Kind | Meaning for the target issue |
|---|---|
| `decision` | a decision constrains its design |
| `scope` | something was cut from it or moved into it |
| `friction` | implementation found a problem in code it touches |
| `supersede` | the source replaces or invalidates part of it |
| `amend` | the source changes a premise or clause of it; the earlier decision still stands |
| `unblock` | a blocker closed; informational |

### Where events come from

| Source | Command | Status when created |
|---|---|---|
| a person or agent | `perturb push` | pending |
| an ADR consequence naming issues in `affects:`, or an ADR `supersedes:`, `amends:`, or deprecation | `perturb propose adr:<N>` | pending |
| an ADR consequence routed through areas or `#N` mentions | `perturb propose adr:<N>` | proposed |
| a plan's decisions or scope cuts that mention other issues | `perturb propose plan:<slug>` | proposed |
| a friction log's commits touching other areas | `perturb propose friction:<slug>` | proposed |
| an audit's CRITICAL and PLANNING DEBT items | `perturb propose audit:<slug>` | proposed |
| a closed blocker | any verb that syncs | pending (`unblock`) |

### Lifecycle

```
propose ──▶ proposed ──confirm──▶ pending ──ack──▶ acknowledged
                │                    │
                └──dismiss───────────┴──dismiss──▶ dismissed
```

- **proposed:** a tool found a plausible target. It waits for a person or a planning agent to
  `confirm` or `dismiss` it, and shows in `perturb inbox <issue> --include proposed`.
- **pending:** the target should see this. It shows in the inbox and counts toward the stale gate.
- **acknowledged:** the target's planner absorbed it and recorded how.
- **dismissed:** not relevant to the target. It is kept so the same proposal is not raised again.

The same source, target, kind and summary are never recorded twice: re-running `propose` adds
nothing new. If an ADR consequence's text changes, that is a new decision and a new event.

## Inboxes and acknowledgements

`perturb inbox 32` lists the pending events for #32, quoting each one's `detail`. Whoever plans #32
folds each event into the plan, then records that with `perturb ack`. An acknowledgement stores who
made it, their note, the plan's path, and the plan's exact committed version, so the plan must be
committed and its `closes:` must name the issue. Acknowledging again overwrites the previous one.

## The stale gate

`perturb stale 32` checks a planned issue against its events and fails (exit 1) when:

- a **pending** event was created after the plan's last commit, or
- an **acknowledged** event was acknowledged against a version of the plan that has since changed.

Run it immediately before implementing. It compares the event's creation time with the plan's
commit time, so an event recorded on a branch that merges late can slip past; see
[Working in a team](teams.md).

## Areas

Many findings are about code rather than an issue. An **area** is a named part of the codebase,
declared by hand as path globs in `perturb/areas.yaml`. An issue is in an area when it carries the
area's label (`area:<slug>` by default) or its plan lists the area under `areas:`. Areas route:

- ADR consequences with `affects: [area:fares]`, and consequences without `affects` in an ADR whose
  `areas:` lists the area;
- friction logs: files the run touched that its plan didn't declare;
- audits: the paths a CRITICAL item names.

Each goes to the open issues in the matching areas, as proposals. Details are in
[configuration](configuration.md#areas-perturbareasyaml).

## Checks

`perturb check` is the whole-ledger lint, meant for CI. It fails when an ADR breaks the
[format](adr-format.md#validation-in-perturb-check) or an accepted ADR was never propagated, when
a pending event targets a closed issue, when an event's `detail` no longer resolves, or when a
planned issue is stale. Each finding includes the command that fixes it.
