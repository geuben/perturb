# Configuration and repository files

## Principle

Anything a person decides is committed to the repository, next to the artefact that caused it,
in the same PR. Anything derived from GitHub is a cache and is gitignored. There is exactly one
writable store, so there is nothing to sync.

## Committed: `perturb/`

```
perturb/
  areas.yaml                 # area declarations
  config.yaml                # where plans, friction logs and audits live; labels. All optional
  events/
    01J9Q7K2M4X8.yaml        # one file per event, named by ULID
    01J9QB0P3N1R.yaml
  README.md                  # explains the directory
```

**One file per event, not one JSONL.** Two branches appending to the same JSONL always conflict
at the tail. Two branches each adding a distinct file never conflict. Acknowledging an event edits
its file in place; a conflict there means two people acknowledged the same event on two branches,
which is a real conflict worth seeing.

**YAML, not JSON.** Events are read in PR review far more often than by machines. The `summary`
and `note` fields are prose.

## Areas: `perturb/areas.yaml`

An area is a named part of the codebase. An issue is in an area when it carries the area's label
(`area:<slug>`, or the area's `issues_label`) or its plan lists the area under `areas:`. Paths are
globs with `.gitignore` rules. See [concepts](concepts.md#areas) for what areas route.

```yaml
areas:
  rides:
    paths: ["src/core/rides/**", "migrations/*ride*"]
    issues_label: "area:rides"       # optional; default is area:<slug>
  fares:
    paths: ["src/core/fares/**"]
  ingestion:
    paths: ["src/ingest/**", "docs/04-ingestion.md"]
```

## Config: `perturb/config.yaml`

Repository conventions. Every key is optional and the values below are the defaults; `perturb init`
writes this file with every line commented out.

```yaml
paths:
  plan: tasks/{slug}.md
  friction_log: tasks/friction-logs/{slug}-friction.md
  audit: tasks/friction-audits/{slug}-audit.md
labels:
  ready_to_implement: ready-to-implement   # with a plan, marks an issue planned; gates `stale`
  epic: epic                               # epics are never ready and never event targets
```

- Each path is relative to the repository root and contains `{slug}` exactly once, with no other
  braces or glob characters. The slug names the plan (`plan:<slug>`) and ties it to its friction log
  (`friction:<slug>`) and audit (`audit:<slug>`); the plan-path ref form follows `paths.plan`.
- Labels are non-empty strings, matched exactly against GitHub label names.
- An invalid file is never silently ignored: every verb that reads it refuses with `config_invalid`
  before any GitHub call. The derived graph is rebuilt when the config changes.
- The GitHub CLI is personal rather than a repository convention, so it is chosen by the
  `PERTURB_GH` environment variable instead (see [cli.md](cli.md#perturb-sync---full)).

What `perturb` reads from plans, friction logs and audits is specified in
[run-evidence-format.md](run-evidence-format.md).

## Plans and ADRs

All optional. The tool degrades to lower-confidence proposals when they are absent.

ADR: the structured format in [adr-format.md](adr-format.md). `affects`, `areas` and
`supersedes` per ADR, `id`/`text`/`affects` per consequence.

Plan (`closes:` is required):

```yaml
areas: [fares]               # optional; otherwise derived from declared files vs area globs
files: [src/core/fares/pricing.py]   # optional; the files the plan expects to change
```

Friction logs and audits: see [run-evidence-format.md](run-evidence-format.md) for exactly what
is read; any tool can write them.

## Cached: `.perturb/` (gitignored)

Verbs that read the issue graph first sync issues from GitHub into `.perturb/`, a cache per clone
that is never committed. The sync is incremental, and when GitHub is unreachable the verb refuses
with `github_unreachable` rather than answer from the cache. Deleting `.perturb/` is safe: the next
verb rebuilds it, though that first sync records no `unblock` events for blockers that closed in
the meantime. How the sync works is described in [design/sync-and-cache.md](design/sync-and-cache.md).

## What is deliberately not stored

- Issue bodies beyond the head. The `Task file:` line is in the first few lines by convention.
- Any copy of plan, ADR or friction content inside an event. `detail` is a path plus anchor. The
  repo already holds the text; copying it invites drift.
- Ack history. One ack per event. Revising a plan makes the ack stale (blob mismatch) and the
  planner acks again, overwriting. The old ack is in git history if it is ever needed.
