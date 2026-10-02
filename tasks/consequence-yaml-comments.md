---
closes: 28
cycles:
  - n: 1
    project: perturb
    pin_cycle: true
    title: "pin the consequence forms that keep a # and parse whole"
    test: "tests/test_adr.py::test_consequence_forms_that_keep_a_hash_parse_whole"
    files: []
    commit_pin: "test: pin the consequence forms that keep a # intact"
  - n: 2
    project: perturb
    pin_cycle: true
    title: "pin that adr migrate quotes a text with a mid-sentence mention"
    test: "tests/test_adr.py::test_migrate_quotes_a_text_with_a_mid_sentence_mention"
    files: []
    commit_pin: "test: pin that migrate quotes a text with a mid-sentence #N"
  - n: 3
    project: perturb
    title: "a consequence value lost to a YAML comment is refused"
    test: "tests/test_adr.py::test_a_value_lost_to_a_yaml_comment_is_refused"
    files: ["src/perturb/adr.py"]
    commit_red: "test: a consequence value lost to a YAML comment is refused"
    commit_green: "fix: refuse a consequence text or affects entry cut off by a YAML comment"
    commit_refactor: "docs: document the mid-sentence # rule for consequence text and affects"
  - n: 4
    project: perturb
    title: "a Consequences block that is not valid YAML is refused, not a traceback"
    test: "tests/test_adr.py::test_a_consequences_block_that_is_not_yaml_is_refused"
    files: ["src/perturb/adr.py"]
    commit_red: "test: a Consequences block that is not valid YAML is refused"
    commit_green: "fix: wrap a Consequences YAML error in AdrError bad_consequences"
    commit_refactor: "refactor: tidy consequence parsing"
  - n: 5
    project: perturb
    title: "check reports consequence_comment and affects_comment as their own findings"
    test: "tests/test_check.py::test_a_consequence_lost_to_a_yaml_comment_is_its_own_finding"
    files: ["src/perturb/check.py"]
    commit_red: "test: a consequence lost to a YAML comment is its own check finding"
    commit_green: "feat: check reports consequence_comment and affects_comment"
    commit_refactor: "docs: list consequence_comment and affects_comment in the check validation"
  - n: 6
    project: perturb
    title: "propose adr: refuses an ADR that does not parse instead of raising"
    test: "tests/test_cli.py::test_propose_adr_refuses_an_adr_that_does_not_parse"
    files: ["src/perturb/cli.py"]
    commit_red: "test: propose adr: refuses an ADR that does not parse"
    commit_green: "fix: propose adr: refuses with the parser's reason"
    commit_refactor: "docs: changelog and cli reference for refused ADRs"
ancillary_files:
  - "docs/adr-format.md"
  - "docs/cli.md"
  - "CHANGELOG.md"
---

# An unquoted `#N` in a consequence is read as a YAML comment

## Context

