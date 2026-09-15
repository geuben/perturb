import pytest

from perturb.events import EventNotFound, EventStore, LoadError, TransitionError

FIXED_NOW = "2026-09-12T10:00:00Z"
FIXED_ID = "01J9Q7K2M4X8"
SECOND_ID = "01J9Q7K2M4Y9"


def make_store(tmp_path, ids=None):
    id_iter = iter(ids or [FIXED_ID])
    return EventStore(
        tmp_path,
        now=lambda: FIXED_NOW,
        new_id=lambda: next(id_iter),
    )


def test_create_writes_yaml_with_documented_fields_in_order(tmp_path):
    store = make_store(tmp_path)
    store.create(
        source="adr:0002#refund-grain",
        target="#13",
        kind="decision",
        summary="Refunds carry a grain column",
        detail="docs/adr/0002-per-trip-grain.md#refund-grain",
        proposed_by="perturb propose",
        reason="affects",
        status="pending",
    )
    expected = (
        "id: 01J9Q7K2M4X8\n"
        "at: '2026-09-12T10:00:00Z'\n"
        "source: adr:0002#refund-grain\n"
        "target: '#13'\n"
        "kind: decision\n"
        "summary: Refunds carry a grain column\n"
        "detail: docs/adr/0002-per-trip-grain.md#refund-grain\n"
        "proposed_by: perturb propose\n"
        "reason: affects\n"
        "status: pending\n"
    )
    assert (tmp_path / f"{FIXED_ID}.yaml").read_text() == expected


def test_create_writes_at_as_quoted_string(tmp_path):
    store = make_store(tmp_path)
    store.create(
        source="adr:0002#refund-grain",
        target="#13",
        kind="decision",
        summary="Refunds carry a grain column",
        proposed_by="perturb propose",
        reason="affects",
    )
    text = (tmp_path / f"{FIXED_ID}.yaml").read_text()
    assert "at: '2026-09-12T10:00:00Z'" in text


def test_create_duplicate_returns_existing_and_writes_nothing(tmp_path):
    store = make_store(tmp_path, ids=[FIXED_ID, SECOND_ID])
    store.create(
        source="adr:0002#refund-grain",
        target="#13",
        kind="decision",
        summary="Refunds carry a grain column",
        detail="original detail",
        proposed_by="perturb propose",
        reason="affects",
        status="proposed",
    )

    # Simulate dismiss by rewriting the file's status line directly.
    yaml_path = tmp_path / f"{FIXED_ID}.yaml"
    yaml_path.write_text(yaml_path.read_text().replace("status: proposed", "status: dismissed"))

    result = store.create(
        source="adr:0002#refund-grain",
        target="#13",
        kind="decision",
        summary="Refunds carry a grain column",
        detail="different detail",
        proposed_by="perturb propose",
        reason="affects",
        status="proposed",
    )

    assert result.id == FIXED_ID
    assert result.status == "dismissed"
    assert len(list(tmp_path.iterdir())) == 1


def test_load_reports_malformed_files_and_continues(tmp_path):
    store = make_store(tmp_path)
    store.create(
        source="adr:0002#refund-grain",
        target="#13",
        kind="decision",
        summary="Refunds carry a grain column",
        proposed_by="perturb propose",
        reason="affects",
    )

    (tmp_path / "bad.yaml").write_text("id: [unclosed")
    (tmp_path / "notes.txt").write_text("not a yaml file")

    result = store.load()
    assert len(result.events) == 1
    assert result.events[0].id == FIXED_ID
    assert len(result.errors) == 1
    assert result.errors[0].path == tmp_path / "bad.yaml"
    assert isinstance(result.errors[0], LoadError)


def test_confirm_moves_proposed_to_pending(tmp_path):
    store = make_store(tmp_path)
    event = store.create(
        source="adr:0002#refund-grain",
        target="#13",
        kind="decision",
        summary="Refunds carry a grain column",
        proposed_by="perturb propose",
        reason="affects",
    )

    store.confirm(event.id)

    fresh = EventStore(tmp_path, now=lambda: FIXED_NOW, new_id=lambda: FIXED_ID)
    assert fresh.load().events[0].status == "pending"


