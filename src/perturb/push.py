from pathlib import Path

from perturb.envelope import Refusal
from perturb.events import EventStore
from perturb.graph import is_epic
from perturb.inbox import resolve_excerpt
from perturb.refs import parse_ref


def resolve_targets(graph_issues, refs):
    result = []
    for ref_text in refs:
        ref = parse_ref(ref_text)
        if ref.kind != "issue":
            raise Refusal("target_not_issue", str(ref))
        issue = graph_issues.get(ref.id)
        if issue is None:
            raise Refusal("unknown_target", f"#{ref.id}")
        if is_epic(issue):
            children = [
                f"#{n}"
                for n, i in graph_issues.items()
                if i.get("epic") == issue["number"] and i.get("state") == "OPEN"
            ]
            detail = f"#{ref.id} is an epic; open children: {', '.join(children)}"
            raise Refusal("epic_target", detail)
        if issue.get("state") != "OPEN":
            raise Refusal("target_closed", f"#{ref.id}")
        result.append(str(ref))
    return result


def validate_detail(repo_root, detail):
    _excerpt, warning = resolve_excerpt(repo_root, detail)
    if warning is not None:
        raise Refusal("detail_unresolved", warning)


def push(events_dir, *, source, targets, kind, summary, detail, proposed_by, now=None, new_id=None):
    events_dir = Path(events_dir)
    events_dir.mkdir(parents=True, exist_ok=True)
    store = EventStore(events_dir, now=now, new_id=new_id)
    created = []
    for target in targets:
        event = store.create(
            source=source,
            target=target,
            kind=kind,
            summary=summary,
            detail=detail,
            proposed_by=proposed_by,
            reason="manual",
            status="pending",
        )
        created.append({"id": event.id, "target": event.target})
    return {"created": created}
