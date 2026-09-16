# Plan, friction log and audit formats

What `perturb` reads from the artefacts left by planning and implementing an issue. None of them
has to come from a particular tool: anything that writes these files will do. The
[planning](planning.md), [implementing](implementing.md) and [reviewing](reviewing.md) guides show
where each is written. Where each file lives, and which labels matter, is
set in `perturb/config.yaml` ([configuration.md](configuration.md#config-perturbconfigyaml)).

## Plan

**Location:** `paths.plan`, default `tasks/{slug}.md`. The slug is the plan's identity
(`plan:<slug>`) and ties it to its friction log and audit.

**Front-matter** (YAML between `---` lines):

| Key | Required | Used for |
|---|---|---|
| `closes` | yes | the issue number (an integer) this plan implements; joins issue and plan |
| `areas` | no | area slugs from `perturb/areas.yaml`; routes findings to this issue |
| `files` | no | repository paths the plan expects to change |

The plan's **declared files** are its `files` list. A plan that declares none makes every file its
run touched count as outside the plan.

> Optional: if you use tdd-cli, the file lists in its plan contract count as declared files too — as
> do the test ids in `cycles[].test`, `cycles[].tests` and `cycles[].modifies_tests`, resolved to
> paths via `tdd plan paths` (requires tdd-cli >= 0.11.0) — so `files` isn't needed. See
> [Using perturb with tdd-cli](tdd-cli.md#plans).

**Body sections** read by `perturb propose plan:<slug>`:

- `## Design decisions…`: each list item that names `#N` proposes a `decision` event to issue N;
- `## Deliberate scope cuts…`: the same with kind `scope`.

Links to issues in other repositories (`[#13](https://…)`) are ignored.

An issue is **planned** when a plan closes it and the issue carries the ready-to-implement label
(`labels.ready_to_implement`, default `ready-to-implement`). Planned issues are what `perturb stale`
gates and what `perturb next` skips.

## Friction log

The side output of implementing a plan: where the plan fell short, what the run touched that the
plan never mentioned, and what the implementer struggled with.

**Location:** `paths.friction_log`, default `tasks/friction-logs/{slug}-friction.md`, with the same
slug as the plan.

**Required: the commits the run made**, as a front-matter list:

```markdown
---
commits:
  - "a89ed3b7b"
  - "57ce145d9"
---
```

Each SHA is 7 to 40 lowercase hex characters; quote them in YAML so a SHA made only of digits stays
a string. Every commit must be reachable from the checkout, or `propose friction:` refuses with
`friction_commits_unreachable`.

> Optional: if you use tdd-cli, the friction log `tdd log render` writes lists its commits in a form
> perturb also reads, so it needs no `commits:` list. See
> [Using perturb with tdd-cli](tdd-cli.md#friction-logs).

`perturb propose friction:<slug>` asks git which files those commits touched, removes the plan's
declared files, and proposes `friction` events to the open issues in the areas the remaining files
fall in.

**Recommended but not read by `perturb`**, because audits need them: the outcome (complete or
blocked), how delivery compared with the plan (skipped or unreached steps, human interventions),
and the implementer's own account of what was hard.

## Audit

A review of a friction log that decides which findings matter.

**Location:** `paths.audit`, default `tasks/friction-audits/{slug}-audit.md`.

`perturb propose audit:<slug>` reads checkbox items that carry a level:

```markdown
- [ ] **[CRITICAL]** `src/core/fares/pricing.py` mixes pence and pounds; see #31
- [ ] **[PLANNING DEBT]** the plan never named the refund backfill
```

- The level is `CRITICAL` or `PLANNING DEBT` in bold square brackets, optionally followed by a
  colon. Lines indented under an item continue it; a blank line or a new list item ends it.
- A `CRITICAL` item routes to the open issues in the areas of the backticked paths it names (falling
  back to the plan's `areas`, then its declared files) and to any `#N` it mentions. An item with no
  target is offered as a new issue under `perturb propose audit:<slug> --review`.
- A `PLANNING DEBT` item is proposed to `area:planning` when that area is declared, and dismissed
  with a note otherwise.
- Everything else in the file is ignored.

## Producers

Anything can write these files; audits are always written by your review step. The smallest valid friction log is front-matter with a
  `commits:` list.
