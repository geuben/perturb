# Documentation

**New to perturb?** Start with [Getting started](getting-started.md), which sets up a repository and
walks through the whole loop.

**Understand it**

- [Concepts](concepts.md): refs, the issue graph, events and their lifecycle, inboxes, the stale
  gate, areas and checks

**Guides**

- [Using perturb with agents](agents.md): reading perturb's output, and the loop from choosing an
  issue to reviewing the run
- [Planning an issue](planning.md): absorbing the inbox, passing decisions on, acknowledging
- [Implementing a plan](implementing.md): gating on `stale`, then proposing friction
- [Reviewing a run](reviewing.md): writing an audit and deciding proposals
- [Using perturb with tdd-cli](tdd-cli.md): what tdd-cli's plans and run logs give perturb for free
- [Working in a team](teams.md): what works, the pitfalls of branches and parallel work, and the
  habits that help

**Reference**

- [CLI reference](cli.md): every verb, its output and its refusals
- [Configuration and repository files](configuration.md): `perturb/`, `config.yaml`, areas and the
  cache
- [ADR format](adr-format.md): structured ADRs, whose consequences become events
- [Plan, friction log and audit formats](run-evidence-format.md): what any tool must write

**Design notes**

- [docs/design/](design/README.md): why perturb is built the way it is, for people working on it
