# 05 — Integration with the existing skills

The skills stay the drivers. The tool adds a query at the points where each skill currently
relies on memory, and a write at the points where each skill currently produces a decision that
goes nowhere.

The changes were first made to this repository's copies of those skills. The repository no longer
ships them: the user docs describe the same integration points, without prescribing a workflow, in
the [planning](../planning.md), [implementing](../implementing.md) and [reviewing](../reviewing.md)
guides. This note records the original design.

## `plan-issue`

**Phase A (resolve the issue)** — after reading the issue:

```sh
perturb inbox <NNN> --json --include proposed
```

Rule added: every `pending` event must end up in exactly one of the plan's sections, "Design
decisions (locked)" or "Deliberate scope cuts (do not build)", citing the event id. A pending
event with no home is a planning failure of the same class as a PROSE-ONLY behaviour in E-3.
`proposed` events are read but not binding; the planner confirms or dismisses them as part of
Phase A rather than leaving them for someone else.

**Phase C (walk the decision tree)** — when a locked decision constrains another open issue
(sibling under the same epic, an issue this one blocks, an issue sharing an area), the planner
runs `perturb push` for it before moving on. The test for "constrains": would the other issue's
planner make a different choice if they did not know this? Phase C already asks the user about
genuine design choices; the knock-on question is asked in the same breath.

**Phase D (draft)** — a new ADR written during planning uses the structured format, each
consequence carrying `affects:` for the issues the planner already knows about, then
`perturb propose adr:NNNN`.

**Phase E (harden)** — new check, E-19:

```sh
perturb ack <NNN> --all --plan tasks/<slug>.md --note "..."   # after the plan is committed
perturb stale <NNN>                                            # must be empty
```

The readiness report gains a line: events acknowledged, events dismissed, events pushed.

## `implement-issue`

**Section 1, gate 6**: `perturb stale <NNN>` must be empty. Non-empty → **stop**. Print the
stale events, leave a comment on the issue naming them and stating that implementation was not
started, and exit without opening a worktree or a run. `implement-issue` runs autonomously in a
session with nobody watching and no planning context; it never re-plans, never edits the plan,
and never invokes `plan-issue`. Re-planning is a separate, human-initiated session that acks the
events and re-hardens the plan; the next dispatch of `implement-issue` then passes the gate.
The existing symbol spot-check stays and gets the same stop semantics; it catches code drift,
this catches decision drift.

If a run is already active in an existing worktree (the resume clause in section 2), the gate is
still checked first. Stale with a run in flight → stop before resuming; the committed cycles are
kept and the ledger is untouched. Partial progress on a stale plan is worth less than a clean
re-plan that knows about it.

**Section 4, after the friction log is rendered and committed**:

```sh
perturb propose friction:<slug>
```

Written as proposals only. The implementing agent is the wrong party to confirm them (it is the
party the audit skill is designed to cross-check), so they wait for `audit-friction-log`.

## `audit-friction-log`

**New step 6**: after the audit file is written,

```sh
perturb propose audit:<slug> --review
```

The auditor confirms or dismisses the friction proposals from the run and the audit's own
CRITICAL items. A CRITICAL item with no target issue is offered during `--review` as `accept (create issue) /
skip`. Accepting opens a GitHub issue and records a `pending` event on it, so architectural debt
gets an issue in the graph rather than a checkbox in a report nobody reopens. A skipped item is
offered again on the next run.
PLANNING DEBT items target the skill, not an issue; they are recorded as events on
`area:planning` if that area is declared, otherwise dismissed with a note.

## `tdd-cli`

No changes. `tdd log render` already writes friction logs in the format in
[run-evidence-format.md](../run-evidence-format.md), and tdd-cli plans declare their files
through `cycles`. Other executors write the same files; a front-matter `commits:` list is the
simplest way to do it.

## Hooks

One advisory hook, **not built yet**:

- **PostToolUse on Write/Edit** matching `docs/adr/*.md`: print "new or changed ADR; run
  `perturb propose adr:NNNN` before committing". Advisory because the propose step needs a human.
  Until it exists, `perturb check` catches an unpropagated accepted ADR in CI.

## CI

`perturb check` as a job on PRs and pushes to `main`
(`.github/workflows/perturb-check.yml`). Every finding fails the job; there is no warning tier,
so an unpropagated ADR or a pending event on a closed issue blocks the merge until it is fixed.

The GraphQL sync needs a token. On the runner `perturb` calls `gh` (leave `PERTURB_GH` unset), which
reads the workflow's `GH_TOKEN` (`contents: read`, `issues: read`). The checkout uses `fetch-depth: 0` because stale detection reads each plan's
last commit time from `git log`.

## Claude Code skill surface

A thin `perturb` skill so the verbs are discoverable by name ("what's next", "what changed for
31", "is 29 still valid"). It contains no logic: each phrase maps to one verb and the JSON is
rendered. The planning and implementing skills call the CLI directly, never the skill.
