---
closes: 4
cycles:
  - n: 1
    project: perturb
    title: "detect whether a plan contract names any test ids"
    test: "tests/test_propose.py::test_plan_declares_test_ids_across_every_id_field"
    stub_expected: ["src/perturb/propose.py"]
    files: ["src/perturb/propose.py"]
    commit_red: "test: plan_declares_test_ids across every id field"
    commit_green: "feat: detect test ids in a plan contract"
  - n: 2
    project: perturb
    title: "resolve test ids to paths through tdd plan paths"
    test: "tests/test_propose.py::test_resolve_test_paths_runs_tdd_plan_paths_in_the_repo_root"
    stub_expected: ["src/perturb/propose.py"]
    files: ["src/perturb/propose.py"]
    commit_red: "test: resolve_test_paths runs tdd plan paths in the repo root"
    commit_green: "feat: resolve a plan's test ids with tdd plan paths"
  - n: 3
    project: perturb
    title: "warn and yield nothing when tdd plan paths is unavailable"
    test: "tests/test_propose.py::test_resolve_test_paths_warns_and_yields_nothing_when_tdd_unavailable"
    files: ["src/perturb/propose.py"]
    commit_red: "test: resolve_test_paths warns when tdd is unavailable"
    commit_green: "feat: fall back with a warning when tdd plan paths cannot run"
  - n: 4
    project: perturb
    title: "warn about ids tdd could not resolve to a file"
    test: "tests/test_propose.py::test_resolve_test_paths_warns_about_unresolved_ids"
    files: ["src/perturb/propose.py"]
    commit_red: "test: resolve_test_paths warns about unresolved ids"
    commit_green: "feat: warn about test ids with no resolved path"
  - n: 5
    project: perturb
    title: "union the contract's path lists with the resolved test paths"
    test: "tests/test_propose.py::test_declared_paths_unions_contract_paths_and_resolved_test_paths"
    stub_expected: ["src/perturb/propose.py"]
    files: ["src/perturb/propose.py"]
    commit_red: "test: declared_paths unions contract paths and resolved test paths"
    commit_green: "feat: declared_paths counts a plan's test ids as declared"
  - n: 6
    project: perturb
    title: "skip tdd entirely when the contract names no test ids"
    test: "tests/test_propose.py::test_declared_paths_does_not_run_tdd_when_no_test_ids"
    files: ["src/perturb/propose.py"]
    commit_red: "test: declared_paths does not run tdd when no test ids"
    commit_green: "feat: skip tdd when a plan names no test ids"
  - n: 7
    project: perturb
    title: "propose friction: treats a planned test edit as declared"
    test: "tests/test_cli.py::test_propose_friction_counts_modifies_tests_as_declared"
    files: ["src/perturb/propose.py", "src/perturb/cli.py"]
    commit_red: "test: propose friction counts modifies_tests as declared"
    commit_green: "fix: propose friction no longer flags a plan's declared test edits"
  - n: 8
    project: perturb
    title: "show plan: lists the resolved test paths"
    test: "tests/test_show.py::test_show_plan_lists_resolved_test_paths"
    stub_expected: ["src/perturb/show.py"]
    files: ["src/perturb/show.py"]
    commit_red: "test: show plan lists resolved test paths"
    commit_green: "feat: show plan lists a contract's test files"
  - n: 9
    project: perturb
    title: "wire show plan: to the transport runner"
    test: "tests/test_cli.py::test_show_plan_resolves_test_paths_through_the_transport_runner"
    files: ["src/perturb/cli.py"]
    commit_red: "test: show plan resolves test paths through the transport runner"
    commit_green: "feat: give show plan a runner so it can resolve test ids"
ancillary_files:
  - "docs/tdd-cli.md"
  - "docs/run-evidence-format.md"
  - "docs/cli.md"
  - "CHANGELOG.md"
---

# Count a tdd-cli plan's test ids as declared files

## Context

