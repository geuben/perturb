# Reviewing a run with perturb

After implementation, a reviewer, whether a person or a separate agent, reads the friction log,
checks it against what the commits actually did, and decides which findings should reach other
issues. perturb turns those decisions into events. How you review, and what else an audit says, is
up to you.

## 1. Check the friction log against git

This isn't a perturb step, but it is what makes the resulting events worth trusting. Implementers
err in two directions: they understate problems ("everything went fine") and they misattribute them
(blaming the plan for their own choices). Before believing the log:

- compare the files the commits changed with the files the plan declared;
- read the tests or code the log calls hard, rather than taking its word;
- look for changes the log doesn't mention at all.

## 2. Write the audit

Write it at `paths.audit` (default `tasks/friction-audits/<slug>-audit.md`, with the plan's slug).
perturb reads only checkbox items carrying a level:

```markdown
- [ ] **[CRITICAL]** `src/core/fares/pricing.py` mixes pence and pounds; see #31
- [ ] **[PLANNING DEBT]** the plan never checked that the refund routes existed
```

- **Spell the levels exactly.** Other spellings, or a level in a heading or table, are ignored.
- **`CRITICAL`** is a problem in the code that other work will hit. Put paths in backticks and name
  issues as `#N`: that is how the item finds its targets.
- **`PLANNING DEBT`** is a problem in how the work was planned. It is proposed to `area:planning`
  when `perturb/areas.yaml` declares that area, and recorded as dismissed otherwise. Declare it if
  you track improvements to your planning process as issues.
- **Everything else is yours.** A summary, what you verified, the unplanned changes and where the
  plan failed are all useful, and perturb ignores them.

The format is in [Plan, friction log and audit formats](run-evidence-format.md#audit).

## 3. Propose and decide

Commit the audit, then decide the run's proposals together with the audit's own. The reviewer
decides because the review is the check on the implementer.

**By hand:**

```sh
perturb propose audit:<slug> --review
```

This walks every still-proposed event from the run's friction log and every proposal the audit
just created, asking accept, dismiss or skip. Then it offers each `CRITICAL` item that found no
target: accepting creates a GitHub issue with a pending event on it, so the problem joins the
issue graph instead of sitting in a report. A skipped item is offered again next time.

**As an agent:**

```sh
perturb propose audit:<slug> --json       # the audit's proposals, and untargeted CRITICAL items
perturb propose friction:<slug> --json    # re-running lists the run's events and their status
perturb confirm <id>...
perturb dismiss <id> --note "<why>"
```

Decide every event whose status is `proposed`. `CRITICAL` items with no target come back as
warnings; open an issue for each one that deserves it:

```sh
perturb push --from audit:<slug> --new "<issue title>" --kind friction "<summary>"
```

Either way, commit `perturb/events` with the audit.

## Rules worth keeping

- **Don't review your own run.** An agent that implemented a plan shouldn't audit it in the same
  session.
- **Dismiss with a reason.** A dismissal is kept so the proposal isn't raised again; the note tells
  the next reader why.
- **Prefer an issue over a checkbox.** An untargeted `CRITICAL` item left in an audit is rarely
  reopened.

## What stays yours

What the audit covers, how it is structured, how deeply claims are checked, and who reviews. The
only fixed parts are the checkbox items above and the file's location.

## Example instructions

A fragment to adapt into a review prompt or skill:

```markdown
To review the run for plan <slug>:
- Read the friction log and verify its claims against `git show` for each listed commit and
  against the plan's declared files.
- Write the audit at tasks/friction-audits/<slug>-audit.md. Record findings as
  `- [ ] **[CRITICAL]** ...` (code problems; backtick the paths) or
  `- [ ] **[PLANNING DEBT]** ...` (planning problems).
- Commit it, run `perturb propose audit:<slug> --json` and `perturb propose friction:<slug> --json`,
  and confirm or dismiss (with a note) every event still `proposed`. For a CRITICAL item with no
  target that deserves one, run `perturb push --from audit:<slug> --new "<title>" --kind friction
  "<summary>"`. Commit perturb/events.
```
