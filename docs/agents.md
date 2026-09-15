# Using perturb with agents

perturb was built for workflows where planning, implementing and reviewing run as separate agent
sessions, each starting with only what it is given. It doesn't ship those agents or mandate their
shape. Instead it offers fixed points to hook into, described in one guide per phase. This page
covers what every phase shares: reading perturb's output, and the loop as a whole.

## Reading perturb's output

Every verb takes `--json` and prints one envelope:

```json
{"ok": true, "verb": "next", "synced_at": "2026-09-15T19:26:20Z", "data": {"issues": []}, "warnings": []}
```

A refusal sets `ok` to false and explains itself:

```json
{"ok": false, "verb": "show", "reason": "config_invalid", "detail": "config.yaml: paths.plan must contain {slug} exactly once: 'plans/plan.md'"}
```

- **Exit codes:** 0 on success; 1 on a refusal or a failing gate (`stale`, `check`); 2 on a usage
  error. An agent can gate on the exit code alone.
- **Refusals are stops, not hints.** Report the `reason` and `detail`; don't retry blindly or answer
  from memory. The common network refusals are `github_unreachable`, `github_error` and
  `no_github_remote`.
- **Credentials:** perturb calls `gh`, which uses its own login or `GH_TOKEN`, or the wrapper named
  in `PERTURB_GH`. Never put a token in a command an agent runs; commands end up in transcripts.

## The loop

| Phase | What perturb adds | Guide |
|---|---|---|
| choose | `perturb next --json`: the first issue is ready, unplanned, and unblocks the most other work | |
| plan | read and absorb the inbox, pass decisions on, acknowledge, check `stale` | [Planning an issue](planning.md) |
| implement | gate on `stale` and stop if it fails; afterwards propose friction from the run's commits | [Implementing a plan](implementing.md) |
| review | audit the run, then confirm or dismiss its proposals and the audit's | [Reviewing a run](reviewing.md) |

Three rules hold the loop together:

- **Each phase decides only what it is positioned to judge.** The planner decides proposals for its
  issue; the implementer never re-plans; the reviewer, not the implementer, decides friction.
- **Stopping is a valid outcome.** An implementer that refuses a stale plan has done its job.
- **Ledger changes are committed with the work that caused them**, so they are reviewed with it.

Each guide ends with example instructions to adapt into your own prompts or skills.

## Answering questions

A thin assistant can map questions straight onto read verbs:

| Question | Command |
|---|---|
| what should I plan next? | `perturb next --json` |
| what's ready? | `perturb ready --json` |
| what changed for 32? | `perturb inbox 32 --json --include proposed` |
| is 32's plan still valid? | `perturb stale 32 --json` |
| tell me about 32 | `perturb show 32 --json` |
| is the ledger clean? | `perturb check --json` |

## The perturb skill

The [`perturb` skill](../skills/perturb/SKILL.md) teaches an agent exactly this: each question maps
to one read verb, and the skill never writes to the ledger. It is written in the
[Agent Skills](https://agentskills.io) format.

In Claude Code, install it as a plugin from this repository:

```sh
claude plugin marketplace add geuben/perturb
claude plugin install perturb@perturb
```

With other agents, or to install it by hand, copy [`skills/perturb/`](../skills/perturb) wherever
your agent loads skills from (for Claude Code, `.claude/skills/` in a repository or
`~/.claude/skills/`).
