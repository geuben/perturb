---
closes: 3
cycles:
  - n: 1
    project: perturb
    title: "parse_adr reads amends and amended_by"
    test: "tests/test_adr.py::test_amends_and_amended_by_are_parsed"
    stub_expected: ["src/perturb/adr.py"]
    files: ["src/perturb/adr.py"]
    commit_red: "test: amends and amended_by are parsed from ADR front-matter"
    commit_green: "feat: parse amends and amended_by in ADR front-matter"
    commit_refactor: "refactor: tidy ADR relation parsing"
  - n: 2
    project: perturb
    title: "check validates amends entries like supersedes entries"
    test: "tests/test_check.py::test_amends_entries_are_validated_like_supersedes"
    files: ["src/perturb/check.py"]
    commit_red: "test: amends entries are validated like supersedes"
    commit_green: "feat: check reports invalid and unresolved amends entries"
    commit_refactor: "refactor: share supersedes and amends entry validation"
  - n: 3
    project: perturb
    title: "check reports an amended_by entry that names no ADR"
    test: "tests/test_check.py::test_an_amended_by_entry_that_names_no_adr_is_a_finding"
    files: ["src/perturb/check.py"]
    commit_red: "test: an amended_by entry naming no ADR is a finding"
    commit_green: "feat: check reports unresolved amended_by entries"
    commit_refactor: "refactor: tidy amended_by resolution"
  - n: 4
    project: perturb
    title: "check requires the amending ADR to list the amended one in amends"
    test: "tests/test_check.py::test_amended_by_needs_the_amending_adr_to_list_it_in_amends"
    files: ["src/perturb/check.py"]
    commit_red: "test: amended_by needs a matching amends entry"
    commit_green: "feat: check reports amend_backlink"
    commit_refactor: "refactor: tidy amend backlink check"
  - n: 5
    project: perturb
    title: "check requires the amended ADR to list the amending one in amended_by"
    test: "tests/test_check.py::test_amends_needs_the_earlier_adr_to_list_it_in_amended_by"
    files: ["src/perturb/check.py"]
    commit_red: "test: amends needs a matching amended_by entry"
    commit_green: "feat: check reports amended_by_missing"
    commit_refactor: "refactor: tidy amends symmetry checks"
  - n: 6
    project: perturb
    title: "propose raises amend events to the amended ADR's acknowledgers"
    test: "tests/test_propose.py::test_amends_targets_the_amended_adrs_acknowledgers"
    files: ["src/perturb/propose.py"]
    commit_red: "test: amends targets the amended ADR's acknowledgers"
    commit_green: "feat: propose raises amend events for amends"
    commit_refactor: "refactor: share the supersedes and amends acknowledger pass"
  - n: 7
    project: perturb
    title: "push accepts --kind amend"
    test: "tests/test_cli.py::test_push_verb_accepts_the_amend_kind"
    files: ["src/perturb/cli.py"]
    commit_red: "test: push accepts the amend kind"
    commit_green: "feat: push accepts --kind amend"
    commit_refactor: "refactor: tidy push kind choices"
  - n: 8
    project: perturb
    title: "adr migrate carries whole-ADR amends / amended-by relations from the status line"
    test: "tests/test_adr.py::test_migrate_carries_whole_adr_relations_from_the_status_line"
    files: ["src/perturb/adr.py"]
    commit_red: "test: migrate carries whole-ADR relations from the status line"
    commit_green: "feat: adr migrate carries amends and amended_by from the status line"
    commit_refactor: "refactor: tidy status line relation parsing"
  - n: 9
    project: perturb
    title: "adr migrate warns with each status segment it does not carry verbatim"
    test: "tests/test_adr.py::test_migrate_warns_with_the_status_segments_it_does_not_carry"
    files: ["src/perturb/adr.py"]
    commit_red: "test: migrate warns with the status segments it does not carry"
    commit_green: "feat: adr migrate warns per uncarried status segment, with an amends hint"
    commit_refactor: "refactor: tidy status line warnings"
ancillary_files:
  - "docs/adr-format.md"
  - "docs/cli.md"
  - "docs/concepts.md"
  - "docs/design/02-model.md"
  - "docs/planning.md"
  - "docs/getting-started.md"
  - "docs/configuration.md"
  - "CHANGELOG.md"
