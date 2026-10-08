# 06 — Open questions

> Exploratory. See the [index](README.md).

| # | Question | Leaning | Depends on |
|---|---|---|---|
| 1 | Area membership: keep `area:x` labels, or move to area-targeted events pulled at planning time? | area-targeted events; multi-repo makes label lookups expensive | whether events stay one-off deltas (6) |
| 2 | How do area-targeted events gate? A new area event would make every plan in the area stale, including in-flight ones | gate only unmerged plans; reach in-flight work only through a planner's re-plan | 1 |
| 3 | Is every decision-maker planning through PRs, or do some decide in Jira, Confluence or elsewhere? | assumed all in git | if not, the service needs an API for authoring events, finalised without a PR |
| 4 | Service outage: do readers fail closed or fall back to the git reader? | fall back; the git reader is the same query interface | [05](05-ledger-service.md) |
| 5 | Who runs the ledger service, and is a git-only mode kept for single teams? | keep git-only as the zero-infrastructure mode | product direction |
| 6 | Do teams record standing rules as ADRs, so events stay one-off deltas? | needs checking against real teams; if not, area events accumulate and need another retirement rule | |
| 7 | Mechanics of resuming after a plan amendment: how does tdd-cli resume a run against an amended plan whose early cycles stand? | a plan delta naming kept and redone cycles | tdd-cli |
| 8 | Epics: drop the concept, or let the dispatcher expand events aimed at epics? | drop from perturb | [03](03-scope-reduction.md) |
| 9 | Identity: record the agent run (`actor`) separately from the operator who launched it (`on_behalf_of`)? | yes, for audit | |
| 10 | Archiving: settled events for closed issues need compacting so reads stay fast | archive by age once closed | scale |
| 11 | Do agents ever self-select work with no dispatcher? If so, something must provide claims | assumed a dispatcher always assigns | [02](02-in-flight-changes.md) |
