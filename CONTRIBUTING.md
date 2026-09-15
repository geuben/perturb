# Contributing

## Setup

You need Python 3.11+, [`uv`](https://docs.astral.sh/uv/) and `git`. The test suite never calls
GitHub, so `gh` is only needed to run perturb against a real repository.

```sh
uv sync
uv run pytest
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run python scripts/check_doc_links.py
```

CI runs all of these on every pull request and push to `main`, along with the tests on Python 3.11
and 3.14 on Linux and macOS, a build and smoke test of the wheel, a workflow audit, and
`perturb check` on this repository's own ledger ([`.github/workflows/`](.github/workflows)).
Releases are described in [RELEASING.md](RELEASING.md), and security reports in
[SECURITY.md](SECURITY.md).

## Repository layout

| Path | Contents |
|---|---|
| `src/perturb/` | the CLI; `cli.py` wires each verb to its module |
| `tests/` | pytest suite |
| `docs/` | user documentation; [`docs/design/`](docs/design/README.md) holds the design notes |
| `perturb/` | this repository's own ledger, see [perturb/README.md](perturb/README.md) |
| `tasks/` | plans and friction logs for work in progress, see [tasks/README.md](tasks/README.md) |
| `skills/perturb/`, `.claude-plugin/` | the `perturb` agent skill, and the manifests that make this repository a Claude Code plugin |
| `tdd.toml` | the [`tdd-cli`](https://github.com/geuben/tdd-cli) project definition |

## How perturb is built

perturb is developed with the workflow it supports, so the repository holds that workflow's working
files:

- **Issues** on GitHub, organised with sub-issues and blocked-by links.
- **Plans** in `tasks/`, one per issue, each with `closes: <issue>`. An issue carries the
  `ready-to-implement` label once its plan is ready.
- **The ledger** in `perturb/`: decisions and friction that travel between issues.
- **Execution** with `tdd-cli`, which leaves a friction log per run in `tasks/friction-logs/`.
- **Agents** that plan, implement and review follow the [planning](docs/planning.md),
  [implementing](docs/implementing.md) and [reviewing](docs/reviewing.md) guides. The maintainer's
  skills for them are personal and not in the repository.

None of this is required to change perturb: an ordinary branch with tests is enough.

## Conventions

- **Output is an interface.** The `--json` envelope, the event YAML, `perturb/config.yaml` and the
  formats in [run-evidence-format.md](docs/run-evidence-format.md) are read by other tools.
  Say so when a change alters any of them.
- **Tests do not touch GitHub.** Commands take an injected transport; see `tests/test_cli.py` for
  fakes. Construct `GhTransport` with an explicit `env` so a developer's `PERTURB_GH` cannot change
  a test's result.
- **Lines stay under 100 characters**, checked by ruff; code is formatted with `ruff format`.
- **Every verb and argument has `--help` text.** A test fails when one is missing.
- **Touching `.github/` means running `uv run zizmor .` too.** CI audits the workflows with
  [zizmor](https://github.com/zizmorcore/zizmor) and fails on any finding. Actions are hash-pinned
  with a `# vN` comment, and Dependabot moves the pins. If a finding is a deliberate choice rather
  than a bug, suppress it with a `# zizmor: ignore[audit-name]` comment that says why; don't loosen
  the gate.
- **GitHub CLI wrappers are personal.** If you use one, set `PERTURB_GH` in your shell rather than
  in the repository.
