# 07 — Roadmap

Each step is usable on its own and is a prerequisite for the next. Stop after any step if the
value is not there.

## 1. ✅ `sync`, `next`, `ready`, `show`, `graph`
GraphQL fetch through `gh`, cache, derived ready-ness, priority order. No `perturb/` directory
yet. Answers "what do I plan next?" and gives the epic picture. Verify against the worked example in
[02-model.md](02-model.md) (epic #3): must print #29 and #30.

## 2. ✅ Events: `push`, `inbox`, `ack`, `stale`
The ledger with human-authored events only. `plan-issue` Phase A/C/E and `implement-issue` gate 6
change to call it. This is the point where decisions made while planning one issue reach the next,
which is the original complaint.

## 3. ✅ Structured ADRs, `adr migrate`, `propose` from ADRs, `confirm`, `dismiss`, `check`
The format in 08, the migration command, per-consequence proposals, `supersedes`. The PostToolUse
hook is not built (see [05-integration.md](05-integration.md#hooks)). Migrate existing prose ADRs and confirm the proposals match what a human would
have written.

## 4. ✅ Areas, `propose` from plans, friction logs and audits
`areas.yaml`, glob matching against cycle `files` and friction commit lists, the audit step.
`implement-issue` and `audit-friction-log` change.

## 5. ✅ CI job, `perturb` skill, mirror comments (if decision 4 flips)
`.github/workflows/perturb-check.yml` runs `perturb check` on every PR and push to `main`, and fails
on any finding. The `perturb` skill in `skills/perturb/`, installable as a Claude Code plugin, maps questions to
read verbs.
Mirror comments are not built: decision 4 has not flipped.

Adoption ergonomics tracked alongside: ✅ `perturb init` to bootstrap the `perturb/` ledger for a
new repo instead of assembling it by hand (#51).

## Acceptance for the whole thing
Over one epic planned and implemented end to end: zero cases of "I found out about that decision
while implementing" that were not already in the inbox, and `perturb check` green at every merge.
If the dismissal rate on proposals is above roughly half, the proposal rules are too loose and step
3's area and mention rules need tightening before step 4 adds more sources.
