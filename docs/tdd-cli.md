# Using perturb with tdd-cli

perturb works with any way of planning and implementing, but it pairs especially well with
[tdd-cli](https://github.com/geuben/tdd-cli), which executes plans as test-driven cycles and is what
perturb itself is built with. tdd-cli's plans and run logs already contain what perturb reads, so
there's nothing extra to write.

## Plans

A tdd-cli plan is Markdown with its contract in YAML front-matter. Add `closes:` (and optionally
`areas:`) and perturb reads it as a plan. Its declared files, which `perturb propose friction:`
leaves out, come from the contract as well as any `files:` list:

| Field | Meaning in tdd-cli |
|---|---|
| `cycles[].files` | production files the cycle changes |
| `cycles[].stub_expected` | files the cycle stubs before its failing test |
| `ancillary_files` | other paths the plan writes, such as docs and generated files |

Because a contract names its files per cycle, friction proposals flag only files the plan genuinely
didn't expect. `perturb show plan:<slug>` lists them.

## Friction logs

`tdd log render --out tasks/friction-logs/<slug>-friction.md` writes one list item per commit, each
hash followed by its phase:

```markdown
- `a89ed3b7b` [red] test: propose friction writes events
- `57ce145d9` [green] feat: wire the friction source
```

perturb reads these directly, so a rendered log needs no `commits:` front-matter. The rest of it,
including the outcome, human interventions, integrity events and the executor's notes, is the
evidence a review works from. The default paths of the two tools match.

## Fitting the loop

- **Planning:** commit the plan before `tdd plan register` and `perturb ack`, since both pin the
  committed version.
- **Implementing:** run `perturb stale <N>` before `tdd run start`, and again before resuming an
  active run.
- **After the run:** once `next_action.terminal` is true, render the friction log, commit it, and
  run `perturb propose friction:<slug>`.
- **Reviewing:** events such as `undeclared_file_touched` and the run's `tdd note` entries show
  where the audit should look first.

The [planning](planning.md), [implementing](implementing.md) and [reviewing](reviewing.md) guides
describe each phase without assuming tdd-cli.
