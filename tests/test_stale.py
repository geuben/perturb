import datetime

from perturb.events import EventStore
from perturb.stale import render_stale, stale_findings

_UTC = datetime.UTC


def _at_to_epoch(at: str) -> float:
    return datetime.datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_UTC).timestamp()


def test_stale_findings_flags_pending_newer_than_plan_commit(tmp_path):
    events_dir = tmp_path / "events"
    events_dir.mkdir()

    older_at = "2001-09-08T21:46:39Z"
    newer_at = "2001-09-08T21:46:41Z"
    # commit_epoch sits between the two: epoch of the mid-second
    commit_epoch = int(_at_to_epoch("2001-09-08T21:46:40Z"))

    ids = iter(["EVT-OLDER", "EVT-NEWER"])
    times = iter([older_at, newer_at])
    store = EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids))

    ev_older = store.create(
        source="#4",
        target="#29",
        kind="spike",
        summary="older event",
        proposed_by="bot",
        reason="test",
        status="pending",
    )
    ev_newer = store.create(
        source="#4",
        target="#29",
        kind="spike",
        summary="newer event",
        proposed_by="bot",
        reason="test",
        status="pending",
    )

    planned = [
        {"issue": 29, "plan": "tasks/foo.md", "commit_epoch": commit_epoch, "current_blob": "CUR"}
    ]
    findings = stale_findings(planned, [ev_older, ev_newer])

    assert len(findings) == 1
    finding = findings[0]
    assert finding["issue"] == 29
    stale_events = finding["stale_events"]
    assert len(stale_events) == 1
    assert stale_events[0]["id"] == ev_newer.id
    assert stale_events[0]["why"] == "pending_newer"


def test_stale_findings_flags_ack_blob_mismatch(tmp_path):
    events_dir = tmp_path / "events"
    events_dir.mkdir()

    at = "2001-09-08T21:46:39Z"
    # Both acked events are older than commit_epoch so pending recency rule won't fire
    commit_epoch = int(_at_to_epoch("2001-09-08T21:46:40Z"))

    ids = iter(["EVT-MISMATCH", "EVT-MATCH", "ACK1", "ACK2"])
    times = iter([at, at, "2001-09-08T22:00:00Z", "2001-09-08T22:00:01Z"])
    store = EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids))

    ev_mismatch = store.create(
        source="#4",
        target="#29",
        kind="spike",
        summary="mismatch event",
        proposed_by="bot",
        reason="test",
        status="pending",
    )
    ev_match = store.create(
        source="#4",
        target="#29",
        kind="spike",
        summary="match event",
        proposed_by="bot",
        reason="test",
        status="pending",
    )
    ev_mismatch = store.acknowledge(
        ev_mismatch.id, by="bot", plan="tasks/foo.md", plan_blob="OLD", note=""
    )
    ev_match = store.acknowledge(
        ev_match.id, by="bot", plan="tasks/foo.md", plan_blob="CUR", note=""
    )

    planned = [
        {"issue": 29, "plan": "tasks/foo.md", "commit_epoch": commit_epoch, "current_blob": "CUR"}
    ]
    findings = stale_findings(planned, [ev_mismatch, ev_match])

    assert len(findings) == 1
    finding = findings[0]
    assert finding["issue"] == 29
    stale_events = finding["stale_events"]
    assert len(stale_events) == 1
    assert stale_events[0]["id"] == ev_mismatch.id
    assert stale_events[0]["why"] == "ack_blob_mismatch"


def test_stale_findings_target_restricts_to_one_issue(tmp_path):
    events_dir = tmp_path / "events"
    events_dir.mkdir()

    newer_at = "2001-09-08T21:46:41Z"
    commit_epoch = int(_at_to_epoch("2001-09-08T21:46:40Z"))

    ids = iter(["EVT-29", "EVT-30"])
    times = iter([newer_at, newer_at])
    store = EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids))

    ev29 = store.create(
        source="#4",
        target="#29",
        kind="spike",
        summary="event 29",
        proposed_by="bot",
        reason="test",
        status="pending",
    )
    ev30 = store.create(
        source="#4",
        target="#30",
        kind="spike",
        summary="event 30",
        proposed_by="bot",
        reason="test",
        status="pending",
    )

    planned = [
        {"issue": 29, "plan": "tasks/p29.md", "commit_epoch": commit_epoch, "current_blob": "CUR"},
        {"issue": 30, "plan": "tasks/p30.md", "commit_epoch": commit_epoch, "current_blob": "CUR"},
    ]
    findings = stale_findings(planned, [ev29, ev30], target=30)

    assert len(findings) == 1
    assert findings[0]["issue"] == 30


def test_render_stale_matches_documented_layout():
    data = [
        {
            "issue": 10,
            "plan": "tasks/foo.md",
            "stale_events": [
                {"id": "EVT-A", "at": "2026-01-01T00:00:00Z", "why": "pending_newer"},
            ],
        },
        {
            "issue": 20,
            "plan": "tasks/bar.md",
            "stale_events": [
                {"id": "EVT-B", "at": "2026-01-02T00:00:00Z", "why": "ack_blob_mismatch"},
            ],
        },
    ]
    expected = (
        "Stale issues:\n"
        "  #10  tasks/foo.md\n"
        "    EVT-A  pending_newer\n"
        "  #20  tasks/bar.md\n"
        "    EVT-B  ack_blob_mismatch\n"
    )
    assert render_stale(data) == expected
