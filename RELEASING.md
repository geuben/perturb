# Releasing

Publishing uses PyPI [trusted publishing](https://docs.pypi.org/trusted-publishers/):
`release.yml` publishes from the `pypi` GitHub environment; no tokens are stored.

## One-time setup

1. On pypi.org, add a pending trusted publisher for the `perturb` project: owner `geuben`,
   repository `perturb`, workflow `release.yml`, environment `pypi`.
2. In the repository settings, create the `pypi` environment. Restrict its deployments to tags
   matching `v*`, and add yourself as a required reviewer so a release waits for approval.

## Per release

1. Update `__version__` in `src/perturb/__init__.py` (the single source of truth: `pyproject.toml`
   reads it via hatch), and `version` in `.claude-plugin/plugin.json` to match.
2. Move the `Unreleased` notes in `CHANGELOG.md` under the new version with today's date.
3. Commit, PR, merge to `main`; wait for CI to pass.
4. Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.
5. Create a GitHub Release from the tag (paste the changelog section). Its publication triggers
   `release.yml`, which builds and publishes to PyPI via trusted publishing.
6. Verify: `uvx perturb@X.Y.Z --version`.
