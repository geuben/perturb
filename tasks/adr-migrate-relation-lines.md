---
closes: 12
cycles:
  - n: 1
    project: perturb
    pin_cycle: true
    title: "a line whose label is not a relation label keeps today's treatment"
    test: "tests/test_adr.py::test_migrate_leaves_a_non_relation_label_line_alone"
    files: []
    commit_pin: "test: pin how migrate treats non-relation label lines"
  - n: 2
    project: perturb
    title: "a whole-ADR **Amends:** / **Amended by:** line is carried into front-matter"
    test: "tests/test_adr.py::test_migrate_carries_a_relation_line_in_every_accepted_label_form"
    files: ["src/perturb/adr.py"]
    commit_red: "test: migrate carries a relation line in every accepted label form"
    commit_green: "feat: adr migrate carries **Amends:** and **Amended by:** lines"
    commit_refactor: "refactor: tidy relation line label matching"
  - n: 3
    project: perturb
    title: "a wrapped relation line is read as one line"
    test: "tests/test_adr.py::test_migrate_joins_a_wrapped_relation_line"
    files: ["src/perturb/adr.py"]
    commit_red: "test: migrate joins a wrapped relation line"
    commit_green: "feat: adr migrate joins a relation line's continuation lines"
    commit_refactor: "refactor: share the continuation-line join"
  - n: 4
    project: perturb
    title: "a relation line with a reason clause carries its refs, keeps the line, and warns"
    test: "tests/test_adr.py::test_migrate_carries_a_relation_line_with_a_reason_clause_and_warns"
    files: ["src/perturb/adr.py"]
    commit_red: "test: migrate carries a relation line with a reason clause and warns"
    commit_green: "feat: adr migrate carries a relation line whose refs carry an explanation"
    commit_refactor: "refactor: tidy reason clause splitting"
  - n: 5
    project: perturb
    title: "a relation line that names more than whole ADRs carries nothing and warns"
    test: "tests/test_adr.py::test_migrate_keeps_and_warns_about_a_partial_relation_line"
    files: ["src/perturb/adr.py"]
    commit_red: "test: migrate keeps and warns about a partial relation line"
    commit_green: "feat: adr migrate warns about a partial relation line with a consequence hint"
    commit_refactor: "refactor: share the partial relation line warning"
  - n: 6
    project: perturb
    title: "status-line and body-line relations merge without duplicates"
    test: "tests/test_adr.py::test_migrate_merges_status_line_and_body_line_relations"
    files: ["src/perturb/adr.py"]
    commit_red: "test: status line and body line relations merge without duplicates"
    commit_green: "feat: adr migrate merges status line and body line relations"
    commit_refactor: "refactor: tidy relation merging"
ancillary_files:
  - "docs/adr-format.md"
  - "CHANGELOG.md"
---

# adr migrate: carry `**Amends:**` and `**Amended by:**` lines

## Context