Issue [#4](https://github.com/geuben/perturb/issues/4). perturb's declared files come from
`cycles[].files`, `cycles[].stub_expected` and `ancillary_files`
([`read_declared_paths`](../src/perturb/propose.py)). A tdd-cli cycle also declares the test it
drives (`test` / `tests`) and the existing tests it is authorised to change (`modifies_tests`),
but those are **test ids, not paths**, so `perturb propose friction:<slug>` counts a planned test
edit as a file touched outside the plan, and `perturb show plan:<slug>` omits it.

The blocker named in the issue body, [geuben/tdd-cli#119](https://github.com/geuben/tdd-cli/issues/119),
is **closed** (PR #124, merged 2026-09-16) and `tdd plan paths` ships in **tdd-cli v0.11.0**. It is
read-only, needs no `plan register` and no active run, and owns the per-adapter id-to-path mapping
so perturb does not have to mirror it.

## Design decisions (locked)

1. **Resolve ids with `tdd plan paths <plan> --json`; never mirror an adapter.** Locked by the
   issue body itself ("perturb will resolve test ids to files with `tdd plan paths` instead of
   mirroring each adapter"). Reproducing `target_path`, id qualification and `tdd.toml` roots in
   perturb would drift on every adapter change.

2. **Both id fields count: a cycle's own `test`/`tests` and its `modifies_tests`.** Locked by the
   issue body ("A cycle's own `test`/`tests` will count as declared too"). `tdd plan paths` covers
   both and tags each result with `field`.

3. **The result is `result.paths[].path`, not a bare object.** Verified empirically (see
   Probe evidence): real output is the tdd-cli envelope
   `{"ok": true, "envelope_version": 1, "run": null, "result": {"plan":…, "paths": […],
   "unresolved": […]}, "next_action": …}`. **The example JSON in issue #4 and in tdd-cli #119 shows
   the bare inner object and is wrong** — parse `result.paths`, never the top level.

4. **`tdd plan paths` must run with `cwd` set to the repository root.** Verified empirically: it
   shells `git rev-parse --show-toplevel` and exits 1 with
   `"error": "git rev-parse --show-toplevel failed: fatal: not a git repository…"` when the cwd is
   outside a repo, *even when the plan argument is an absolute path*. Pass `cwd=repo_root` and a
   repo-relative plan path. Returned paths are already repository-relative.

5. **Unavailable tdd warns and falls back to today's text-only declared paths; it never refuses.**
   perturb is usable without tdd-cli and must stay standalone (user decision). Three unavailability
   forms, all handled identically (all three verified empirically):
   - binary absent → `OSError` / `FileNotFoundError` from the runner;
   - too old (0.10.1 has no `plan paths` subcommand) → **exit 2**, argparse usage on stderr,
     **stdout empty and not JSON**;
   - tdd reports an error (bad cwd, malformed contract, unknown project) → **exit 1**, stdout is a
     JSON envelope with `"ok": false` and an `"error"` string.

   Cost accepted: friction proposals may over-report until tdd is upgraded, which is the behaviour
   perturb has today.

6. **Shell out only when the contract actually names a test id** (user decision). A plain-Markdown
   plan, or a contract with only `files`, never spawns a subprocess and never emits an
   unavailability warning. This is also what keeps the existing suite green — see Test-side blast
   radius.

7. **Ids tdd reports as `unresolved` produce a warning naming them, and never block** (user
   decision). Their files will still be reported as touched outside the plan, and the warning is the
   reviewer's signal that such a proposal may be a false positive. perturb itself is pytest-only, so
   this matters for gradle/xctest/cargo-`lib::` consumers.

8. **Both `propose friction:` and `show plan:` use the resolved set.** One definition of "declared
   files" across the tool (user decision); the issue's repro names both. `show plan:` therefore
   gains a runner.

9. **The runner seam is the existing injected `runner`, reached through the transport.**
   `propose_friction` already takes `runner=` and `cli.py` already passes `_transport.runner` to run
   `git show` for friction commits, so `tdd` goes through the same seam and is faked the same way in
   tests. **Note the fake's signature:** the existing `FrictionTransport.runner` in
   `tests/test_cli.py` is `(self, argv, capture_output=True, text=True)` and has **no `cwd`
   parameter** — every new or amended fake runner must accept `cwd` or it raises `TypeError`.

10. **`warn` is optional with a no-op default** on the new functions, so `propose_friction` and
    `show` can thread the dispatcher's `warn` callback without breaking their existing callers.

## Deliberate scope cuts (do not build)

- **No `PERTURB_TDD` binary override.** Premise: the issue does not ask for one, and TDD rule 4
  forbids building what no test in scope demands. perturb calls `tdd` by bare name.
  *Re-evaluation trigger:* this repo's own `tdd` on `PATH` is **0.10.1**, so after this lands
  perturb's own `propose friction:` runs will take the decision-5 warning path until tdd-cli is
  upgraded to >= 0.11.0. If the run shows the bare name resolving to a wrong or missing version in a
  way the warning does not make obvious, **stop and raise a blocker** rather than adding the env var
  inside a refactor commit.
- **No end-to-end test against a really installed `tdd`.** Premise: it would bind the suite to the
  machine's tdd version and fail today on 0.10.1. Every cycle fakes the runner. Consequence: the
  suite proves perturb's side of the contract, not tdd-cli's; decisions 3, 4 and 5 are what tie the
  two together, and each was verified by probe rather than by a committed test.
- **No normalising of `files` / `stub_expected` / `ancillary_files`.** Already paths; explicitly out
  of scope in tdd-cli #119.
- **No `perturb/areas.yaml` change.** The work stays in `src/perturb/propose.py`,
  `src/perturb/show.py` and `src/perturb/cli.py`, all already mapped to areas (`proposals`, `graph`,
  `cli`). No new module is created.

## Test-side blast radius

No existing test is modified by this plan: every cycle's `modifies_tests` is empty. That is a
consequence of decision 6, and it was checked rather than assumed.

Discovery command, re-run it and report any delta:

    grep -n "cycles" tests/test_show.py tests/test_cli.py tests/test_propose.py

Every plan fixture the suite builds declares only `files` / `stub_expected` — **none carries
`test`, `tests` or `modifies_tests`**. So under decision 6 none of them reaches the runner, and the
signature changes are additive:

- `tests/test_show.py::test_show_plan_returns_issue_and_declared_files` asserts an exact dict and
  calls `show(ref, repo_root=...)` with no runner. Cycle 8's new parameters default to `None` and
  its fixture has no test ids, so the assertion is unchanged.
- `tests/test_cli.py::test_show_plan_verb_is_local_and_emits_plan_view` passes no transport.
  Cycle 9 constructs `GhTransport()` in that branch, which only reads `PERTURB_GH` and sets
  `runner`; it makes no call. `data.files` is unchanged.
- `tests/test_cli.py::test_propose_friction_writes_events_and_emits_json` and the
  `propose_friction` tests in `tests/test_propose.py` fake a runner whose signature has **no `cwd`
  parameter**. Their plans have no test ids, so `tdd` is never invoked and the missing `cwd`
  keyword never raises. Do not add `cwd` to those fakes; only cycle 7's new fake needs it.

If any of these turns red, the guard in cycle 6 is wrong — that is a `plan_defect` blocker, not a
test to relax. Never widen an assertion or delete a test to absorb it.

## Probe evidence

Run against tdd-cli 0.11.0 via `uvx --from tdd-cli==0.11.0`, on a throwaway contract declaring both
`test` and `modifies_tests`, then deleted (`git status` clean):

- Both fields resolve, each tagged: `{"cycle": 1, "field": "test", "id":
  "tests/test_propose.py::test_probe", "project": "perturb", "path": "tests/test_propose.py"}` and
  the matching `"field": "modifies_tests"` row for `tests/test_show.py`.
- `"unresolved": []` for a pytest project.
- From `/tmp` with an absolute plan path: exit 1, `"ok": false`, the `git rev-parse` error above.
- `tdd 0.10.1 plan paths …`: exit 2, `tdd plan: error: argument plan_command: invalid choice:
  'paths' (choose from register)` on stderr, empty stdout.

## Cycles

Each cycle's GREEN adds exactly the increment named below **and nothing earlier**. All nine land in
the same two or three files, so resist writing a later cycle's test early: a test that passes on
arrival is a `red_first_violation`, not a shortcut.

### Cycle 1 — `plan_declares_test_ids`

Adds the decision-6 predicate **and nothing else** — no subprocess, no path resolution.
`plan_declares_test_ids(plan_text)` returns True when any cycle in the front-matter carries `test`,
`tests` or `modifies_tests`, else False. One table-driven test over all four forms (each of the
three fields alone, and a contract with only `files`), because they are the accepted forms of one
surface (E-12c).

Production target: `src/perturb/propose.py::plan_declares_test_ids`.

**EXPECTED FAILURE:** with `src/perturb/propose.py` stubbed (`def plan_declares_test_ids(plan_text):
raise NotImplementedError`), the test fails with `NotImplementedError`. It must not fail with
`ImportError`.

### Cycle 2 — `resolve_test_paths` happy path

Adds the subprocess call and the parse **and nothing else** — no error handling, no `unresolved`
warning, no union. `resolve_test_paths(plan_rel_path, *, runner, repo_root, warn=None)` calls
`runner(["tdd", "plan", "paths", plan_rel_path, "--json"], capture_output=True, text=True,
cwd=repo_root)` and returns `{row["path"] for row in json.loads(stdout)["result"]["paths"]}`.

The single test asserts the returned set **and** the argv **and** `cwd=repo_root` — the cwd is
decision 4 and the probe's most consequential finding, so it is pinned here, not left to prose. The
fake runner returns the full envelope shape from Probe evidence, including the `result` wrapper.

Production target: `src/perturb/propose.py::resolve_test_paths`.

**EXPECTED FAILURE:** stubbed, the test fails with `NotImplementedError`.

### Cycle 3 — unavailable tdd warns

Adds decision 5's error handling **and nothing else** — cycle 2's happy path keeps working
unchanged. One table-driven test over the three unavailability forms from Probe evidence: the runner
raising `OSError`; a result with `returncode=2` and empty non-JSON stdout; a result with
`returncode=1` and an `{"ok": false, "error": …}` envelope. Each must return an **empty set** and
call `warn` exactly once with a message naming `tdd plan paths`.

Production target: `src/perturb/propose.py::resolve_test_paths`.

**EXPECTED FAILURE:** the `OSError` case propagates out of `resolve_test_paths` and the test errors
with `OSError` before reaching its assertions.

### Cycle 4 — unresolved ids warn

Adds decision 7 **and nothing else**. When `result.unresolved` is non-empty, `warn` is called with a
message naming each unresolved `id`; the resolved paths are still returned. The single test supplies
an envelope with one resolved row and one unresolved row and asserts both the returned set and the
warning text.

Production target: `src/perturb/propose.py::resolve_test_paths`.

**EXPECTED FAILURE:** `AssertionError` — no warning is emitted, so the assertion on the captured
warnings list fails against an empty list.

### Cycle 5 — `declared_paths` unions

Adds the union **and nothing else** — not the decision-6 skip, which is cycle 6.
`declared_paths(plan_text, plan_rel_path, *, runner, repo_root, warn=None)` returns
`read_declared_paths(plan_text) | resolve_test_paths(...)`. `read_declared_paths` stays exactly as it
is: text-only and pure, still directly tested by
`tests/test_propose.py::test_read_declared_paths_unions_files_stub_and_ancillary`.

Production target: `src/perturb/propose.py::declared_paths`.

**EXPECTED FAILURE:** stubbed, the test fails with `NotImplementedError`.

### Cycle 6 — `declared_paths` skips tdd

Adds decision 6's guard **and nothing else**. When `plan_declares_test_ids(plan_text)` is False,
`declared_paths` must not invoke `runner` at all. The test passes a runner that raises
`AssertionError("tdd must not run")` if called, and asserts the contract-only paths come back.

Production target: `src/perturb/propose.py::declared_paths`.

**EXPECTED FAILURE:** `AssertionError: tdd must not run` — cycle 5's implementation calls the runner
unconditionally.

### Cycle 7 — `propose friction:` counts a planned test edit as declared

The issue's acceptance criterion, exercised end to end so it also proves the `warn` plumbing.
`propose_friction` gains `warn=None`, swaps `read_declared_paths(plan_text)` for
`declared_paths(...)`, and `cli.py` passes `warn=warn` in the existing `friction` branch.

The test is modelled on `tests/test_cli.py::test_propose_friction_writes_events_and_emits_json`. Its
plan declares `modifies_tests: ["tests/test_show.py::test_old"]` and an area-matching `files` entry;
its friction commit touches `tests/test_show.py`; the fake transport's runner answers the `tdd plan
paths` argv with a resolving envelope. **The fake runner must accept a `cwd` keyword** (decision 9).
Assertion: the envelope proposes nothing for that issue, because the touched test file was declared.

Production target: `src/perturb/propose.py::propose_friction`, wired in `src/perturb/cli.py`.

**EXPECTED FAILURE:** `AssertionError` on the proposal count — one friction event is proposed today
because `tests/test_show.py` is not in the declared set. It will **not** fail on the unexpected-argv
`AssertionError` in the fake, because the fake is written to answer the tdd argv from the start.

### Cycle 8 — `show plan:` lists the resolved test paths

`show()` gains `runner=None` and `warn=None` and uses `declared_paths` for the plan branch. The test
writes a contract with a `test` id, passes a fake runner returning a resolving envelope, and asserts
the returned `files` list contains the test file alongside the contract paths.

Production target: `src/perturb/show.py::show`.

**EXPECTED FAILURE:** with `show.py` carrying signature stubs only (the two new keyword parameters
added with `None` defaults and unreferenced in the body), the test fails with `AssertionError` —
`files` lacks the test path. Declaring the signature stub is what keeps this an assertion failure
rather than a `TypeError` on an unexpected keyword.

### Cycle 9 — `show plan:` reaches the runner through the transport

The plan branch of `show` in `cli.py` is fully offline today. It gains
`_transport = transport if transport is not None else GhTransport()` and passes
`runner=_transport.runner, warn=warn`, matching what the `propose friction:` branch already does.
No GitHub call is added — only the runner is taken from the transport.

The test calls `main(["show", "plan:<slug>", "--json"], transport=fake, repo_root=repo)` with a
contract naming a test id, and asserts the emitted `data.files` includes the resolved test file.

Production target: `src/perturb/cli.py`, the `parsed.verb == "show"` plan branch.

**EXPECTED FAILURE:** `AssertionError` — `data.files` omits the test path because no runner reaches
`show`, so `declared_paths` falls back to the contract paths alone.

## Docs (ancillary, not a cycle)

- `docs/tdd-cli.md` — the "Plans" table gains `cycles[].test` / `cycles[].tests` and
  `cycles[].modifies_tests` rows, with a note that resolution needs tdd-cli >= 0.11.0 and degrades
  to a warning without it.
- `docs/run-evidence-format.md` — the tdd-cli blockquote under "declared files" says test ids count
  too.
- `docs/cli.md` — the `perturb show plan:` section says `files` includes resolved test files.
- `CHANGELOG.md` — an `### Fixed` entry under `[Unreleased]`, in the existing bolded-sentence style.

## Execution

This plan is executed through `tdd-cli`. **You run every command below yourself** — do not ask the
user to start the run. `tdd run start` records which model is executing, resolved from your own
session; a run started by anyone else attributes this work to the wrong agent.

    git checkout -b friction-declared-test-paths   # first, before anything else
    tdd doctor                                     # must report healthy: true
    tdd run start --plan tasks/friction-declared-test-paths.md

If the branch already exists, do not force-checkout and do not pick another name: check it out
only if it carries this plan's commit and no unrelated work, otherwise stop and ask.

Then repeat until done: read `next_action.verb`, do exactly what it says, run `tdd advance`.
Stop when `next_action.terminal` is `true`.

When `next_action.terminal` is `true`, finish the run: render the friction log, commit it, and
raise the PR — see Done-criteria below.

- `tdd advance` is the only command that changes phase. Do not `git add` or `git commit` — the
  tool stages and commits, deriving the file set from the phase.
- The baseline is captured at `run start` and subtracted from later verdicts. The suite is green
  today: expect `357 passed`. A different number means the branch moved — stop and check.
- Verbs this plan will hit: `annotate_cycle` → `tdd annotate --key --value` (this plan declares no
  custom annotation keys; only the reserved `plan_defect` and `friction_note` apply);
  `resolve_blocker` → `tdd blocker --kind --detail` (expected kinds here: `plan_defect` for a cycle
  whose EXPECTED FAILURE does not match, `environment` if `tdd plan paths` behaviour differs from
  Probe evidence); `confirm_cycle_applicable` on a cycle that no longer applies →
  `tdd cycle skip --reason`. `run_sensitivity_check` → `tdd sensitivity begin|check|end` if a
  standard cycle's test passes on arrival.

## Done-criteria

**Before finishing:** run `tdd log render --out tasks/friction-logs/friction-declared-test-paths-friction.md`
and `tdd metrics`. Report the plan-fidelity section — declared vs delivered vs skipped — and every
integrity event. Do not narrate what the ledger already records.

Each ancillary doc is a deliverable, not a hope. Every one of these must be non-empty:

    git diff --stat origin/main -- docs/tdd-cli.md
    git diff --stat origin/main -- docs/run-evidence-format.md
    git diff --stat origin/main -- docs/cli.md
    git diff --stat origin/main -- CHANGELOG.md

If any is empty, the PR body must say which cycle dropped it and why.

This PR changes no user-visible UI surface, so no demo recording is required; the CLI behaviour
change is evidenced by the cycle 7 and cycle 9 tests.

Then commit the friction log and raise the PR:

    git add tasks/friction-logs/friction-declared-test-paths-friction.md
    git commit -m "docs: friction log for friction-declared-test-paths"

Then invoke the **`raise-pr` skill** (`/raise-pr`), which runs the quality gates, pushes the
branch and opens the PR against `main`. Do not push or call the GitHub API by hand. If a gate
fails, fix it and re-run the skill — a failed gate is work, not a reason to hand back.
