---
closes: 6
cycles:
  - n: 1
    project: perturb
    title: "classify_adr_filename sorts names into ADR, near miss and other"
    test: "tests/test_adr.py::test_adr_filenames_are_classified_by_what_propose_can_resolve"
    stub_expected: ["src/perturb/adr.py"]
    files: ["src/perturb/adr.py"]
    commit_red: "test: ADR filenames are classified by what propose can resolve"
    commit_green: "feat: classify ADR filenames"
    commit_refactor: "refactor: tidy ADR filename classification"
  - n: 2
    project: perturb
    title: "check reads only ADR-named files"
    test: "tests/test_check.py::test_check_reads_only_adr_named_files"
    files: ["src/perturb/check.py"]
    commit_red: "test: check reads only ADR-named files"
    commit_green: "fix: check skips Markdown in docs/adr that isn't named like an ADR"
    commit_refactor: "refactor: tidy check's ADR file listing"
  - n: 3
    project: perturb
    title: "check reports a near-miss ADR filename"
    test: "tests/test_check.py::test_a_near_miss_adr_filename_is_a_finding"
    files: ["src/perturb/check.py"]
    commit_red: "test: a near-miss ADR filename is a finding"
    commit_green: "feat: check reports adr_filename for near-miss names"
    commit_refactor: "refactor: tidy adr_filename finding"
  - n: 4
    project: perturb
    pin_cycle: true
    title: "pin which files resolve_adr_path finds"
    test: "tests/test_propose.py::test_resolve_adr_path_finds_only_the_padded_name"
    files: []
    commit_pin: "test: pin which files resolve_adr_path finds"
  - n: 5
    project: perturb
    refactor_cycle: true
    title: "resolve_adr_path uses classify_adr_filename"
    files: ["src/perturb/propose.py"]
    commit_refactor: "refactor: resolve ADR paths with the shared filename classifier"
ancillary_files:
  - "docs/adr-format.md"
  - "docs/cli.md"
  - "CHANGELOG.md"
---

# check reads only ADR-named files in docs/adr

## Context

