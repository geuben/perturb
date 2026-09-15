from pathlib import Path

AREAS_TEMPLATE = """\
# Declared areas for this repository. Hand-edited, never inferred; keep under ten.
# Globs are matched against plan cycle `files` and friction commit file lists to route
# findings to open issues. Replace `areas: {}` below with a map like this example:
#
# areas:
#   rides:
#     paths: ["src/core/rides/**", "migrations/*ride*"]
#     issues_label: "area:rides"   # optional; default is area:<slug>
#
# Docs: https://github.com/geuben/perturb/blob/main/docs/configuration.md
areas: {}
"""

CONFIG_TEMPLATE = """\
# Repository conventions for perturb. Every key is optional: the values below are the
# defaults, so a file of comments changes nothing. Uncomment a line to change it.
#
# paths:
#   plan: tasks/{slug}.md
#   friction_log: tasks/friction-logs/{slug}-friction.md
#   audit: tasks/friction-audits/{slug}-audit.md
# labels:
#   ready_to_implement: ready-to-implement
#   epic: epic
#
# Docs: https://github.com/geuben/perturb/blob/main/docs/configuration.md
"""

README_TEMPLATE = """\
# `perturb/` — the event ledger

This is the one writable store for decisions made while planning or implementing an issue, kept
next to the code and committed in the same PR as the artefact that caused them. `areas.yaml`
declares the path-glob areas that route findings between issues; `config.yaml` says where plans,
friction logs and audits live and which labels mark epics and issues ready to implement; `events/`
holds one YAML file per event, named by ULID (created by `perturb push` / `perturb propose`,
acknowledged in place by `perturb ack`). Anything derived from GitHub is a gitignored cache under
`.perturb/`, never here.

Docs: [configuration](https://github.com/geuben/perturb/blob/main/docs/configuration.md),
[concepts](https://github.com/geuben/perturb/blob/main/docs/concepts.md).
"""


def init_ledger(repo_root):
    root = Path(repo_root)
    planning = root / "perturb"
    events_dir = planning / "events"

    created = []
    existing = []

    for rel, template in (
        ("areas.yaml", AREAS_TEMPLATE),
        ("config.yaml", CONFIG_TEMPLATE),
        ("README.md", README_TEMPLATE),
    ):
        path = planning / rel
        if path.exists():
            existing.append(f"perturb/{rel}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(template)
            created.append(f"perturb/{rel}")

    if events_dir.exists():
        existing.append("perturb/events/")
    else:
        events_dir.mkdir(parents=True, exist_ok=True)
        (events_dir / ".gitkeep").write_text("")
        created.append("perturb/events/")

    if _ensure_cache_ignored(root / ".gitignore"):
        created.append(".gitignore")
    else:
        existing.append(".gitignore")

    return {"created": created, "existing": existing}


CACHE_ENTRY = ".perturb/"
_CACHE_ENTRY_FORMS = {".perturb", ".perturb/", "/.perturb", "/.perturb/"}


def _ensure_cache_ignored(gitignore):
    """Add the cache to `.gitignore`, creating the file if needed.

    Returns False when an entry for the cache is already there, and the file is left as is.
    """
    text = gitignore.read_text() if gitignore.exists() else ""
    if any(line.strip() in _CACHE_ENTRY_FORMS for line in text.splitlines()):
        return False
    separator = "" if not text or text.endswith("\n") else "\n"
    gitignore.write_text(f"{text}{separator}{CACHE_ENTRY}\n")
    return True