def test_dismiss_from_pending_records_ack_note(tmp_path):
    store = make_store(tmp_path)
    event = store.create(
        source="adr:0002#refund-grain",
        target="#13",
        kind="decision",
        summary="Refunds carry a grain column",
        proposed_by="perturb propose",
        reason="affects",
        status="pending",
    )

    store.dismiss(event.id, by="geuben", note="already implemented")

    fresh = EventStore(tmp_path, now=lambda: FIXED_NOW, new_id=lambda: FIXED_ID)
    loaded = fresh.load().events[0]
    assert loaded.status == "dismissed"
    assert loaded.ack == {
        "at": FIXED_NOW,
        "by": "geuben",
        "note": "already implemented",
    }


def test_acknowledge_pins_plan_blob(tmp_path):
    store = make_store(tmp_path)
    event = store.create(
        source="adr:0002#refund-grain",
        target="#13",
        kind="decision",
        summary="Refunds carry a grain column",
        proposed_by="perturb propose",
        reason="affects",
        status="pending",
    )

    store.acknowledge(
        event.id,
        by="plan-issue",
        plan="tasks/refund-backfill.md",
        plan_blob="4ef5700046bc1340bbca16f4baceae14c47c8703",
        note="Locked as design decision 3",
    )

    fresh = EventStore(tmp_path, now=lambda: FIXED_NOW, new_id=lambda: FIXED_ID)
    loaded = fresh.load().events[0]
    assert loaded.status == "acknowledged"
    assert loaded.ack == {
        "at": FIXED_NOW,
        "by": "plan-issue",
        "plan": "tasks/refund-backfill.md",
        "plan_blob": "4ef5700046bc1340bbca16f4baceae14c47c8703",
        "note": "Locked as design decision 3",
    }


def test_reacknowledge_overwrites_previous_ack(tmp_path):
    store = make_store(tmp_path)
    event = store.create(
        source="adr:0002#refund-grain",
        target="#13",
        kind="decision",
        summary="Refunds carry a grain column",
        proposed_by="perturb propose",
        reason="affects",
        status="pending",
    )

    store.acknowledge(event.id, by="plan-issue", plan="tasks/a.md", plan_blob="aaaa", note="first")
    store.acknowledge(event.id, by="plan-issue", plan="tasks/a.md", plan_blob="bbbb", note="second")

    fresh = EventStore(tmp_path, now=lambda: FIXED_NOW, new_id=lambda: FIXED_ID)
    loaded = fresh.load().events[0]
    assert loaded.ack["plan_blob"] == "bbbb"
    assert loaded.ack["note"] == "second"


def test_illegal_transition_names_current_status(tmp_path):
    store = make_store(tmp_path)
    event = store.create(
        source="adr:0002#refund-grain",
        target="#13",
        kind="decision",
        summary="Refunds carry a grain column",
        proposed_by="perturb propose",
        reason="affects",
    )

    # proposed -> acknowledged is illegal
    with pytest.raises(TransitionError) as exc_info:
        store.acknowledge(
            event.id,
            by="plan-issue",
            plan="tasks/a.md",
            plan_blob="aaaa",
            note="bad",
        )
    assert "proposed" in str(exc_info.value)
    assert event.id in str(exc_info.value)

    # dismissed -> pending via confirm is also illegal
    store.dismiss(event.id, by="geuben")
    with pytest.raises(TransitionError) as exc_info2:
        store.confirm(event.id)
    assert "dismissed" in str(exc_info2.value)


def test_transition_on_unknown_id_raises_event_not_found(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(EventNotFound):
        store.confirm("01NOPE")


def test_load_treats_non_mapping_yaml_as_error(tmp_path):
    store = make_store(tmp_path)
    store.create(
        source="adr:0002#refund-grain",
        target="#13",
        kind="decision",
        summary="Refunds carry a grain column",
        proposed_by="perturb propose",
        reason="affects",
    )
    (tmp_path / "list.yaml").write_text("- item1\n- item2\n")

    result = store.load()
    assert len(result.events) == 1
    assert len(result.errors) == 1
    assert result.errors[0].path == tmp_path / "list.yaml"


def test_load_treats_yaml_with_missing_required_keys_as_error(tmp_path):
    store = make_store(tmp_path)
    (tmp_path / "partial.yaml").write_text("id: abc123\nstatus: proposed\n")

    result = store.load()
    assert result.events == []
    assert len(result.errors) == 1
    assert result.errors[0].path == tmp_path / "partial.yaml"
