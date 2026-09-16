---
closes: 7
cycles:
  - n: 1
    project: perturb
    title: "a bare-string supersedes is read as one ref, not one per character"
    test: "tests/test_check.py::test_a_bare_string_supersedes_is_read_as_one_ref"
    files: ["src/perturb/adr.py"]
    commit_red: "test: a bare-string supersedes is read as one ref"
    commit_green: "fix: normalise a bare-string supersedes to a one-element list"
    commit_refactor: "docs: document the bare-string supersedes spelling"
  - n: 2
    project: perturb
    title: "supersede_backlink matches supersedes entries by parsed ADR number"
    test: "tests/test_check.py::test_supersede_backlink_accepts_equivalent_ref_spellings"
    files: ["src/perturb/check.py"]
    commit_red: "test: supersede_backlink accepts equivalent ADR ref spellings"
    commit_green: "fix: match the supersede backlink by parsed ADR number"
    commit_refactor: "docs: document which supersedes spellings satisfy the backlink"
  - n: 3
    project: perturb
    title: "a one-element list superseded_by is normalised to its string"
    test: "tests/test_adr.py::test_a_one_element_list_superseded_by_is_normalised"
    files: ["src/perturb/adr.py"]
    commit_red: "test: a one-element list superseded_by is normalised"
    commit_green: "fix: normalise a one-element list superseded_by to its entry"
    commit_refactor: "refactor: tidy ADR relation normalisation"
  - n: 4
    project: perturb
    title: "check reports an unresolvable superseded_by instead of passing it over"
    test: "tests/test_check.py::test_an_unresolvable_superseded_by_is_a_finding"
    files: ["src/perturb/check.py"]
    commit_red: "test: an unresolvable superseded_by is a finding"
    commit_green: "feat: check reports superseded_by_unresolved"
    commit_refactor: "docs: document superseded_by_unresolved"
ancillary_files:
  - "docs/adr-format.md"
  - "CHANGELOG.md"
---

# check: supersede_backlink misses equivalent ADR ref spellings

## Context

