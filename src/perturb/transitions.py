from perturb.envelope import Refusal
from perturb.events import EventNotFound, EventStore, TransitionError


def confirm(events_dir, *, event_ids, source, all_selected):
    if event_ids and (source is not None or all_selected):
        raise Refusal("confirm_conflicting_selection", "ids cannot be used with --source/--all")
    if not event_ids and not (source is not None and all_selected):
        raise Refusal("confirm_no_selection", "provide event ids or both --source and --all")

    store = EventStore(events_dir)
    confirmed = []
    if all_selected and source is not None:
        prefix = source + "#"
        for event in store.load().events:
            if event.status == "proposed" and (
                event.source == source or event.source.startswith(prefix)
            ):
                updated = store.confirm(event.id)
                confirmed.append({"id": updated.id, "target": updated.target})
    else:
        for eid in event_ids:
            try:
                event = store.confirm(eid)
            except EventNotFound:
                raise Refusal("unknown_event", f"event {eid!r} not found") from None
            except TransitionError:
                raise Refusal("event_not_proposed", f"event {eid!r} is not proposed") from None
            confirmed.append({"id": event.id, "target": event.target})
    return {"confirmed": confirmed}


def dismiss(events_dir, *, event_ids, by, note=None, now=None):
    store_kwargs = {}
    if now is not None:
        store_kwargs["now"] = lambda: now
    store = EventStore(events_dir, **store_kwargs)
    dismissed = []
    for eid in event_ids:
        try:
            event = store.dismiss(eid, by=by, note=note)
        except EventNotFound:
            raise Refusal("unknown_event", f"event {eid!r} not found") from None
        except TransitionError:
            raise Refusal("event_not_dismissable", f"event {eid!r} is not dismissable") from None
        dismissed.append({"id": event.id, "target": event.target})
    return {"dismissed": dismissed}
