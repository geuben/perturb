# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.0.1] - 2026-09-15

First public release. perturb was developed privately under the name `planner`; nothing was
published under that name. Repositories that used a private build need these changes:

### Changed

- **Renamed.** The command is `perturb`, the committed ledger is `perturb/` (was `planning/`), and
  the local cache is `.perturb/` (was `.planner/`).
- **The label marking a planned issue is `ready-to-implement`** (was `hardened`), configurable as
  `labels.ready_to_implement` in `perturb/config.yaml`.
- **`perturb show plan:<slug>` reports `files`**, the plan's declared files, instead of `cycles`.

### Added

- **`perturb/config.yaml`** sets where plans, friction logs and audits live, and which labels mark
  epics and ready issues.
- **`PERTURB_GH`** names the GitHub CLI to call; the default is `gh`.
- **Friction logs can list their commits in front-matter** (`commits:`).
- **`perturb init` adds `.perturb/` to `.gitignore`**, creating the file if needed.
- **An ADR can supersede a single consequence** of an earlier one:
  `supersedes: ["adr:0003#postgres-over-sqlite"]` raises `supersede` events only to the issues that
  acknowledged that consequence, and `perturb check` reports entries that don't resolve.
- **Every verb has `--help`** with a description of the verb and each argument.

### Fixed

- **`perturb adr migrate` no longer drops text silently.** A `**Supersedes:**` line naming whole
  ADRs is carried into `supersedes`; one it can't interpret stays in the body with a warning, as
  does any annotation on the status line. Prose between the status line and the first heading is
  kept.