Issue [#6](https://github.com/geuben/perturb/issues/6). `perturb check` lists `docs/adr/*.md`
twice in `src/perturb/check.py`: once in `adr_findings`, once in `unpropagated_adr_findings`. Any
other Markdown file in that directory is treated as an ADR. `perturb propose adr:N` finds ADRs
differently, by globbing `docs/adr/{int(N):04d}-*.md` in `resolve_adr_path`
(`src/perturb/propose.py`). An index `docs/adr/README.md` is a common convention, and with one
`check` can never pass.

Probed on `main` at `01bfa61`:

- A directory holding a valid `0002-x.md`, an index `README.md`, and a `template.md` with ADR
  front-matter gives:
  - `adr_findings` → `[('adr_parse', 'README.md')]`
  - `unpropagated_adr_findings` → `[('adr_unpropagated', 'template.md')]`
- A valid ADR saved as `2-x.md`, `0002_x.md`, `00002-x.md`, `0002.md` or `0002x.md` gives no
  finding at all. `check` validates it, but `propose adr:2` can never find it.

This plan adds one filename classifier shared by `check` and `propose`. `check` validates only the
files `propose` can resolve, skips other Markdown silently, and reports a file that looks like a
misnamed ADR.

Nothing else in `src/perturb` lists ADRs (`grep -rn 'glob(' src/perturb`: the two `check.py`
loops, `resolve_adr_path`, plus unrelated plan and event globs). `cli.py` passes `docs/adr` to both
`check` functions and needs no change.

Baseline: `uv run pytest -q` → `357 passed`. No `docs/INVARIANTS.md` in this repo. Every existing
test writes ADR fixtures under canonical names (`0001-a.md` … `0009-x.md`), so no existing test
changes.

## Design decisions (locked)

1. **An ADR filename is exactly a name `propose adr:` can resolve.** Decided by evidence:
   `resolve_adr_path` globs `{int(N):04d}-*.md`.
   - The rule: the name matches `(\d+)(.*)\.md`, the digit run equals `f"{int(digits):04d}"`, and
     the remainder starts with `-`.
   - So `0002-x.md`, `0002-.md` and `12345-x.md` are ADRs.
2. **A near miss is a Markdown name that starts with digits but isn't an ADR filename.** Examples:
   `2-x.md`, `0002_x.md`, `00002-x.md`, `0002.md`, `0002x.md`. Decided by the user.
   - `check` does not parse a near miss and reports one finding for it: kind `adr_filename`,
     ref = the filename.
   - Detail: `"{name} starts with an ADR number but propose adr:{n:04d} looks for {n:04d}-<title>.md"`.
   - Fix: `"rename {name} to {n:04d}-<title>.md"`.
   - A near miss never also produces `adr_parse`, `filename_id_mismatch` or `adr_unpropagated`.
3. **Every other name is skipped silently** (`README.md`, `index.md`, `template.md`,
   `adr-0002-x.md`). Decided by the user; this is the issue's fix.
4. **One helper, `classify_adr_filename(name: str) -> tuple[str, int | None]`, in
   `src/perturb/adr.py`.** It returns `("adr", n)`, `("near_miss", n)` or `("other", None)`. Decided
   by the issue ("one shared helper so the two can't drift"). All three callers use it:
   - `adr_findings`;
   - `unpropagated_adr_findings`;
   - `resolve_adr_path`: list `docs/adr/*.md` and keep names classified `("adr", int(ref_id))`.
     The `adr_not_found` / `adr_ambiguous` refusals and their messages are unchanged.
5. **Listing stays `sorted(adr_dir.glob("*.md"))`, not recursive; classification is by name
   only.** Evidence: the current behaviour of both modules. *Trap:* do not replace the glob with
   `glob("[0-9]*.md")`, which would hide near misses from cycle 3.
6. **No knock-on pushes.** #3's plan (`tasks/adr-amends.md`) extends `adr_findings` in cycles 2–5,
   but its fixtures use canonical names (`0003-old.md`, `0005-new.md`). This is a merge overlap only.
   #4 does not touch ADRs.

## Deliberate scope cuts (do not build)

- **`0000-template.md` is an ADR filename.** Premise: `propose adr:0` would resolve it too, so the
  two sides agree. An adr-tools-style numbered template must carry valid front-matter or be renamed.
- **Upper-case extensions (`0002-x.MD`) are neither listed nor flagged.** Premise: pathlib's glob is
  case-sensitive on POSIX, and `propose` has the same behaviour.
- **Subdirectories of `docs/adr` are not scanned**, and the ADR directory stays fixed at
  `docs/adr`. Both are unchanged behaviour.
- **`perturb adr migrate <file>` accepts any path.** It takes the id from the filename's leading
  digits, and this plan does not constrain it.

## Cycles

### Cycle 1: classify_adr_filename sorts names into ADR, near miss and other

- **Test:** `tests/test_adr.py::test_adr_filenames_are_classified_by_what_propose_can_resolve`,
  parametrized `name, expected`; asserts `classify_adr_filename(name) == expected`.
  - `("adr", n)`:

    | name | expected |
    |---|---|
    | `0002-per-trip.md` | `("adr", 2)` |
    | `0021-render.md` | `("adr", 21)` |
    | `12345-big.md` | `("adr", 12345)` |
    | `0002-.md` | `("adr", 2)` |
    | `0000-template.md` | `("adr", 0)` |

  - `("near_miss", n)`:

    | name | expected |
    |---|---|
    | `2-x.md` | `("near_miss", 2)` |
    | `0002_x.md` | `("near_miss", 2)` |
    | `00002-x.md` | `("near_miss", 2)` |
    | `0002.md` | `("near_miss", 2)` |
    | `0002x.md` | `("near_miss", 2)` |

  - `("other", None)`: `README.md`, `index.md`, `template.md`, `adr-0002-x.md`.
- **Production:** `src/perturb/adr.py`, new `classify_adr_filename`.
- **Stub (RED commit):** `def classify_adr_filename(name: str) -> tuple[str, int | None]: return ("other", None)`,
  appended to `src/perturb/adr.py`, which the test imports.
- **EXPECTED FAILURE** (probed with that stub): ``AssertionError: assert ('other', None) == ('adr', 2)``
  (the `other` params pass on arrival).

### Cycle 2: check reads only ADR-named files

- **Test:** `tests/test_check.py::test_check_reads_only_adr_named_files`.
  - `adr_dir` holds:
    - `0002-x.md` = `_adr(2, "accepted", "no-propagation: true\nno-propagation-reason: prose only\n")`;
    - `README.md` = `"# ADRs\n\n| ADR | Status |\n|---|---|\n| [0002](0002-x.md) | accepted |\n"`;
    - `template.md` = `_adr(0, "accepted")`.
  - Asserts `([(f["kind"], f["ref"]) for f in adr_findings(adr_dir, {"issues": {}})], [(f["kind"], f["ref"]) for f in unpropagated_adr_findings(adr_dir, [])]) == ([], [])`.
- **Production:** `src/perturb/check.py`. Both loops skip any path whose
  `classify_adr_filename(path.name)[0] != "adr"` (decision 4).
- **Increment:** skipping only. Cycle 3 adds the near-miss finding.
- **EXPECTED FAILURE** (probed): ``AssertionError: assert ([('adr_parse', 'README.md')], [('adr_unpropagated', 'template.md')]) == ([], [])``.
- **Docs:**
  - `docs/adr-format.md`, top of "Validation in `perturb check`": an ADR is a file in `docs/adr`
    named `NNNN-<title>.md` (the name `propose adr:` finds), and other Markdown there, such as an
    index `README.md`, is ignored.
  - `CHANGELOG.md` `[Unreleased]` `### Fixed`: `perturb check` no longer fails on an index
    `README.md` in `docs/adr`.

### Cycle 3: check reports a near-miss ADR filename

- **Test:** `tests/test_check.py::test_a_near_miss_adr_filename_is_a_finding`, parametrized `name`
  over `2-x.md`, `0002_x.md`, `00002-x.md`, `0002.md`.
  - `adr_dir` holds only `name`, containing
    `_adr(2, "accepted", "no-propagation: true\nno-propagation-reason: prose only\n")`.
  - Asserts `[(f["kind"], f["ref"]) for f in adr_findings(adr_dir, {"issues": {}})] == [("adr_filename", name)]`.
- **Production:** `src/perturb/check.py` `adr_findings`, the finding from decision 2.
  `unpropagated_adr_findings` already skips near misses after cycle 2.
- **EXPECTED FAILURE** (probed: each name gives `[]` today and after cycle 2):
  ``AssertionError: assert [] == [('adr_filename', '2-x.md')]``.
- **Docs:**
  - `docs/adr-format.md` "Validation in `perturb check`": a bullet for `adr_filename`.
  - `docs/cli.md` `perturb check`: a bullet saying a Markdown file in `docs/adr` that starts with
    a number but isn't named `NNNN-<title>.md` is a finding.

### Cycle 4 (pin): which files resolve_adr_path finds

- **Test:** `tests/test_propose.py::test_resolve_adr_path_finds_only_the_padded_name`, parametrized
  `names, expected`. Add `import pytest` at the top of the file.
  - Writes each name under `tmp_path / "docs" / "adr"`, then
    `outcome = resolve_adr_path(tmp_path, "2").name`, or `exc.reason` on `Refusal`.
  - Asserts `outcome == expected`. Cases:

    | names | expected |
    |---|---|
    | `["0002-x.md", "README.md"]` | `"0002-x.md"` |
    | `["0002-a.md", "0002-b.md"]` | `"adr_ambiguous"` |
    | `["00002-x.md"]` | `"adr_not_found"` |
    | `["2-x.md"]` | `"adr_not_found"` |
    | `["0002_x.md"]` | `"adr_not_found"` |

- **Why a pin:** it characterises today's glob before cycle 5 replaces it. The existing
  `test_resolve_adr_path_globs_and_refuses_when_absent` covers only found and absent, not
  ambiguity or near misses.
- **Probed:** all five outcomes above are what `resolve_adr_path` returns on `main`, so the test
  passes on arrival.

### Cycle 5 (refactor): resolve_adr_path uses classify_adr_filename

- **Production:** `src/perturb/propose.py` `resolve_adr_path`. Replace the
  `glob(f"docs/adr/{padded}-*.md")` with `sorted(Path(repo_root, "docs", "adr").glob("*.md"))`
  filtered to `classify_adr_filename(p.name) == ("adr", int(ref_id))`. Keep the `ValueError` →
  `adr_not_found` handling and both refusal messages.
- **Guards:** cycle 4's pin, `test_resolve_adr_path_globs_and_refuses_when_absent`, and the
  `propose adr:` CLI tests in `tests/test_cli.py`.
- **Stop rule:** if any guard needs a change to pass, the classifier and the glob disagree. Raise a
  `plan_contradiction` blocker; do not edit the guard.

## Behaviour census

- **Pinned:**
  - ADR / near-miss / other classification: cycle 1.
  - `check` skipping non-ADR names in both loops: cycle 2.
  - The `adr_filename` finding: cycle 3.
  - `resolve_adr_path` outcomes: cycle 4.
- **Specified but not asserted:** the finding's detail and fix text (decision 2).
- **Cross-boundary:** `cli.py` calls the two `check` functions unchanged, so `perturb check` exits 0
  with an index README once cycle 2 lands. No new test doubles.

## Execution

This plan is executed through `tdd-cli`. **You run every command below yourself** — do not ask the
user to start the run. `tdd run start` records which model is executing, resolved from your own
session; a run started by anyone else attributes this work to the wrong agent.

    git checkout -b adr-filenames               # first, before anything else
    tdd doctor                                  # must report healthy: true
    tdd run start --plan tasks/adr-filenames.md # captures baselines, opens cycle 1

If the branch already exists, do not force-checkout and do not pick another name: check it out
only if it carries this plan's commit and no unrelated work, otherwise stop and ask.

Then repeat until done: read `next_action.verb`, do exactly what it says, run `tdd advance`.
Stop when `next_action.terminal` is `true`.

When `next_action.terminal` is `true`, finish the run: render the friction log, commit it, and
raise the PR — see Done-criteria below.

- `tdd advance` is the only command that changes phase. Do not `git add` or `git commit` — the
  tool stages and commits, deriving the file set from the phase.
- The baseline is captured at `run start` and subtracted from later verdicts. Expected summary
  line: `357 passed`.
- Cycles 2 and 3 both extend `adr_findings`. Cycle 2's GREEN adds only the skip, **and nothing
  later**; cycle 3 adds the `adr_filename` finding. Write each cycle's test only when that cycle
  opens.
- Map the verbs the plan will actually hit:
  - `run_sensitivity_check` → `tdd sensitivity begin|check|end`.
  - `annotate_cycle` → `tdd annotate --key --value`. This plan declares no keys beyond the
    reserved `plan_defect` and `friction_note`.
  - `resolve_blocker` → `tdd blocker --kind --detail`. Kinds are free-form labels:
    `plan_contradiction` (the plan disagrees with the code, including cycle 5's stop rule) and
    `environment` (uv/pytest cannot run).
  - `confirm_cycle_applicable` on a non-existent cycle → `tdd cycle skip --reason`.

## Done-criteria

> **Before finishing:** run `tdd log render --out tasks/friction-logs/adr-filenames-friction.md` and `tdd metrics`. Report the plan-fidelity section — declared vs delivered vs skipped — and every integrity event. Do not narrate what the ledger already records.
>
> Then commit the friction log and raise the PR:
>
>     git add tasks/friction-logs/adr-filenames-friction.md
>     git commit -m "docs: friction log for adr-filenames"
>
> Then invoke the **`raise-pr` skill** (`/raise-pr`), which runs the quality gates, pushes the
> branch and opens the PR against `main`. Do not push or call the GitHub API by hand. If a gate
> fails, fix it and re-run the skill — a failed gate is work, not a reason to hand back.

Ancillary docs are deliverables. Each must be non-empty, or the PR body says which cycle dropped
it and why:

- `git diff --stat origin/main -- docs/adr-format.md` (cycles 2, 3)
- `git diff --stat origin/main -- docs/cli.md` (cycle 3)
- `git diff --stat origin/main -- CHANGELOG.md` (cycle 2)
