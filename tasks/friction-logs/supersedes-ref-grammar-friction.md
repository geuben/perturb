# Implementation Friction Log: tasks/supersedes-ref-grammar.md

- Run: 3
- Executor: claude-sonnet-4-6 (source: transcript)
- Plan blob: `1b372681414308749023f12d4dfd02ccb9779038` (declared)
- Started: 2026-09-16T12:47:51.411090+00:00  Ended: 2026-09-16T12:53:49.053255+00:00  Outcome: complete
- Baseline failures at start: perturb=0

## Plan fidelity

- Declared cycles: 2
- Delivered: 2   Skipped: 0
- Never reached: none
- Human interventions: 0

### Cycle 2: migrate carries a Supersedes line in every whole-ADR ref form  _(standard)_
- **Target:** `perturb::tests/test_adr.py::test_migrate_carries_a_supersedes_line_in_every_whole_adr_ref_form[0003-supersedes3]`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 3, 'SENSITIVITY': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** not_found (**not_found**)
- **Sensitivity check:** verified, restore byte-identical
  - observed: `AssertionError: assert [] == ['adr:0003']`
- **Commits:**
  - `f259259be` [refactor] refactor: tidy the whole-ADR ref grammar (2 files)
- **Event — multiple_new_tests:** ["perturb::tests/test_adr.py::test_migrate_carries_a_supersedes_line_in_every_whole_adr_ref_form[0003, [0004](0004-y.md) & ADR:5-supersedes6]", "perturb::tests/test_adr.py::test_migrate_carries_a_supersedes_line_in_every_whole_adr_ref_form[0003-supersedes3]", "perturb::tests/test_adr.py::test_migrat
- **Event — target_named_by_agent:** perturb::tests/test_adr.py::test_migrate_carries_a_supersedes_line_in_every_whole_adr_ref_form[0003-supersedes3]
- **Event — red_first_violation:** ["perturb::tests/test_adr.py::test_migrate_carries_a_supersedes_line_in_every_whole_adr_ref_form[0003-supersedes3]"]
> **note** _(during SENSITIVITY_REQUIRED)_: Implemented code during fix_regression to resolve 5 other_failures: all 9 parametrized variants of test_migrate_carries_a_supersedes_line_in_every_whole_adr_ref_form cover the same behavior; only one bare-number variant could be named as target, but the fix required implementing _whole_adr_numbers at once.

### Cycle 1: pin the Supersedes lines migrate keeps in the body  _(pin)_
- **Target:** `perturb::tests/test_adr.py::test_migrate_keeps_a_supersedes_line_that_does_not_name_only_whole_adrs[3.5-adr:NNNN#]`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_PIN': 2, 'SENSITIVITY': 2, 'CLOSE_SWEEP': 1}
- **First run outcome:** not_found (**not_found**)
- **Sensitivity check:** verified, restore byte-identical
  - observed: `IndexError: list index out of range`
- **Commits:**
  - `d8c52704c` [pin] test: pin the Supersedes lines migrate keeps in the body (1 files)
- **Event — multiple_new_tests:** ["perturb::tests/test_adr.py::test_migrate_keeps_a_supersedes_line_that_does_not_name_only_whole_adrs[3.5-adr:NNNN#]", "perturb::tests/test_adr.py::test_migrate_keeps_a_supersedes_line_that_does_not_name_only_whole_adrs[ADR 0003's storage half-adr:0003#]", "perturb::tests/test_adr.py::test_migrate_k
- **Event — target_named_by_agent:** perturb::tests/test_adr.py::test_migrate_keeps_a_supersedes_line_that_does_not_name_only_whole_adrs[3.5-adr:NNNN#]

## Executor narrative

_Claims from the executor, unverified by design._

> Hardest part: parametrized test in cycle 2 - tdd-cli targets one variant but all 9 share behavior; implemented code during fix_regression to resolve all at once. Plan was accurate: _whole_adr_numbers design decision 2 was precise, lookarounds handled 3.5 and ADR-0003#postgres correctly. No plan defects.

