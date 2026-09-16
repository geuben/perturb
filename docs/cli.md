# CLI reference

The CLI is `perturb`. Every verb accepts `--json` and prints a stable envelope; the human
rendering is derived from the same object. Exit code 0 on success, 1 on a refusal with a `reason`,
2 on a usage error.

```json
{ "ok": true, "verb": "next", "synced_at": "2026-09-12T15:02:11Z", "data": { ... }, "warnings": [] }
```

## Configuration

Verbs that read repository conventions load `perturb/config.yaml` first: plan, friction-log and
audit locations, and the labels that mark an epic and a plan ready to implement (see
[configuration.md](configuration.md#config-perturbconfigyaml)). An invalid file refuses with
`config_invalid` before any GitHub call. `PERTURB_GH` chooses the GitHub CLI (see `perturb sync`).

## Read verbs

### `perturb ref <ref>`
Parses `<ref>` and returns the canonical form, kind, and id. A debugging aid — useful for
confirming what form the CLI will resolve before passing a ref to another verb.

```
ref: #29
kind: issue
id: 29
```

With `--json`: `{"ok": true, "verb": "ref", "data": {"ref": "#29", "kind": "issue", "id": "29"}, ...}`.
An unrecognised ref exits 2 and prints the accepted forms to stderr.

### `perturb sync [--full]`
Refresh `.perturb/github.json` incrementally and rederive `graph.json`. Emits `unblock` events
(status `pending`) for any issue whose last open blocker closed since the previous sync. Every
other verb runs this first; calling it directly is only useful with `--full`, which discards the
cursor and repages everything. After a successful sync, `graph.json` is derived from the cache and
plan front-matter (`paths.plan`); the response includes a `ready` count of open non-epic issues with all
blockers closed.

GitHub calls go through the command named in `PERTURB_GH`, or `gh` when it is unset or empty. It
must accept `gh`'s arguments (`api graphql`, `issue create`); a wrapper that supplies credentials
is the usual reason to set it. The value is one command name or path, not a command line: a
wrapper that needs arguments of its own belongs in a script. `gh` itself authenticates from its
login or from `GH_TOKEN`, which is how CI runs it.

Failure reasons: `no_github_remote` when the repository has no usable GitHub remote (not inside a
git repository, no `origin`, or a non-GitHub `origin`); `github_unreachable` when the GitHub CLI cannot
reach GitHub (network error, timeout, an unparseable response, or a CLI that cannot be run); `github_error` when the GraphQL
query itself is rejected (schema change, bad variable, authentication failure). All three are
refusals — the cache is never written on failure.

### `perturb next [--epic N] [--limit 5]`
Issues that are ready and not planned, ordered by how many open issues each would unblock, then by
number (see [concepts](concepts.md#ready-planned-and-next)).

```
#  issue  title                                  unblocks  epic
1  #29    Backfill daily rides from the logbook  1         #3
2  #30    Backfill monthly memberships           1         #3
```

### `perturb ready [--epic N] [--all]`
Every ready issue including planned ones. `--all` adds blocked issues with their open blockers,
which is the full epic picture.

```
issue  title                                  unblocks  epic
#29    Backfill daily rides from the logbook  1         #3
#30    Backfill monthly memberships           1         #3

Blocked

#31  Compute daily deltas  blocked by #29
#32  Monthly report        blocked by #30
```

### `perturb inbox <ref> [--include proposed]`
Pending events for a node, rendered with the source excerpt pulled from the `detail` anchor.
`inbox` does not sync — it reads `perturb/events/` only and works offline.
When a `detail` anchor cannot be resolved, a `warning: …` line is printed to stderr and the
item's excerpt is omitted.

```
Inbox for #29  (1 pending, 0 proposed)

[01J9Q7K2M4X8] decision from adr:0002#backfill-grain  (2026-09-08, reason: affects)
  Backfilled days remain daily-grain, marked source='logbook-backfill'
  > Backfilled days from the logbook remain daily-grain with a pre-computed split, and are
  > marked `source='logbook-backfill'` so they are never re-priced as if they were recorded
  > per trip.
  docs/adr/0002-per-trip-grain.md#consequences
```

### `perturb stale [<ref>]`
The gate before implementing. Reports planned issues that have drifted from their event ledger:

- A `pending` event whose `at` is strictly later than the plan file's last commit time
  (`why: "pending_newer"`).
- An `acknowledged` event whose `ack.plan_blob` differs from the plan's current committed blob
  (`why: "ack_blob_mismatch"`).

**Exit codes:** 0 when there are no stale issues; 1 when one or more are found. Scripts and agents
can gate on the exit code alone.

**`--json` envelope (empty — exit 0):**
```json
{"ok": true, "verb": "stale", "synced_at": "...", "data": []}
```

**`--json` envelope (non-empty — exit 1):**
```json
{
  "ok": false,
  "verb": "stale",
  "synced_at": "...",
  "reason": "stale",
  "data": [
    {
      "issue": 29,
      "plan": "tasks/foo.md",
      "stale_events": [
        {"id": "EVT-XXX", "at": "2026-09-01T10:00:00Z", "why": "pending_newer"}
      ]
    }
  ]
}
```

With `<ref>` (an issue number), restricts the report to that one issue. A syntactically bad ref is
a usage error (exit 2). Syncs GitHub first (network required).

### `perturb show <ref>`
Everything the graph knows about one node. Accepted refs: an issue number (`#29` or `29`) or a
plan slug (`plan:show-verb` or `tasks/show-verb.md`). Issue refs sync first (network required);
plan refs are local.

For an issue:
```
#29  Backfill daily rides
  state: OPEN
  ready: True
  planned: False
  epic: #3
  labels: task
  plan: none
  blocked by:
  blocking: #31
  events: (added by the ledger epic)
```

For a plan:
```
plan:show-verb
  issue: #6
  files:
    src/perturb/cli.py
    src/perturb/show.py
```

`files` lists the plan's [declared files](run-evidence-format.md#plan), including any test files
resolved from the plan's `test`, `tests` and `modifies_tests` ids (via tdd-cli >= 0.11.0), or
`none`. With `--json` it is a list.

Failure reasons: `unknown_issue` when the ref is not in the synced graph; `plan_not_found` when
the plan file is missing; `unsupported_ref` for ref kinds other than issue and plan (adr, area,
friction, audit); `github_unreachable` / `github_error` on sync failure (issue refs only).

With `--json`, the data object matches the text layout fields.

### `perturb graph [--epic N] [--format mermaid|dot]`
Exports the structural graph. Syncs first (GitHub unreachable is a refusal).

By default emits Mermaid flowchart syntax; `--format dot` emits Graphviz DOT. Text mode prints
the graph text verbatim. JSON mode wraps it: `{"format": "mermaid"|"dot", "text": "..."}`.

Node identifiers are `N<number>`; labels are `#<number> <title>`. Nodes appear in ascending
number order; sub-issue edges (solid) follow, then blocks edges labelled `blocks`, each group
sorted by source then target. Closed issues are rendered dimmed (Mermaid: `classDef closed`
style; DOT: `style=dashed` with grey colour and font). Edges whose other endpoint falls outside
the included set are dropped.

`--epic N` restricts to the transitive subtree rooted at N: N itself plus every issue reachable
by following sub-issue (parent) edges downward, including nested sub-epics and their children.
This is intentionally deeper than the `--epic` filter on `next`/`ready`/`show`, where `--epic`
means direct children only.

### `perturb check`
Lint, intended for CI. Non-zero when:

- an ADR fails the validation in [adr-format.md](adr-format.md#validation-in-perturb-check),
  including an accepted ADR with no events and no `no-propagation: true` flag with a reason;
- a Markdown file in `docs/adr` starts with a number but is not named `NNNN-<title>.md` (e.g.
  `2-x.md` or `0002_x.md`) — rename it to the four-digit padded form `perturb propose adr:` uses;
- an event targets a closed issue and is still pending;
- an event's `detail` anchor no longer resolves;
- a ready-to-implement issue is stale.

Each finding carries the command that fixes it.

## Write verbs

### `perturb init`
Bootstrap the committed `perturb/` store in the current git repository: `perturb/areas.yaml` (a
commented starter ending in `areas: {}`), `perturb/config.yaml` (every setting commented out at
its default), `perturb/README.md` (explaining the directory), and `perturb/events/` (with
`.gitkeep`). It also adds `.perturb/` to the repository's `.gitignore`, creating the file if
needed. Idempotent: an entry that already exists is reported and never rewritten, an existing
`events/` directory is left as is, and a `.gitignore` that already lists the cache (`.perturb`,
`.perturb/`, `/.perturb` or `/.perturb/`) is left unchanged. Fully local: no sync, no GitHub call.

`data` is `{"created": [...], "existing": [...]}`, each a list of `perturb/areas.yaml`,
`perturb/config.yaml`, `perturb/README.md`, `perturb/events/`, `.gitignore` in that order.
`.gitignore` is under `created` when perturb created the file or added the line.

Failure reasons: `not_a_git_repo` when run outside a git repository (nothing is created).

### `perturb adr migrate <file>`
Rewrite a prose ADR into the structured format in [adr-format.md](adr-format.md#migration-for-existing-adrs),
in place. The ADR id is taken from the leading digits of the filename. Fully local. `data` is
`{"path": "...", "consequences": N}`; an unparseable ADR refuses with the parser's reason.
`warnings` lists status-line segments that were not fully carried into the front-matter: a
`**Supersedes:**` line that doesn't name only whole ADRs (it stays in the body); a status-line
segment whose wording contains more than the ADR ref (a reason clause, an anchored ref, or
unrecognised text); or an `amends`/`amended_by` ref whose annotation was carried into the
front-matter but whose surrounding prose (e.g. the reason clause) is lost. Segments that are
wholly carried — a bare `amends ADR NNNN` or `amended by ADR NNNN` — produce no warning.

### `perturb propose <source-ref> [--review] [--by name]`
Read the source artefact, compute candidate targets, write `proposed` events. An epic ref as a
target (in `affects` or a mention) expands to the epic's open non-epic children; events never
target an epic. Candidate rules by source kind:

| Source | Rule | Born as |
|---|---|---|
| adr | per consequence, see [adr-format.md](adr-format.md) | pending for `affects: ["#N"]`, proposed otherwise |
| plan | "Design decisions (locked)" entries that name another `#NNN` | proposed |
| plan | "Deliberate scope cuts" entries that name another `#NNN` ("moves to #34") | proposed, kind `scope` |
| friction | files touched outside the plan's `files` → areas → open issues in area | proposed, kind `friction` |
| audit | CRITICAL and PLANNING DEBT items → open issues in the audit's areas | proposed, kind `friction` |
| audit | CRITICAL item with no candidate issue | with `--review`, accepted → new GitHub issue + event (reason `manual`); otherwise prints "no target; `perturb push --new`" | pending, kind `friction` |

One summary per candidate, taken from the consequence or bullet that produced the match.
`--review` walks the list interactively, for a human who has just written an ADR at the terminal.
Without it the tool writes the proposals and prints them as JSON for `confirm`/`dismiss`, which
is how agents drive it (see [agents.md](agents.md)). Nothing other
than an explicit `affects` or `supersedes`, or an issue the auditor accepts in
`propose audit: --review`, is ever born `pending`. A no-target item that already has such an
issue is listed under `already_raised` and never offered again. A failed `gh issue create`
refuses with `github_error`.

### `perturb confirm <event-id>... | --source <ref> --all`
`proposed → pending`.

### `perturb dismiss <event-id>... [--note "..."]`
`proposed|pending → dismissed`.

### `perturb push --from <ref> (--to <ref>... | --new "title") --kind decision|scope|friction|supersede|amend "summary" [--detail path#anchor] [--by name]`
Human-authored event, born `pending` with `reason: manual`. Syncs first and refuses if
GitHub is unreachable. `--from` is canonicalised but not validated against the cache. `--to` takes
one or more open, non-epic issue refs; an epic target is refused and lists its open children.
`--new "title"` instead of `--to` creates a GitHub issue via `gh issue create` with the summary
as body, then targets the returned issue number without cache validation. `--to` and `--new` are
mutually exclusive and exactly one is required. `--detail path#anchor` must resolve via the inbox
resolver. `proposed_by` is `--by <name>` if given, else `git config user.name`.

### `perturb ack <target-ref> [<event-id>... | --all] --plan tasks/<slug>.md --note "..." [--by <name>]`
`pending → acknowledged`, pinning the plan's current committed blob. `--plan` and `--note` are
required. Exactly one of positional `<event-id>...` or `--all` must be given:

- `--all` acknowledges every `pending` event for the target.
- One or more `<event-id>` arguments acknowledge only those events.

Re-acking an already-acknowledged event overwrites the ack and reports `was_acknowledged: true`.

Refusals:
- `plan_not_committed` — the plan is dirty (`git status --porcelain`) or not in HEAD
  (`git rev-parse HEAD:<plan>` non-zero). Reason: the ack must name a version that exists.
- `plan_target_mismatch` — the plan's `closes:` front-matter does not match `<target-ref>`.
- `ack_no_selection` — neither ids nor `--all` given.
- `ack_conflicting_selection` — both ids and `--all` given.
- `unknown_event` — an id not found in the ledger.
- `event_target_mismatch` — an id whose event targets a different issue.
- `event_not_pending` — an id whose event is not `pending` or `acknowledged`.

`by` is `--by <name>` if given, else `git config user.name`. No GitHub call is made; this verb
is fully local and offline-safe.

## Refs on the command line

`#29`, `29`, `adr:0002`, `adr:2`, `plan:fare-schema`, `tasks/fare-schema.md`,
`friction:fare-schema`, `area:fares` all resolve. Quoting `'#29'` is needed in zsh; bare `29`
is accepted to avoid that.

The plan-path form follows `paths.plan`: with `plan: plans/{slug}/plan.md`,
`plans/fare-schema/plan.md` resolves to `plan:fare-schema`.

## Worked session

```sh
perturb next                          # → #29, #30
perturb inbox 29                      # one pending decision from adr:0002
# planning #29 locks a decision that affects #33
perturb push --from 29 --to 33 --kind decision \
  "Reconciliation compares whole pence, not decimal strings; parser emits pence" \
  --detail tasks/backfill-daily-rides.md#design-decisions-locked
perturb ack 29 --all --plan tasks/backfill-daily-rides.md \
  --note "Design decision 2: backfill rows carry source='logbook-backfill'"
perturb stale                         # empty
# #29 is implemented and its friction log committed
perturb propose friction:backfill-daily-rides --review
perturb check                         # clean
```
