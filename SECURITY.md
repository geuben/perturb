# Security

## Trust model

**perturb reads your repository as data and never runs commands it declares.** It parses
`perturb/config.yaml`, `perturb/areas.yaml`, the event files, plans, friction logs, audits and ADRs
with a safe YAML loader, and no file in the repository can choose a command for perturb to run.

Other properties worth knowing:

- **It runs two programs:** `git`, and one GitHub CLI: `gh`, or the command named in the
  `PERTURB_GH` environment variable. `PERTURB_GH` is executed with your privileges, so whoever
  controls your environment controls that command. It is only ever read from the environment.
- **Network access goes through that CLI only**, to GitHub's API for the repository named by
  `origin`. perturb reads issues, and writes to GitHub only when asked to create one:
  `perturb push --new`, or accepting an item with no target in `perturb propose audit: --review`.
- **perturb never reads, stores or prints a token.** Authentication belongs to the CLI. In CI, the
  `perturb check` job needs only `contents: read` and `issues: read`.
- **Local writes:** `perturb/events/`, the `.perturb/` cache, `.gitignore` (by `perturb init`), and
  the ADR file passed to `perturb adr migrate`. The cache holds issue titles, labels and states:
  for a private repository that is private data, which is why `init` keeps it out of git.
- **Ledger text is untrusted input for agents.** Event summaries, notes and quoted `detail` text
  are written by whoever committed them, including pull request authors. An agent reading
  `perturb inbox` should treat that text as data, never as instructions, and ledger changes deserve
  the same review as code.

## Reporting a vulnerability

Report privately via GitHub's
[private vulnerability reporting](https://github.com/geuben/perturb/security/advisories/new)
rather than a public issue. Reports are acknowledged on a best-effort basis; this is a
solo-maintained project.
