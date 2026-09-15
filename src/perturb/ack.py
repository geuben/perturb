from perturb.envelope import Refusal
from perturb.events import EventStore


def ack(events_dir, *, target, event_ids, all_pending, plan, plan_blob, by, note, now=None):
    kwargs = {} if now is None else {"now": now}
    store = EventStore(events_dir, **kwargs)
    load_result = store.load()
    events_by_id = {e.id: e for e in load_result.events}

    if all_pending and event_ids:
        raise Refusal("ack_conflicting_selection")
    if not all_pending and not event_ids:
        raise Refusal("ack_no_selection")

    if all_pending:
        ids_to_ack = [
            e.id for e in load_result.events if e.target == target and e.status == "pending"
        ]
    else:
        for event_id in event_ids:
            if event_id not in events_by_id:
                raise Refusal("unknown_event", f"event {event_id!r} not found")
            event = events_by_id[event_id]
            if event.target != target:
                raise Refusal("event_target_mismatch", f"{event_id} targets {event.target}")
            if event.status not in ("pending", "acknowledged"):
                raise Refusal("event_not_pending", f"{event_id} is {event.status!r}")
        ids_to_ack = list(event_ids)

    acked = []
    for event_id in ids_to_ack:
        was_acknowledged = events_by_id[event_id].status == "acknowledged"
        store.acknowledge(event_id, by=by, plan=plan, plan_blob=plan_blob, note=note)
        acked.append({"id": event_id, "target": target, "was_acknowledged": was_acknowledged})

    return {"acked": acked}


def render_ack(data):
    acked = data["acked"]
    target = acked[0]["target"] if acked else ""
    lines = [f"Acked {len(acked)} event(s) for {target}:"]
    for entry in acked:
        suffix = " (re-acked)" if entry["was_acknowledged"] else ""
        lines.append(f"  {entry['id']}{suffix}")
    return "\n".join(lines) + "\n"
