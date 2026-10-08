# 05 — A ledger service, finalised by the merge queue

> Exploratory. See the [index](README.md).

Federation over git works, but makes git act like a database: a registry, N fetches per
checkpoint, responses scattered across teams' repositories, roll-ups joining several ledgers with
GitHub state. A shared ledger service does those natively. The question is what git still buys.

## What git buys

1. **Reviewed with the plan.** Events and acks are in the reviewed diff, and become final in the
   same commit as the plan. Reverting the PR reverts the decision.
2. **No visibility window.** A merged decision is visible on the next fetch.
3. **No infrastructure,** offline reads, repository permissions, free history.

## Finalising in the merge queue

Events are still authored as YAML files in the planning PR, because reviewers must see them. A
**merge-queue job** writes them to the service before the merge completes, so if the merge
completes, the service already has them. That removes the window in (2).

The converse needs care: a PR can leave the queue after its job ran (a later check fails, a group
ahead of it fails and the queue rebuilds, someone removes it). So the job writes events as
**staged**, keyed by the merge-group commit SHA. GitHub's merge queue fast-forwards `main` to the
exact commit it tested, so:

> an event is final ⇔ its merge-group SHA is reachable from `main`

- readers or the service check ancestry; correctness depends on git, not on a later job;
- a post-merge webhook can flip staged to final as an optimisation;
- a sweeper drops staged entries whose SHA never landed;
- retried groups restage the same event ids under new SHAs, harmlessly;
- a revert PR passes through the same job, which sees event files deleted and writes withdrawals.

## Two kinds of write

| Write | Reviewed? | Path |
|---|---|---|
| events and acks | yes, in planning PRs | files in the PR → merge-queue job → service |
| confirm, dismiss | no, triage | service API directly |
| friction and audit proposals | no, inert until confirmed | service API, from code repositories' CI |

Unreviewed writes never touch git, so friction proposals stop cluttering planning repository
history, and there is still only one store holding each piece of status.

## What git still does

The review surface (event files in planning PRs) and the audit log (those files on `main`). The
service holds the queryable state: all teams' events and responses, roll-ups, notifications to
proposal owners, webhook-fed issue state for delivery tracking, and the registry.

## Query interface

The read side (`inbox`, `stale`, delivery roll-up, cross-team views) sits behind one interface
with two implementations:

- **git reader:** fetch the registered ledgers and compute. Zero infrastructure; the mode for a
  single team, and a fallback when the service is down;
- **service client.**

This is where an adapter earns its keep: organisations choose the read backend; data model and
review flow stay the same.

## Costs

- Someone runs the service. Under team ownership it is shared infrastructure, needing a platform
  owner.
- If the service is down, planning PRs cannot merge (the queue job fails). Readers either fail
  closed, stalling every agent's gates, or fall back to the git reader.
- Permissions are duplicated: who may confirm or ack for team B must be enforced by the service.
- perturb becomes a CLI plus a service, which changes how it is distributed and adopted.

## Alternatives considered

| Option | Why not |
|---|---|
| ledger stays in working copies (today) | each checkout sees only itself; unmerged and newly merged decisions are invisible to running agents |
| a dedicated ledger branch, events pushed on creation | loses review in the planning PR; needs explicit provisional status |
| read events from every branch on the remote | read cost grows with branches; conflicting acks across branches; moot once review shifted left |
| GitHub issue comments as the store | fragile structured state, no compare-and-set, rate limits; fine as a notification mirror |
| an external service finalised post-merge | not atomic: a merged plan without its events if the job fails; a window where gates miss a merged decision |