Issue [#7](https://github.com/geuben/perturb/issues/7), blocked by #3 (closed, merged as
[#16](https://github.com/geuben/perturb/pull/16)).

`perturb check` matches an ADR's `superseded_by` against the newer ADR's `supersedes` list by
**string equality** (`supersede_backlink`, in `adr_findings` in `src/perturb/check.py`), so
equivalent spellings of the same ADR do not match. #3 gave the parallel `amends` / `amended_by`
relation number-based matching and bare-string normalisation, so the two relations now behave
differently on identical input. #3's plan deliberately routed that fix here
(ledger event `01M2KJEVPKT1C3CFZAW240D26N`, `kind: scope`, from `plan:adr-amends`).

Three defects, all reproduced by probe on `main` at `9c0802b` (ADR 0002 `status: superseded`,
`superseded_by: adr:0005`; ADR 0005 supersedes it):

| input | today |
|---|---|
| `supersedes: ["adr:0002"]` | no finding (correct) |
| `supersedes: ["adr:2"]` | `supersede_backlink` — wrong |
| `supersedes: ["adr:0002#v"]` | `supersede_backlink` — wrong |
| `supersedes: adr:0002` (bare string) | eight `supersedes_invalid` findings, one per character |
| `superseded_by: ADR 5` | **no finding at all** — silently skipped |
| `superseded_by: adr:0009` (no such ADR) | **no finding at all** — silently skipped |
| `superseded_by: adr:0005#v` (anchored) | **no finding at all** — silently skipped |
| `superseded_by: ["adr:0005"]` | `TypeError: expected string or bytes-like object, got 'list'` |

Code as it stands (`9c0802b`):

- `src/perturb/adr.py`: `Adr` is a frozen dataclass with `supersedes: list` and
  `superseded_by: str | None`. `parse_adr` reads `supersedes` as `fm.get("supersedes") or []` —
  no normalisation — and `superseded_by` as `fm.get("superseded_by")` raw. The local helper
  `_as_list` inside `parse_adr` already normalises `amends` and `amended_by` (#3, decision 5).
  `parse_supersedes_ref(entry)` returns `(number, consequence_id | None)` for `adr:NNNN` and
  `adr:NNNN#id`, and `None` for anything else including a non-`str`.
- `src/perturb/check.py`: the backlink block near the end of `adr_findings` resolves
  `adr.superseded_by` with `parse_ref` (from `src/perturb/refs.py`, which calls `re.fullmatch`
  on the value — hence the `TypeError` on a list), `continue`s on `RefError`, on a non-`adr`
  kind and on a target missing from the directory, then compares the literal string
  `f"adr:{adr.id:04d}"` against `target.supersedes`.
  The `amended_by_unresolved` block above it is the shape this plan mirrors: it uses
  `parse_supersedes_ref`, rejects anchored refs, and emits a finding with `"ref": str(entry)`.
- `src/perturb/propose.py`: `compute_candidates` iterates `adr.supersedes`, so a bare-string
  `supersedes` makes it iterate characters and raise no `supersede` events. It takes an `Adr`
  and is fixed by the same `parse_adr` normalisation (cycle 1).

Baseline: `uv run pytest -q` → `429 passed`; `uv run ruff check` → `All checks passed!`.
No `docs/INVARIANTS.md` in this repo.

## Design decisions (locked)

1. **`supersede_backlink` compares parsed ADR numbers, not strings.** The newer ADR's
   `supersedes` entries are resolved with `parse_supersedes_ref` and the earlier ADR's own
   number is looked for among the resulting numbers. Decided by the issue, which pins `adr:2`
   and `adr:0002#v` as spellings that must satisfy the backlink, and by parity with
   `amend_backlink`, which #3 already implemented exactly this way
   (`{parse_supersedes_ref(e)[0] for e in amender.amends if parse_supersedes_ref(e) is not None}`).
2. **An anchored `supersedes` entry satisfies the whole-ADR backlink.** `supersedes: ["adr:0002#v"]`
   on ADR 5 clears `supersede_backlink` for ADR 2. Decided by the issue's probe table and by
   parity with `amend_backlink`, whose number set deliberately does not filter anchored entries.
   The backlink check asks "does the newer ADR point back at this one at all", and
   `supersedes_unresolved` separately validates that the named consequence exists.
3. **A bare-string `supersedes` is normalised to a one-element list in `parse_adr`.**
   `supersedes: adr:0001` becomes `["adr:0001"]`, via the existing `_as_list` helper. Decided by
   the issue and by parity with #3 decision 5, which did this for `amends`/`amended_by`.
   Normalising at parse time fixes every consumer at once: `check` stops reporting one
   `supersedes_invalid` per character and `propose` stops iterating characters.
4. **`superseded_by` is singular and stays singular; a one-element list is unwrapped.**
   `superseded_by: ["adr:0005"]` parses as `"adr:0005"`; an empty list parses as `None` (so
   `superseded_no_link` fires as it does for an absent key). Decided by the user. It is the
   mirror image of decision 3 — tolerate the sibling keys' spelling — while keeping the field a
   scalar and never silently dropping an entry the author wrote.
5. **A list of two or more entries is a finding, not a silent truncation.**
   `superseded_by: ["adr:0005", "adr:0006"]` stays a list on the `Adr` and `check` reports
   `superseded_by_unresolved`. Decided by the user, rejecting "take the first entry": silently
   discarding an ADR the author named is the same class of loss this issue exists to fix.
6. **An unresolvable `superseded_by` becomes a `superseded_by_unresolved` finding**, mirroring
   `amended_by_unresolved` from #3: same kind-name shape, `"ref": str(entry)`, and a detail
   naming the owning ADR. Decided by the issue. Today all four rejected forms are skipped in
   silence, which means an ADR declaring `status: superseded` can pass `check` with no backlink
   verified at all.
7. **`superseded_by` accepts a whole-ADR ref only; an anchor is rejected.**
   `superseded_by: adr:0005#v` is `superseded_by_unresolved`. Decided by the user, by parity with
   `amended_by`, which #3 documented as "whole-ADR ref only". Asymmetric with decision 2 on
   purpose: `supersedes` may name one consequence, `superseded_by` records that *this whole
   record* was replaced.
8. **Resolution short-circuits the backlink.** When `superseded_by` is unresolvable the cycle
   reports `superseded_by_unresolved` and does not also report `supersede_backlink` for the same
   ADR — one defect, one finding, exactly as the `amended_by` blocks do.

## Deliberate scope cuts (do not build)

- **`superseded_by` is not made plural.** Premise: an ADR replaced by two ADRs is not a shape the
  issue raises, and `status: superseded` + one replacement is the documented model
  (`docs/adr-format.md`, "Superseding part of an ADR"). Decision 5 turns the plural spelling into
  a finding rather than a supported form. Re-evaluation trigger: if a cycle finds an existing
  ADR or test in this repo that relies on a plural `superseded_by`, stop and raise a
  `plan_defect` blocker — do not widen the field to a list to make a cycle green.
- **`supersede` events for equivalent spellings are not re-examined.** Premise: `propose`
  already resolves `supersedes` entries through `parse_supersedes_ref`, so it matches by number
  today; only `check`'s backlink used string equality. Cycle 1 restores `propose` for the
  bare-string spelling as a side effect of parse-time normalisation. Re-evaluation trigger: if
  cycle 1's probe or GREEN shows `propose` mis-resolving `adr:2` or `adr:0002#v`, raise a
  `plan_defect` blocker rather than editing `propose.py` under this plan's `files`.
- **`**Supersedes:**` body-line parsing in `adr migrate` is untouched.** Premise: #3's plan
  routed the migrate-parser divergence to #8, and issue #12 owns the remaining migrate work.
  `_whole_adr_numbers` and `migrate_adr` are out of scope. If a cycle finds it must change either
  to go green, stop and raise a `plan_defect` blocker.
- **No `superseded_by_missing` symmetry check** (the mirror of `amended_by_missing`: ADR 5
  supersedes ADR 2, therefore ADR 2 must carry `superseded_by`). Premise: the issue asks only
  that the existing backlink match equivalent spellings, and a whole-ADR supersede already gets
  `superseded_no_link` from the other direction whenever the old ADR's status is `superseded`.
  Adding it would fire on every partial (`adr:0002#v`) supersede, where the earlier ADR
  deliberately keeps `status: accepted`.

## Cycles

### Cycle 1 — a bare-string `supersedes` is read as one ref

**Behaviour.** `parse_adr` normalises a `supersedes` value written as a bare string into a
one-element list, so every consumer sees a list of refs.

**Test** — `tests/test_check.py::test_a_bare_string_supersedes_is_read_as_one_ref`, one
assertion: an ADR directory whose newer ADR carries `supersedes: adr:0002` (no brackets, no
quotes) and whose ADR 2 is `status: superseded`, `superseded_by: adr:0005`, yields no findings
at all. Build it with the module's existing `_adr(i, status, extra_fm)` helper and
`adr_findings(adr_dir, {"issues": {}})`, as `test_superseded_by_target_missing_backlink_is_a_finding`
does.

**Production target** — `parse_adr` in `src/perturb/adr.py`: the `supersedes=fm.get("supersedes") or []`
argument becomes `supersedes=_as_list(fm.get("supersedes"))`, reusing the `_as_list` closure
already defined a few lines above it for `amends`. That increment **and nothing later** — leave
`superseded_by` alone (cycle 3) and `check.py` untouched (cycles 2 and 4).

**EXPECTED FAILURE** — verified by probe: the assertion fails with the eight per-character
findings, `assert [('supersedes_invalid', 'a'), ('supersedes_invalid', 'd'), ('supersedes_invalid', 'r'), ('supersedes_invalid', ':'), ('supersedes_invalid', '0'), ('supersedes_invalid', '0'), ('supersedes_invalid', '0'), ('supersedes_invalid', '2')] == []`.

**Docs (refactor phase)** — `docs/adr-format.md`: note in the validation list that `supersedes`
may be written as a bare string and is read as a one-element list.

### Cycle 2 — `supersede_backlink` matches by parsed ADR number

**Behaviour.** The backlink from `superseded_by` to the newer ADR's `supersedes` list is
satisfied by any spelling that names the same ADR.

**Test** — `tests/test_check.py::test_supersede_backlink_accepts_equivalent_ref_spellings`, one
assertion: for each of the three accepted spellings on ADR 5 — `["adr:0002"]`, `["adr:2"]`,
`["adr:0002#v"]` — an ADR 2 with `superseded_by: adr:0005` yields no findings. Drive the three
spellings from a list inside the test body and collect `(spelling, findings)` pairs, so the
assertion names the spelling that failed. Each spelling gets its own `tmp_path` subdirectory.

**Production target** — the backlink block in `adr_findings`, `src/perturb/check.py`:
`expected_back not in target.supersedes` becomes a membership test of `adr.id` in
`{parse_supersedes_ref(e)[0] for e in target.supersedes if parse_supersedes_ref(e) is not None}`,
the same expression `amend_backlink` uses. That increment **and nothing later** — the
`superseded_by` resolution above it keeps using `parse_ref` and keeps `continue`-ing silently
until cycle 4.

**EXPECTED FAILURE** — verified by probe: `adr:2` and `adr:0002#v` each produce
`[('supersede_backlink', 'adr:0002')]` where `[]` is expected; the first spelling (`adr:0002`)
already passes, so the assertion fails on the second row.

**Rejected spellings, already covered** — `supersedes: ["ADR 3"]` is `supersedes_invalid`
(`test_supersedes_a_malformed_entry_is_a_finding`) and `supersedes: ["adr:0009"]` is
`supersedes_unresolved` (`test_supersedes_an_unknown_adr_is_a_finding`). Both keep firing, and
neither is a backlink match, because `parse_supersedes_ref` returns `None` for the first and the
number set contains `9`, not `2`, for the second. Do not change either test.

**Docs (refactor phase)** — `docs/adr-format.md`: state in the validation list that the backlink
matches by ADR number, so `adr:2`, `adr:0002` and `adr:0002#id` are equivalent for it.

### Cycle 3 — a one-element list `superseded_by` is normalised

**Behaviour.** `parse_adr` unwraps `superseded_by: ["adr:0007"]` to `"adr:0007"`, and reads an
empty list as `None`.

**Test** — `tests/test_adr.py::test_a_one_element_list_superseded_by_is_normalised`, one
assertion: `parse_adr(<adr with superseded_by: ["adr:0007"]>).superseded_by == "adr:0007"`.
Model it on `test_superseded_by_is_parsed` in the same module.

**Production target** — `parse_adr` in `src/perturb/adr.py`: `superseded_by=fm.get("superseded_by")`
becomes a normalisation that returns the single entry of a one-element list, `None` for an empty
list or an absent key, and the value unchanged otherwise (so a two-element list reaches `check`
intact for cycle 4 to report). That increment **and nothing later** — `check.py` is untouched
here; a multi-element list still raises `TypeError` in `check` until cycle 4, which is that
cycle's RED.

**EXPECTED FAILURE** — verified by probe: `parse_adr` returns the list unchanged, so the test
fails with `assert ['adr:0007'] == 'adr:0007'`.

### Cycle 4 — `check` reports an unresolvable `superseded_by`

**Behaviour.** A `superseded_by` that is not a whole-ADR ref naming an ADR in the directory is a
`superseded_by_unresolved` finding instead of being skipped in silence or crashing.

**Test** — `tests/test_check.py::test_an_unresolvable_superseded_by_is_a_finding`, one assertion:
for each rejected form on ADR 2 — `ADR 5` (malformed), `adr:0009` (no such ADR), `adr:0005#v`
(anchored) and `["adr:0005", "adr:0006"]` (plural) — `adr_findings` returns exactly one finding
whose `kind` is `superseded_by_unresolved`. Drive the four forms from a list in the test body and
assert on the collected `(form, kinds)` pairs. ADR 5 in the fixture carries
`supersedes: ["adr:0002"]`, so no `supersede_backlink` can be in the result and the assertion is
about resolution alone.

**Production target** — the backlink block in `adr_findings`, `src/perturb/check.py`: resolve
`adr.superseded_by` with `parse_supersedes_ref` instead of `parse_ref` (it returns `None` for a
non-`str`, which removes the `TypeError` path, and exposes the anchor so an anchored ref can be
rejected). Emit `{"kind": "superseded_by_unresolved", "ref": str(adr.superseded_by), "detail": ...,
"fix": ...}` when the value is not a whole-ADR ref or names an ADR not in `adr_dir`, then
`continue` — decision 8 — and keep the number-set backlink test from cycle 2 for the resolvable
case. Drop the now-unused `parse_ref`/`RefError` import from that block only if nothing else in
the module uses them (`affects` resolution above does — check before deleting the import).

**EXPECTED FAILURE** — verified by probe: `ADR 5`, `adr:0009` and `adr:0005#v` each yield `[]`
today, so the test fails on the first row with `assert ('ADR 5', []) == ('ADR 5', ['superseded_by_unresolved'])`.
The fourth row is the one that raises `TypeError: expected string or bytes-like object, got 'list'`
today; it is not reached in RED and is a GREEN correctness requirement.

**Existing coverage to keep green** — `tests/test_check.py::test_superseded_by_target_missing_backlink_is_a_finding`
(`superseded_by: adr:0001`, resolvable, target lists nothing) must still report exactly
`supersede_backlink`, and `test_unpropagated_accepted_adr_is_a_finding` uses
`superseded_by: adr:0002` where ADR 2 exists. Neither is in `modifies_tests`: if a cycle cannot go
green without changing them, the plan is wrong — raise a `plan_defect` blocker.

**Docs (refactor phase)** — `docs/adr-format.md`: add `superseded_by_unresolved` to the
"Validation in `perturb check`" list, and state that `superseded_by` is a whole-ADR ref
(`adr:NNNN`, or a one-element list of one) with no consequence anchor.
`CHANGELOG.md`: one `### Fixed` entry under `[Unreleased]` for the backlink spellings and the
bare-string `supersedes`, and one `### Added` entry for `superseded_by_unresolved`.

## Execution

This plan is executed through `tdd-cli`. **You run every command below yourself** — do not ask the
user to start the run. `tdd run start` records which model is executing, resolved from your own
session; a run started by anyone else attributes this work to the wrong agent.

    git checkout -b supersede-backlink-ref-spellings   # first, before anything else
    tdd doctor                                         # must report healthy: true
    tdd run start --plan tasks/supersede-backlink-ref-spellings.md

If the branch already exists, do not force-checkout and do not pick another name: check it out
only if it carries this plan's commit and no unrelated work, otherwise stop and ask.

Then repeat until done: read `next_action.verb`, do exactly what it says, run `tdd advance`.
Stop when `next_action.terminal` is `true`.

When `next_action.terminal` is `true`, finish the run: render the friction log, commit it, and
raise the PR — see Done-criteria below.

- `tdd advance` is the only command that changes phase. Do not `git add` or `git commit` — the
  tool stages and commits, deriving the file set from the phase.
- The baseline is captured at `run start` and subtracted from later verdicts. Expected summary
  line: `429 passed`.
- Cycles 1 and 3 both edit `parse_adr`; cycles 2 and 4 both edit the backlink block of
  `adr_findings`. Each GREEN adds only its own increment, **and nothing later**:
  - cycle 1 normalises `supersedes` only;
  - cycle 2 changes the backlink comparison to parsed numbers only, leaving `superseded_by`
    resolution on `parse_ref` and silent;
  - cycle 3 normalises `superseded_by` only, leaving `check.py` alone;
  - cycle 4 replaces the resolution and adds the `superseded_by_unresolved` finding.
  Write each cycle's test only when that cycle opens.
- Map the verbs the plan will actually hit:
  - `run_sensitivity_check` → `tdd sensitivity begin|check|end`.
  - `annotate_cycle` → `tdd annotate --key --value`. This plan declares no keys beyond the
    reserved `plan_defect` and `friction_note`.
  - `resolve_blocker` → `tdd blocker --kind --detail`, with kinds `plan_defect` (the plan
    contradicts the code, or a scope-cut re-evaluation trigger fires) and `environment`
    (uv/pytest cannot run).
  - `confirm_cycle_applicable` on a non-existent cycle → `tdd cycle skip --reason`.

## Done-criteria

> **Before finishing:** run `tdd log render --out tasks/friction-logs/supersede-backlink-ref-spellings-friction.md` and `tdd metrics`. Report the plan-fidelity section — declared vs delivered vs skipped — and every integrity event. Do not narrate what the ledger already records.
>
> Then commit the friction log and raise the PR:
>
>     git add tasks/friction-logs/supersede-backlink-ref-spellings-friction.md
>     git commit -m "docs: friction log for supersede-backlink-ref-spellings"
>
> Then invoke the **`raise-pr` skill** (`/raise-pr`), which runs the quality gates, pushes the
> branch and opens the PR against `main`. Do not push or call the GitHub API by hand. If a gate
> fails, fix it and re-run the skill — a failed gate is work, not a reason to hand back.

Ancillary docs are deliverables. Each of these must be non-empty, or the PR body says which cycle
dropped it and why:

- `git diff --stat origin/main -- docs/adr-format.md` (cycles 1, 2, 4)
- `git diff --stat origin/main -- CHANGELOG.md` (cycle 4)

`uv run python scripts/check_doc_links.py` must pass.
