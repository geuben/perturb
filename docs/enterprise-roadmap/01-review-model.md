# 01 — Review shifts left

> Exploratory. See the [index](README.md).

## The model

Planning output gets the most review. That output includes the decisions that become perturb
events. Implementation output gets much less review, on the assumption that it faithfully executes
a reviewed plan; the friction log and declared-files check are the evidence of faithfulness. Once
an implementation PR merges, its fallout (friction and audit findings) is feedback into *future*
planning, not an urgent signal.

Consequences:

- **A decision is binding when its planning PR merges.** Before that it is a draft, and nothing
  should react to it. This is what lets `main` of the planning repository serve as the
  authoritative ledger.
- **A plan merged to `main` is approved.** The ready-to-implement label becomes redundant:
  "planned" can mean "a plan on `main` closes this issue".
- **Triage of a new event happens at planning time,** by the target's planner, who has the plan
  context. See [02](02-in-flight-changes.md).

## Which pull requests may carry which events

| Event source | Arrives via | Status when merged | Consumed by |
|---|---|---|---|
| planning decisions (`decision`, `scope`, `supersede`, `amend`) | planning PR, heavily reviewed | pending | target planners; in-flight runs at their next checkpoint |
| ADR consequences | ADR PR, reviewed | pending or proposed, as today | same |
| implementation fallout (`friction`, audit) | implementation PR or post-merge job, lightly reviewed | proposed | target planners confirm or dismiss |

`perturb check` could enforce this from the PR's diff:

- a PR that adds a pending `decision`, `scope`, `supersede` or `amend` event must also change a
  plan or an ADR;
- an implementation PR may add only proposed events, and may not change a plan (already the rule in
  [implementing.md](../implementing.md));
- two plans may not `closes:` the same issue (today only a warning, in `load_plans`).

## Planning PRs should be small and merge on approval

The review latency of a planning PR is how long in-flight implementers keep building on the old
decision. That is correct, since an unreviewed decision should not stop anyone, but slow planning
reviews cost rework. Genuinely urgent decisions (cancel this issue) are fast-tracked through
review, not routed around it.
