# Implementation Friction Log: tasks/adr-filenames.md

- Run: 1
- Executor: claude-sonnet-4-6 (source: transcript)
- Plan blob: `7213b4aca94f70addd726c557f3eee18d1549a44` (declared)
- Started: 2026-09-16T11:34:02.852624+00:00  Ended: 2026-09-16T11:41:36.886862+00:00  Outcome: complete
- Baseline failures at start: perturb=0

## Plan fidelity

- Declared cycles: 5
- Delivered: 5   Skipped: 0
- Never reached: none
- Human interventions: 0

### Cycle 5: resolve_adr_path uses classify_adr_filename  _(refactor)_
- **Target:** none
- **Projects:** `perturb`
- **Suite runs by phase:** {'CLOSE_SWEEP': 1}
- **Commits:**
  - `d7042c231` [refactor] refactor: resolve ADR paths with the shared filename classifier (1 files)

### Cycle 4: pin which files resolve_adr_path finds  _(pin)_
- **Target:** `perturb::tests/test_propose.py::test_resolve_adr_path_finds_only_the_padded_name[names0-0002-x.md]`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_PIN': 2, 'SENSITIVITY': 2, 'CLOSE_SWEEP': 1}
- **First run outcome:** not_found (**not_found**)
- **Sensitivity check:** verified, restore byte-identical
  - observed: `AssertionError: assert 'adr_ambiguous' == '0002-x.md'`
- **Commits:**
  - `4b46725a8` [pin] test: pin which files resolve_adr_path finds (1 files)
- **Event — multiple_new_tests:** ["perturb::tests/test_adr.py::test_adr_filenames_are_classified_by_what_propose_can_resolve", "perturb::tests/test_check.py::test_a_near_miss_adr_filename_is_a_finding", "perturb::tests/test_check.py::test_check_reads_only_adr_named_files", "perturb::tests/test_propose.py::test_resolve_adr_path_find
- **Event — target_named_by_agent:** perturb::tests/test_propose.py::test_resolve_adr_path_finds_only_the_padded_name[names0-0002-x.md]

### Cycle 3: check reports a near-miss ADR filename  _(standard)_
- **Target:** `perturb::tests/test_check.py::test_a_near_miss_adr_filename_is_a_finding`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `bad207c39` [red] test: a near-miss ADR filename is a finding (1 files)
  - `c90239aac` [green] feat: check reports adr_filename for near-miss names (1 files)
  - `55711a0a7` [refactor] refactor: tidy adr_filename finding (2 files)

### Cycle 2: check reads only ADR-named files  _(standard)_
- **Target:** `perturb::tests/test_check.py::test_check_reads_only_adr_named_files`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `7f8845cb1` [red] test: check reads only ADR-named files (1 files)
  - `776391b60` [green] fix: check skips Markdown in docs/adr that isn't named like an ADR (1 files)
  - `27071d9b8` [refactor] refactor: tidy check's ADR file listing (2 files)

### Cycle 1: classify_adr_filename sorts names into ADR, near miss and other  _(standard)_
- **Target:** `perturb::tests/test_adr.py::test_adr_filenames_are_classified_by_what_propose_can_resolve`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 3, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** not_found (**not_found**)
- **Sensitivity check:** verified, restore byte-identical
- **Commits:**
  - `9ee5b7781` [red] test: ADR filenames are classified by what propose can resolve (2 files)
  - `4328ad394` [green] feat: classify ADR filenames (1 files)
- **Event — multiple_new_tests:** ["perturb::tests/test_adr.py::test_adr_filenames_are_classified_by_what_propose_can_resolve[0000-template.md-expected4]", "perturb::tests/test_adr.py::test_adr_filenames_are_classified_by_what_propose_can_resolve[00002-x.md-expected7]", "perturb::tests/test_adr.py::test_adr_filenames_are_classified_
- **Event — target_named_by_agent:** perturb::tests/test_adr.py::test_adr_filenames_are_classified_by_what_propose_can_resolve[0002-per-trip.md-expected0]
- **Event — declared_test_mismatch:** {"declared": ["perturb::tests/test_adr.py::test_adr_filenames_are_classified_by_what_propose_can_resolve[0002-per-trip.md-expected0]"], "adopted": ["perturb::tests/test_adr.py::test_adr_filenames_are_classified_by_what_propose_can_resolve"]}

## Executor narrative

_Claims from the executor, unverified by design._

> Hardest cycle: cycle 1 - parametrized test variants triggered other_failures in tdd-cli since only one variant was targeted; restructured to a single non-parametrized function to avoid this. Plan deviation: used non-parametrized tests in cycles 1 and 3 instead of @pytest.mark.parametrize, keeping all assertions but targeting one test ID. Plan accuracy: all cycle specs correct, docs targets accurate, classify_adr_filename regex handled all cases cleanly.

