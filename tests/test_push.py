import pytest

from perturb.envelope import Refusal
from perturb.events import EventStore
from perturb.push import push, resolve_targets, validate_detail

# Graph fixture: epic #3 (label "epic"); #29, #31 (children of 3, OPEN); #30 (child of 3, CLOSED)
GRAPH_ISSUES = {
    "3": {"number": 3, "epic": None, "labels": ["epic"], "state": "OPEN", "title": "Epic"},
    "29": {"number": 29, "epic": 3, "labels": [], "state": "OPEN", "title": "Child A"},
    "30": {"number": 30, "epic": 3, "labels": [], "state": "CLOSED", "title": "Child B"},
    "31": {"number": 31, "epic": 3, "labels": [], "state": "OPEN", "title": "Child C"},
}


def test_resolve_targets_accepts_open_non_epic_issues():
    result = resolve_targets(GRAPH_ISSUES, ["29", "#31"])
    assert result == ["#29", "#31"]


def test_push_creates_one_pending_event_per_target(tmp_path):
    events_dir = tmp_path / "events"
    counter = [0]

    def fake_now():
        return "2026-09-12T00:00:00Z"

    def fake_id():
        counter[0] += 1
        return f"00000000000000000000000{counter[0]:01d}"

    result = push(
        events_dir,
        source="#5",
        targets=["#29", "#31"],
        kind="decision",
        summary="s",
        detail="docs/a.md",
        proposed_by="geuben",
        now=fake_now,
        new_id=fake_id,
    )

    assert len(result["created"]) == 2

    store = EventStore(events_dir)
    load_result = store.load()
    events = load_result.events
    assert len(events) == 2

    targets_found = {e.target for e in events}
    assert targets_found == {"#29", "#31"}

    for event in events:
        assert event.status == "pending"
        assert event.reason == "manual"
        assert event.proposed_by == "geuben"
        assert event.kind == "decision"


def test_validate_detail_accepts_resolvable_refuses_unresolvable(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# Heading One\nsome content")

    assert validate_detail(tmp_path, "docs/a.md#heading-one") is None

    with pytest.raises(Refusal) as exc_info:
        validate_detail(tmp_path, "docs/missing.md")
    assert exc_info.value.reason == "detail_unresolved"

    with pytest.raises(Refusal) as exc_info:
        validate_detail(tmp_path, "docs/a.md#nope")
    assert exc_info.value.reason == "detail_unresolved"


@pytest.mark.parametrize(
    "ref_text,reason,detail_contains",
    [
        ("adr:2", "target_not_issue", "adr:0002"),
        ("999", "unknown_target", "#999"),
        ("3", "epic_target", "#29"),
        ("30", "target_closed", "#30"),
    ],
)
def test_resolve_targets_refuses_invalid_targets(ref_text, reason, detail_contains):
    with pytest.raises(Refusal) as exc_info:
        resolve_targets(GRAPH_ISSUES, [ref_text])
    assert exc_info.value.reason == reason
    assert detail_contains in exc_info.value.detail


def test_resolve_targets_refuses_an_issue_the_graph_marked_as_an_epic():
    import pytest

    from perturb.envelope import Refusal
    from perturb.push import resolve_targets

    graph = {
        "7": {"number": 7, "state": "OPEN", "labels": ["initiative"], "is_epic": True},
        "8": {"number": 8, "state": "OPEN", "labels": [], "is_epic": False, "epic": 7},
    }
    with pytest.raises(Refusal) as exc_info:
        resolve_targets(graph, ["7"])
    assert exc_info.value.reason == "epic_target"
    assert resolve_targets(graph, ["8"]) == ["#8"]
