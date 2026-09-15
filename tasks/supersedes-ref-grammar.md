---
closes: 8
cycles:
  - n: 1
    project: perturb
    pin_cycle: true
    title: "pin the Supersedes lines migrate keeps in the body"
    test: "tests/test_adr.py::test_migrate_keeps_a_supersedes_line_that_does_not_name_only_whole_adrs"
    files: []
    commit_pin: "test: pin the Supersedes lines migrate keeps in the body"
  - n: 2
    project: perturb
    title: "migrate carries a Supersedes line in every whole-ADR ref form"
    test: "tests/test_adr.py::test_migrate_carries_a_supersedes_line_in_every_whole_adr_ref_form"
    files: ["src/perturb/adr.py"]
    commit_red: "test: migrate carries a Supersedes line in every whole-ADR ref form"
    commit_green: "feat: adr migrate carries Supersedes lines naming ADRs by bare number"
    commit_refactor: "refactor: tidy the whole-ADR ref grammar"
ancillary_files:
  - "docs/adr-format.md"
  - "CHANGELOG.md"
---

# One ADR ref grammar: bare numbers on Supersedes lines

## Context

Issue [#8](https://github.com/geuben/perturb/issues/8). `perturb adr migrate` reads ADR refs out of prose
in two places.

- **Today, `**Supersedes:**` lines:** `_whole_adr_numbers` in `src/perturb/adr.py` carries a line into
  `supersedes` only when it names whole ADRs, and every ref needs an `ADR` prefix (`_PROSE_ADR_REF`).
- **Once #3 lands, status-line relations:** they will also accept bare numbers, as
  `tasks/adr-amends.md` decision 9 specifies, because ADRs in the wild write `amended by 0021` and
  `[0022](0022-x.md)`.

This plan makes `_whole_adr_numbers` accept the same bare and linked-number refs, so both sources of
relations read one grammar.

Probed on `main` at `1c29d94`, using `**Supersedes:** <text>`:

| text | `supersedes` today | kept in body |
|---|---|---|
| `ADR 0003` | `["adr:0003"]` | no |
| `[ADR-0003](0003-x.md) and ADR 4` | `["adr:0003", "adr:0004"]` | no |
| `ADR 3.` | `["adr:0003"]` | no |
| `0003` / `3` / `[0003](0003-typescript-stack.md)` | `[]` | yes, with a warning |
| `0003, [0004](0004-y.md) & ADR:5` / `ADR 0003 and 0004` | `[]` | yes, with a warning |
| `3.5` / `ADR-0003#postgres` / `the 2024 plan` | `[]` | yes, with a warning |

Evidence on demand: geuben/desk-display's 24 ADRs contain no `**Supersedes:**` line at all. This
plan follows the user's decision to unify the grammars anyway, ahead of any observed case.

Baseline: `uv run pytest -q` → `357 passed`. No `docs/INVARIANTS.md` in this repo.

## Design decisions (locked)

1. **`**Supersedes:**` lines accept bare ADR numbers.** Decided by the user in planning. This absorbs
   ledger event `01M2KJEVPNE2DM109QXHAKZ72Q` from `plan:adr-amends`, which moved "whether to unify
   them" to this issue.
2. **The whole-ADR ref grammar**, implemented in `_whole_adr_numbers(text) -> list[int] | None`:
   1. Replace each markdown link with its text (`_MARKDOWN_LINK`), dropping the target.
   2. Strip whitespace, then **one** trailing `.`.
   3. A ref is an optional `ADR` prefix followed by digits (case-insensitive, prefix `ADR[\s:-]*`),
      not preceded or followed by a word character or `#`. Pattern:
      `(?<![\w#])(?:ADR[\s:-]*)?(\d+)(?![\w#])`.
   4. Remove every ref. What remains may contain only the joiners `and`, `,`, `;`, `&` and
      whitespace.
   5. Return the numbers in order when there is at least one ref and nothing else remains; otherwise
      `None`.

   Traps:
   - Today's rest-strip removes `.` **anywhere**. With an optional prefix, `3.5` would then read as
     refs 3 and 5 with nothing left over and be carried. Only a single trailing `.` may be stripped
     (cycle 1 pins `3.5` as kept).
   - The lookarounds are what keep `ADR-0003#postgres` partial. Without `(?![\w#])`, `0003` matches
     and only `#postgres` is left, which is still rejected, but `v2` and `2024x` would yield refs.
     Keep them.
3. **The partial-line hint is unchanged.** The warning's example number still comes from
   `_PROSE_ADR_REF`, which requires the prefix. So `the 2024 plan` keeps the placeholder
   `adr:NNNN#<consequence-id>` and never suggests `adr:2024#…`. Cycle 1 pins the example per case.
4. **No new event or push to #3 from this plan.** #3's hardened plan builds its own status-line ref
   parsing (decision 9 there). Pointing it at `_whole_adr_numbers` would change that plan and make it
   stale, so that choice is left to the user (see the readiness report).

## Deliberate scope cuts (do not build)

- **#3's status-line parser is not rewired to `_whole_adr_numbers`.**
  - **Mirror:** `tasks/adr-amends.md` decision 9's status-line ref list.
  - **Divergence risk:** #3's joiners are `and`, `,`, `&`, with no `;`, and it does not mention a
    trailing `.`.
  - **Tracking:** #3 itself. If #3 lands first and exposes a shared helper, cycle 2's GREEN may call
    it only when every param of both cycle tests stays green. Otherwise raise a
    `plan_contradiction` blocker; do not change #3's helper to fit.
- **`**Amends:**` / `**Amended by:**` lines** are tracked in #12, blocked by #3.
- **A bare number that is not an ADR** (`**Supersedes:** 2024`) is carried as `adr:2024`. Premise:
  the issue accepts this risk, and `perturb check` then reports `supersedes_unresolved` because no
  ADR 2024 exists.

## Cycles

### Cycle 1 (pin): Supersedes lines migrate keeps in the body

- **Test:** `tests/test_adr.py::test_migrate_keeps_a_supersedes_line_that_does_not_name_only_whole_adrs`,
  parametrized `named, example`.
  - Input: `"# ADR 0006 — Use DuckDB\n\n**Status:** accepted · 2026-09-10\n**Supersedes:** {named}\n\n## Context\n\nPROSE.\n\n## Consequences\n\n- X happens.\n"`,
    run through `migrate_adr(text, adr_id=6)`.
  - Asserts
    `(parse_adr(result).supersedes, "**Supersedes:**" in result.split("## Context")[0], re.search(r"adr:(?:NNNN|\d{4})#", warnings[0]).group(0)) == ([], True, example)`.
  - Cases:

    | named | example |
    |---|---|
    | `the storage engine half of [ADR 0003](0003-x.md)` | `adr:0003#` |
    | `ADR-0003#postgres` | `adr:0003#` |
    | `ADR 0003's storage half` | `adr:0003#` |
    | `the 2024 plan` | `adr:NNNN#` |
    | `[the storage decision](0003-x.md)` | `adr:NNNN#` |
    | `3.5` | `adr:NNNN#` |

- **Why a pin:** the probe shows all six are kept with exactly these examples today. Cycle 2 loosens
  the grammar, and this test is what stops it from carrying any of them.
- **Probed:** passes on arrival.

### Cycle 2: migrate carries a Supersedes line in every whole-ADR ref form

- **Test:** `tests/test_adr.py::test_migrate_carries_a_supersedes_line_in_every_whole_adr_ref_form`,
  parametrized `named, supersedes`. Same input template as cycle 1; asserts
  `parse_adr(migrate_adr(text, adr_id=6)[0]).supersedes == supersedes`.
  - Cases:

    | named | supersedes |
    |---|---|
    | `ADR 0003` | `["adr:0003"]` |
    | `[ADR-0003](0003-x.md) and ADR 4` | `["adr:0003", "adr:0004"]` |
    | `ADR 3.` | `["adr:0003"]` |
    | `0003` | `["adr:0003"]` |
    | `3` | `["adr:0003"]` |
    | `[0003](0003-typescript-stack.md)` | `["adr:0003"]` |
    | `0003, [0004](0004-y.md) & ADR:5` | `["adr:0003", "adr:0004", "adr:0005"]` |
    | `ADR 0003 and 0004` | `["adr:0003", "adr:0004"]` |
    | `0003; 0004` | `["adr:0003", "adr:0004"]` |

- **Production:** `src/perturb/adr.py` `_whole_adr_numbers`, implementing decision 2.
  `migrate_adr`'s Supersedes block and its hint (decision 3) are unchanged.
- **EXPECTED FAILURE** (probed): ``AssertionError: assert [] == ['adr:0003']`` for `0003`. The three
  prefixed params pass on arrival.
- **Existing tests that must stay green unchanged:**
  - `test_migrate_carries_a_whole_adr_supersedes_line`;
  - `test_migrate_keeps_and_warns_about_a_partial_supersedes_line`;
  - `test_adr_migrate_warns_about_a_supersedes_line_it_cannot_carry` in `tests/test_cli.py`;
  - cycle 1's pin.
- **Docs:**
  - `docs/adr-format.md` "Migration for existing ADRs" step 2: whole ADRs may be named with or
    without the `ADR` prefix (`**Supersedes:** [0003](0003-x.md) and ADR 4`).
  - `CHANGELOG.md` `[Unreleased]`: `perturb adr migrate` carries a `**Supersedes:**` line that names
    ADRs by bare number.

## Behaviour census

- **Pinned:** accepted forms (cycle 2); kept forms and their hint examples (cycle 1).
- **Specified but not asserted:** none beyond the grammar text, which both tables exercise.
- **Cross-boundary:** none. The carried list feeds `parse_adr`, and cycle 2 asserts it through
  `parse_adr`.
- **Test doubles:** none.

## Execution

This plan is executed through `tdd-cli`. **You run every command below yourself** — do not ask the
user to start the run. `tdd run start` records which model is executing, resolved from your own
session; a run started by anyone else attributes this work to the wrong agent.

    git checkout -b supersedes-ref-grammar               # first, before anything else
    tdd doctor                                           # must report healthy: true
    tdd run start --plan tasks/supersedes-ref-grammar.md # captures baselines, opens cycle 1

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
- Map the verbs the plan will actually hit:
  - `run_sensitivity_check` → `tdd sensitivity begin|check|end`.
  - `annotate_cycle` → `tdd annotate --key --value`. This plan declares no keys beyond the
    reserved `plan_defect` and `friction_note`.
  - `resolve_blocker` → `tdd blocker --kind --detail`. Kinds are free-form labels:
    `plan_contradiction` (the plan disagrees with the code, including the #3 scope cut's trigger)
    and `environment` (uv/pytest cannot run).
  - `confirm_cycle_applicable` on a non-existent cycle → `tdd cycle skip --reason`.

## Done-criteria

> **Before finishing:** run `tdd log render --out tasks/friction-logs/supersedes-ref-grammar-friction.md` and `tdd metrics`. Report the plan-fidelity section — declared vs delivered vs skipped — and every integrity event. Do not narrate what the ledger already records.
>
> Then commit the friction log and raise the PR:
>
>     git add tasks/friction-logs/supersedes-ref-grammar-friction.md
>     git commit -m "docs: friction log for supersedes-ref-grammar"
>
> Then invoke the **`raise-pr` skill** (`/raise-pr`), which runs the quality gates, pushes the
> branch and opens the PR against `main`. Do not push or call the GitHub API by hand. If a gate
> fails, fix it and re-run the skill — a failed gate is work, not a reason to hand back.

Ancillary docs are deliverables. Each must be non-empty, or the PR body says which cycle dropped
it and why:

- `git diff --stat origin/main -- docs/adr-format.md` (cycle 2)
- `git diff --stat origin/main -- CHANGELOG.md` (cycle 2)
