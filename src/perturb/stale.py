import datetime

_UTC = datetime.UTC


def _at_epoch(at: str) -> float:
    return datetime.datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_UTC).timestamp()


def stale_findings(planned, events, *, target=None):
    results = []
    for entry in planned:
        if target is not None and entry["issue"] != target:
            continue
        issue = entry["issue"]
        commit_epoch = entry["commit_epoch"]
        current_blob = entry["current_blob"]

        stale_evts = []
        for ev in events:
            if ev.target != f"#{issue}":
                continue
            if ev.status == "pending" and _at_epoch(ev.at) > commit_epoch:
                stale_evts.append({"id": ev.id, "at": ev.at, "why": "pending_newer"})
            elif (
                ev.status == "acknowledged"
                and ev.ack is not None
                and ev.ack.get("plan_blob") != current_blob
            ):
                stale_evts.append({"id": ev.id, "at": ev.at, "why": "ack_blob_mismatch"})

        if stale_evts:
            results.append({"issue": issue, "plan": entry["plan"], "stale_events": stale_evts})

    return results


def render_stale(data):
    lines = ["Stale issues:"]
    for entry in data:
        lines.append(f"  #{entry['issue']}  {entry['plan']}")
        for ev in entry["stale_events"]:
            lines.append(f"    {ev['id']}  {ev['why']}")
    return "\n".join(lines) + "\n"
