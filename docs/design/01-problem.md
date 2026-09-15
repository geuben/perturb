# 01 — Problem

## What exists today

The pipeline for one unit of work, as it runs today:

```
GitHub issue ──plan-issue──▶ tasks/<slug>.md ──implement-issue──▶ tdd-cli run ──▶ PR
     ▲                            (closes: N)                          │
     │ epic / sub-issue                                                ▼
     │ blocked-by / blocking                              tasks/friction-logs/<slug>-friction.md
     │                                                                 │ audit-friction-log
docs/adr/NNNN-*.md                                                     ▼
  (no front-matter; body                                  tasks/friction-audits/<slug>-audit.md
   mentions #NNN in prose)                                  (CRITICAL / PLANNING DEBT / MINOR)
```

What each artefact already carries, and therefore what the new layer can rely on:

| Artefact | Machine-readable linkage today | Where it lives |
|---|---|---|
| Issue | sub-issue parent, `blockedBy`, `blocking`, labels (`epic`, `ready-to-implement`), `Task file:` line in body | GitHub |
| Plan | `closes: N` front-matter, cycle `files` lists, "Design decisions (locked)", "Deliberate scope cuts" | repo, `tasks/` |
| Friction log | plan path in title, plan blob hash, per-cycle commits and files, `tdd note` narrative | repo, `tasks/friction-logs/` |
| Friction audit | remediation items with level | repo, `tasks/friction-audits/` |
| ADR | none today. Number in filename, status line, `#NNN` mentions in prose. Format change agreed, see [adr-format.md](../adr-format.md) | repo, `docs/adr/` |

## Where it leaks

Three questions have no answer short of reading everything:

1. **What should I plan next?** The answer is one GraphQL query (open issues whose blockers are
   all closed) but nobody runs it, so it is answered from memory.
2. **What has changed since this issue was written?** ADR 0002 names `#13` and `#35` in its
   consequences. Nothing puts that fact in front of the person planning `#13`. Phase A of
   `plan-issue` reads the issue's own comments, which is the right instinct, but the
   consequence was written on the ADR, not on the issue.
3. **Is this ready-to-implement plan still the plan?** `implement-issue` spot-checks two symbols. It cannot
   know that a decision locked while planning `#31` yesterday invalidated a scope cut in the
   already-planned `#29`.

The common cause: decisions are recorded where they are *made* (an ADR, a plan's locked-decisions
section, a friction audit) and never delivered to where they are *needed* (the issue that will be
planned next month). Every artefact is a node; there is no mechanism for a node to leave a message
for another node.

## What the missing layer is

A ledger of **events**: "source node X changed something that may affect target node Y". Each
event is proposed (by a tool reading X), confirmed (by a human or the planning agent), and later
**acknowledged** by whoever plans Y, who records what they did about it. Unacknowledged events are
queryable, which turns "is this plan stale?" into a lookup.

## Non-goals

- Replacing GitHub issues, sub-issues or blocked-by. They work; `#3` uses them correctly.
- Replacing the executor. Implementation runs in whatever tool the team uses (`tdd-cli` in this
  repository); this layer only reads the friction logs it leaves, in the format in
  [run-evidence-format.md](../run-evidence-format.md).
- Automatic propagation without review. The tool proposes targets; a person or planning agent
  confirms. Unreviewed fan-out is noise, and noise gets ignored, which is the current state.
- Cross-repo graphs. One ledger per repository. Revisit if issues in one repository start
  blocking issues in another in practice.
- A UI. `perturb graph` emits Mermaid/DOT; render it wherever.
