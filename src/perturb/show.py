from pathlib import Path

import yaml

from perturb.config import Config
from perturb.envelope import Refusal
from perturb.propose import read_declared_paths


def show(ref, *, graph_issues=None, repo_root=None, config=None):
    if ref.kind == "issue":
        issue = (graph_issues or {}).get(str(ref.id))
        if issue is None:
            raise Refusal("unknown_issue", f"#{ref.id} not found in graph")
        blocked_by = [
            {"number": b, "state": (graph_issues or {}).get(str(b), {}).get("state", "unknown")}
            for b in issue.get("blocked_by", [])
        ]
        return {
            "kind": "issue",
            "number": issue["number"],
            "title": issue["title"],
            "state": issue["state"],
            "labels": issue["labels"],
            "epic": issue["epic"],
            "ready": issue["ready"],
            "planned": issue["planned"],
            "plan": issue["plan"],
            "blocked_by": blocked_by,
            "blocking": issue["blocks"],
        }
    if ref.kind == "plan":
        plan_rel_path = (config or Config()).plan_path(ref.id)
        path = Path(repo_root) / plan_rel_path
        if not path.exists():
            raise Refusal("plan_not_found", f"{plan_rel_path} not found")
        text = path.read_text()
        lines = text.split("\n")
        try:
            end = lines.index("---", 1)
        except ValueError:
            end = len(lines)
        fm = yaml.safe_load("\n".join(lines[1:end])) or {}
        files = sorted(p for p in read_declared_paths(text) if isinstance(p, str))
        return {"kind": "plan", "slug": ref.id, "issue": fm.get("closes"), "files": files}
    raise Refusal("unsupported_ref", f"ref kind {ref.kind!r} is not supported by show")


def render_show(data):
    if data["kind"] == "issue":
        lines = [f"#{data['number']}  {data['title']}"]
        lines.append(f"  state: {data['state']}")
        lines.append(f"  ready: {data['ready']}")
        lines.append(f"  planned: {data['planned']}")
        epic = data["epic"]
        lines.append(f"  epic: #{epic}" if epic is not None else "  epic: none")
        labels = ", ".join(data["labels"]) if data["labels"] else "none"
        lines.append(f"  labels: {labels}")
        plan = data["plan"]
        lines.append(f"  plan: {plan}" if plan else "  plan: none")
        lines.append("  blocked by:")
        for b in data["blocked_by"]:
            lines.append(f"    #{b['number']} ({b['state'].lower()})")
        blocking = data["blocking"]
        if blocking:
            lines.append("  blocking: " + " ".join(f"#{n}" for n in blocking))
        else:
            lines.append("  blocking: none")
        lines.append("  events: (added by the ledger epic)")
        return "\n".join(lines) + "\n"
    if data["kind"] == "plan":
        lines = [f"plan:{data['slug']}"]
        issue = data["issue"]
        lines.append(f"  issue: #{issue}" if issue is not None else "  issue: none")
        if data["files"]:
            lines.append("  files:")
            lines.extend(f"    {path}" for path in data["files"])
        else:
            lines.append("  files: none")
        return "\n".join(lines) + "\n"
    return ""