Issue [#28](https://github.com/geuben/perturb/issues/28). Consequences are parsed as real YAML
(`yaml.safe_load` in `_parse_consequences`, `src/perturb/adr.py`). An unquoted ` #` in the middle
of a plain `text` value starts a YAML comment. The text is silently cut off at the `#`, the `#N` it
named never becomes a `mentions` proposal, and `check` passes. Naming an issue mid-sentence is the
ordinary way to write a consequence, and `docs/adr-format.md` warns only about a *leading* indicator.

Probed on `main` at `b5c9db6` (each row is a consequence body inside the usual fenced block):

| body | today |
|---|---|
| `text: General knowledge, which happens to mention #7 in passing.` | text `'General knowledge, which happens to mention'` — truncated, no error |
| `text: Plain sentence.  # TODO` | text `'Plain sentence.'` — truncated |
| `text: Backfilled days remain daily-grain,` / `    see #29 for the split.` | text `'Backfilled days remain daily-grain, see'` — truncated |
| `affects:` / `    - #7` | `affects == [None]`; `check` and `propose` skip the `None` silently |
| `affects: #7` | `affects == []` (null → `or []`) — the ref vanishes |
| `text: Backfilled days, see #29` / `    and never re-priced.` | `yaml.parser.ParserError` escapes `parse_adr`; `check` crashes with a traceback |
| `text: mentions<TAB>#7 here.` | `yaml.scanner.ScannerError` escapes; same crash |

And for `propose adr:2`, `parse_adr` is called *before* `dispatch` in `main` (`src/perturb/cli.py`,
the `# adr path (unchanged)` block of the `propose` verb), so any `AdrError` escapes as a traceback:
a probe with an ADR missing `status` raised `AdrError: required front-matter field 'status' is absent`
out of `main`. With the truncating ADR above, `propose` exits 0 and writes events with the cut-off
summary.

`adr migrate` is already safe: it writes consequences with `yaml.safe_dump`, which single-quotes any
string containing ` #` (probe: `text: 'General knowledge, mentions #7 in passing.'`), and it moves
every `#NNN` into `affects` anyway. Cycle 2 pins that.

Overlap: open issue #29 (prose before the YAML list under `## Consequences` crashes `check` and
`propose`) has the same root crash. The user chose to build the YAML-error wrapping here (decision 5);
#29 is told via a ledger push.

Baseline in a fresh worktree: `uv run pytest -q` → `439 passed`; `uv run ruff check` →
`All checks passed!`; `tdd doctor` → healthy. No worktree setup script is needed. No
`docs/INVARIANTS.md` in this repo. No mirrored implementation of consequence parsing exists
(`skills/perturb/SKILL.md` does not describe the consequence format).

## Design decisions (locked)

1. **A consequence `text` cut off by a YAML comment refuses the whole ADR.** `parse_adr` raises
   `AdrError("consequence_comment", …)`. Decided by the user over a check-only finding or recovering
   the raw text. A finding alone would still let `propose` write the truncated summary. Recovering the
   raw text would make perturb read YAML differently from every other tool. The cost is accepted: a
   deliberate trailing comment after `text:` is refused too, and the author moves it to its own line.
2. **Detection is by node position, not by scanning raw lines.** Compose the *same fence-stripped
   string* that `_parse_consequences` loads (`yaml.compose(stripped)`), walk each consequence mapping,
   and for the `text` value node: if `node.style is None` (plain) and
   `stripped.split("\n")[node.end_mark.line][node.end_mark.column:]` matches `^\s+#`, refuse.
   Footgun: `end_mark` line/column are relative to the composed string, so composing the whole file,
   or the fenced text, gives wrong positions. Quoted (`'`, `"`) and block (`|`, `>`) scalars have a
   non-`None` style and are never flagged, which is how cycle 1's accepted forms stay accepted. A raw
   " ` #` in the line" scan would wrongly flag them. Decided from evidence: a probe showed a multi-line
   plain scalar's `end_mark` sits on its last line, at the comment (`' #29 for the split.'`).
3. **The `consequence_comment` detail is exact:**
   `consequence '<id>' text is cut off at a YAML comment, dropping '<tail>'; put the text in double quotes`,
   where `<tail>` is that source line from the `#` to its end, with trailing whitespace stripped
   (e.g. `#7 in passing.`). Decided by the planner. It names the consequence, as the issue asks, and
   shows the author what was lost.
4. **An `affects` ref lost to a comment also refuses the ADR**, as `AdrError("affects_comment", …)`
   with detail exactly
   `consequence '<id>' has an affects entry lost to a YAML comment; write each issue ref as "#N"`.
   Decided by the user (same mechanism, same silent loss). Two forms are refused:
   - an `affects` **sequence item** that is a null scalar (`tag:yaml.org,2002:null`). An empty item is
     never a valid ref, so any null item is refused, whatever caused it;
   - an `affects` value that is a null scalar where the key's source line, from the key node's
     `end_mark.column`, matches `^:[ \t]+#\d`. So `affects: #7` is refused, while a bare `affects:` and
     `affects:  # none yet` stay accepted as "no affects".
   `id`, `kind` and comments on their own lines are never inspected.
