# Working in a team

perturb's files are designed to merge cleanly, and its checks run on every pull request. Some of
its behaviour still assumes one person working in order, though, and that shows once plans and
events move on separate branches. This guide covers what to expect and the habits that help.

## What works well

- **Files rarely conflict.** Each event is its own file named by a unique ID, so two branches adding
  events never collide. The one conflict you can hit is two people acknowledging the same event on
  two branches, which is a real disagreement worth seeing.
- **Decisions are reviewed like code.** Events arrive in the pull request that caused them, and CI
  runs `perturb check` on it.
- **Conventions are shared, tooling is personal.** `perturb/areas.yaml` and `perturb/config.yaml`
  are committed, so everyone routes findings and reads labels the same way. The `.perturb/` cache
  belongs to each clone, and each person chooses their own GitHub CLI with `PERTURB_GH`.
- **There is a record of who did what.** Acknowledgements and dismissals store the name from
  `git config user.name` (`perturb ack --by` overrides it).

## Pitfalls

### Events on branches can slip past the stale gate

`perturb stale` compares when an event was *created* with when the plan was last *committed*. Take
three days:

1. On Monday, Alice records an event for #32 on her branch.
2. On Tuesday, Bob plans #32 on his branch, without seeing it, and acknowledges his inbox.
3. On Wednesday, Alice's branch merges.

Alice's event is older than Bob's plan, so `perturb stale 32` passes. The event is still pending in
#32's inbox, but nothing fails. Differences between people's clocks can cause the same thing.

### Each checkout sees only itself

`inbox`, `stale` and `check` read the ledger in your working copy. Events on branches that haven't
merged are invisible to you, and to CI on any other pull request.

### The same event can be recorded twice

perturb avoids duplicates by comparing against the events already in your checkout. When two
people run `perturb propose adr:0002` on different branches, or both sync after a blocker closes,
the same event is created twice with different IDs, and after merging the inbox shows it twice.
`perturb check` doesn't catch this.

### Syncing can write events into any branch

Every verb that reads the issue graph syncs first, and a sync that sees a blocker close writes an
`unblock` event into your working copy. Someone who only ran `perturb next` can find ledger files
in an unrelated pull request.

### Proposals have no owner

A proposed event waits until someone confirms or dismisses it. Nothing assigns that job, so without
an agreement proposals pile up unreviewed.

### Plan edits mean acknowledging again

An acknowledgement pins one version of the plan. When several people edit a plan, each change makes
its acknowledgements stale, and the repeated `perturb ack` runs edit the same event files, which can
conflict.

## Habits that help

- **Keep branches short** and merge ledger changes quickly.
- **Check an up-to-date `main` before implementing.** Pull, then run `perturb stale <N>` and
  `perturb inbox <N>`. Treat any pending event in the inbox as blocking, not only what `stale`
  reports.
- **Give proposals an owner:** the planner of the target issue, or a rotating reviewer.
- **Commit `unblock` events from `main` only.** Discard stray ones that appear on feature branches.
- **Dismiss duplicates** when they show up, with a note pointing at the original.
- **Call out ledger changes** in pull request descriptions, so reviewers read them.
- **Review changes to `areas.yaml` and `config.yaml`** like any shared configuration: they change
  where everyone's findings go.
