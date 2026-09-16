# Implementation Friction Log: tasks/friction-declared-test-paths.md

- Run: 4
- Executor: claude-sonnet-4-6 (source: transcript)
- Plan blob: `094c15543da327d89404b1bd199700d65448193b` (declared)
- Started: 2026-09-16T12:47:55.965185+00:00  Ended: 2026-09-16T13:00:39.905174+00:00  Outcome: complete
- Baseline failures at start: perturb=0

## Plan fidelity

- Declared cycles: 9
- Delivered: 9   Skipped: 0
- Never reached: none
- Human interventions: 0

### Cycle 9: wire show plan: to the transport runner  _(standard)_
- **Target:** `perturb::tests/test_cli.py::test_show_plan_resolves_test_paths_through_the_transport_runner`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `bf76c858c` [red] test: show plan resolves test paths through the transport runner (1 files)
  - `5755e16b5` [green] feat: give show plan a runner so it can resolve test ids (2 files)
- **Event — implementation_during_red:** ["src/perturb/propose.py"]
> **note** _(during AWAITING_IMPL)_: implementation_during_red: added runner=None guard to resolve_test_paths during cycle 9 RED — necessary so cycle 9's expected failure is AssertionError (test path absent from files) rather than TypeError (NoneType not callable); the actual GREEN implementation is the cli.py transport wiring, untouched in RED

### Cycle 8: show plan: lists the resolved test paths  _(standard)_
- **Target:** `perturb::tests/test_show.py::test_show_plan_lists_resolved_test_paths`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `7d7f0bfe6` [red] test: show plan lists resolved test paths (2 files)
  - `7941786b0` [green] feat: show plan lists a contract's test files (1 files)

### Cycle 7: propose friction: treats a planned test edit as declared  _(standard)_
- **Target:** `perturb::tests/test_cli.py::test_propose_friction_counts_modifies_tests_as_declared`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `e770014a7` [red] test: propose friction counts modifies_tests as declared (1 files)
  - `d78e1d3ef` [green] fix: propose friction no longer flags a plan's declared test edits (2 files)

### Cycle 6: skip tdd entirely when the contract names no test ids  _(standard)_
- **Target:** `perturb::tests/test_propose.py::test_declared_paths_does_not_run_tdd_when_no_test_ids`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `6ecd027ef` [red] test: declared_paths does not run tdd when no test ids (1 files)
  - `23378f220` [green] feat: skip tdd when a plan names no test ids (1 files)

### Cycle 5: union the contract's path lists with the resolved test paths  _(standard)_
- **Target:** `perturb::tests/test_propose.py::test_declared_paths_unions_contract_paths_and_resolved_test_paths`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `7d73b5c3b` [red] test: declared_paths unions contract paths and resolved test paths (2 files)
  - `854853e4d` [green] feat: declared_paths counts a plan's test ids as declared (1 files)

### Cycle 4: warn about ids tdd could not resolve to a file  _(standard)_
- **Target:** `perturb::tests/test_propose.py::test_resolve_test_paths_warns_about_unresolved_ids`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `73f1fb6fd` [red] test: resolve_test_paths warns about unresolved ids (1 files)
  - `a1bcb0b6b` [green] feat: warn about test ids with no resolved path (1 files)

### Cycle 3: warn and yield nothing when tdd plan paths is unavailable  _(standard)_
- **Target:** `perturb::tests/test_propose.py::test_resolve_test_paths_warns_and_yields_nothing_when_tdd_unavailable`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `5950e19ae` [red] test: resolve_test_paths warns when tdd is unavailable (1 files)
  - `b56cfdec4` [green] feat: fall back with a warning when tdd plan paths cannot run (1 files)

### Cycle 2: resolve test ids to paths through tdd plan paths  _(standard)_
- **Target:** `perturb::tests/test_propose.py::test_resolve_test_paths_runs_tdd_plan_paths_in_the_repo_root`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 1, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 1}
- **First run outcome:** failed (as expected)
- **Commits:**
  - `d9c38a0d9` [red] test: resolve_test_paths runs tdd plan paths in the repo root (2 files)
  - `bfd91701d` [green] feat: resolve a plan's test ids with tdd plan paths (1 files)

### Cycle 1: detect whether a plan contract names any test ids  _(standard)_
- **Target:** `perturb::tests/test_propose.py::test_plan_declares_test_ids_across_every_id_field`
- **Projects:** `perturb`
- **Suite runs by phase:** {'AWAITING_TEST': 4, 'AWAITING_IMPL': 1, 'CLOSE_SWEEP': 2}
- **First run outcome:** not_found (**not_found**)
- **Commits:**
  - `5150fb5ff` [red] test: plan_declares_test_ids across every id field (2 files)
  - `61ce65a53` [green] feat: detect test ids in a plan contract (1 files)
  - `34d4e01ef` [refactor] refactor: detect whether a plan contract names any test ids (1 files)
- **Event — multiple_new_tests:** ["perturb::tests/test_propose.py::test_plan_declares_test_ids_across_every_id_field[---\\ncycles:\\n  - n: 1\\n    files: [src/a.py]\\n---\\n-False]", "perturb::tests/test_propose.py::test_plan_declares_test_ids_across_every_id_field[---\\ncycles:\\n  - n: 1\\n    modifies_tests: [tests/test_a.py::t
- **Event — multiple_new_tests:** ["perturb::tests/test_propose.py::test_plan_declares_test_ids_across_every_id_field[---\\ncycles:\\n  - n: 1\\n    files: [src/a.py]\\n---\\n-False]", "perturb::tests/test_propose.py::test_plan_declares_test_ids_across_every_id_field[---\\ncycles:\\n  - n: 1\\n    modifies_tests: [tests/test_a.py::t
- **Event — target_named_by_agent:** perturb::tests/test_propose.py::test_plan_declares_test_ids_across_every_id_field[---\ncycles:\n  - n: 1\n    modifies_tests: [tests/test_a.py::test_old]\n    files: [src/a.py]\n---\n-True]
- **Event — declared_test_mismatch:** {"declared": ["perturb::tests/test_propose.py::test_plan_declares_test_ids_across_every_id_field[---\\ncycles:\\n  - n: 1\\n    modifies_tests: [tests/test_a.py::test_old]\\n    files: [src/a.py]\\n---\\n-True]"], "adopted": ["perturb::tests/test_propose.py::test_plan_declares_test_ids_across_every_

## Executor narrative

_Claims from the executor, unverified by design._

> hardest cycle: 1 — plan declares test function without parametrize suffix; tdd-cli required a specific parametrized ID when written as @pytest.mark.parametrize, solved by rewriting as a loop to give a single test ID. plan inaccuracy: expected 357 baseline tests but suite had 405 (PRs #15 and #16 added tests after the plan was audited). harness friction: cycle 9 needed runner=None guard added during RED to produce AssertionError rather than TypeError as the expected failure.

