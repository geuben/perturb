# Implementation Friction Log: tasks/supersede-backlink-ref-spellings.md

- Run: 5
- Executor: claude-sonnet-4-6 (source: transcript)
- Plan blob: `1120efb972e5b8a2bd2a9a41951c32b7f56caf30` (declared)
- Started: 2026-09-16T13:29:11.784647+00:00  Ended: 2026-09-16T13:32:34.413942+00:00  Outcome: complete
- Baseline failures at start: perturb=0

## Plan fidelity

- Declared cycles: 4
- Delivered: 4   Skipped: 0
- Never reached: none
- Human interventions: 0

### Cycle 4: check reports an unresolvable superseded_by instead of passing it over  _(standard)_
- **Target:** `perturb::tests/test_check.py::test_an_unresolvable_superseded_by_is_a_finding`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `fafbb4c79` [red] test: an unresolvable superseded_by is a finding (1 files)
  - `1b189781d` [green] feat: check reports superseded_by_unresolved (1 files)
  - `da7b3bd10` [refactor] docs: document superseded_by_unresolved (2 files)

### Cycle 3: a one-element list superseded_by is normalised to its string  _(standard)_
- **Target:** `perturb::tests/test_adr.py::test_a_one_element_list_superseded_by_is_normalised`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `80524de24` [red] test: a one-element list superseded_by is normalised (1 files)
  - `a83619da3` [green] fix: normalise a one-element list superseded_by to its entry (1 files)

### Cycle 2: supersede_backlink matches supersedes entries by parsed ADR number  _(standard)_
- **Target:** `perturb::tests/test_check.py::test_supersede_backlink_accepts_equivalent_ref_spellings`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `f35b98fc8` [red] test: supersede_backlink accepts equivalent ADR ref spellings (1 files)
  - `7cbef9e31` [green] fix: match the supersede backlink by parsed ADR number (1 files)
  - `ca8a67007` [refactor] docs: document which supersedes spellings satisfy the backlink (1 files)

### Cycle 1: a bare-string supersedes is read as one ref, not one per character  _(standard)_
- **Target:** `perturb::tests/test_check.py::test_a_bare_string_supersedes_is_read_as_one_ref`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `ed2fd3677` [red] test: a bare-string supersedes is read as one ref (1 files)
  - `d31e30398` [green] fix: normalise a bare-string supersedes to a one-element list (1 files)
  - `e69d0e970` [refactor] docs: document the bare-string supersedes spelling (1 files)

## Executor narrative

_Claims from the executor, unverified by design._

> hardest cycle: cycle 4 — replacing parse_ref with parse_supersedes_ref in the superseded_by backlink block while also adding superseded_by_unresolved for the four rejected forms (malformed, anchored, missing target, plural list); plan got right: the _unwrap_one helper for cycle 3 covers the one-element list case cleanly and leaves multi-element lists intact for cycle 4 to report; harness friction: none

