# 03 — Scope reduction: leave work ordering to a dispatcher

> Exploratory. See the [index](README.md).

## `next` is not about the ledger

`next_issues` (`src/perturb/queue.py`) filters issues that are ready and not planned, sorts by how
many open issues each unblocks, then by number. Its inputs are GitHub state, labels, blocked-by
links and sub-issue parents, plus plan files' `closes:`. Events play no part.

In an enterprise setup, deciding what to plan or implement next belongs to a dispatcher (an
orchestrator, GitHub Projects, a person), which also owns claims. perturb would drop `next`,
`ready` and `graph`, and become purely a ledger with gates.

## What that removes

Dropping the three verbs alone removes about 270 of ~4,950 lines (`queue.py`, `graph_export.py`,
their CLI handlers, the unblocks count). The larger saving is what `next` forces: a mirror of the
whole issue graph, incremental sync, the `.perturb/` cache and graph rederivation, run before
every verb. Without `next`, each remaining use of GitHub can be reconsidered:

| Use | Where | Fate |
|---|---|---|
| planned needs the ready-to-implement label | `graph.py`, used by `stale` and `check` | drop: a plan on `main` is approved ([01](01-review-model.md)) |
| `unblock` events written by sync | `sync.py` | drop: blocker state is work ordering, the dispatcher's concern |
| `show` prints state, labels, blockers | `show.py` | keep the plan and ledger part only |
| epics: `push` refuses them, `propose` fans out to children | `push.py`, `propose.py` | drop the concept, or let the dispatcher expand |
| target must exist and be open | `push.py`, `propose.py`, `check.py` | keep, as a targeted batch lookup in `push` and `check`; optional offline |
| area membership from `area:x` labels | `propose.py` | open: see area-targeted events in [04](04-multi-repo.md) and [06](06-open-questions.md) |

End state: perturb's only GitHub dependency is "does this issue exist, and is it open?" (plus issue
state for delivery roll-ups, [04](04-multi-repo.md)). `sync.py`, the cache, graph rederivation and
fail-closed sync before every verb go. `inbox`, `ack`, `stale`, `propose`, `confirm` and `dismiss`
become pure ledger operations.

## What the dispatcher needs from perturb

Re-planning is the queue that parallel work creates: a halted run is waiting on a planned issue
with pending events. The dispatcher should rank those first. perturb exposes it as one query,
issues with pending events or stale acknowledgements (`perturb stale --json` across all issues, or
`perturb inbox --json` without an issue).

## What is given up

- `next` was roadmap step 1, the value delivered before the ledger existed; the README pitch
  changes to "a ledger and its gates".
- The skill's "what's next?" questions hand off to the dispatcher.
- A breaking change for users of `next`, cheap before 1.0.
