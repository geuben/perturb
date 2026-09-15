import hashlib
import json
from pathlib import Path

import yaml

from perturb.config import (
    DEFAULT_EPIC_LABEL,
    DEFAULT_PLAN_PATTERN,
    DEFAULT_READY_TO_IMPLEMENT_LABEL,
    SLUG_PLACEHOLDER,
    Config,
    match_slug,
)


def parse_plan_closes(text: str) -> int | None:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    front_matter = "\n".join(lines[1:end])
    try:
        data = yaml.safe_load(front_matter)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    closes = data.get("closes")
    return closes if isinstance(closes, int) else None


def load_plans(
    repo_root: Path, pattern: str = DEFAULT_PLAN_PATTERN
) -> tuple[dict[int, str], list[str]]:
    repo_root = Path(repo_root)
    plans: dict[int, str] = {}
    warnings: list[str] = []
    for path in sorted(repo_root.glob(pattern.replace(SLUG_PLACEHOLDER, "*"))):
        rel = path.relative_to(repo_root).as_posix()
        if not path.is_file() or match_slug(pattern, rel) is None:
            continue
        closes = parse_plan_closes(path.read_text())
        if closes is None:
            continue
        if closes in plans:
            warnings.append(f"#{closes}: {plans[closes]} and {rel}")
        else:
            plans[closes] = rel
    return plans, warnings


def is_epic(issue: dict) -> bool:
    """Whether an issue is an epic. Derived graph issues carry `is_epic`, computed with the
    configured label; an issue dict without it falls back to the default `epic` label."""
    if "is_epic" in issue:
        return bool(issue["is_epic"])
    return DEFAULT_EPIC_LABEL in issue.get("labels", [])


def derive(
    cache_issues: dict,
    plans: dict[int, str],
    *,
    ready_to_implement_label: str = DEFAULT_READY_TO_IMPLEMENT_LABEL,
    epic_label: str = DEFAULT_EPIC_LABEL,
) -> dict:
    result = {}
    for key, issue in cache_issues.items():
        number = issue["number"]
        blocked_by = sorted(b["number"] for b in issue.get("blockedBy", []))
        blocks = sorted(set(b["number"] for b in issue.get("blocking", [])))
        labels = issue["labels"]
        blocked_by_entries = issue.get("blockedBy", [])
        epic = epic_label in labels
        ready = (
            issue["state"] == "OPEN"
            and not epic
            and all(b["state"] == "CLOSED" for b in blocked_by_entries)
        )
        plan = plans.get(number)
        planned = plan is not None and ready_to_implement_label in labels
        result[key] = {
            "blocked_by": blocked_by,
            "blocks": blocks,
            "epic": issue.get("parent"),
            "is_epic": epic,
            "labels": labels,
            "number": number,
            "plan": plan,
            "planned": planned,
            "ready": ready,
            "state": issue["state"],
            "title": issue["title"],
        }
    # Add inverse blocks edges from other issues' blockedBy
    for _key, issue in cache_issues.items():
        for blocker in issue.get("blockedBy", []):
            blocker_key = str(blocker["number"])
            if blocker_key in result:
                blocks_set = set(result[blocker_key]["blocks"])
                blocks_set.add(issue["number"])
                result[blocker_key]["blocks"] = sorted(blocks_set)
    # Compute unblocks for each issue
    for key in result:
        n = result[key]["number"]
        result[key]["unblocks"] = _count_unblocks(n, result, {n})
    return result


def _count_unblocks(number: int, result: dict, visited: set) -> int:
    key = str(number)
    if key not in result:
        return 0
    count = 0
    for downstream in result[key]["blocks"]:
        if downstream in visited:
            continue
        visited.add(downstream)
        if result.get(str(downstream), {}).get("state") == "OPEN":
            count += 1
        count += _count_unblocks(downstream, result, visited)
    return count


def write_graph(
    root: Path, *, issues: dict, head: str, cache_hash: str, warnings: list, config=None
) -> None:
    data = {"cache_hash": cache_hash, "head": head, "issues": issues, "warnings": warnings}
    if config is not None:
        data["config"] = config
    (root / "graph.json").write_text(json.dumps(data, indent=1, sort_keys=True))


def ensure_graph(root: Path, repo_root: Path, head: str, config: Config | None = None) -> dict:
    cfg = config if config is not None else Config()
    fingerprint = cfg.fingerprint()
    github_bytes = (root / "github.json").read_bytes()
    cache_hash = hashlib.sha256(github_bytes).hexdigest()

    graph_path = root / "graph.json"
    if graph_path.exists():
        existing = json.loads(graph_path.read_text())
        if (
            existing.get("head") == head
            and existing.get("cache_hash") == cache_hash
            and existing.get("config") == fingerprint
        ):
            return existing

    cache_issues = json.loads(github_bytes)["issues"]
    plans, warnings = load_plans(repo_root, cfg.plan)
    issues = derive(
        cache_issues,
        plans,
        ready_to_implement_label=cfg.ready_to_implement_label,
        epic_label=cfg.epic_label,
    )
    write_graph(
        root,
        issues=issues,
        head=head,
        cache_hash=cache_hash,
        warnings=warnings,
        config=fingerprint,
    )
    return json.loads(graph_path.read_text())
