# tasks/

TDD plans, one file per issue, written as described in
[docs/planning.md](../docs/planning.md) and executed with `tdd-cli`.

- `tasks/<kebab-slug>.md` — a plan, with `closes: <issue>` in its front-matter.
  The tracking issue carries a `Task file:` line and the `ready-to-implement` label once
  the plan has been audited.
- `tasks/friction-logs/` — friction logs written at the end of each run
  (`tdd log render`), reviewed as described in [docs/reviewing.md](../docs/reviewing.md).

Plans are committed before execution begins: the `ready-to-implement` label is a claim
about a file that exists in the repository, not about a draft in a transcript.

Test ids are project-relative to the repo root: `tests/test_x.py::test_y`.
