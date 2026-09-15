import pytest  # noqa: F401

from perturb.envelope import Refusal  # noqa: F401
from perturb.events import EventStore
from perturb.transitions import confirm, dismiss  # noqa: F401

FIXED_NOW = "2026-09-13T10:00:00Z"


def _make_store(tmp_path, ids):
    id_iter = iter(ids)
    return EventStore(tmp_path, now=lambda: FIXED_NOW, new_id=lambda: next(id_iter))


def _seed_proposed(tmp_path, ids, target="#13", source="plan:x"):
    store = _make_store(tmp_path, ids)
    for i, _eid in enumerate(ids):
        store.create(
            source=source,
            target=target,
            kind="decision",
            summary=f"decision {i}",
            proposed_by="geuben",
            reason="affects",
            status="proposed",
        )
    return tmp_path


def test_dismiss_non_dismissable_id_refuses(tmp_path):
    store = _make_store(tmp_path, ["EV1"])
    store.create(
        source="plan:x",
        target="#13",
        kind="decision",
        summary="decision",
        proposed_by="geuben",
        reason="affects",
        status="proposed",
    )
    # Dismiss once so it's in dismissed state
    store.dismiss("EV1", by="geuben")

    with pytest.raises(Refusal) as exc_info:
        dismiss(tmp_path, event_ids=["EV1"], by="geuben")
    assert exc_info.value.reason == "event_not_dismissable"


def test_dismiss_unknown_id_refuses(tmp_path):
    with pytest.raises(Refusal) as exc_info:
        dismiss(tmp_path, event_ids=["NOPE"], by="geuben")
    assert exc_info.value.reason == "unknown_event"


def test_dismiss_moves_proposed_and_pending_to_dismissed(tmp_path):
    store = _make_store(tmp_path, ["P", "Q"])
    store.create(
        source="plan:x",
        target="#13",
        kind="decision",
        summary="proposed one",
        proposed_by="geuben",
        reason="affects",
        status="proposed",
    )
    store.create(
        source="plan:x",
        target="#13",
        kind="decision",
        summary="pending one",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )

    result = dismiss(
        tmp_path,
        event_ids=["P", "Q"],
        by="geuben",
        note="already implemented",
        now=FIXED_NOW,
    )

    assert len(result["dismissed"]) == 2
    ids_returned = {d["id"] for d in result["dismissed"]}
    assert ids_returned == {"P", "Q"}
    for d in result["dismissed"]:
        assert d["target"] == "#13"

    reload = EventStore(tmp_path)
    loaded = {e.id: e for e in reload.load().events}
    assert loaded["P"].status == "dismissed"
    assert loaded["P"].ack == {"at": FIXED_NOW, "by": "geuben", "note": "already implemented"}
    assert loaded["Q"].status == "dismissed"
    assert loaded["Q"].ack == {"at": FIXED_NOW, "by": "geuben", "note": "already implemented"}


def test_confirm_refuses_invalid_selection(tmp_path):
    # (a) No ids and not both --source and --all
    with pytest.raises(Refusal) as exc_info:
        confirm(tmp_path, event_ids=[], source=None, all_selected=False)
    assert exc_info.value.reason == "confirm_no_selection"

    # (b) ids + --source only (no --all) — catches `or` → `and` mutation on line 6
    with pytest.raises(Refusal) as exc_info:
        confirm(tmp_path, event_ids=["X"], source="adr:0002", all_selected=False)
    assert exc_info.value.reason == "confirm_conflicting_selection"

    # (c) Positional ids mixed with --source and --all
    with pytest.raises(Refusal) as exc_info:
        confirm(tmp_path, event_ids=["X"], source="adr:0002", all_selected=True)
    assert exc_info.value.reason == "confirm_conflicting_selection"

    # (d) --source given without --all — catches `and` → `or` mutation on line 8
    with pytest.raises(Refusal) as exc_info:
        confirm(tmp_path, event_ids=[], source="adr:0002", all_selected=False)
    assert exc_info.value.reason == "confirm_no_selection"


