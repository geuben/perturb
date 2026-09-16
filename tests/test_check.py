import datetime

import pytest

from perturb.areas import AreaSet
from perturb.check import (
    adr_findings,
    event_findings,
    stale_check_findings,
    unpropagated_adr_findings,
)
from perturb.events import EventStore


def _adr(i, status, extra_fm=""):
    return (
        f"---\nid: {i}\ntitle: T{i}\nstatus: {status}\ndate: 2026-09-08\n{extra_fm}---\n\n"
        "## Consequences\n\n```yaml\n- id: v\n  text: ok.\n  kind: decision\n```\n"
    )


_UTC = datetime.UTC


def _epoch(at: str) -> int:
    dt = datetime.datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_UTC)
    return int(dt.timestamp())


def test_stale_result_becomes_a_check_finding(tmp_path):
    events_dir = tmp_path / "events"
    events_dir.mkdir()
    commit_epoch = _epoch("2001-09-08T21:46:40Z")
    store = EventStore(
        events_dir,
        now=lambda: "2001-09-08T21:46:41Z",
        new_id=lambda: "EVT-NEW",
    )
    ev = store.create(
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
    findings = stale_check_findings(planned, [ev])
    assert len(findings) == 1
    assert findings[0]["kind"] == "stale_plan"
    assert "29" in findings[0]["ref"] or findings[0]["ref"] == "#29"


def test_event_dead_detail_anchor_is_a_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    adr_dir = repo_root / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0002-x.md").write_text("# Some heading\n\nContent.\n")
    events_dir = tmp_path / "events"
    events_dir.mkdir()
    store = EventStore(events_dir)
    store.create(
        source="#1",
        target="#5",
        kind="spike",
        summary="dead anchor event",
        proposed_by="bot",
        reason="test",
        status="pending",
        detail="docs/adr/0002-x.md#no-such-anchor",
    )
    events = store.load().events
    graph = {"issues": {"5": {"state": "OPEN"}}}
    findings = event_findings(events, graph, repo_root)
    assert len(findings) == 1
    assert findings[0]["kind"] == "dead_anchor"


def test_pending_event_on_closed_issue_is_a_finding(tmp_path):
    events_dir = tmp_path / "events"
    events_dir.mkdir()
    store = EventStore(events_dir)
    store.create(
        source="#1",
        target="#42",
        kind="spike",
        summary="some event",
        proposed_by="bot",
        reason="test",
        status="pending",
    )
    events = store.load().events
    graph = {"issues": {"42": {"state": "CLOSED"}}}
    findings = event_findings(events, graph, tmp_path)
    assert len(findings) == 1
    assert findings[0]["kind"] == "pending_on_closed"


def test_superseded_by_target_missing_backlink_is_a_finding(tmp_path):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    # ADR A: id=2, superseded, points to ADR B (id=1)
    (adr_dir / "0002-x.md").write_text(
        "---\nid: 2\ntitle: A\nstatus: superseded\ndate: 2026-09-08\n"
        "superseded_by: adr:0001\n---\n\n"
        "## Consequences\n\n```yaml\n- id: v\n  text: ok.\n  kind: decision\n```\n"
    )
    # ADR B: id=1, does NOT list adr:0002 in supersedes
    (adr_dir / "0001-y.md").write_text(
        "---\nid: 1\ntitle: B\nstatus: accepted\ndate: 2026-09-07\nsupersedes: []\n---\n\n"
        "## Consequences\n\n```yaml\n- id: v\n  text: ok.\n  kind: decision\n```\n"
    )
    graph = {"issues": {}}
    findings = adr_findings(adr_dir, graph)
    assert len(findings) == 1
    assert findings[0]["kind"] == "supersede_backlink"


def _supersedes_findings(tmp_path, entry):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    (adr_dir / "0003-old.md").write_text(_adr(3, "accepted"))
    (adr_dir / "0005-new.md").write_text(_adr(5, "accepted", f'supersedes: ["{entry}"]\n'))
    return [(f["kind"], f["ref"]) for f in adr_findings(adr_dir, {"issues": {}})]


def test_supersedes_a_single_existing_consequence_is_valid(tmp_path):
    assert _supersedes_findings(tmp_path, "adr:0003#v") == []


def test_supersedes_an_unknown_consequence_is_a_finding(tmp_path):
    assert _supersedes_findings(tmp_path, "adr:0003#nope") == [
        ("supersedes_unresolved", "adr:0003#nope")
    ]


def test_supersedes_an_unknown_adr_is_a_finding(tmp_path):
    assert _supersedes_findings(tmp_path, "adr:0009") == [("supersedes_unresolved", "adr:0009")]


def test_supersedes_a_malformed_entry_is_a_finding(tmp_path):
    assert _supersedes_findings(tmp_path, "ADR 3") == [("supersedes_invalid", "ADR 3")]


def test_superseded_without_superseded_by_is_a_finding(tmp_path):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    (adr_dir / "0002-x.md").write_text(
        "---\nid: 2\ntitle: A title\nstatus: superseded\ndate: 2026-09-08\n---\n\n"
        "## Consequences\n\n```yaml\n- id: v\n  text: ok.\n  kind: decision\n```\n"
    )
    graph = {"issues": {}}
    findings = adr_findings(adr_dir, graph)
    assert len(findings) == 1
    assert findings[0]["kind"] == "superseded_no_link"


def test_adr_affects_unresolved_issue_is_a_finding(tmp_path):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    (adr_dir / "0002-x.md").write_text(
        "---\nid: 2\ntitle: A title\nstatus: accepted\ndate: 2026-09-08\n---\n\n"
        "## Consequences\n\n```yaml\n"
        '- id: v\n  text: ok.\n  kind: decision\n  affects: ["#999", "area:x"]\n'
        "```\n"
    )
    graph = {"issues": {}}
    findings = adr_findings(adr_dir, graph)
    assert len(findings) == 1
    assert findings[0]["kind"] == "affects_unresolved"
    assert "#999" in findings[0]["ref"]


def test_adr_affects_undeclared_area_is_a_finding(tmp_path):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    (adr_dir / "0002-x.md").write_text(
        "---\nid: 2\ntitle: A title\nstatus: accepted\ndate: 2026-09-08\n---\n\n"
        "## Consequences\n\n```yaml\n"
        '- id: v\n  text: ok.\n  kind: decision\n  affects: ["area:unknown-slug"]\n'
        "```\n"
    )
    graph = {"issues": {}}
    area_set = AreaSet(areas=[], errors=[])
    findings = adr_findings(adr_dir, graph, area_set=area_set)
    assert len(findings) == 1
    assert findings[0]["kind"] == "affects_unresolved"
    assert "area:unknown-slug" in findings[0]["ref"]


def test_adr_filename_id_mismatch_is_a_finding(tmp_path):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    (adr_dir / "0009-x.md").write_text(
        "---\nid: 2\ntitle: A title\nstatus: accepted\ndate: 2026-09-08\n---\n\n"
        "## Consequences\n\n```yaml\n- id: v\n  text: ok.\n  kind: decision\n```\n"
    )
    graph = {"issues": {}}
    findings = adr_findings(adr_dir, graph)
    assert len(findings) == 1
    assert findings[0]["kind"] == "filename_id_mismatch"


def test_no_propagation_flag_exempts_and_requires_a_reason(tmp_path):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    events_dir = tmp_path / "events"
    events_dir.mkdir()

    (adr_dir / "0001-a.md").write_text(
        _adr(1, "accepted", "no-propagation: true\nno-propagation-reason: prose only\n")
    )
    (adr_dir / "0002-b.md").write_text(_adr(2, "accepted", "no-propagation: true\n"))
    (adr_dir / "0003-c.md").write_text(
        _adr(3, "accepted", 'no-propagation: true\nno-propagation-reason: "   "\n')
    )
    (adr_dir / "0004-d.md").write_text(_adr(4, "proposed", "no-propagation: true\n"))
    (adr_dir / "0005-e.md").write_text(_adr(5, "accepted", "no-propagation-reason: why\n"))
    (adr_dir / "0006-f.md").write_text(_adr(6, "accepted", "no-propagation: true\n"))

    store = EventStore(events_dir)
    store.create(
        source="adr:0006#v",
        target="#1",
        kind="decision",
        summary="ok.",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )
    events = store.load().events

    findings = unpropagated_adr_findings(adr_dir, events)
    assert [(f["kind"], f["ref"]) for f in findings] == [
        ("no_propagation_without_reason", "0002-b.md"),
        ("no_propagation_without_reason", "0003-c.md"),
        ("adr_unpropagated", "0005-e.md"),
        ("no_propagation_without_reason", "0006-f.md"),
    ]
    assert findings[0] == {
        "kind": "no_propagation_without_reason",
        "ref": "0002-b.md",
        "detail": "no-propagation: true needs a non-empty no-propagation-reason",
        "fix": 'add no-propagation-reason: "<why>" to the front-matter of 0002-b.md',
    }


def test_adr_parse_failure_is_a_finding(tmp_path):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    (adr_dir / "0002-x.md").write_text(
        "---\nid: 2\nstatus: accepted\ndate: 2026-09-08\n---\n\n"
        "## Consequences\n\n```yaml\n- id: v\n  text: ok.\n  kind: decision\n```\n"
    )
    graph = {"issues": {}}
    findings = adr_findings(adr_dir, graph)
    assert len(findings) == 1
    assert findings[0]["kind"] == "adr_parse"


def test_unpropagated_accepted_adr_is_a_finding(tmp_path):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    events_dir = tmp_path / "events"
    events_dir.mkdir()

    (adr_dir / "0001-a.md").write_text(_adr(1, "accepted"))
    (adr_dir / "0002-b.md").write_text(_adr(2, "accepted"))
    (adr_dir / "0003-c.md").write_text(_adr(3, "accepted"))
    (adr_dir / "0004-d.md").write_text(_adr(4, "proposed"))
    (adr_dir / "0005-e.md").write_text(_adr(5, "superseded", "superseded_by: adr:0002\n"))
    (adr_dir / "0006-f.md").write_text(_adr(6, "deprecated"))
    (adr_dir / "0009-bad.md").write_text(
        "---\nid: 9\nstatus: accepted\ndate: 2026-09-08\n---\n\n"
        "## Consequences\n\n```yaml\n- id: v\n  text: ok.\n  kind: decision\n```\n"
    )

    store = EventStore(events_dir)
    store.create(
        source="adr:0002#v",
        target="#1",
        kind="decision",
        summary="ok.",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )
    store.dismiss(store.load().events[0].id, by="geuben")
    store.create(
        source="adr:0003",
        target="#1",
        kind="decision",
        summary="ok.",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )
    events = store.load().events

    findings = unpropagated_adr_findings(adr_dir, events)
    assert findings == [
        {
            "kind": "adr_unpropagated",
            "ref": "0001-a.md",
            "detail": "accepted ADR adr:0001 has no events and no no-propagation flag",
            "fix": (
                "perturb propose adr:0001"
                "  # or set no-propagation: true and no-propagation-reason in 0001-a.md"
            ),
        }
    ]


@pytest.mark.parametrize(
    "entry, expected",
    [
        ("adr:0003#v", []),
        ("adr:0003#nope", [("amends_unresolved", "adr:0003#nope")]),
        ("adr:0009", [("amends_unresolved", "adr:0009")]),
        ("ADR 3", [("amends_invalid", "ADR 3")]),
    ],
)
def test_amends_entries_are_validated_like_supersedes(tmp_path, entry, expected):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    (adr_dir / "0003-old.md").write_text(_adr(3, "accepted", 'amended_by: ["adr:0005"]\n'))
    (adr_dir / "0005-new.md").write_text(_adr(5, "accepted", f'amends: ["{entry}"]\n'))
    findings = [(f["kind"], f["ref"]) for f in adr_findings(adr_dir, {"issues": {}})
                if f["kind"].startswith("amends_")]
    assert findings == expected


@pytest.mark.parametrize(
    "old_extra, new_extra, expected",
    [
        ("", 'amends: ["adr:0003#v"]\n', [("amended_by_missing", "adr:0003#v")]),
        ('amended_by: ["adr:0005"]\n', 'amends: ["adr:0003#v"]\n', []),
        ('amended_by: ["adr:5"]\n', 'amends: ["adr:3#v"]\n', []),
    ],
)
def test_amends_needs_the_earlier_adr_to_list_it_in_amended_by(tmp_path, old_extra, new_extra, expected):  # noqa: E501
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    (adr_dir / "0003-old.md").write_text(_adr(3, "accepted", old_extra))
    (adr_dir / "0005-new.md").write_text(_adr(5, "accepted", new_extra))
    findings = [(f["kind"], f["ref"]) for f in adr_findings(adr_dir, {"issues": {}})]
    assert findings == expected


@pytest.mark.parametrize(
    "new_extra, expected",
    [
        ("", [("amend_backlink", "adr:0003")]),
        ('amends: ["adr:0003#v"]\n', []),
        ('amends: ["adr:3"]\n', []),
    ],
)
def test_amended_by_needs_the_amending_adr_to_list_it_in_amends(tmp_path, new_extra, expected):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    (adr_dir / "0003-old.md").write_text(_adr(3, "accepted", 'amended_by: ["adr:0005"]\n'))
    (adr_dir / "0005-new.md").write_text(_adr(5, "accepted", new_extra))
    findings = [(f["kind"], f["ref"]) for f in adr_findings(adr_dir, {"issues": {}})]
    assert findings == expected


@pytest.mark.parametrize("entry", ["adr:0009", "ADR 5", "adr:0005#v"])
def test_an_amended_by_entry_that_names_no_adr_is_a_finding(tmp_path, entry):
    adr_dir = tmp_path / "adr"
    adr_dir.mkdir()
    (adr_dir / "0003-old.md").write_text(_adr(3, "accepted", f'amended_by: ["{entry}"]\n'))
    (adr_dir / "0005-new.md").write_text(_adr(5, "accepted"))
    findings = [(f["kind"], f["ref"]) for f in adr_findings(adr_dir, {"issues": {}})]
    assert findings == [("amended_by_unresolved", entry)]
