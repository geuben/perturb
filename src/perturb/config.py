"""Repository conventions: where plans, friction logs and audits live, and which issue labels
mean "ready to implement" and "epic". Read from `perturb/config.yaml`; every key is optional."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

SLUG_PLACEHOLDER = "{slug}"
SLUG_PATTERN = r"[A-Za-z0-9._-]+"

DEFAULT_PLAN_PATTERN = "tasks/{slug}.md"
DEFAULT_FRICTION_LOG_PATTERN = "tasks/friction-logs/{slug}-friction.md"
DEFAULT_AUDIT_PATTERN = "tasks/friction-audits/{slug}-audit.md"
DEFAULT_READY_TO_IMPLEMENT_LABEL = "ready-to-implement"
DEFAULT_EPIC_LABEL = "epic"

_PATH_KEYS = {"plan": "plan", "friction_log": "friction_log", "audit": "audit"}
_LABEL_KEYS = {"ready_to_implement": "ready_to_implement_label", "epic": "epic_label"}


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    plan: str = DEFAULT_PLAN_PATTERN
    friction_log: str = DEFAULT_FRICTION_LOG_PATTERN
    audit: str = DEFAULT_AUDIT_PATTERN
    ready_to_implement_label: str = DEFAULT_READY_TO_IMPLEMENT_LABEL
    epic_label: str = DEFAULT_EPIC_LABEL

    def plan_path(self, slug: str) -> str:
        return self.plan.replace(SLUG_PLACEHOLDER, slug)

    def friction_log_path(self, slug: str) -> str:
        return self.friction_log.replace(SLUG_PLACEHOLDER, slug)

    def audit_path(self, slug: str) -> str:
        return self.audit.replace(SLUG_PLACEHOLDER, slug)

    def fingerprint(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


def match_slug(pattern: str, path: str) -> str | None:
    """The slug `path` fills into `pattern`, or None when it does not fit the pattern."""
    head, tail = pattern.split(SLUG_PLACEHOLDER)
    m = re.fullmatch(re.escape(head) + f"({SLUG_PATTERN})" + re.escape(tail), path)
    return m.group(1) if m else None


def load_config(path: Path) -> Config:
    path = Path(path)
    if not path.exists():
        return Config()
    name = path.name
    try:
        doc = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ConfigError(f"{name}: not valid YAML ({exc})") from None
    if doc is None:
        return Config()
    if not isinstance(doc, dict):
        raise ConfigError(f"{name}: expected a mapping with optional 'paths' and 'labels'")
    unknown = sorted(set(doc) - {"paths", "labels"})
    if unknown:
        raise ConfigError(f"{name}: unknown key(s) {', '.join(unknown)}; expected paths, labels")

    values = {}
    for key, value in _section(doc, "paths", _PATH_KEYS, name).items():
        _check_pattern(f"paths.{key}", value, name)
        values[_PATH_KEYS[key]] = value
    for key, value in _section(doc, "labels", _LABEL_KEYS, name).items():
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{name}: labels.{key} must be a non-empty string")
        values[_LABEL_KEYS[key]] = value.strip()
    return Config(**values)


def _section(doc, section_name, allowed, name):
    section = doc.get(section_name)
    if section is None:
        return {}
    if not isinstance(section, dict):
        raise ConfigError(f"{name}: '{section_name}' must be a mapping")
    unknown = sorted(set(section) - set(allowed))
    if unknown:
        raise ConfigError(
            f"{name}: unknown {section_name} key(s) {', '.join(unknown)}; "
            f"expected {', '.join(sorted(allowed))}"
        )
    return section


def _check_pattern(key, value, name):
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{name}: {key} must be a path pattern string")
    if value.count(SLUG_PLACEHOLDER) != 1:
        raise ConfigError(f"{name}: {key} must contain {{slug}} exactly once: {value!r}")
    if any(ch in value.replace(SLUG_PLACEHOLDER, "") for ch in "{}*?[]"):
        raise ConfigError(
            f"{name}: {key} may not contain braces or glob characters besides {{slug}}: {value!r}"
        )
    if value.startswith("/") or "\\" in value or ".." in value.split("/"):
        raise ConfigError(f"{name}: {key} must be a relative path inside the repository: {value!r}")
