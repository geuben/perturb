import pytest

from perturb.ack import ack, render_ack
from perturb.envelope import Refusal
from perturb.events import EventStore

FIXED_NOW = "2026-09-12T10:00:00Z"


def _make_store(tmp_path, ids):
    id_iter = iter(ids)
    return EventStore(tmp_path, now=lambda: FIXED_NOW, new_id=lambda: next(id_iter))


def _seed_ledger(tmp_path):
    """Seed two pending events for #29 and one pending event for #30."""
    store = _make_store(tmp_path, ["E0", "E1", "E2"])
    store.create(
        source="plan:x",
        target="#29",
        kind="decision",
        summary="first decision",
        detail="docs/x.md",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )
    store.create(
        source="plan:x",
        target="#29",
        kind="decision",
        summary="second decision",
        detail="docs/x.md",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )
    store.create(
        source="plan:x",
        target="#30",
        kind="decision",
        summary="other target decision",
        detail="docs/x.md",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )
    return tmp_path


def test_ack_all_acknowledges_pending_for_target(tmp_path):
    events_dir = _seed_ledger(tmp_path)
    result = ack(
        events_dir,
        target="#29",
        event_ids=[],
        all_pending=True,
        plan="tasks/x.md",
        plan_blob="deadbeef",
        by="geuben",
        note="n",
        now=lambda: FIXED_NOW,
    )
    acked_ids = [entry["id"] for entry in result["acked"]]
    assert sorted(acked_ids) == ["E0", "E1"]

    store = EventStore(events_dir)
    load_result = store.load()
    events = {e.id: e for e in load_result.events}
    assert events["E0"].status == "acknowledged"
    assert events["E0"].ack["plan_blob"] == "deadbeef"  # type: ignore[index]
    assert events["E1"].status == "acknowledged"
    assert events["E1"].ack["plan_blob"] == "deadbeef"  # type: ignore[index]
    assert events["E2"].status == "pending"


def test_ack_acknowledges_named_event_ids(tmp_path):
    events_dir = _seed_ledger(tmp_path)
    result = ack(
        events_dir,
        target="#29",
        event_ids=["E1"],
        all_pending=False,
        plan="tasks/x.md",
        plan_blob="deadbeef",
        by="geuben",
        note="n",
        now=lambda: FIXED_NOW,
    )
    acked_ids = [entry["id"] for entry in result["acked"]]
    assert acked_ids == ["E1"]

    store = EventStore(events_dir)
    load_result = store.load()
    events = {e.id: e for e in load_result.events}
    assert events["E1"].status == "acknowledged"
    assert events["E0"].status == "pending"


def test_ack_reack_overwrites_and_flags(tmp_path):
    store = _make_store(tmp_path, ["E0"])
    store.create(
        source="plan:x",
        target="#29",
        kind="decision",
        summary="some decision",
        detail="docs/x.md",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )
    store.acknowledge("E0", by="geuben", plan="tasks/x.md", plan_blob="oldhash", note="first")

    result = ack(
        tmp_path,
        target="#29",
        event_ids=["E0"],
        all_pending=False,
        plan="tasks/x.md",
        plan_blob="newhash",
        by="geuben",
        note="re-ack",
        now=lambda: FIXED_NOW,
    )
    assert result["acked"][0]["was_acknowledged"] is True

    store2 = EventStore(tmp_path)
    load_result = store2.load()
    events = {e.id: e for e in load_result.events}
    assert events["E0"].ack["plan_blob"] == "newhash"  # type: ignore[index]


def test_ack_refuses_invalid_selection_and_ids(tmp_path):
    events_dir = _seed_ledger(tmp_path)

    # neither ids nor --all
    with pytest.raises(Refusal) as exc_info:
        ack(
            events_dir,
            target="#29",
            event_ids=[],
            all_pending=False,
            plan="tasks/x.md",
            plan_blob="h",
            by="geuben",
            note="n",
        )
    assert exc_info.value.reason == "ack_no_selection"

    # both ids and --all
    with pytest.raises(Refusal) as exc_info:
        ack(
            events_dir,
            target="#29",
            event_ids=["E0"],
            all_pending=True,
            plan="tasks/x.md",
            plan_blob="h",
            by="geuben",
            note="n",
        )
    assert exc_info.value.reason == "ack_conflicting_selection"

    # unknown id
    with pytest.raises(Refusal) as exc_info:
        ack(
            events_dir,
            target="#29",
            event_ids=["UNKNOWN"],
            all_pending=False,
            plan="tasks/x.md",
            plan_blob="h",
            by="geuben",
            note="n",
        )
    assert exc_info.value.reason == "unknown_event"

    # id targeting #30 while target="#29"
    with pytest.raises(Refusal) as exc_info:
        ack(
            events_dir,
            target="#29",
            event_ids=["E2"],
            all_pending=False,
            plan="tasks/x.md",
            plan_blob="h",
            by="geuben",
            note="n",
        )
    assert exc_info.value.reason == "event_target_mismatch"

    # dismissed id
    dismissed_dir = tmp_path / "dismissed"
    dismissed_dir.mkdir()
    dismissed_store = _make_store(dismissed_dir, ["D0"])
    dismissed_store.create(
        source="plan:x",
        target="#29",
        kind="decision",
        summary="d",
        detail="d.md",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )
    dismissed_store.dismiss("D0", by="geuben", note="no")
    with pytest.raises(Refusal) as exc_info:
        ack(
            dismissed_dir,
            target="#29",
            event_ids=["D0"],
            all_pending=False,
            plan="tasks/x.md",
            plan_blob="h",
            by="geuben",
            note="n",
        )
    assert exc_info.value.reason == "event_not_pending"


def test_render_ack_matches_documented_layout():
    data = {
        "acked": [
            {"id": "E0", "target": "#29", "was_acknowledged": False},
            {"id": "E1", "target": "#29", "was_acknowledged": True},
        ]
    }
    result = render_ack(data)
    expected = "Acked 2 event(s) for #29:\n  E0\n  E1 (re-acked)\n"
    assert result == expected