5. **A Consequences block that is not valid YAML raises `AdrError("bad_consequences", …)`.** That
   replaces the raw `yaml.YAMLError`. The detail is
   `Consequences block is not valid YAML: <first line of str(exc)>; an unquoted ' #' starts a YAML comment, so put any text containing one in double quotes`.
   Decided by the user, building here the wrapping that #29 also needs. It reuses the existing
   `bad_consequences` reason (today raised for a non-list block). `check` reports it through its
   existing `adr_parse` path. The tests assert only the reason and the fixed hint suffix, because
   PyYAML's wording is not ours.
6. **`check` gives the two comment reasons their own finding kinds.** In the `except AdrError` of
   `adr_findings` (`src/perturb/check.py`):
   - `consequence_comment` → `{"kind": "consequence_comment", "ref": <file>, "detail": str(exc), "fix": "put the consequence text in double quotes in <file>"}`
   - `affects_comment` → `{"kind": "affects_comment", "ref": <file>, "detail": str(exc), "fix": "write each issue ref in affects as \"#N\" in <file>"}`
   - every other reason, `bad_consequences` included, stays `adr_parse` with its existing fix.
   Decided by the planner. Agents act on `kind`. `adr_parse` with "fix the front-matter or body" does
   not say what to change, while these kinds do.
7. **`propose adr:N` refuses with the `AdrError`'s reason and detail for any ADR that does not parse.**
   It no longer raises. Wrap the `parse_adr(adr_path.read_text())` call. On `AdrError`, return
   `dispatch("propose", <handler raising Refusal(exc.reason, exc.detail)>, json_out=…, out=…, err=…)`,
   the same shape as the `_propose_refusal` block at the top of the verb. Exit code 1, envelope
   `ok: false`, `reason` = the parser's reason. Decided by decision 1: refusing the ADR means nothing
   in propose, and a traceback is not a refusal. This also fixes #29's propose half.
8. **`adr migrate` is not changed.** `yaml.safe_dump` already quotes, and `migrate` already parses its
   output before writing (and refuses if that fails). Cycle 2 pins the quoting. Decided from evidence.

## Deliberate scope cuts (do not build)

- **Prose before the fence under `## Consequences` (#29's own case) gets no dedicated kind or hint,
  and is not skipped.** Premise: named non-goal. It is a separate open issue (#29) with an open design
  question (a dedicated finding kind, or ignoring prose outside the fence), and #28 does not raise it.
  After this plan, #29's input gets decision 5's `bad_consequences` refusal (`adr_parse` in `check`, a
  refusal in `propose`) rather than a traceback. Re-evaluation trigger: if a cycle would have to change
  how text outside the fence is read in order to go green, stop and raise a `plan_defect` blocker.
- **`unpropagated_adr_findings` keeps silently skipping an ADR that does not parse.** Premise: named
  non-goal. That ADR already yields an `adr_findings` finding, so a second "unpropagated" finding for
  the same file would be noise. The issue asks only that the loss be reported once.

## Cycles

Every `tests/test_adr.py` cycle builds its ADR with a module-level helper, added in cycle 1's test
step and reused by cycles 3 and 4:

```python
def _adr_with_consequences(body: str) -> str:
    return (
        "---\nid: 1\ntitle: T\nstatus: accepted\ndate: 2026-01-01\nsupersedes: []\n"
        "areas: []\n---\n\n## Context\nx\n\n## Decision\ny\n\n## Consequences\n\n```yaml\n"
        + body
        + "```\n"
    )
```

Table rows are driven from a list inside the test body (house style; no `parametrize`), and the one
assertion compares the collected per-row results against the expected list. Then a failing row is
named in the diff.

### Cycle 1 — pin the forms that keep a `#` and parse whole (`pin_cycle`)

**Behaviour (existing).** Each of these consequence bodies parses today with its whole text and
affects. This guards cycle 3: the detector must flag plain scalars cut off by a comment, and nothing
else.