def test_confirm_non_proposed_id_refuses(tmp_path):
    store = _make_store(tmp_path, ["EV1"])
    store.create(
        source="plan:x",
        target="#13",
        kind="decision",
        summary="decision",
        proposed_by="geuben",
        reason="affects",
        status="proposed",
    )
    # Move to pending first
    store.confirm("EV1")

    with pytest.raises(Refusal) as exc_info:
        confirm(tmp_path, event_ids=["EV1"], source=None, all_selected=False)
    assert exc_info.value.reason == "event_not_proposed"


def test_confirm_unknown_id_refuses(tmp_path):
    with pytest.raises(Refusal) as exc_info:
        confirm(tmp_path, event_ids=["NOPE"], source=None, all_selected=False)
    assert exc_info.value.reason == "unknown_event"


def test_confirm_source_all_confirms_matching_proposed(tmp_path):
    store = _make_store(tmp_path, ["A", "B", "C", "D"])
    for eid, src, tgt in [
        ("A", "adr:0002#refund-grain", "#13"),
        ("B", "adr:0002#band-windows", "#31"),
        ("C", "adr:0003#other", "#40"),
    ]:
        store.create(
            source=src,
            target=tgt,
            kind="decision",
            summary=f"decision {eid}",
            proposed_by="geuben",
            reason="affects",
            status="proposed",
        )
    # D is already pending
    store.create(
        source="adr:0002#done",
        target="#13",
        kind="decision",
        summary="decision D",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )

    result = confirm(tmp_path, event_ids=[], source="adr:0002", all_selected=True)

    assert {c["id"] for c in result["confirmed"]} == {"A", "B"}

    reload = EventStore(tmp_path)
    loaded = {e.id: e for e in reload.load().events}
    assert loaded["A"].status == "pending"
    assert loaded["B"].status == "pending"
    assert loaded["C"].status == "proposed"
    assert loaded["D"].status == "pending"


def test_confirm_source_all_exact_match_no_fragment(tmp_path):
    # Covers `event.source == source` branch (event has no #fragment) — catches `==` → `!=` mutation
    store = _make_store(tmp_path, ["EXACT", "OTHER"])
    store.create(
        source="plan:x",
        target="#13",
        kind="decision",
        summary="exact source",
        proposed_by="geuben",
        reason="affects",
        status="proposed",
    )
    store.create(
        source="plan:y",
        target="#14",
        kind="decision",
        summary="other source",
        proposed_by="geuben",
        reason="affects",
        status="proposed",
    )

    result = confirm(tmp_path, event_ids=[], source="plan:x", all_selected=True)

    assert {c["id"] for c in result["confirmed"]} == {"EXACT"}
    reload = EventStore(tmp_path)
    loaded = {e.id: e for e in reload.load().events}
    assert loaded["EXACT"].status == "pending"
    assert loaded["OTHER"].status == "proposed"


def test_confirm_named_ids_moves_proposed_to_pending(tmp_path):
    store = _make_store(tmp_path, ["P1", "P2"])
    store.create(
        source="plan:x",
        target="#13",
        kind="decision",
        summary="first",
        proposed_by="geuben",
        reason="affects",
        status="proposed",
    )
    store.create(
        source="plan:x",
        target="#13",
        kind="decision",
        summary="second",
        proposed_by="geuben",
        reason="affects",
        status="proposed",
    )

    result = confirm(tmp_path, event_ids=["P1", "P2"], source=None, all_selected=False)

    assert len(result["confirmed"]) == 2
    ids_returned = {c["id"] for c in result["confirmed"]}
    assert ids_returned == {"P1", "P2"}
    for c in result["confirmed"]:
        assert c["target"] == "#13"

    reload = EventStore(tmp_path)
    loaded = {e.id: e for e in reload.load().events}
    assert loaded["P1"].status == "pending"
    assert loaded["P2"].status == "pending"