Issue [#12](https://github.com/geuben/perturb/issues/12), blocked by #3 (closed, merged as
[#16](https://github.com/geuben/perturb/pull/16)).

`perturb adr migrate` carries a relation into front-matter from two places today: the
`**Supersedes:**` body line, and status-line annotations (`amends` / `amended by`, added by #3).
ADRs in the wild also state amendments as their own labelled lines under the title, and migrate
reads neither. Verified by probe on `main` at `5834773`, migrating the issue's own ADR 0007
sample: `amends=[]`, `amended_by=[]`, `warnings=[]`, and both lines left sitting in the body. The
relation never reaches front-matter, so `check` and `propose` cannot see it, and nothing warns —
only `**Supersedes:**` lines are inspected.

This plan makes a labelled relation line a third source of `amends` / `amended_by`, sharing the
ref grammar the other two already use.

Ledger events absorbed:

- `01M2KM3EDWGF0RFFMD4Z7TDTEM` (`scope`, from `plan:supersedes-ref-grammar`) — "`**Amends:**` /
  `**Amended by:**` lines are tracked in #12, blocked by #3". That is this plan's whole subject;
  #8's plan deliberately left these lines alone and routed them here.
- `01M2N5XA1P2FPKA30W33HBHPC0` (`unblock`, from #3) — #3 has closed, so the `amends` /
  `amended_by` front-matter keys and the status-line parser this plan builds on now exist.

Code as it stands (`5834773`), all in `src/perturb/adr.py`:

- `migrate_adr(text, adr_id)` walks the lines before the first `## ` heading, collecting a
  `carried: set[int]` of line indices that were absorbed into front-matter; whatever is left
  becomes the `preamble` and is written back into the body.
- The `**Status:**` branch joins wrapped continuation lines — it appends following lines until one
  is blank, starts with `>`, or starts with `**` — then calls `_parse_status_relations` for
  `amends` / `amended_by` and `_status_warning_segments` for the warning text.
- The `**Supersedes:**` branch matches the label as an exact-case substring, takes the first such
  line only, does **not** join continuations, and calls `_whole_adr_numbers(named)`. Not `None` →
  `supersedes` is written and the line index is added to `carried` (the line disappears from the
  body). `None` → the line stays in the body and a warning suggests
  `supersedes: ["adr:NNNN#<consequence-id>"]`.
- `_whole_adr_numbers(text)` is the shared ref grammar #8 widened: markdown links are flattened,
  one trailing `.` is dropped, `_WHOLE_ADR_REF` matches an optional `ADR` prefix plus digits, and
  the line qualifies only when nothing but `and`, `,`, `;`, `&` and whitespace remains.
- `_SL_REASON_SEP` (`" [—–] |: "`) is how the status-line parser splits a reason clause off a
  relation before matching refs.

Baseline: `uv run pytest -q` → `429 passed`; `uv run ruff check` → `All checks passed!`.
No `docs/INVARIANTS.md` in this repo.

## Design decisions (locked)

1. **A relation line carries its refs, keeps its explanation in the body, and warns.** For
   `**Amends:** [ADR-0003](0003-x.md) (module boundary unchanged; the tiers stand)`, migrate
   writes `amends: ["adr:0003"]`, **leaves the line in the body**, and warns naming the clause it
   did not carry. Decided by the user, choosing this over both existing precedents: #3's
   status-line rule carries the relation and deletes the line, which would lose the caveat prose
   from the file; the `**Supersedes:**` rule would carry nothing at all, and the issue's real-world
   sample is exactly this shape. Nothing is lost here — the relation becomes machine-readable and
   a human can still fold the caveat into a consequence.
2. **A relation line with no explanation is fully absorbed**: refs carried, line removed from the
   body, no warning. Decided by parity with the clean `**Supersedes:**` case — the line is then
   entirely represented by the front-matter, so leaving it would duplicate it.
3. **Continuation lines are joined, by the status line's rule.** Following lines are appended
   until one is blank, starts with `>`, or starts with `**`. Decided by the user. The issue's
   sample wraps, and `**` is exactly where the next label (`**Amended by:**`) begins, so the rule
   already separates adjacent relation lines. Every joined line index goes into `carried` when the
   line is absorbed, and stays out of it when the line is kept (decision 1).
4. **The accepted labels are `**Amends:**`, `**Extends:**`, `**Amended by:**` and
   `**Extended by:**`, matched case-insensitively, with `-` accepted for the space in the two-word
   forms.** Decided by evidence: #3 established `extends` as an alias of `amends` with no separate
   front-matter key (`docs/adr-format.md`, "Amending an ADR"), so the line labels mirror the status
   verbs. The full form set is enumerated in cycle 2 and pinned in one table.
   - **Accepted, equivalent, → `amends`:** `**Amends:**`, `**amends:**`, `**Extends:**`.
   - **Accepted, equivalent, → `amended_by`:** `**Amended by:**`, `**Amended By:**`,
     `**Amended-by:**`, `**Extended by:**`.
   - **Rejected, left in the body untouched:** `**Amendment:**` (not a relation verb) and
     `**Amends**:` (colon outside the bold). The label must be the whole bolded run including the
     colon, as `**Supersedes:**` is.
   - **Rejected, and already consumed by something else:** an unbolded `Amends: ADR 3` **placed
     directly under the status line** is swallowed by the status line's continuation join (it does
     not start with `**`), reported as an uncarried status-line annotation, and removed from the
     body. Probe-verified. This is pre-existing behaviour and is pinned, not changed — see the
     scope cut below.
5. **The label regex is anchored at the start of the line**
   (`^\*\*(amends|extends|amended[ -]by|extended[ -]by):\*\*`, `re.IGNORECASE`), not an
   unanchored substring. Decided by evidence: prose in the preamble can mention `**Amends:**`
   mid-sentence, and the mechanism footgun here is `in line` substring matching, which is what
   `**Supersedes:**` uses and what would make such a mention a false positive.
6. **A reason clause starts at the first ` — `, ` – `, `: ` or ` (` in the line's text**, and
   everything from there is the explanation. Decided by evidence plus one addition: `_SL_REASON_SEP`
   already gives the dash and colon forms, and the issue's sample adds a parenthetical. The
   mechanism footgun is the markdown link: `[ADR-0003](0003-x.md)` contains `](`, so the
   parenthesis alternative **must** require a preceding space (`\s\(`), or every linked ref splits
   at its own URL. Probe-verified against `[ADR-0003](0003-x.md) (module boundary unchanged)`,
   which splits at the second parenthesis.
7. **Every relation line in the preamble is read, not just the first.** Decided by evidence: an
   ADR carries `**Amends:**` and `**Amended by:**` as separate lines (the issue's ADR 0007), so the
   single-line `break` the `**Supersedes:**` branch uses cannot be reused. Two lines with the same
   label union.
8. **Body-line relations merge with status-line relations, status first, de-duplicated.** Decided
   by evidence: both are the same relation and `_parse_status_relations` already de-duplicates
   within itself, so a ref named in both places must appear once. Order is status-line refs first,
   then body-line refs not already present.
9. **A partial line keeps the `**Supersedes:**` warning shape**: the line stays in the body,
   nothing is carried, and the warning names the line and suggests
   `amends: ["adr:NNNN#<consequence-id>"]` with the ADR number filled in where one was mentioned.
   Decided by parity with `test_migrate_keeps_a_supersedes_line_that_does_not_name_only_whole_adrs`,
   which is the existing contract for the same situation on the other label.

## Deliberate scope cuts (do not build)

- **The `**Supersedes:**` branch is not rewired.** It keeps its exact-case substring match, its
  first-line-only `break`, and its no-continuation-join behaviour, and it gains no reason-clause
  handling. Premise: #12 asks for the amends lines; unifying the two body-line parsers is #8's
  territory and the ledger event that routed this work here says so explicitly. The two branches
  will read the same *refs* (both call `_whole_adr_numbers`) while differing on labels, wrapping
  and reason clauses. Re-evaluation trigger: if a cycle cannot go green without editing the
  `**Supersedes:**` branch or changing `_whole_adr_numbers`, stop and raise a `plan_defect`
  blocker — do not "just unify them" inside a refactor phase.
- **The status-line continuation join is not changed to spare an unbolded `Amends:` line.**
  Premise: that line is already consumed as a status annotation and warned about (decision 4,
  probe-verified), so the author does see it; changing the join would alter behaviour #3 shipped
  and is not what #12 asks for. Cycle 1 pins the current outcome. Re-evaluation trigger: if the
  pin fails on arrival, the premise is wrong — raise a `plan_defect` blocker rather than editing
  the pin to match.
- **No new `check` finding for a relation line left in the body.** Premise: `migrate` is a one-off
  authoring tool whose warnings are its report, and `check` validates front-matter, not prose.
  A kept line is prose.
- **`**Superseded by:**` is not added as a label.** Premise: the issue names only the amends pair,
  and `superseded_by` is a scalar with its own status-driven rules (#7). Adding it here would
  invent a carry rule for a field the issue never mentions.

## Cycles

### Cycle 1 — pin how a non-relation label line is treated (`pin_cycle`)

**Behaviour (existing).** Lines that are not accepted relation labels keep exactly today's
treatment. This is the guard for cycles 2–6: the label matcher must not widen past its list.

**Test** — `tests/test_adr.py::test_migrate_leaves_a_non_relation_label_line_alone`, one assertion
over a table of four lines, each placed on the line directly after `**Status:** accepted · 2026-09-10`
in a minimal ADR, comparing `(amends, amended_by, supersedes, warnings, label-still-in-preamble)`:

| line | today, and after this plan |
|---|---|
| `**Amendment:** ADR 3` | nothing carried, no warning, line kept |
| `**Amends**: ADR 3` | nothing carried, no warning, line kept |
| `**Supersedes:** ADR 3` | `supersedes == ["adr:0003"]`, no warning, line removed |
| `Amends: ADR 3` | nothing carried, warning `status line annotation not carried into the front-matter: Amends: ADR 3`, line removed |

The last row is position-dependent: it is consumed by the status line's continuation join *because
it directly follows the status line*. Keep it in that position; do not "fix" it.

**Production target** — none. A pin cycle writes no production code, so `files` is `[]` and the
cycle has a single `commit_pin` phase.

**EXPECTED FAILURE** — none. **This test must pass on arrival**, probe-verified row by row on
`main` at `5834773`. If it fails, the plan's reading of the preamble walk is wrong: raise a
`plan_defect` blocker, do not adjust the table.

### Cycle 2 — a whole-ADR relation line is carried into front-matter

**Behaviour.** A preamble line whose label is an accepted relation label and whose text names
nothing but whole ADRs has its refs written to `amends` or `amended_by`, and the line is removed
from the body.

**Test** — `tests/test_adr.py::test_migrate_carries_a_relation_line_in_every_accepted_label_form`,
one assertion over the accepted label table from decision 4 — `**Amends:** ADR 3`,
`**amends:** ADR 3`, `**Extends:** ADR 3`, `**Amended by:** ADR 9`, `**Amended By:** ADR 9`,
`**Amended-by:** ADR 9`, `**Extended by:** ADR 9`, and
`**Amends:** [ADR-0007](0007-x.md), [ADR-0009](0009-y.md)` for the multi-ref form — comparing
`(amends, amended_by, warnings, label-still-in-preamble)` per row against the expected tuple.

**Production target** — `migrate_adr` in `src/perturb/adr.py`, plus a module-level label pattern
constant beside `_SL_AMENDS_VERB`. Add a branch to the preamble walk that matches the anchored
label regex (decision 5), calls the existing `_whole_adr_numbers` on the rest of the line, and on
a non-`None` result appends `adr:NNNN` refs to the right list and adds the line index to
`carried`. That increment **and nothing later**: no continuation join (cycle 3), no reason-clause
splitting (cycle 4), no warning on a partial line (cycle 5), and no de-duplication against the
status-line lists (cycle 6).

**EXPECTED FAILURE** — probe-verified: every row carries nothing today, so the test fails on the
first row with `amends=[]` where `["adr:0003"]` is expected — e.g.
`assert ([], [], [], True) == (['adr:0003'], [], [], False)`.

### Cycle 3 — a wrapped relation line is read as one line

**Behaviour.** A relation line's continuation lines are joined before its refs are read.

**Test** — `tests/test_adr.py::test_migrate_joins_a_wrapped_relation_line`, one assertion: for
`**Amends:** [ADR-0007](0007-x.md),` wrapping onto `[ADR-0009](0009-y.md)`, `amends` is
`["adr:0007", "adr:0009"]`, there is no warning, and neither physical line survives in the body.

**Production target** — `migrate_adr` in `src/perturb/adr.py`: before matching refs, extend the
relation line with following lines until one is blank, starts with `>`, or starts with `**`
(decision 3), adding each joined index to `carried` alongside the label line's. The `**Status:**`
branch has this loop already; share it rather than writing a second one. That increment **and
nothing later** — no reason-clause handling yet.

**EXPECTED FAILURE** — probe-verified: today nothing is carried, and after cycle 2 only the first
physical line is read, so `amends` is `["adr:0007"]` and the orphaned continuation line is still
in the body. Fails with `assert ['adr:0007'] == ['adr:0007', 'adr:0009']`.

### Cycle 4 — a relation line with a reason clause carries its refs, keeps the line, and warns

**Behaviour.** Decision 1, and the composition of decisions 1 and 3 on the issue's real sample.

**Test** — `tests/test_adr.py::test_migrate_carries_a_relation_line_with_a_reason_clause_and_warns`,
one assertion over three rows, comparing `(amends, amended_by, label-still-in-preamble, warnings)`:

| line | carries | warning names |
|---|---|---|
| `**Amends:** [ADR-0003](0003-x.md) (module boundary unchanged)` | `amends: ["adr:0003"]` | `(module boundary unchanged)` |
| `**Amended by:** [ADR-0009](0009-y.md) — the tiers stand` | `amended_by: ["adr:0009"]` | `— the tiers stand` |
| the issue's ADR 0007 line: `**Amends:** [ADR-0003](0003-single-process.md) (module boundary unchanged;` wrapping onto `the tiers stand)` | `amends: ["adr:0003"]` | the joined clause |

Every row keeps its line in the body. Write the warning text as one shape and assert it in full;
do not assert with `in`.

**Production target** — `migrate_adr` in `src/perturb/adr.py` plus a module-level reason-split
pattern beside `_SL_REASON_SEP`. Split the joined line text at the first ` — `, ` – `, `: ` or
` (` (decision 6 — the space before `(` is mandatory), match refs against the head only, and when
a reason is present carry the refs but leave every line index of that relation line **out** of
`carried` and append the warning. That increment **and nothing later** — a line whose *head* is
not whole refs still carries nothing and still warns nothing until cycle 5.

**EXPECTED FAILURE** — probe-verified: today all three rows carry nothing and warn nothing, and
after cycles 2–3 the parenthetical makes `_whole_adr_numbers` return `None`, so the row still
carries nothing. Fails with `assert ([], [], True, []) == (['adr:0003'], [], True, ['<the warning>'])`.

### Cycle 5 — a partial relation line carries nothing and warns

**Behaviour.** Decision 9: a relation line naming more than whole ADRs keeps the
`**Supersedes:**` treatment — line kept, nothing carried, warning with a consequence-anchor hint.

**Test** — `tests/test_adr.py::test_migrate_keeps_and_warns_about_a_partial_relation_line`, one
assertion: for `**Amends:** the module boundary half of [ADR 0003](0003-x.md)`, `amends` is `[]`,
the line is still in the body, and the single warning names the line and contains
`amends: ["adr:0003#<consequence-id>"]`. Mirror
`test_migrate_keeps_and_warns_about_a_partial_supersedes_line` for the warning's shape, and derive
the hint's ADR number with `_PROSE_ADR_REF` as the `**Supersedes:**` branch does (falling back to
`adr:NNNN` when no number is mentioned).

**Production target** — `migrate_adr` in `src/perturb/adr.py`: the `else` arm of cycle 2's branch.
That increment **and nothing later** — cycle 4 added the warning for a line that *was* carried;
this is the warning for one that was not, and the two texts are different.

**EXPECTED FAILURE** — probe-verified: today, and after cycles 2–4, the line is left alone in
silence. Fails with `assert ([], True, []) == ([], True, ['<the warning>'])` — the refs and the
kept line are already right; the missing warning is what fails.

### Cycle 6 — status-line and body-line relations merge without duplicates

**Behaviour.** Decision 8.

**Test** — `tests/test_adr.py::test_migrate_merges_status_line_and_body_line_relations`, one
assertion: an ADR whose status line reads `**Status:** accepted · 2026-09-10 · amends ADR 0008`
and which also carries `**Amends:** ADR 0008, ADR 9` produces `amends == ["adr:0008", "adr:0009"]`.

**Production target** — `migrate_adr` in `src/perturb/adr.py`: merge the line-derived lists into
`amends_from_status` / `amended_by_from_status`, appending only refs not already present, before
the front-matter is serialised.

**EXPECTED FAILURE** — two possibilities, both RED, and which one appears tells you how cycle 2
landed. Probe-verified today: the status line alone carries `["adr:0008"]`, so the test fails with
`assert ['adr:0008'] == ['adr:0008', 'adr:0009']`. If cycles 2–5 concatenated the two sources
instead of replacing, it fails with `assert ['adr:0008', 'adr:0008', 'adr:0009'] == ['adr:0008', 'adr:0009']`.
Either failure is legitimate RED; a **pass** on arrival is not — it means an earlier cycle built
this cycle's behaviour, so stop and raise a `plan_defect` blocker rather than running the
sensitivity check on a cycle that should have been RED.

**Docs (refactor phase, cycle 6)** — `docs/adr-format.md`, "Migration for existing ADRs": add a
numbered step for `**Amends:**` / `**Amended by:**` lines, naming the four label verbs, the
case-insensitive and hyphen forms, the continuation join, and the two warning cases (carried with
an explanation the author should fold into a consequence; not carried because the line names more
than whole ADRs). `CHANGELOG.md`: one `### Added` entry under `[Unreleased]`.

## Execution

This plan is executed through `tdd-cli`. **You run every command below yourself** — do not ask the
user to start the run. `tdd run start` records which model is executing, resolved from your own
session; a run started by anyone else attributes this work to the wrong agent.

    git checkout -b adr-migrate-relation-lines   # first, before anything else
    tdd doctor                                   # must report healthy: true
    tdd run start --plan tasks/adr-migrate-relation-lines.md

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
- Cycle 1 is a **pin**: its test must pass on arrival and it adds no production code. Cycles 2–6
  all edit the same preamble walk in `migrate_adr`. Each GREEN adds only its own increment, **and
  nothing later**:
  - cycle 2 matches the labels and carries a clean single-line relation;
  - cycle 3 joins continuation lines;
  - cycle 4 splits a reason clause off, carries the refs, keeps the line, and warns;
  - cycle 5 warns about a line whose refs could not be read at all;
  - cycle 6 merges with the status-line lists and de-duplicates.
  Write each cycle's test only when that cycle opens.
- Map the verbs the plan will actually hit:
  - `run_sensitivity_check` → `tdd sensitivity begin|check|end`.
  - `annotate_cycle` → `tdd annotate --key --value`. This plan declares no keys beyond the
    reserved `plan_defect` and `friction_note`.
  - `resolve_blocker` → `tdd blocker --kind --detail`, with kinds `plan_defect` (the plan
    contradicts the code, the cycle 1 pin fails on arrival, cycle 6 passes on arrival, or a
    scope-cut re-evaluation trigger fires) and `environment` (uv/pytest cannot run).
  - `confirm_cycle_applicable` on a non-existent cycle → `tdd cycle skip --reason`.

## Done-criteria

> **Before finishing:** run `tdd log render --out tasks/friction-logs/adr-migrate-relation-lines-friction.md` and `tdd metrics`. Report the plan-fidelity section — declared vs delivered vs skipped — and every integrity event. Do not narrate what the ledger already records.
>
> Then commit the friction log and raise the PR:
>
>     git add tasks/friction-logs/adr-migrate-relation-lines-friction.md
>     git commit -m "docs: friction log for adr-migrate-relation-lines"
>
> Then invoke the **`raise-pr` skill** (`/raise-pr`), which runs the quality gates, pushes the
> branch and opens the PR against `main`. Do not push or call the GitHub API by hand. If a gate
> fails, fix it and re-run the skill — a failed gate is work, not a reason to hand back.

Ancillary docs are deliverables. Each of these must be non-empty, or the PR body says which cycle
dropped it and why:

- `git diff --stat origin/main -- docs/adr-format.md` (cycle 6)
- `git diff --stat origin/main -- CHANGELOG.md` (cycle 6)

`uv run python scripts/check_doc_links.py` must pass.
