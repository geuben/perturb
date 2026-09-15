# Implementing a plan with perturb

The implementing step is often an agent that starts with nothing but the plan. perturb gives it two
jobs: refuse to start when the plan is out of date, and afterwards record what the work touched
that the plan didn't expect. What runs in between, whether an agent, a person or a tool, is up to
you.

## 1. Before starting: gate on the plan

```sh
perturb show <N> --json
perturb stale <N> --json
```

Check these in order and stop at the first that fails:

1. **The issue is open.** A closed issue shipped or was withdrawn.
2. **The issue is planned.** `show` reports `planned: true` and the `plan` path. Check this
   explicitly: `stale` only gates planned issues, so on an unplanned one it finds nothing and
   exits 0.
3. **The plan is committed and unchanged locally** (`git status --porcelain <plan>` prints
   nothing). The version you run should be the version that was acknowledged.
4. **`perturb stale <N>` exits 0.** Exit 1 lists events the plan hasn't absorbed: pending events
   newer than the plan, or acknowledgements made against an older version of it.

perturb catches decision drift, not code drift. A cheap addition is to confirm that a couple of
the files or functions the plan names still exist.

### When the gate fails: stop, report, exit

Don't re-plan, don't edit the plan, and don't start with a note to fix it later. Report what failed
(for example, a comment on the issue listing the stale event ids and saying work didn't start), then
exit.

The implementer runs without the planning context, so its changes to the plan would be neither
reviewed nor acknowledged. Partial work on a stale plan is worth less than a fresh plan that knows
about the new events. Re-planning is a separate planning session that acknowledges the events; the
next implementation run then passes the gate.

**Resuming interrupted work?** Gate again first. Events can arrive while a run is paused.

## 2. While implementing

perturb has no part to play. When the work turns up something that affects another issue, write it
in the friction log rather than pushing an event yourself, so the reviewer sees it first.

## 3. After implementing: friction log and proposals

Write a friction log at `paths.friction_log` (default `tasks/friction-logs/<slug>-friction.md`,
with the plan's slug). The only part perturb reads is the list of commits the work made:

```markdown
---
commits: ["a89ed3b", "57ce145"]
---

## What the plan got wrong
...
```

The rest is for the reviewer, and the more honest it is the more useful the review: the outcome,
where delivery differed from the plan, what was hard, and why any file outside the plan changed.
The format is in [Plan, friction log and audit formats](run-evidence-format.md#friction-log).

Commit the log, then propose from it:

```sh
perturb propose friction:<slug> --json
git add perturb/events && git commit -m "Friction proposals for <slug>"
```

perturb asks git which files those commits touched, drops the files the plan declared, and
proposes `friction` events to open issues in the areas the rest fall in.

- **Leave the proposals alone.** Don't confirm or dismiss them: the implementer is the party the
  review exists to check.
- **A refusal is a failed step.** `friction_log_not_found` means the log isn't where the config
  says; `friction_commits_unreachable` means a listed commit isn't in this checkout. Propose before
  a squash merge deletes the branch's commits. Fix the cause and re-run.
- **Re-running is safe.** An event that already exists is returned, not written again.

## Rules worth keeping

- **Gate immediately before starting**, not when the run was scheduled.
- **Stopping is a result.** A run that refused on a stale plan did its job; say so plainly rather
  than reporting a failure to implement.
- **Propose friction before raising the pull request**, so the events travel with the code.

## What stays yours

What executes the plan, how commits are made, what else the friction log records, and how a failed
gate is reported. Whatever writes the friction log only needs to include the `commits:` list.

## Example instructions

A fragment to adapt into an implementing prompt or skill:

```markdown
Before starting issue N:
- Run `perturb show N --json`. Stop unless the issue is open and `planned` is true.
- Confirm the plan file is committed with no local changes.
- Run `perturb stale N`. If it exits 1, do not start: comment on the issue with the stale
  event ids, say implementation was not started, and exit. Never edit the plan.

After implementing: write the friction log with a `commits:` list, commit it, run
`perturb propose friction:<slug> --json`, and commit perturb/events. Do not confirm or dismiss
the proposals. If any perturb command refuses, fix the cause and re-run before finishing.
```
