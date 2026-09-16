# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **`adr migrate` now carries `**Amends:**`, `**Extends:**`, `**Amended by:**`, and
  `**Extended by:**` body lines** into `amends:` and `amended_by:` front-matter. A clean
  whole-ADR line is absorbed and removed from the body; a line with a reason clause keeps
  the line in the body and warns; a partial line (non-whole-ADR refs) keeps the line and warns
  with a consequence-anchor hint. Continuation lines are joined. Body-line refs merge with
  status-line refs, de-duplicated, status-line first. Closes #12.

- **`superseded_by_unresolved` finding.** `perturb check` now reports `superseded_by_unresolved`
  when an ADR's `superseded_by` value is malformed, anchored (`adr:NNNN#id`), names an ADR not in
  the directory, or is a list of two or more entries. Previously all four forms were silently
  skipped, allowing `status: superseded` ADRs to pass `check` with no verified backlink.

- **`amends` and `amended_by` front-matter keys** for Architecture Decision Records. An ADR that
  amends an earlier one lists it in `amends: ["adr:NNNN"]` or `amends: ["adr:NNNN#consequence-id"]`;
  the earlier ADR lists the amending ADR in `amended_by: ["adr:NNNN"]`. Both stay in force.
- **`amend` event kind.** `perturb propose` raises `amend` events (via `push --kind amend` or from
  `amends:` front-matter) to the issues that acknowledged events from the amended ADR or
  consequence. `perturb push --kind amend` now accepted.
- **Check findings for amends/amended_by symmetry:** `amends_invalid`, `amends_unresolved`,
  `amended_by_unresolved`, `amend_backlink`, and `amended_by_missing` — analogous to the existing
  supersedes findings.
- **`perturb adr migrate` carries a `**Supersedes:**` line that names ADRs by bare number.**
  `**Supersedes:** 0003`, `**Supersedes:** [0003](0003-x.md) and 4`, and `**Supersedes:** 0003; 0004`
  are now carried into `supersedes:` front-matter, matching the existing behaviour for `ADR`-prefixed
  refs.

- **`perturb adr migrate` carries `amends`/`amended_by` from the status line.** Bare
  `amends ADR NNNN`, `amended by ADR NNNN`, `extends ADR NNNN`, and list forms
  (`amends ADR 4 and 0005`) are carried into front-matter; anchored refs and segments with
  surrounding prose are reported as warnings so the author can verify what is lost.

### Fixed

- **`supersede_backlink` now matches equivalent ADR ref spellings.** `adr:2`, `adr:0002`, and
  `adr:0002#consequence-id` in a `supersedes` list are all accepted as pointing at ADR 2.
  Previously the check used string equality, causing false `supersede_backlink` findings for
  alternative spellings of the same ADR number.
- **A bare-string `supersedes` is no longer iterated character by character.** `supersedes: adr:0001`
  (without brackets) is normalised to `["adr:0001"]` at parse time, so `perturb check` and
  `perturb propose` see a one-element list. Previously it caused one `supersedes_invalid` finding
  per character.

- **`perturb propose friction:` and `perturb show plan:` no longer flag a planned test edit as
  outside the plan.** A tdd-cli cycle's `test`, `tests` and `modifies_tests` ids are resolved to
  file paths via `tdd plan paths` (tdd-cli >= 0.11.0) and counted as declared. On older tdd-cli a
  warning is emitted and the tool falls back to the previous behaviour.

- **`perturb check` no longer fails on an index `README.md` in `docs/adr`.** Only files named
  `NNNN-<title>.md` are now treated as ADRs; other Markdown in that directory is ignored.

- **`perturb adr migrate` deleted consequences written as paragraphs.** Only `- ` bullets were
  carried; a Consequences section of prose paragraphs (`**Gains.** …`) was rewritten as an empty
  list. Each paragraph is now a consequence, like each bullet.

- **`perturb adr migrate` wrote front-matter that didn't parse** when a title contained a colon or
  started with a YAML indicator. Titles are now quoted, and an `ADR-0021:` prefix is stripped as
  well as `ADR 0021 —`.
- **`perturb adr migrate` no longer overwrites an ADR with a result it can't parse.** It refuses
  with the parser's reason and leaves the file untouched.
- **A status line wrapped over several lines** is read as one annotation instead of leaving its
  continuation lines in the body.
- **Consequence `affects` no longer picks up refs that don't name issues**: a `#N` inside a link
  to something other than an issue (`[Risk #9](../hardware.md#risks)`), or after `PR` or
  `pull request`.

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
