# 06 — Decisions

All resolved 2026-09-12. Kept as a record of the alternatives considered.

| # | Decision | Default in this draft | Alternative | Why the default |
|---|---|---|---|---|
| 1 | Name | **decided**: `perturb` | | |
| 2 | Language | **decided**: Python, `uv`, same layout as `tdd-cli` | | one toolchain for both agent-facing CLIs |
| 3 | Event storage | **decided**: one YAML file per event under `perturb/events/` | JSONL; GitHub issue comments; SQLite | merge-safe, reviewable in PRs, no sync. Comments were tempting because `plan-issue` already reads them; rejected because acks and dismissals would need structured comments too, and GitHub becomes a second store |
| 4 | Mirror to GitHub | **decided**: none in v1 | `perturb sync --comment` posting a one-line "1 pending event, see perturb/events/…" comment per issue | keep one store until the ledger proves useful; the mirror is additive later |
| 5 | Areas in v1 | **decided**: yes, declared in `areas.yaml` | | friction → issue has no other path |
| 6 | ADR format | **decided**: structured ADRs, consequence is the unit of propagation, see [adr-format.md](../adr-format.md) | optional front-matter only; mentions only | user agreed to change the format; per-consequence targets give the planner the exact bullet, not the whole ADR |
| 7 | Who confirms proposals | **decided**: a human, or the planning agent inside `plan-issue` Phase A. Only `affects` and `supersedes` are born pending | auto-confirm above a confidence threshold | see non-goals. Revisit once dismissal rate is known |
| 8 | Where `ready`/`next` lives | **decided**: in this tool, roadmap step 1 | a 40-line script now, tool later | the query is trivial; shipping it first (roadmap step 1) gets value before the ledger exists, and keeps one binary |
| 9 | Cache staleness | **decided**: always sync before every verb; GitHub unreachable → fail with reason `github_unreachable`, never answer from the cache | 1-hour warn; fall back to cache on outage | never answer from stale data; the skills' gates fail closed. The cache becomes an incremental-sync optimisation, not a fallback |
| 10 | Epic scoping | **decided**: `--epic N` filter; no epic-level events. `propose` expands an epic ref to its open children | events on epics fan out to children | an epic is an aggregate; decisions target concrete work |
| 11 | Multi-repo | **decided**: per repository only | a `repos:` list in a home-dir config | see non-goals |
| 12 | Interactive review | **decided**: both. `--review` in the terminal; skills use `--json` and `confirm`/`dismiss` | review only through the skill | a human runs `propose adr:` after writing an ADR by hand, outside any skill |
| 13 | Consequence syntax inside the ADR | **decided**: fenced YAML block under `## Consequences` | | parses and validates with no custom grammar |
