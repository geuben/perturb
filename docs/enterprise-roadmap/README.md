# Enterprise roadmap

> **Status: exploratory.** Nothing here is decided or scheduled. These notes record a design
> discussion (2026-10-08) about what perturb would need to become to serve many operators and
> many implementing agents working in parallel, across many repositories owned by different
> teams. Where a note says "would", read it as a proposal. The design as built is in
> [`docs/design/`](../design/README.md).

## The scenario

An enterprise programme: several teams, each owning several repositories (often microservices),
each running planning and implementing agents in parallel. A decision made by one team, or by an
agent mid-plan, can affect work another agent is implementing right now, in another repository,
owned by another team.

perturb as built assumes one repository, roughly one person at a time, and a ledger read from the
working copy. [Working in a team](../teams.md) lists the resulting pitfalls and asks for habits to
cover them. At enterprise scale the habits have to become guarantees.

## Direction in one paragraph

Review shifts left: planning output, including the decisions that become events, is what gets
reviewed, and a decision is binding when its planning PR merges. Implementing agents re-check the
ledger at every cycle boundary and halt on any pending event, and re-planning does the triage.
perturb drops work ordering (`next`, `ready`, `graph`) to a dispatcher and keeps only a thin
GitHub dependency. Ledgers are federated by team: each team has a planning repository holding its
issues, plans and ledger, and code repositories hold code. Events are still authored and reviewed
as files in planning PRs, but finalised into a shared ledger service by a merge-queue job, so the
service is current the moment a merge completes.

## Notes

| Note | Contents |
|---|---|
| [01-review-model.md](01-review-model.md) | review shifts left; which pull requests may carry which events |
| [02-in-flight-changes.md](02-in-flight-changes.md) | how a running implementer learns of a new decision, halts and resumes |
| [03-scope-reduction.md](03-scope-reduction.md) | dropping `next`, `ready` and `graph`, and most of the GitHub sync |
| [04-multi-repo.md](04-multi-repo.md) | team-owned federation, planning repositories, delivering one decision to many services |
| [05-ledger-service.md](05-ledger-service.md) | an external ledger finalised by the merge queue, with git as the review and audit record |
| [06-open-questions.md](06-open-questions.md) | what is still undecided |

## Decisions in docs/design this would revisit

| [Decision](../design/06-open-decisions.md) | Today | Enterprise direction |
|---|---|---|
| 3. Event storage | one YAML file per event, the store | YAML files stay as the reviewed form; a service holds queryable state ([05](05-ledger-service.md)) |
| 7. Who confirms proposals | a human or the planning agent | unchanged, but cross-team events always arrive as proposals to the target team ([04](04-multi-repo.md)) |
| 8. `ready`/`next` in this tool | yes | delegated to a dispatcher ([03](03-scope-reduction.md)) |
| 9. Sync before every verb | full issue-graph sync, fail closed | targeted lookups only; no cache ([03](03-scope-reduction.md)) |
| 11. Multi-repo | per repository only | federated per team, with a registry ([04](04-multi-repo.md)) |

The non-goals in [01-problem.md](../design/01-problem.md) would also change: "cross-repo graphs"
becomes a goal, and "replacing the executor" is reinforced, since work ordering leaves too.
