# Getting started

This guide takes a repository from nothing to the whole loop: see what is ready, record a decision,
plan an issue against its inbox, gate before implementing, and feed back what implementation found.
The examples use the bike-share app from the [README](../README.md).

## Before you start

- A GitHub repository whose `origin` remote is on GitHub.
- Issues organised with sub-issues and blocked-by links, if you want `perturb next` to be useful.
  Epics carry the `epic` label.
- Python 3.11+, [`uv`](https://docs.astral.sh/uv/) or [`pipx`](https://pipx.pypa.io/), and
  [`gh`](https://cli.github.com/) logged in with
  access to the repository (or `GH_TOKEN` set). If you use a wrapper around `gh`, set `PERTURB_GH`
  to its name.

## Install and set up a repository

```sh
uv tool install perturb      # or: pipx install perturb
cd your-repo
perturb init
```

`perturb init` creates a `perturb/` directory: an empty `areas.yaml`, a `config.yaml` with every
setting commented out at its default, a `README.md`, and an `events/` directory. It also adds
`.perturb/`, a local cache of your issues, to `.gitignore`. It never overwrites a file that
already exists.

Create the label that marks a plan as ready to implement, unless you already use one; to use your
own, set `labels.ready_to_implement` in `perturb/config.yaml`.

```sh
gh label create ready-to-implement --description "Plan committed and ready to implement"
```

Then commit the setup:

```sh
git add perturb .gitignore && git commit -m "Set up perturb"
```

## Declare your areas

Areas let findings about code reach the issues that touch it. Edit `perturb/areas.yaml`:

```yaml
areas:
  fares:
    paths: ["src/core/fares/**", "migrations/*fare*"]
  refunds:
    paths: ["src/core/refunds/**"]
```

An issue is in an area when it carries the `area:fares` label or its plan lists `areas: [fares]`.
You can start with no areas and add them once friction starts reaching nobody.

## See what's ready

```sh
perturb next              # ready, unplanned issues, the ones that unblock the most first
perturb ready --all       # every ready issue, plus blocked ones and what blocks them
perturb show 32           # one issue: state, labels, epic, plan, blockers
perturb graph --epic 3    # an epic as a Mermaid diagram
```

These verbs sync issues from GitHub first. If GitHub cannot be reached they refuse rather than
answer from old data.

## Record a decision that affects another issue

You are planning #31 and decide that fare periods are half-open. #32 depends on fare periods:

```sh
perturb push --from 31 --to 32 --kind decision "Fare periods are half-open"
```

This writes a `pending` event to `perturb/events/`. Commit it with the work that made the decision.
The target must be an open issue that isn't an epic. The kinds are `decision`, `scope`, `friction`
and `supersede`.

## Plan an issue against its inbox

Before planning #32, read what has changed for it:

```sh
perturb inbox 32
```

A plan is a Markdown file, `tasks/<slug>.md` by default, naming the issue it implements in its
front-matter. Fold each event into the plan and say where it went:

```markdown
---
closes: 32
areas: [refunds]
files: [src/core/refunds/backfill.py]
---

# Backfill refunds

## Design decisions (locked)

1. Refund periods reuse fare periods, which are half-open (event 01J9Q7K2M4X8).
```

Commit the plan, add the `ready-to-implement` label to #32, then acknowledge the events:

```sh
git add tasks/backfill-refunds.md && git commit -m "Plan #32"
perturb ack 32 --all --plan tasks/backfill-refunds.md --note "Design decision 1"
git add perturb/events && git commit -m "Acknowledge #32's inbox"
```

`ack` refuses if the plan has uncommitted changes or its `closes:` names a different issue: an
acknowledgement records exactly which version of the plan absorbed the events.

## Gate before implementing

```sh
perturb stale 32
```

Exit 0 means the plan has seen everything. Exit 1 lists what it missed: a pending event newer than
the plan's last commit, or an acknowledged event whose plan has changed since. Update the plan,
acknowledge again, and re-run.

## Propose from ADRs (optional)

If you record architecture decisions in `docs/adr/`, write them in the [ADR format](adr-format.md);
`perturb adr migrate docs/adr/0002-store-rides.md` converts a prose ADR. Each consequence can name
the issues or areas it affects:

```sh
perturb propose adr:0002              # pending for issues it names, proposed for areas and mentions
perturb inbox 13 --include proposed   # proposals wait here until someone decides
perturb confirm <event-id>            # or: perturb dismiss <event-id> --note "already handled"
```

Add `--review` to `propose` to go through the proposals interactively.

## Feed back what implementation found

After implementing a plan, write a friction log at `tasks/friction-logs/<slug>-friction.md`. The
minimum is the commits the work made:

```markdown
---
commits: ["a89ed3b", "57ce145"]
---

Backfilling refunds needed changes in src/core/fares/ that the plan never mentioned.
```

Then propose from it:

```sh
perturb propose friction:backfill-refunds
```

perturb asks git which files those commits touched, ignores the files the plan declared, and
proposes `friction` events to open issues in the areas the rest fall in. Someone other than the
implementer should confirm or dismiss them. The full format, including audits, is in
[Plan, friction log and audit formats](run-evidence-format.md).

## Run the checks in CI

`perturb check` fails on ADRs that break the format or were never propagated, pending events on
closed issues, events whose `detail` link no longer resolves, and stale plans. To run it on every
pull request, add `.github/workflows/perturb-check.yml`:

```yaml
name: perturb check

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  issues: read

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0 # the stale gate reads each plan's last commit from git history
      - uses: astral-sh/setup-uv@v6
      # pin the version so a new perturb release can't change CI without a commit
      - run: uvx perturb@0.0.1 check
        env:
          GH_TOKEN: ${{ github.token }}
```

## Where next

- [Concepts](concepts.md) explains events, their lifecycle and the stale gate in full.
- [Using perturb with agents](agents.md) maps these steps onto planning, implementing and
  reviewing agents, with a guide for each.
- [Working in a team](teams.md) covers branches and parallel work.
- [CLI reference](cli.md) lists every verb and option.
