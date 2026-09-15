import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from perturb import __version__
from perturb.config import DEFAULT_EPIC_LABEL
from perturb.events import EventStore

ISSUES_QUERY = """\
query($owner:String!,$name:String!,$after:String){
  repository(owner:$owner,name:$name){
    issues(first:50,after:$after,states:[OPEN,CLOSED],orderBy:{field:UPDATED_AT,direction:DESC}){
      pageInfo{hasNextPage endCursor}
      nodes{
        number title state updatedAt
        labels(first:20){nodes{name}}
        parent{number}
        blockedBy(first:20){nodes{number state}}
        blocking(first:20){nodes{number state}}
        body
      }
    }
  }
}"""


@dataclass
class SyncResult:
    fetched: int
    total: int
    synced_at: str


def _reduce_node(node):
    body = node.get("body") or ""
    lines = body.split("\n")
    body_head = "\n".join(lines[:40])
    parent = node.get("parent")
    return {
        "blockedBy": [
            {"number": n["number"], "state": n["state"]} for n in node["blockedBy"]["nodes"]
        ],
        "blocking": [
            {"number": n["number"], "state": n["state"]} for n in node["blocking"]["nodes"]
        ],
        "body_head": body_head,
        "labels": [n["name"] for n in node["labels"]["nodes"]],
        "number": node["number"],
        "parent": parent["number"] if parent else None,
        "state": node["state"],
        "title": node["title"],
        "updatedAt": node["updatedAt"],
    }


def _load_meta(root):
    meta_path = root / "meta.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text())
    return None


def _load_existing(root):
    cache_path = root / "github.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text()).get("issues", {})
    return {}


def newly_ready_unblocks(prev_issues, new_issues, *, epic_label=DEFAULT_EPIC_LABEL):
    results = []
    for issue_key, new_issue in new_issues.items():
        prev_issue = prev_issues.get(issue_key)
        if prev_issue is None:
            continue
        if epic_label in prev_issue.get("labels", []) or epic_label in new_issue.get("labels", []):
            continue
        prev_open_blockers = {b["number"] for b in prev_issue["blockedBy"] if b["state"] == "OPEN"}
        if not prev_open_blockers:
            continue
        new_open_blockers = {b["number"] for b in new_issue["blockedBy"] if b["state"] == "OPEN"}
        if new_open_blockers:
            continue
        closed_blockers = sorted(
            b["number"]
            for b in new_issue["blockedBy"]
            if b["number"] in prev_open_blockers and b["state"] == "CLOSED"
        )
        if not closed_blockers:
            continue
        source = closed_blockers[0]
        results.append(
            {
                "target": f"#{new_issue['number']}",
                "source": f"#{source}",
                "summary": f"#{source} closed; this issue is now ready",
            }
        )
    return results


def sync(
    root,
    transport,
    *,
    owner,
    name,
    full=False,
    now=None,
    events_dir=None,
    new_id=None,
    epic_label=DEFAULT_EPIC_LABEL,
):
    _now = now if now is not None else (lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)

    meta = _load_meta(root)
    cursor = None if full else (meta["cursor"] if meta else None)

    all_nodes = []
    after = None

    while True:
        data = transport.graphql(ISSUES_QUERY, {"owner": owner, "name": name, "after": after})
        issues = data["repository"]["issues"]
        page_info = issues["pageInfo"]
        nodes = issues["nodes"]
        all_nodes.extend(nodes)

        should_stop = not full and cursor is not None and nodes and nodes[-1]["updatedAt"] <= cursor
        if not page_info["hasNextPage"] or should_stop:
            break
        after = page_info["endCursor"]

    existing = _load_existing(root)
    fetched_reduced = {str(n["number"]): _reduce_node(n) for n in all_nodes}
    merged = {**existing, **fetched_reduced}
    cache = {"issues": merged}
    (root / "github.json").write_text(json.dumps(cache, indent=1, sort_keys=True))

    synced_at = _now()
    new_cursor = max(n["updatedAt"] for n in all_nodes) if all_nodes else cursor
    meta_out = {"cursor": new_cursor, "perturb_version": __version__, "synced_at": synced_at}
    (root / "meta.json").write_text(json.dumps(meta_out, indent=1, sort_keys=True))

    if events_dir is not None:
        transitions = newly_ready_unblocks(existing, merged, epic_label=epic_label)
        if transitions:
            events_path = Path(events_dir)
            events_path.mkdir(parents=True, exist_ok=True)
            store = EventStore(events_path, now=_now, new_id=new_id)
            for t in transitions:
                store.create(
                    source=t["source"],
                    target=t["target"],
                    kind="unblock",
                    summary=t["summary"],
                    proposed_by="perturb sync",
                    reason="blocks",
                    status="pending",
                )

    return SyncResult(fetched=len(all_nodes), total=len(merged), synced_at=synced_at)
