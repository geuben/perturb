# `perturb/` — this repository's own ledger

perturb is built with perturb. This directory is not part of the tool and you do not need it to use
it: it is the ledger for perturb's own issues, the same `perturb/` directory that `perturb init`
creates in any repository that adopts the tool.

- `areas.yaml` declares the areas of this codebase (ledger, proposals, graph, areas, cli, planning)
  that route findings to the open issues touching them.
- `events/` holds one YAML file per event, named by ULID: created by `perturb push` or
  `perturb propose`, acknowledged in place by `perturb ack`.
- There is no `config.yaml`, so the defaults apply: plans, friction logs and audits under `tasks/`,
  and the `ready-to-implement` and `epic` issue labels.

Events are committed in the same pull request as the change that caused them, and CI runs
`perturb check` against them ([`.github/workflows/perturb-check.yml`](../.github/workflows/perturb-check.yml)).
Anything derived from GitHub is a gitignored cache under `.perturb/`, never here.

To use perturb in your own repository, run `perturb init` there rather than copying this directory.

Docs: [configuration](../docs/configuration.md), [concepts](../docs/concepts.md).
