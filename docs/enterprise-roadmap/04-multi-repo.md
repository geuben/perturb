# 04 — Many repositories, many teams

> Exploratory. See the [index](README.md).

Planning is team-owned, and a team may own several repositories (microservices). A decision may
need delivering to several of them, some owned by other teams.

## A planning repository per team

Each team keeps one planning repository holding its **issues, plans, ADRs, areas and ledger**.
Its code repositories hold code only and point at it (`ledger: org/team-plan`).

- `#42` means the team's planning repository; implementation PRs in service repositories close it
  with `org/team-plan#42`.
- One plan may span services: plan files are repository-qualified, and one plan produces one
  implementation PR per repository, each gated against the team's ledger.
- Within a team, multiple repositories only show up in area paths, friction proposals and the
  implementation gate.
- Cost: a service's issue tracker no longer lists its work. GitHub Projects can show it across
  repositories.

## Federation between teams

One rule places all state: **a team's ledger holds only what that team decided.**

| State | Lives with |
|---|---|
| an event | the source team, where its decision was reviewed |
| confirm, dismiss and ack records for it | the target team, as separate append-only records naming the event by qualified id (`orgA/plan:01M2K…`) |

No write ever crosses into another team's repository. A team's inbox and stale gate read its own
ledger plus every peer's, keep events aimed at its issues or areas, and apply its own records.

### Cross-team events arrive as proposals

Team A cannot amend team B's plans. An event crossing teams arrives in B as **proposed**, whatever
its status in A. B's planner confirms it (it becomes pending and gates B, including halting B's
in-flight runs) or dismisses it with a note. Within a team, events are pending on merge as before.
Each team needs an owner for incoming cross-team proposals.

### Feedback to the source

A's `check` reports on its outgoing cross-team events: unanswered for N days, or dismissed with B's
note. A dismissal makes the conflict visible; perturb does not resolve it.

### Discovery: an org registry

If B reads a fixed peer list, events from unlisted teams vanish silently. Instead, one org-level
registry lists every team's ledger; everyone reads every registered ledger, and A's `check` fails on
an event targeting an unregistered repository. Org-wide ADRs fit naturally: the architecture group
is one more registered ledger.

### Refs

Every ref is qualified (`org/repo#32`, `org/repo:area:fares`, `org/repo:adr:0007`); short forms
mean the local ledger. Area paths are repository-qualified (`api:src/fares/**`), and a whole
repository can be an area (`area:billing-service`).

## Delivering one decision to many services

An ADR changes the order-event schema; five services must change. An inbox entry informs each
planner, but nothing tracks that all five ship.

**One decision, N events.** No new event shape: N events sharing a `source`
(`adr:0007#order-schema-v2`), one per target, each with its own response record. perturb already
does this when fanning out from an epic. What is new is a roll-up by source:

```
perturb delivery adr:0007#order-schema-v2

orders-service      delivered (issue closed)
billing-service     planned (acked, plan v2)
shipping-service    pending
teamB/notify        proposed, unanswered 4 days
```

**Targets are often areas.** Often no issue exists yet in a service when the decision is made. An
event can target the area (`area:shipping-service`) and be pulled at planning time: `perturb inbox`
for a plan declaring `areas: [shipping-service]` includes the area's open events. **The first plan
in the area to ack the event claims it**; the area's delivery completes when that plan's issue
closes, and later planners are not asked again. This avoids fan-out to N issues, reaches issues
created after the event, and removes the label lookup across many repositories.

**Events are one-off deltas; standing rules are ADRs.** "Migrate to schema v2" is an event and
finishes. "All new consumers use schema v2" never finishes, so it belongs in an ADR that planners
read, not in inboxes. Without this split, area events accumulate.

**Rollout order is not perturb's job.** Producer before consumer, expand-migrate-contract: that is
work order, expressed in plans and blocked-by links and acted on by the dispatcher.

## Changes implied

1. Qualified refs throughout (`refs.py`, event format, every verb parsing targets).
2. Ledger location configured separately from the code repository.
3. Append-only response records, separate from events.
4. The org registry, and `check` rules for unregistered targets and unanswered outgoing events.
5. Area-targeted events claimed by the first ack, and the delivery roll-up.
6. Repository-qualified area paths and plan file lists (tdd-cli `cycles[].files` too).
7. Friction proposals written from a code repository's post-merge CI into the team's ledger.