**Test** — `tests/test_adr.py::test_consequence_forms_that_keep_a_hash_parse_whole`. One assertion:
`[(c.text, c.affects) for each row's consequences[0]] == [expected...]`, over:

| # | body | expected `(text, affects)` |
|---|---|---|
| 1 | `- id: g\n  text: "mentions #7 here"\n` | `("mentions #7 here", [])` |
| 2 | `- id: g\n  text: 'mentions #7 here'\n` | `("mentions #7 here", [])` |
| 3 | `- id: g\n  text: \|\n    mentions #7 here\n` | `("mentions #7 here\n", [])` |
| 4 | `- id: g\n  text: >\n    mentions #7\n    here\n` | `("mentions #7 here\n", [])` |
| 5 | `- id: g\n  text: Written in C# and issue#7.\n` | `("Written in C# and issue#7.", [])` |
| 6 | `# leading note\n- id: g  # slug\n  # between\n  text: t\n  kind: scope  # why\n` | `("t", [])` |
| 7 | `- id: g\n  text: t\n  affects: ["#7"]  # the DST issue\n` | `("t", ["#7"])` |
| 8 | `- id: g\n  text: t\n  affects:\n    - "#7"\n` | `("t", ["#7"])` |
| 9 | `- id: g\n  text: t\n  affects: []  # none yet\n` | `("t", [])` |
| 10 | `- id: g\n  text: t\n  affects:  # none yet\n` | `("t", [])` |
| 11 | `- id: g\n  text: t\n  affects:\n` | `("t", [])` |

(`\|` in row 3 is a literal `|` block indicator.)

**Production target** — none. `parse_adr` / `_parse_consequences` in `src/perturb/adr.py`, read only.

**EXPECTED** — passes on arrival. Verified by probe: all 11 rows produced exactly these tuples on
`b5c9db6`. If it fails, a row is wrong. Fix the row, never the parser.

### Cycle 2 — pin that `adr migrate` quotes a text with a mid-sentence mention (`pin_cycle`)

**Behaviour (existing).** `migrate_adr` writes a prose bullet containing ` #7` so that it parses
back whole.

**Test** — `tests/test_adr.py::test_migrate_quotes_a_text_with_a_mid_sentence_mention`. One assertion:
`parse_adr(migrate_adr(src, adr_id=5)[0]).consequences[0].text == "General knowledge, which happens to mention #7 in passing."`,
where `src` is
`"# ADR 0005 — Mentions\n\n**Status:** accepted · 2026-09-13\n\n## Consequences\n\n- General knowledge, which happens to mention #7 in passing.\n"`
(the shape of `PROSE_ADR_SUBSECTION`).

**Production target** — none. `migrate_adr` in `src/perturb/adr.py`, read only.

**EXPECTED** — passes on arrival. Verified by probe: `yaml.safe_dump` writes the entry as
`text: 'General knowledge, which happens to mention #7 in passing.'` (single-quoted), and it parses
back whole.

### Cycle 3 — a consequence value lost to a YAML comment is refused

**Behaviour.** `parse_adr` raises `AdrError` when a plain `text` is cut off by a comment
(`consequence_comment`, decisions 1–3), or an `affects` ref is lost to one (`affects_comment`,
decision 4).

**Test** — `tests/test_adr.py::test_a_value_lost_to_a_yaml_comment_is_refused`. For each row, call
`parse_adr(_adr_with_consequences(body))` in a `try`. Record `(exc.reason, exc.detail)` on `AdrError`
and `None` if it parses. One assertion: the collected list equals:

| # | body | expected `(reason, detail)` |
|---|---|---|
| 1 | `- id: general\n  text: General knowledge, which happens to mention #7 in passing.\n` | `("consequence_comment", "consequence 'general' text is cut off at a YAML comment, dropping '#7 in passing.'; put the text in double quotes")` |
| 2 | `- id: note\n  text: Plain sentence.  # TODO\n` | `("consequence_comment", "consequence 'note' text is cut off at a YAML comment, dropping '# TODO'; put the text in double quotes")` |
| 3 | `- id: backfill\n  text: Backfilled days remain daily-grain,\n    see #29 for the split.\n` | `("consequence_comment", "consequence 'backfill' text is cut off at a YAML comment, dropping '#29 for the split.'; put the text in double quotes")` |
| 4 | `- id: dst\n  text: t\n  affects:\n    - #7\n` | `("affects_comment", "consequence 'dst' has an affects entry lost to a YAML comment; write each issue ref as \"#N\"")` |
| 5 | `- id: refund\n  text: t\n  affects: #7\n` | `("affects_comment", "consequence 'refund' has an affects entry lost to a YAML comment; write each issue ref as \"#N\"")` |

**Production target** — `_parse_consequences` in `src/perturb/adr.py`. After the existing
`yaml.safe_load(stripped)`, compose the same `stripped` and walk the consequence mappings as decisions
2 and 4 describe. Raise on the first offending consequence, in document order. `yaml.compose` returns
`None` for an empty block, so guard for it. This increment **and nothing later**: do not wrap
`yaml.YAMLError` (cycle 4), and leave `check.py` and `cli.py` alone (cycles 5–6).

**EXPECTED FAILURE** — derived from the probe table above (all five rows parse today): the assertion
fails with `assert [None, None, None, None, None] == [('consequence_comment', ...), ...]`.

**Must stay green** — cycle 1's pin, all of `tests/test_adr.py`, `tests/test_propose.py` and the
`STRUCTURED_ADR_*` fixtures in `tests/test_cli.py`. None are in `modifies_tests`. If one breaks, the
detector is too broad: fix the detector.