---

# ADR format: model amends, not only supersedes

## Context

Issue [#3](https://github.com/geuben/perturb/issues/3). Today the ADR format has one relation
between records, `supersedes`. ADRs in the wild also *amend* an earlier record: a premise or clause
changes, but both records stay in force. In one repository 11 of 24 ADRs carry such a relation on
the status line (`Accepted · 2026-09-08 · resolution premise amended by 0021`,
`amends [ADR-0008](…) — an integration no longer solely owns the presented shape`).
`perturb adr migrate` can only warn about them, the relation is lost from front-matter, and
`perturb check` cannot validate it.

This plan adds:

- `amends: ["adr:0008", "adr:0003#shape-ownership"]` in front-matter, with the same entry grammar
  as `supersedes`;
- `amended_by: ["adr:0021"]` on the earlier record, checked for symmetry in both directions;
- `perturb propose adr:N` raising a new `amend` event kind to the issues that acknowledged events
  from the amended ADR (or the one amended consequence), without touching the earlier ADR's status;
- `perturb push --kind amend`;
- `perturb adr migrate` carrying whole-ADR `amends` / `extends` / `amended by` / `extended … by`
  status annotations into front-matter, and warning about everything else.

Code as it stands (verified on `main` at `d9ad782`):

- `src/perturb/adr.py`: `Adr` frozen dataclass; `parse_adr` reads front-matter; `parse_supersedes_ref`
  parses `adr:NNNN` / `adr:NNNN#id`; `migrate_adr` extracts the status line (joining wrapped
  continuation lines), strips the status word and date, and warns with the remainder as
  `status line annotation not carried into the front-matter: <annotation>`; `_whole_adr_numbers`
  handles the `**Supersedes:**` line.
- `src/perturb/check.py`: `adr_findings` validates `supersedes` entries (`supersedes_invalid`,
  `supersedes_unresolved`) and the `superseded_by` backlink (`supersede_backlink`).
- `src/perturb/propose.py`: `compute_candidates` has a supersedes pass (acknowledged events whose
  source is `adr:MMMM`, `adr:MMMM#…`, or exactly `adr:MMMM#id`) emitting `kind: supersede`,
  `reason: supersedes`, `status: pending`, `source: adr:NNNN`, `detail: adr_rel_path`.
- `src/perturb/cli.py`: `push_parser.add_argument("--kind", choices=[...])`.
- No code branches on event kind anywhere else (`grep -rn '"supersede"' src/perturb` finds only the
  push choices and propose), so `inbox`, `stale` and `ack` need no change for a new kind.

Baseline: `uv run pytest -q` → `357 passed`; `uv run ruff check` → `All checks passed!`.
No `docs/INVARIANTS.md` in this repo.

## Design decisions (locked)

1. **Amendments raise a new `amend` event kind.** Decided by the user. Inbox readers can tell
   "a premise changed, the decision stands" from "replaced". `push --kind` gains `amend`; the kind
   tables in `docs/concepts.md` and `docs/design/02-model.md` gain a row.
2. **`extends` is an alias, not a separate relation.** Decided by the user. Propagation is
   identical. `adr migrate` reads `extends X` as `amends` and `extended … by X` as `amended_by`.
   There is no `extends` front-matter key.
3. **`amends` entries use the `supersedes` grammar**, `adr:NNNN` or `adr:NNNN#consequence-id`, parsed
   with `parse_supersedes_ref`. Decided by evidence: the issue asks for "mirroring `supersedes`",
   and partial amendment is the common real case.
4. **`amended_by` is a list of whole-ADR refs `adr:NNNN`.** A consequence anchor is invalid there.
   Decided by evidence: an earlier ADR can be amended many times (supersession is terminal,
   amendment accumulates), and what was amended is recorded on the amending side.
5. **Front-matter forms for both keys.** Absent or `null` → `[]`. A bare string → a one-element list.
   A list → as-is. Any other scalar → a one-element list holding it, so `check` reports it as
   invalid instead of the parser iterating it. Cycle 1 pins all of these.
6. **`check` enforces symmetry in both directions.** Decided by the user.
   - `amended_by: [adr:M]` on ADR N requires ADR M to have an `amends` entry that parses to
     number N, whole or anchored. The finding is `amend_backlink`, ref `adr:NNNN` (the ADR carrying
     `amended_by`).
   - A resolved `amends` entry on ADR M naming ADR N requires N's `amended_by` to have an entry
     that parses to number M. The finding is `amended_by_missing`, ref = the amends entry as written.
   - Matching compares **parsed numbers**, never strings, so `adr:3`, `adr:0003` and `adr:0003#v`
     are equivalent. Unlike the existing `supersede_backlink`, which compares strings.
   - Neither backlink check runs on an entry that already produced `amends_invalid`,
     `amends_unresolved` or `amended_by_unresolved`.
7. **Finding kinds and text** (only `kind` and `ref` are asserted; the text is specified so the
   executor does not invent it):
   - `amends_invalid`: ref = entry; detail `"{own} amends {entry!r}, not adr:NNNN or adr:NNNN#id"`;
     fix `"write it as adr:NNNN or adr:NNNN#<consequence-id> in {own}"`.
   - `amends_unresolved`: ref = entry; detail `"{own} amends adr:NNNN, which is not in {adr_dir}"`
     or `"adr:NNNN has no consequence {id!r}"`; fix `"correct the amends entry {entry!r} in {own}"`.
   - `amended_by_unresolved`: ref = entry; detail
     `"{own} has amended_by {entry!r}, which is not adr:NNNN naming an ADR in {adr_dir}"`; fix
     `"write it as adr:NNNN naming the amending ADR in {own}"`.
   - `amend_backlink`: ref = own; detail `"{own} has amended_by adr:MMMM but adr:MMMM does not amend {own}"`;
     fix `"add {own} or {own}#<consequence-id> to the amends list of adr:MMMM"`.
   - `amended_by_missing`: ref = entry; detail
     `"{own} amends {entry} but adr:NNNN does not list {own} in amended_by"`; fix
     `"add {own} to amended_by in adr:NNNN"`.
   Here `own` is the ADR whose front-matter carries the key, formatted `adr:NNNN`.
8. **`propose` amends pass.** It sits in `compute_candidates` directly after the supersedes pass and
   mirrors it:
   - Targets: for each parseable `amends` entry, the distinct open non-epic targets of `acknowledged`
     events whose source is `adr:MMMM` or starts with `adr:MMMM#` (whole entry), or equals
     `adr:MMMM#id` (anchored entry).
   - Emits `kind: amend`, `reason: amends`, `status: pending`, `source: adr:NNNN` (the amending ADR),
     `detail: adr_rel_path`.
   - `summary` is `adr.title` for a whole entry, or `f"{adr.title} (amends adr:{M:04d}#{id})"` for an
     anchored one.
   - The earlier ADR's `status` is never read or changed by this pass. `amended_by` raises nothing;
     propagation is driven only by the amending ADR, as with `supersedes`.
9. **`migrate` status-line grammar.** The mechanism, with its traps named:
   - **Segments.** After the status word and date are removed (existing code), split the remaining
     annotation on `·`, `•`, `|`, `;`. Strip each segment of whitespace and of the existing
     `_STATUS_SEPARATORS`, and drop empty ones. *Trap:* do not split on `-`, `—` or `,`. `-` is
     inside `ADR-0008`, `—` introduces a reason, `,` separates a ref list.
   - **ADR ref list.** Remove markdown links, keeping only the link *text* (`_MARKDOWN_LINK`), then
     read refs of the form optional `ADR` + optional `[\s:-]*` + digits.
     - This differs from `_PROSE_ADR_REF`, which requires `ADR`: bare `0021` is the form in the wild.
     - The list is "whole" only when nothing but refs and the joiners `and`, `,`, `&` remains
       (compare `_whole_adr_numbers`).
     - *Trap:* strip link targets *before* reading digits, or `0008-shape.md` yields a ref.
   - **amends form.** A segment whose first word is `amends` or `extends` (case-insensitive).
     - Take the text after the verb up to the first reason separator: ` — `, ` – `, or `: `.
     - If that text is a whole ADR ref list, append `adr:{n:04d}` for each to `amends`.
   - **amended_by form.** Otherwise, a segment containing the word `amended` or `extended` followed
     later by the word `by`.
     - The refs are the text after the last `by`, up to a reason separator.
     - If they form a whole list, append each to `amended_by`.
   - Both lists are de-duplicated in order.
   - **Front-matter.** `migrate_adr` always writes `amends: [...]` and `amended_by: [...]` as JSON
     lists directly after `supersedes:`, empty or not, like `supersedes`.
10. **`migrate` warnings.** At most one status-line warning, as today, with the prefix
    `status line annotation not carried into the front-matter: `. Decided by the user: carry the
    relation *and* warn with the wording.
    - A segment carried with no extra wording contributes nothing.
    - These segments contribute their **full original text, verbatim, links included**:
      - a carried segment with extra wording (a reason after a separator, words before
        `amended`/`extended`, or words between the verb and `by`);
      - any segment not carried.
    - Contributed segments are joined with ` · `.
    - If any contributed segment is an amends-form segment that was not carried, append
      `. To amend one consequence, add amends: ["adr:NNNN#<consequence-id>"]` once. `NNNN` is the
      first ADR ref in that segment (zero-padded), or the literal `NNNN` when it names none. This
      mirrors the existing `**Supersedes:**` hint.
    - No contributed segments → no warning.
11. **No ADR and no knock-on pushes.** This repo keeps no `docs/adr/`; the format is specified in
    `docs/adr-format.md`. Open issues #4 and #6 were checked; neither's planning changes with these
    decisions. #6 edits the ADR glob in `adr_findings`, the same function cycles 2–5 extend, which
    is a merge overlap only, not a design dependency.

## Deliberate scope cuts (do not build)

- **`superseded by ADR N` status annotations are not carried into `superseded_by`.** Premise: the
  issue asks only for amends relations, and carrying `superseded_by` implies a status change. They
  keep warning as today (pinned as a rejected form in cycles 8 and 9).
- **`supersede_backlink` keeps its string comparison.** It misses `adr:2` and `adr:0002#x` spellings.
  The new amends checks compare numbers (decision 6); fixing the supersedes side is a separate
  change. Do not touch `supersede_backlink` in a refactor phase: changing its semantics is a
  blocker, not a refactor.
- **`**Supersedes:**` lines keep requiring the `ADR` prefix.** `_whole_adr_numbers` is left alone.
  The status-line ref grammar accepts bare numbers (decision 9) because `amended by 0021` is the
  observed form. This divergence between the two migrate parsers is deliberate. If a cycle finds it
  must change `_whole_adr_numbers` to go green, stop and raise a `plan_defect` blocker.
- **An amending ADR with no acknowledged targets still needs events or `no-propagation`.**
  `unpropagated_adr_findings` is unchanged, as for a superseding ADR today.
- **`perturb show adr:N` does not display relations.** It does not display `supersedes` either.
- **A bare string for `supersedes` is not normalised.** Decision 5 applies to the new keys only.
- **The local `.claude/skills` texts** listing `--kind decision|scope|friction|supersede` are
  untracked and outside this repository.

## Cycles

### Cycle 1: parse_adr reads amends and amended_by

- **Test:** `tests/test_adr.py::test_amends_and_amended_by_are_parsed`. It is table-driven in the
  style of `test_no_propagation_flag_and_reason_are_parsed`: one dict of cases, one assertion that
  the `{case: (adr.amends, adr.amended_by)}` map equals the expected map. It parses a minimal
  structured ADR with each front-matter extra:
  - absent → `([], [])`
  - `amends: ["adr:0008", "adr:0003#shape"]` + `amended_by: ["adr:0021"]` → `(["adr:0008", "adr:0003#shape"], ["adr:0021"])`
  - `amends: adr:0008` → `(["adr:0008"], [])`
  - `amended_by: adr:0021` → `([], ["adr:0021"])`
  - `amends: 42` → `([42], [])`
  - `amends: null` → `([], [])`
- **Production:** `src/perturb/adr.py`, the `Adr` dataclass (two new fields) and `parse_adr`.
- **Stub (RED commit):** add `amends: list = field(default_factory=list)` and
  `amended_by: list = field(default_factory=list)` as the last `Adr` fields
  (`from dataclasses import dataclass, field`). `parse_adr` does not populate them yet.
- **EXPECTED FAILURE** (probed): ``AssertionError: assert {'absent': ([...ng': ([], [])} == {'absent': ([...['adr:0021'])}``,
  with the `both` and `string` cases differing.
- **Docs:** `docs/adr-format.md` "Format" block gains `amends: []` and `amended_by: []` lines with
  comments; `docs/configuration.md` "Plans and ADRs" names `amends` and `amended_by`.

### Cycle 2: check validates amends entries like supersedes entries

- **Test:** `tests/test_check.py::test_amends_entries_are_validated_like_supersedes`,
  parametrized `entry, expected`.
  - Fixture: `0003-old.md` = `_adr(3, "accepted", 'amended_by: ["adr:0005"]\n')` and
    `0005-new.md` = `_adr(5, "accepted", f'amends: ["{entry}"]\n')`.
  - The assertion filters findings to kinds starting with `amends_`, because later cycles add
    backlink findings for the unresolved cases.
  - Cases: `adr:0003#v` → `[]`; `adr:0003#nope` → `[("amends_unresolved", "adr:0003#nope")]`;
    `adr:0009` → `[("amends_unresolved", "adr:0009")]`; `ADR 3` → `[("amends_invalid", "ADR 3")]`.
- **Production:** `src/perturb/check.py` `adr_findings`, next to the supersedes-entry loop. A shared
  helper taking the relation name is welcome in REFACTOR, but supersedes finding kinds and text must
  not change (existing `test_supersedes_*` tests guard them).
- **EXPECTED FAILURE** (probed): ``AssertionError: assert [] == [('amends_unresolved', 'adr:0003#nope')]``
  (the `adr:0003#v` param passes on arrival; the other three fail).
- **Docs:** `docs/adr-format.md` "Validation in `perturb check`" gains the amends-entry bullet.

### Cycle 3: check reports an amended_by entry that names no ADR

- **Test:** `tests/test_check.py::test_an_amended_by_entry_that_names_no_adr_is_a_finding`,
  parametrized `entry`.
  - Fixture: `0003-old.md` = `_adr(3, "accepted", f'amended_by: ["{entry}"]\n')`, `0005-new.md` =
    `_adr(5, "accepted")`.
  - Asserts all findings (unfiltered) equal `[("amended_by_unresolved", entry)]`.
  - Cases: `adr:0009` (no such ADR), `ADR 5` (malformed), `adr:0005#v` (anchor not allowed).
- **Production:** `src/perturb/check.py` `adr_findings`.
- **EXPECTED FAILURE** (same path as the cycle 2 probe): ``AssertionError: assert [] == [('amended_by_unresolved', 'adr:0009')]``.
- **Docs:** `docs/adr-format.md` validation bullet for `amended_by`.

### Cycle 4: check requires the amending ADR to list the amended one in amends

- **Test:** `tests/test_check.py::test_amended_by_needs_the_amending_adr_to_list_it_in_amends`,
  parametrized over `0005-new.md`'s extra front-matter.
  - `0003-old.md` = `_adr(3, "accepted", 'amended_by: ["adr:0005"]\n')` in every case.
  - Asserts all findings (unfiltered). Cases:
    - `""` → `[("amend_backlink", "adr:0003")]`
    - `'amends: ["adr:0003#v"]\n'` → `[]`
    - `'amends: ["adr:3"]\n'` → `[]` (number match, not string)
- **Production:** `src/perturb/check.py` `adr_findings`. Skip `amended_by` entries that cycle 3
  reported.
- **EXPECTED FAILURE:** ``AssertionError: assert [] == [('amend_backlink', 'adr:0003')]`` (the two
  `[]` params pass on arrival).

### Cycle 5: check requires the amended ADR to list the amending one in amended_by

- **Test:** `tests/test_check.py::test_amends_needs_the_earlier_adr_to_list_it_in_amended_by`,
  parametrized `old_extra, new_extra, expected`. Asserts all findings (unfiltered). Cases:
  - `""`, `'amends: ["adr:0003#v"]\n'` → `[("amended_by_missing", "adr:0003#v")]`
  - `'amended_by: ["adr:0005"]\n'`, `'amends: ["adr:0003#v"]\n'` → `[]`
  - `'amended_by: ["adr:5"]\n'`, `'amends: ["adr:3#v"]\n'` → `[]`
- **Production:** `src/perturb/check.py` `adr_findings`. Skip `amends` entries that cycle 2 reported.
- **EXPECTED FAILURE:** ``AssertionError: assert [] == [('amended_by_missing', 'adr:0003#v')]``.
- **Docs:** `docs/adr-format.md` validation bullet for two-way symmetry.

### Cycle 6: propose raises amend events to the amended ADR's acknowledgers

- **Test:** `tests/test_propose.py::test_amends_targets_the_amended_adrs_acknowledgers`,
  parametrized `amends, expected` (add `import dataclasses` and `import pytest` to the file).
  - Acknowledged events: `adr:0001#shape` → `#29`, `adr:0001#other` → `#31`,
    `adr:0001#shape` → `#30` (closed).
  - `adr = dataclasses.replace(_adr(adr_id=2), amends=amends)`, then `compute_candidates` with
    `GRAPH_ISSUES` and `adr_rel_path="docs/adr/0002-per-trip.md"`.
  - Assert the list of `(target, kind, reason, status, source, detail, summary)` equals
    `[(t, "amend", "amends", "pending", "adr:0002", "docs/adr/0002-per-trip.md", s) for t, s in expected]`.
  - Cases: `["adr:0001#shape"]` → `[("#29", "Per-trip sync (amends adr:0001#shape)")]`;
    `["adr:0001"]` → `[("#29", "Per-trip sync"), ("#31", "Per-trip sync")]`.
- **Production:** `src/perturb/propose.py` `compute_candidates`, a new pass directly after the
  supersedes pass (decision 8). REFACTOR may extract a helper shared with the supersedes pass;
  `test_supersedes_targets_prior_acknowledgers` and
  `test_supersedes_a_single_consequence_targets_only_its_acknowledgers` guard it.
- **EXPECTED FAILURE** (probed): ``AssertionError: assert [] == [('#29', 'amend', ...)]``.
- **Docs:**
  - `docs/adr-format.md`: two rows in "What changes for `propose adr:`"
    (`amends: [adr:M]` / `amends: [adr:M#id]` → pending, kind `amend`, reason `amends`), and a new
    section "Amending an ADR" after "Superseding part of an ADR". That section says the earlier ADR
    keeps its status, carries `amended_by`, and that `extends` is written as `amends`.
  - `docs/concepts.md`: kind table row `amend` ("the source changes a premise or clause of it; the
    earlier decision still stands"), and "Where events come from" names `amends:`.
  - `docs/design/02-model.md`: kind table row `amend` (typical source `adr`).

### Cycle 7: push accepts --kind amend

- **Test:** `tests/test_cli.py::test_push_verb_accepts_the_amend_kind`.
  - Same setup as `test_push_verb_creates_pending_event_as_json`
    (`_make_push_transport([_make_page([_make_issue_node(29)])])`, `root=tmp_path / ".perturb"`,
    `repo_root=tmp_path`), running
    `main(["push", "--from", "5", "--to", "29", "--kind", "amend", "s", "--json"], ...)`.
  - Load `EventStore(tmp_path / "perturb" / "events")` and assert
    `(code, [e.kind for e in events]) == (0, ["amend"])`.
- **Production:** `src/perturb/cli.py`, the `--kind` `choices` list on `push_parser`.
- **EXPECTED FAILURE** (probed: argparse exits 2 with `invalid choice: 'amend'`):
  ``AssertionError: assert (2, []) == (0, ['amend'])``.
- **Docs:** `docs/cli.md` push heading `--kind decision|scope|friction|supersede|amend`;
  `docs/planning.md` "Kinds" bullet adds `amend` changes a premise of M's constraint while it stands;
  `docs/getting-started.md` kind list adds `amend`.

### Cycle 8: adr migrate carries whole-ADR relations from the status line

- **Test:** `tests/test_adr.py::test_migrate_carries_whole_adr_relations_from_the_status_line`,
  parametrized `annotation, relations`.
  - Input: `"# ADR 0021 — Resolution\n\n**Status:** Accepted · 2026-09-10 · {annotation}\n\n## Context\n\nPROSE.\n\n## Consequences\n\n- X happens.\n"`.
  - Asserts `(adr.amends, adr.amended_by) == relations` on `parse_adr(migrate_adr(text, adr_id=21)[0])`.
  - Accepted forms:

    | annotation | relations |
    |---|---|
    | `amends ADR 0008` | `(["adr:0008"], [])` |
    | `amends [ADR-0008](0008-shape.md)` | `(["adr:0008"], [])` |
    | `Extends ADR:4 and [0005](0005-x.md)` | `(["adr:0004", "adr:0005"], [])` |
    | `amends 8, ADR 9 & ADR-10` | `(["adr:0008", "adr:0009", "adr:0010"], [])` |
    | `amends [ADR-0008](0008-shape.md) — an integration no longer solely owns the presented shape` | `(["adr:0008"], [])` |
    | `extends ADR 0008: adds panel geometry` | `(["adr:0008"], [])` |
    | `amended by ADR 0021` | `([], ["adr:0021"])` |
    | `resolution premise amended by 0021` | `([], ["adr:0021"])` |
    | `extended to physical geometry by [0022](0022-panel-geometry.md)` | `([], ["adr:0022"])` |
    | `amends ADR 0008 · amended by ADR 0023` | `(["adr:0008"], ["adr:0023"])` |

  - Rejected forms (carry nothing):

    | annotation | relations |
    |---|---|
    | `amends ADR-0002's premise` | `([], [])` |
    | `amends ADR-0008#shape` | `([], [])` |
    | `amends [the shape section](0008-shape.md#shape)` | `([], [])` |
    | `amended by the 2024 review` | `([], [])` |
    | `amended in review` | `([], [])` |
    | `storage engine superseded by ADR 0005` | `([], [])` |

- **Production:** `src/perturb/adr.py` `migrate_adr` (status-line block and front-matter string),
  plus a private helper for decision 9's grammar.
- **Increment: carrying relations only.** The warning text is cycle 9's; leave the existing
  `annotation` warning exactly as it is.
- **EXPECTED FAILURE** (probed with the cycle 1 fields in place): ``AssertionError: assert ([], []) == (['adr:0008'], [])``
  (the rejected params pass on arrival).
- **Existing tests that must stay green unchanged:** `test_migrate_treats_a_wrapped_status_line_as_one_annotation`,
  `test_migrate_keeps_preamble_prose_and_warns_about_a_status_annotation`,
  `test_migrate_roundtrips_through_parser`.
- **Docs:** `docs/adr-format.md` "Migration for existing ADRs" gains a step for status-line
  relations (the accepted forms above, `extends` read as `amends`).

### Cycle 9: adr migrate warns with the status segments it does not carry

- **Test:** `tests/test_adr.py::test_migrate_warns_with_the_status_segments_it_does_not_carry`,
  parametrized `annotation, warnings`. Same input template as cycle 8; asserts
  `migrate_adr(text, adr_id=21)[1] == warnings`.
  - `P = "status line annotation not carried into the front-matter: "`.
  - Cases:

    | annotation | warnings |
    |---|---|
    | `amends ADR 0008` | `[]` |
    | `amended by ADR 0021` | `[]` |
    | `resolution premise amended by 0021` | `[P + "resolution premise amended by 0021"]` |
    | `amends [ADR-0008](0008-shape.md) — an integration no longer solely owns the presented shape` | `[P + <the annotation verbatim>]` |
    | `amends ADR 0008 · reviewed quarterly` | `[P + "reviewed quarterly"]` |
    | `amends ADR-0002's premise` | `[P + "amends ADR-0002's premise" + '. To amend one consequence, add amends: ["adr:0002#<consequence-id>"]']` |
    | `storage engine superseded by ADR 0005` | `[P + "storage engine superseded by ADR 0005"]` |

- **Production:** `src/perturb/adr.py` `migrate_adr`, the status-line warning (decision 10).
- **Increment: the warning only.** Carrying was cycle 8's.
- **EXPECTED FAILURE** (probed: today `amends ADR 0008` yields one warning quoting the whole
  annotation): ``AssertionError: assert ['status line annotation not carried into the front-matter: amends ADR 0008'] == []``.
- **Existing tests that must stay green unchanged:**
  - `test_migrate_treats_a_wrapped_status_line_as_one_annotation`. Probed: its warning quotes the
    raw annotation, links included. Under decision 10 both segments contribute verbatim, so one
    warning still contains `2560x720 on VideoCore IV` and `0022-panel-geometry.md`.
  - `test_migrate_keeps_preamble_prose_and_warns_about_a_status_annotation`.
  - `test_adr_migrate_rewrites_file_in_place`.
- **Docs:**
  - `docs/cli.md` `adr migrate`: `warnings` lists status segments not carried, including carried
    relations whose wording would be lost.
  - `CHANGELOG.md` `[Unreleased]` gains an `### Added` entry covering `amends`/`amended_by`, the
    `amend` kind, the check findings and migrate carrying.

### Behaviour census

Every behaviour promised above is pinned by a cycle test, or listed as a scope cut. Nothing is
PROSE-ONLY: finding `detail`/`fix` text is specified in decision 7 but deliberately not asserted.
The `amends`/`amended_by` keys are always written by migrate (decision 9); roundtrip equality in
cycle 8 covers the values, and the key layout is not asserted. Cross-boundary: `amend` events
flow through `EventStore`, `inbox` and `stale` unchanged, since none branch on kind (verified by
grep). Test doubles: none new; cycle 7 reuses the existing fake GitHub transport.

## Execution

This plan is executed through `tdd-cli`. **You run every command below yourself** — do not ask the
user to start the run. `tdd run start` records which model is executing, resolved from your own
session; a run started by anyone else attributes this work to the wrong agent.

    git checkout -b adr-amends                  # first, before anything else
    tdd doctor                                  # must report healthy: true
    tdd run start --plan tasks/adr-amends.md    # captures baselines, opens cycle 1

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
- Consecutive cycles 2–5 all extend `adr_findings`, and 8–9 both extend `migrate_adr`. Each GREEN
  adds only its own increment, **and nothing later**:
  - cycle 2 adds `amends_invalid`/`amends_unresolved`;
  - 3 adds `amended_by_unresolved`;
  - 4 adds `amend_backlink`;
  - 5 adds `amended_by_missing`;
  - 8 carries relations into front-matter but leaves the warning text alone;
  - 9 rewrites the warning.
  Write each cycle's test only when that cycle opens.
- Map the verbs the plan will actually hit:
  - `run_sensitivity_check` → `tdd sensitivity begin|check|end`.
  - `annotate_cycle` → `tdd annotate --key --value`. This plan declares no keys beyond the
    reserved `plan_defect` and `friction_note`.
  - `resolve_blocker` → `tdd blocker --kind --detail`, with kinds `plan_defect` (the plan
    contradicts the code or a scope-cut premise fails) and `environment` (uv/pytest cannot run).
  - `confirm_cycle_applicable` on a non-existent cycle → `tdd cycle skip --reason`.

## Done-criteria

> **Before finishing:** run `tdd log render --out tasks/friction-logs/adr-amends-friction.md` and `tdd metrics`. Report the plan-fidelity section — declared vs delivered vs skipped — and every integrity event. Do not narrate what the ledger already records.
>
> Then commit the friction log and raise the PR:
>
>     git add tasks/friction-logs/adr-amends-friction.md
>     git commit -m "docs: friction log for adr-amends"
>
> Then invoke the **`raise-pr` skill** (`/raise-pr`), which runs the quality gates, pushes the
> branch and opens the PR against `main`. Do not push or call the GitHub API by hand. If a gate
> fails, fix it and re-run the skill — a failed gate is work, not a reason to hand back.

Ancillary docs are deliverables. Each of these must be non-empty, or the PR body says which cycle
dropped it and why:

- `git diff --stat origin/main -- docs/adr-format.md` (cycles 1, 2, 3, 5, 6, 8)
- `git diff --stat origin/main -- docs/configuration.md` (cycle 1)
- `git diff --stat origin/main -- docs/concepts.md` (cycle 6)
- `git diff --stat origin/main -- docs/design/02-model.md` (cycle 6)
- `git diff --stat origin/main -- docs/cli.md` (cycles 7, 9)
- `git diff --stat origin/main -- docs/planning.md` (cycle 7)
- `git diff --stat origin/main -- docs/getting-started.md` (cycle 7)
- `git diff --stat origin/main -- CHANGELOG.md` (cycle 9)

`uv run python scripts/check_doc_links.py` must pass (the new "Amending an ADR" section adds an
anchor).
