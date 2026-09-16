# Planning an issue with perturb

However you plan, whether through an agent skill, a prompt or by hand, perturb fits in at three
points: before planning, read what already binds the issue; while planning, pass on what this plan
decides for other issues; when the plan is done, record that it absorbed its inbox. This guide
describes those points and the reasons behind them, so you can build them into your own planning
step. It doesn't prescribe how you investigate, how you write the plan, or what executes it.

What perturb needs from a plan is small: a committed Markdown file at `paths.plan` (default
`tasks/{slug}.md`) whose front-matter names the issue with `closes:`, and the ready-to-implement
label on that issue. `areas:` and `files:` are optional and improve routing. The full format is in
[Plan, friction log and audit formats](run-evidence-format.md#plan).

## 1. Before planning: read what binds the issue

```sh
perturb show <N> --json
perturb inbox <N> --json --include proposed
```

**Check the issue.** `show` reports whether it is open, whether it is an epic, and whether it is
already `planned` with a `plan` path. If it is already planned, decide deliberately: re-plan that
file, or stop. Two plans closing the same issue leave nobody sure which one was acknowledged.

**Every pending event must land in the plan.** A pending event is something another plan, ADR or
run decided about this issue. Put each one where a reader of the plan will find it (a design
decision, a scope cut) and cite its id. An event you can't place is a question to resolve now,
not one to skip: the implementer will only see what the plan says.

**Decide every proposed event.** A proposal is a tool's guess that something applies to this issue.
The planner is the one best placed to judge it, and nobody else is going to:

```sh
perturb confirm <id>...                        # it changes this plan; it becomes pending
perturb dismiss <id> --note "<why it doesn't apply>"
perturb confirm --source adr:0002 --all        # every proposal from one source
```

A confirmed event is now pending, so the rule above applies to it. Re-run `inbox`; nothing
proposed should remain.

## 2. While planning: pass on decisions that bind other issues

When a decision would change how another open issue is planned (a sibling in the same epic, an
issue this one blocks, an issue in the same area), record it before moving on:

```sh
perturb push --from <N> --to <M> --kind decision "<the decision, in one sentence>" \
  --detail tasks/<slug>.md#design-decisions
```

- **The test** is whether M's planner would choose differently without knowing this. Most
  decisions don't pass it, which keeps inboxes worth reading.
- **Kinds:** `decision` constrains M's design, `scope` moves work into or out of M, `amend` changes a premise of M's constraint while it still stands, and `supersede`
  replaces part of it.
- **`--detail`** points at the text behind the event, which `perturb inbox` quotes. The file and
  heading must exist when you push, or it refuses with `detail_unresolved`.
- **Work with no issue yet:** `perturb push --from <N> --new "<title>" --kind scope "<summary>"`
  creates the issue with a pending event on it.

Two alternatives to `push`:

- **Decisions big enough for an ADR** go through the ADR. Write it in the
  [ADR format](adr-format.md) with `affects:` naming the issues or areas it binds, commit it, and
  run `perturb propose adr:<NNNN> --json`. Issues named in `affects:` get pending events; areas and
  `#N` mentions get proposals, which you are best placed to confirm or dismiss while the context is
  fresh. A consequence that binds the issue you're planning belongs in your plan, not in an event.
- **Decisions already written in the plan** can be proposed from it. Items under the plan's
  `## Design decisions` and `## Deliberate scope cuts` headings that name `#N` become proposals to
  those issues when you run `perturb propose plan:<slug>`, and wait for their planners to decide.

## 3. When the plan is done: commit, label, acknowledge

```sh
git add tasks/<slug>.md && git commit -m "Plan #<N>"
gh issue edit <N> --add-label ready-to-implement
perturb ack <N> --all --plan tasks/<slug>.md --note "<where each event went>"
git add perturb/events && git commit -m "Acknowledge #<N>'s inbox"
perturb stale <N>    # must exit 0
```

- **Commit before acknowledging.** An acknowledgement pins the plan's committed version, so `ack`
  refuses when the plan has uncommitted changes or its `closes:` names another issue.
- **Label before checking.** The issue only counts as planned with the label, and `stale` only
  checks planned issues: on an unplanned one it finds nothing and exits 0.
- **Write a useful note.** Say where each event went, so a reviewer can check the claim.
- **Editing the plan later means acknowledging again.** Any change to the plan's content makes its
  acknowledgements stale.

## Rules worth keeping

- **Plan from an up-to-date main.** Events on unmerged branches are invisible to you; see
  [Working in a team](teams.md).
- **A refusal stops the step.** When perturb can't reach GitHub or a ref doesn't resolve, report
  the `reason` rather than planning from memory.
- **Commit ledger changes with the plan**, so the pull request that introduces a plan also shows
  what it absorbed and what it passed on.

## What stays yours

The plan's structure beyond `closes:`, how you investigate the code, which questions go to a
person, and which tool executes the plan. perturb reads `files:` as the files a plan expects to
change, so the more accurate that list is, the less noise friction
proposals make later.

## Example instructions

A fragment to adapt into a planning prompt or skill:

```markdown
Before planning issue N, run `perturb inbox N --json --include proposed`.
- Confirm or dismiss every proposed event (`perturb confirm <id>`,
  `perturb dismiss <id> --note "..."`). None may remain.
- Every pending event must appear in the plan's design decisions or scope cuts, citing its id.

While planning, when a decision would change how another open issue is planned, run
`perturb push --from N --to M --kind decision "<one sentence>"`.

When the plan is written: commit it, add the ready-to-implement label, run
`perturb ack N --all --plan <path> --note "<where each event went>"`, commit perturb/events,
and confirm `perturb stale N` exits 0. If any perturb command refuses, stop and report its
reason.
```