**Docs (refactor phase)** — `docs/adr-format.md`, the paragraph after the example ("It is real YAML: a
`text` that starts with a backtick or other YAML indicator must be quoted."). Extend it: a ` #`
anywhere in an unquoted `text` starts a YAML comment, so a `text` that names an issue mid-sentence
must be double-quoted. An issue ref in `affects` is always written `"#N"`. `perturb` refuses an ADR
where either was lost (`consequence_comment`, `affects_comment`).

### Cycle 4 — a Consequences block that is not valid YAML is refused

**Behaviour.** A YAML error in the Consequences block becomes `AdrError("bad_consequences", …)`
(decision 5), not a raw `yaml.YAMLError`.

**Test** — `tests/test_adr.py::test_a_consequences_block_that_is_not_yaml_is_refused`. For each row,
`parse_adr(_adr_with_consequences(body))` in a `try`, recording `(exc.reason, exc.detail.endswith(HINT))`
on `AdrError`, where
`HINT = "an unquoted ' #' starts a YAML comment, so put any text containing one in double quotes"`.
One assertion: the collected list equals `[("bad_consequences", True), ("bad_consequences", True)]`,
over:

| # | body | yaml error today |
|---|---|---|
| 1 | `- id: g\n  text: Backfilled days, see #29\n    and never re-priced.\n` | `ParserError` |
| 2 | `- id: g\n  text: mentions\t#7 here.\n` (a real tab) | `ScannerError` |

**Production target** — `_parse_consequences` in `src/perturb/adr.py`. Catch `yaml.YAMLError` around
the load (and the compose from cycle 3), and raise `AdrError("bad_consequences", f"Consequences block is not valid YAML: {str(exc).splitlines()[0]}; {HINT}")`
`from exc`. This increment **and nothing later**.

**EXPECTED FAILURE** — verified by probe: row 1 raises
`yaml.parser.ParserError: while parsing a block mapping` out of `parse_adr`, which is not an
`AdrError`, so the test fails with that `ParserError`.

### Cycle 5 — `check` reports the two comment reasons as their own findings

**Behaviour.** `adr_findings` turns `consequence_comment` and `affects_comment` into findings of
those kinds with targeted fixes, and reports every other `AdrError` as `adr_parse` (decision 6). A
block that is not valid YAML is now a finding, not a crash.

**Test** — `tests/test_check.py::test_a_consequence_lost_to_a_yaml_comment_is_its_own_finding`. For
each row, write `tmp_path / str(row) / "0002-x.md"` with front-matter
`---\nid: 2\ntitle: T2\nstatus: accepted\ndate: 2026-09-08\n---\n\n## Consequences\n\n```yaml\n<body>```\n`
and call `adr_findings(dir, {"issues": {}})`. One assertion: the collected
`[(f["kind"], f["ref"], f["fix"]) for f in findings]` per row equals:

| # | body | expected findings |
|---|---|---|
| 1 | cycle 3 row 1 (`general`) | `[("consequence_comment", "0002-x.md", "put the consequence text in double quotes in 0002-x.md")]` |
| 2 | cycle 3 row 4 (`dst`) | `[("affects_comment", "0002-x.md", 'write each issue ref in affects as "#N" in 0002-x.md')]` |
| 3 | cycle 4 row 1 (wrapped after `#29`) | `[("adr_parse", "0002-x.md", "fix the front-matter or body of 0002-x.md")]` |

**Production target** — the `except AdrError as exc:` block at the top of the loop in `adr_findings`,
`src/perturb/check.py`. Choose `kind` and `fix` by `exc.reason`, keeping `adr_parse` and its fix for
every other reason. `ref` and `detail` are unchanged. This increment **and nothing later**.

**EXPECTED FAILURE** — derived from the current `except` block, which emits `adr_parse` for every
`AdrError`: once cycles 3–4 are green, rows 1–2 come back as
`("adr_parse", "0002-x.md", "fix the front-matter or body of 0002-x.md")`, and the assertion fails on
row 1. Row 3 already passes after cycle 4.

**Existing coverage to keep green** — `test_adr_parse_failure_is_a_finding` (missing title → still
`adr_parse`). Not in `modifies_tests`.

**Docs (refactor phase)** — `docs/adr-format.md`, "Validation in `perturb check`". Add a bullet: a
consequence whose plain `text` is cut off by a ` #…` comment is `consequence_comment`; an `affects`
ref lost to one (`- #7`, `affects: #7`) is `affects_comment`; a Consequences block that is not valid
YAML is `adr_parse`.

### Cycle 6 — `propose adr:` refuses an ADR that does not parse

**Behaviour.** `perturb propose adr:N` on an ADR that `parse_adr` rejects exits 1 with a refusal
envelope carrying the parser's reason, instead of raising (decision 7). No events are written.

**Test** — `tests/test_cli.py::test_propose_adr_refuses_an_adr_that_does_not_parse`. Model it on
`test_propose_adr_writes_events_and_emits_json`. Write `repo/docs/adr/0002-per-trip.md` as
`STRUCTURED_ADR_TEXT.replace("text: Issue 29 must be updated.", "text: General knowledge, which happens to mention #29 in passing.")`
(unquoted; consequence id `c1`), make `repo/.perturb`, and
build the transport with `_make_propose_transport([_make_page([_make_issue_node(29, title="Issue 29")])])`.
Call `main(["propose", "adr:2", "--by", "geuben", "--json"], transport=…, root=…, repo_root=repo)`.
One assertion:
`(rc, envelope["ok"], envelope["reason"]) == (1, False, "consequence_comment")`. This is the shape of
`test_adr_migrate_leaves_the_file_untouched_when_the_result_does_not_parse`.

**Production target** — the `propose` verb in `main`, `src/perturb/cli.py`: the
`adr = parse_adr(adr_path.read_text())` line under `# adr path (unchanged)`. Wrap it as decision 7
describes. `Refusal` and `AdrError` are already imported in `cli.py`.

**EXPECTED FAILURE** — verified by analogy probe: an ADR missing `status` makes `main` raise
`perturb.adr.AdrError: required front-matter field 'status' is absent` uncaught. Once cycle 3 is
green, this ADR makes `main` raise
`AdrError: consequence 'c1' text is cut off at a YAML comment, dropping '#29 in passing.'; …` the
same way, and the test fails with that exception.

**Docs (refactor phase)**:
- `docs/cli.md`, the `perturb propose` section: add "An ADR that does not parse refuses with the
  parser's reason (e.g. `consequence_comment`, `affects_comment`, `bad_consequences`)."
- `CHANGELOG.md` `[Unreleased]`: an `### Fixed` entry in the existing bolded-sentence style. An
  unquoted mid-sentence `#N` in a consequence `text`, or an unquoted `#N` in `affects`, no longer
  silently truncates or drops; `perturb` refuses the ADR (`consequence_comment` / `affects_comment`).
  A Consequences block that is not valid YAML is an `adr_parse` finding and a `propose` refusal, not a
  traceback; `propose adr:` refuses any ADR that does not parse. Closes #28.

## Execution

This plan is executed through `tdd-cli`. **You run every command below yourself** — do not ask the
user to start the run. `tdd run start` records which model is executing, resolved from your own
session; a run started by anyone else attributes this work to the wrong agent.

    git checkout -b consequence-yaml-comments          # first, before anything else
    tdd doctor                                         # must report healthy: true
    tdd run start --plan tasks/consequence-yaml-comments.md

If the branch already exists, do not force-checkout and do not pick another name: check it out
only if it carries this plan's commit and no unrelated work, otherwise stop and ask.

Then repeat until done: read `next_action.verb`, do exactly what it says, run `tdd advance`.
Stop when `next_action.terminal` is `true`.

When `next_action.terminal` is `true`, finish the run: render the friction log, commit it, and
raise the PR — see Done-criteria below.

- `tdd advance` is the only command that changes phase. Do not `git add` or `git commit` — the
  tool stages and commits, deriving the file set from the phase.
- The baseline is captured at `run start` and subtracted from later verdicts. Expected summary
  line: `439 passed`.
- Cycles 3 and 4 both edit `_parse_consequences`. Each GREEN adds only its own increment, **and
  nothing later**:
  - cycle 3 adds the compose walk and the two `AdrError` raises only — no `YAMLError` handling;
  - cycle 4 adds the `yaml.YAMLError` → `bad_consequences` wrapping only;
  - cycle 5 touches only the `except AdrError` block in `check.py`;
  - cycle 6 touches only the `parse_adr` call in the `propose` verb of `cli.py`.
  Write each cycle's test only when that cycle opens.
- Map the verbs the plan will actually hit:
  - `run_sensitivity_check` → `tdd sensitivity begin|check|end`.
  - `annotate_cycle` → `tdd annotate --key --value`. This plan declares no keys beyond the
    reserved `plan_defect` and `friction_note`.
  - `resolve_blocker` → `tdd blocker --kind --detail`, with kinds `plan_defect` (the plan
    contradicts the code, a pin fails on arrival, or a scope-cut re-evaluation trigger fires) and
    `environment` (uv/pytest cannot run).
  - `confirm_cycle_applicable` on a non-existent cycle → `tdd cycle skip --reason`.

## Done-criteria

> **Before finishing:** run `tdd log render --out tasks/friction-logs/consequence-yaml-comments-friction.md` and `tdd metrics`. Report the plan-fidelity section — declared vs delivered vs skipped — and every integrity event. Do not narrate what the ledger already records.
>
> Then commit the friction log and raise the PR:
>
>     git add tasks/friction-logs/consequence-yaml-comments-friction.md
>     git commit -m "docs: friction log for consequence-yaml-comments"
>
> Then invoke the **`raise-pr` skill** (`/raise-pr`), which runs the quality gates, pushes the
> branch and opens the PR against `main`. Do not push or call the GitHub API by hand. If a gate
> fails, fix it and re-run the skill — a failed gate is work, not a reason to hand back.

The PR body says `Closes #28`.

Ancillary docs are deliverables. Each of these must be non-empty, or the PR body says which cycle
dropped it and why:

- `git diff --stat origin/main -- docs/adr-format.md` (cycles 3, 5)
- `git diff --stat origin/main -- docs/cli.md` (cycle 6)
- `git diff --stat origin/main -- CHANGELOG.md` (cycle 6)

`uv run python scripts/check_doc_links.py` must pass.
