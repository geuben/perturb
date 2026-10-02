# Implementation Friction Log: tasks/consequence-yaml-comments.md

- Run: 1
- Executor: claude-opus-5-5 (source: transcript)
- Plan blob: `7322dd98e75b2d315c7ab1a6162e8050f765a36d` (declared)
- Started: 2026-10-02T23:52:14.558215+00:00  Ended: 2026-10-02T23:55:14.253923+00:00  Outcome: complete
- Baseline failures at start: perturb=0

## Plan fidelity

- Declared cycles: 6
- Delivered: 6   Skipped: 0
- Never reached: none
- Human interventions: 0

### Cycle 6: propose adr: refuses an ADR that does not parse instead of raising  _(standard)_
- **Target:** `perturb::tests/test_cli.py::test_propose_adr_refuses_an_adr_that_does_not_parse`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 2, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `ea9fe788f` [red] test: propose adr: refuses an ADR that does not parse (1 files)
  - `2367e41cb` [green] fix: propose adr: refuses with the parser's reason (1 files)
  - `43c21e578` [refactor] docs: changelog and cli reference for refused ADRs (2 files)

### Cycle 5: check reports consequence_comment and affects_comment as their own findings  _(standard)_
- **Target:** `perturb::tests/test_check.py::test_a_consequence_lost_to_a_yaml_comment_is_its_own_finding`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 2, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `013ba460c` [red] test: a consequence lost to a YAML comment is its own check finding (1 files)
  - `655fbb818` [green] feat: check reports consequence_comment and affects_comment (1 files)
  - `760169622` [refactor] docs: list consequence_comment and affects_comment in the check validation (1 files)

### Cycle 4: a Consequences block that is not valid YAML is refused, not a traceback  _(standard)_
- **Target:** `perturb::tests/test_adr.py::test_a_consequences_block_that_is_not_yaml_is_refused`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 2, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `e7b4e6e9f` [red] test: a Consequences block that is not valid YAML is refused (1 files)
  - `db7bf1e68` [green] fix: wrap a Consequences YAML error in AdrError bad_consequences (1 files)
  - `fcc3ca9c4` [refactor] refactor: tidy consequence parsing (1 files)

### Cycle 3: a consequence value lost to a YAML comment is refused  _(standard)_
- **Target:** `perturb::tests/test_adr.py::test_a_value_lost_to_a_yaml_comment_is_refused`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 2, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `6d7f92842` [red] test: a consequence value lost to a YAML comment is refused (1 files)
  - `ffde47342` [green] fix: refuse a consequence text or affects entry cut off by a YAML comment (1 files)
  - `0155e0d0c` [refactor] docs: document the mid-sentence # rule for consequence text and affects (1 files)

### Cycle 2: pin that adr migrate quotes a text with a mid-sentence mention  _(pin)_
- **Target:** `perturb::tests/test_adr.py::test_migrate_quotes_a_text_with_a_mid_sentence_mention`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_PIN': 1, 'SENSITIVITY': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** passed (as expected)
- **Sensitivity check:** verified, restore byte-identical
  - observed: `AssertionError: assert 'General know...ns to mention' == 'General know...7 in passing.'`
- **Commits:**
  - `c7cc78586` [pin] test: pin that migrate quotes a text with a mid-sentence #N (1 files)

### Cycle 1: pin the consequence forms that keep a # and parse whole  _(pin)_
- **Target:** `perturb::tests/test_adr.py::test_consequence_forms_that_keep_a_hash_parse_whole`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_PIN': 1, 'SENSITIVITY': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** passed (as expected)
- **Sensitivity check:** verified, restore byte-identical
  - observed: `AssertionError: assert [('mentions '...'t', []), ...] == [('mentions #...'t', []), ...]`
- **Commits:**
  - `4715d8cbf` [pin] test: pin the consequence forms that keep a # intact (1 files)

## Time

- Wall clock: 3.0 min. Suite: 0.1 min (4%).

| Phase | Suite runs | Suite (min) | Average (s) |
|---|---|---|---|
| AWAITING_TEST | 4 | 0.0 | 0.2 |
| AWAITING_PIN | 2 | 0.0 | 0.2 |
| SENSITIVITY | 2 | 0.0 | 0.2 |
| AWAITING_IMPL | 8 | 0.0 | 0.3 |
| CLOSE_SWEEP | 6 | 0.0 | 0.5 |

| Cycle | Wall (min) | Suite (min) | Suite runs |
|---|---|---|---|
| 1 | 0.3 | 0.0 | 3 |
| 2 | 0.3 | 0.0 | 3 |
| 3 | 0.6 | 0.0 | 4 |
| 4 | 0.4 | 0.0 | 4 |
| 5 | 0.7 | 0.0 | 4 |
| 6 | 0.6 | 0.0 | 4 |

## Executor narrative

_Claims from the executor, unverified by design._

> hardest cycle: 3 — the node-position detector; the plan's decisions 2 and 4 specified it precisely enough that it went green first try with all 11 cycle-1 pins intact. plan got wrong: nothing material; cycle 4's wrap covers only safe_load since compose of the same string cannot fail once load succeeded. harness friction: run start required an unmentioned 'tdd plan register' first; worktree guard refused heredoc+pipe compound commands, so edits went through Edit instead; cycle 4 refactor was a ruff format of the cycle-1 test line.

