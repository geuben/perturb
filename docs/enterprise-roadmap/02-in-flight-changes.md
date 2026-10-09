# 02 — Changes that arrive mid-implementation

> Exploratory. See the [index](README.md).

Agent A is implementing issue #1. Someone, an agent or a person, merges a decision that affects
#1. How does A find out, and what does it do?

Today: nothing between the start gate and the PR. [implementing.md](../implementing.md) says
perturb has no part to play while implementing. The decision is caught only when a paused run
resumes, or by `perturb check` in CI after all the work is done.

## Pull at checkpoints, not push

A's harness does not need a subscription to #1. A checks at its own checkpoints:

- an agent cannot usefully be interrupted mid-step; a notification would wait for a checkpoint
  anyway;
- polling works in any harness (Claude Code, CI, a person at a terminal); push needs delivery
  infrastructure in each one;
- a lost notification fails silently, a failed check fails closed.

The checkpoint is the cycle boundary. tdd-cli already has the pieces: `tdd advance` is the step
between cycles, `tdd blocker` pauses a run, `tdd resume --unblock` restarts it.

```
tdd run start ──▶ cycle ──▶ checkpoint: perturb stale 1 ──▶ next cycle …
                              │
                              ├─ nothing pending ──▶ continue
                              └─ pending event ────▶ tdd blocker --kind perturbed
                                                     comment on #1 listing the events
                                                     keep the branch
```

The check must read the authoritative ledger (the planning repository's `origin/main`, or the
ledger service in [05](05-ledger-service.md)), not A's working copy, which was cut from an old
`main`.

## Halt on any pending event

Under the [review model](01-review-model.md), a pending event on #1 is a reviewed, merged decision
saying #1's plan must absorb something. Proposals do not count until confirmed. So the rule is
simple: **any pending event halts an in-flight run at its next checkpoint.**

Re-planning is the triage:

- the event does not change the plan → the planner acks it with a note and no plan edit; A passes
  the gate and resumes. The cost is one short planning step;
- the event changes the plan → the planner amends it as a delta against the work done ("cycles
  1–3 stand, redo 4, add 4b"), acks against the new version, and A resumes from the amended plan.
  If the delta undoes too much, the planner abandons the run and re-plans from scratch.

A never re-plans itself. It lacks the planning context and its plan edits would be unreviewed.

## The stale gate changes

`stale` drops the time comparison (event `at` versus plan commit time). It fails when any event for
the issue is pending, or when an acknowledgement pins a plan version that has since changed. Time
comparison is what lets late-merging branches and clock skew slip past today. `stale` also runs in
the merge queue, against what `main` will be after the merge, as the backstop: checkpoints save
wasted work, the merge gate guarantees nothing slips through.

## Findings in the other direction

If A discovers mid-run something that affects issue #2, which B is implementing, the friction log
(read after the run) is too late for B. A should be able to record a *proposed* event mid-run,
routed to #2's planner. If they confirm it, B halts at its next checkpoint. Implementers still never
confirm their own findings.

## Considered and dropped

| Idea | Why dropped |
|---|---|
| An `impact: halt \| advisory` field set by whoever records the event | the decision-maker knows what changed, not what #1's plan assumes or how far A has got, and often did not choose #1 at all (area routing, proposals) |
| A separate triage agent deciding halt or continue, with a path-overlap heuristic against remaining cycles | unnecessary once halting is cheap; re-planning already does the triage |
| An in-flight warning on planning PRs ("#1 is in flight, cycle 4/7, halt it?") | only buys timing; draft PRs and the halted run's issue comment already surface it; would need an in-flight data source |
| Claims and leases in perturb, behind an adapter | implementation runs are started by a dispatcher, which owns exclusivity; duplicate planning is caught by the duplicate-`closes:` check. Claims belong to whatever dispatches work |
