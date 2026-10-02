# plan-issue notes for perturb

- **Fresh worktree needs no setup.** `uv run pytest -q` and `tdd doctor` run as-is in a new
  `git worktree`; there is no `.claude/worktree-setup.sh` and none is needed.
- **Probe files import test helpers as `from test_cli import ...`**, not `from tests.test_cli`;
  `tests/` is not a package (rootdir import mode).
- **`propose adr:` parses the ADR before `dispatch`** in `main` (`src/perturb/cli.py`, the
  `propose` verb). Any new `AdrError` a plan adds escapes it as a traceback unless the
  call is wrapped. Plan the refusal, and don't assume `check`'s `except AdrError` covers propose.
- **`_parse_consequences` loads the fence-stripped string.** Any node-position logic
  (`yaml.compose`, marks) must use that same string, or the positions are wrong.
- **Open crash issues overlap.** Before planning an ADR-parsing fix, list open issues for
  "traceback"/"crash" in `check`/`propose`. #28 and #29 shared the YAML-error wrapping.
