import types

from perturb.adr import Adr, Consequence
from perturb.areas import Area, AreaSet
from perturb.envelope import Refusal
from perturb.propose import (
    compute_candidates,
    compute_friction_candidates,
    compute_plan_candidates,
    files_touched_outside,
    parse_audit_items,
    parse_friction_commits,
    parse_plan_entries,
    propose,
    propose_friction,
    propose_plan,
    read_declared_paths,
    resolve_adr_path,
    review,
)

# Shared graph: #3 epic, #29/#31 open children, #30 closed, #999 absent
GRAPH_ISSUES = {
    "3": {"number": 3, "epic": None, "labels": ["epic"], "state": "OPEN", "title": "Epic"},
    "29": {"number": 29, "epic": 3, "labels": [], "state": "OPEN", "title": "Child A"},
    "30": {"number": 30, "epic": 3, "labels": [], "state": "CLOSED", "title": "Child B"},
    "31": {"number": 31, "epic": 3, "labels": [], "state": "OPEN", "title": "Child C"},
}

AREAS = AreaSet(
    [
        Area("rollup", ["src/rollup/**"], "area:rollup"),
        Area("fares", ["src/fares/**"], "area:fares"),
    ],
    [],
)
AREA_GRAPH = {
    "33": {"number": 33, "state": "OPEN", "labels": ["area:rollup"]},
    "34": {"number": 34, "state": "OPEN", "labels": []},
    "35": {"number": 35, "state": "CLOSED", "labels": ["area:rollup"]},
    "36": {"number": 36, "state": "OPEN", "labels": ["epic", "area:rollup"]},
    "37": {"number": 37, "state": "OPEN", "labels": ["area:fares"]},
    "40": {"number": 40, "state": "OPEN", "labels": []},
}
PLAN_AREAS = {"34": ["rollup"]}


def _adr(consequences=None, supersedes=None, status="accepted", adr_id=2):
    return Adr(
        id=adr_id,
        title="Per-trip sync",
        status=status,
        date="2026-01-01",
        supersedes=supersedes or [],
        areas=[],
        consequences=consequences or [],
    )


def _consequence(cid, text, affects=None, kind="decision"):
    return Consequence(id=cid, text=text, affects=affects or [], kind=kind)


def test_affects_issue_ref_yields_pending_event():
    csq = _consequence("c1", "Migrate the DB", affects=["#29", "#30", "#999"])
    adr = _adr(consequences=[csq])
    candidates = compute_candidates(
        adr,
        GRAPH_ISSUES,
        ack_events=[],
        adr_rel_path="docs/adr/0002-per-trip.md",
    )
    assert len(candidates) == 1
    c = candidates[0]
    assert c["target"] == "#29"
    assert c["status"] == "pending"
    assert c["reason"] == "affects"
    assert c["kind"] == "decision"
    assert c["summary"] == "Migrate the DB"
    assert c["detail"] == "docs/adr/0002-per-trip.md#c1"


def test_affects_epic_expands_to_open_children():
    csq = _consequence("c1", "Expand to children", affects=["#3"])
    adr = _adr(consequences=[csq])
    candidates = compute_candidates(
        adr,
        GRAPH_ISSUES,
        ack_events=[],
        adr_rel_path="docs/adr/0002-per-trip.md",
    )
    targets = {c["target"] for c in candidates}
    assert targets == {"#29", "#31"}
    for c in candidates:
        assert c["status"] == "pending"
        assert c["reason"] == "affects"


def test_mention_not_in_affects_yields_proposed_event():
    # #29 is in affects; `#31` is mentioned in text (backtick form survives YAML)
    csq = _consequence("c1", "Migrate `#31` carefully", affects=["#29"])
    adr = _adr(consequences=[csq])
    candidates = compute_candidates(
        adr,
        GRAPH_ISSUES,
        ack_events=[],
        adr_rel_path="docs/adr/0002-per-trip.md",
    )
    assert any(c["target"] == "#29" and c["reason"] == "affects" for c in candidates)
    assert any(c["target"] == "#31" and c["reason"] == "mentions" for c in candidates)
    # #29 must NOT be re-proposed as a mention (already covered by affects)
    assert sum(1 for c in candidates if c["target"] == "#29") == 1


def test_supersedes_targets_prior_acknowledgers():
    from perturb.events import Event

    ack_events = [
        Event(
            id="e1",
            at="2026-01-01T00:00:00Z",
            source="adr:0001#foo",
            target="#29",
            kind="decision",
            summary="Old decision",
            detail=None,
            proposed_by="geuben",
            reason="affects",
            status="acknowledged",
        ),
        Event(
            id="e2",
            at="2026-01-01T00:00:00Z",
            source="adr:0001#bar",
            target="#30",  # closed
            kind="decision",
            summary="Old decision",
            detail=None,
            proposed_by="geuben",
            reason="affects",
            status="acknowledged",
        ),
    ]
    adr = _adr(supersedes=["adr:0001"], adr_id=2)
    candidates = compute_candidates(
        adr,
        GRAPH_ISSUES,
        ack_events=ack_events,
        adr_rel_path="docs/adr/0002-per-trip.md",
    )
    assert len(candidates) == 1
    c = candidates[0]
    assert c["target"] == "#29"
    assert c["kind"] == "supersede"
    assert c["reason"] == "supersedes"
    assert c["status"] == "pending"
    assert c["summary"] == adr.title
    assert c["source"] == "adr:0002"
    assert c["detail"] == "docs/adr/0002-per-trip.md"


def test_supersedes_a_single_consequence_targets_only_its_acknowledgers():
    from perturb.events import Event

    def acked(eid, source, target):
        return Event(
            id=eid,
            at="2026-01-01T00:00:00Z",
            source=source,
            target=target,
            kind="decision",
            summary="Old decision",
            detail=None,
            proposed_by="geuben",
            reason="affects",
            status="acknowledged",
        )

    ack_events = [
        acked("e1", "adr:0001#postgres-over-sqlite", "#29"),
        acked("e2", "adr:0001#typescript", "#31"),
        acked("e3", "adr:0001", "#31"),
    ]
    adr = _adr(supersedes=["adr:0001#postgres-over-sqlite"], adr_id=2)
    candidates = compute_candidates(
        adr, GRAPH_ISSUES, ack_events=ack_events, adr_rel_path="docs/adr/0002-per-trip.md"
    )
    fields = [(c["target"], c["kind"], c["reason"], c["status"], c["source"]) for c in candidates]
    assert fields == [("#29", "supersede", "supersedes", "pending", "adr:0002")]
    assert candidates[0]["summary"] == f"{adr.title} (supersedes adr:0001#postgres-over-sqlite)"


def test_deprecated_status_targets_this_adrs_acknowledgers():
    from perturb.events import Event

    ack_events = [
        Event(
            id="e1",
            at="2026-01-01T00:00:00Z",
            source="adr:0002#foo",
            target="#29",
            kind="decision",
            summary="Some decision",
            detail=None,
            proposed_by="geuben",
            reason="affects",
            status="acknowledged",
        ),
    ]
    adr = _adr(supersedes=[], status="deprecated", adr_id=2)
    candidates = compute_candidates(
        adr,
        GRAPH_ISSUES,
        ack_events=ack_events,
        adr_rel_path="docs/adr/0002-per-trip.md",
    )
    assert candidates
    c = candidates[0]
    assert c["target"] == "#29"
    assert c["reason"] == "deprecated"
    assert c["kind"] == "supersede"
    assert c["status"] == "pending"


def test_propose_writes_area_proposals_to_the_ledger(tmp_path):
    from perturb.events import EventStore

    csq = _consequence("reprice", "Re-pricing uses the rollup.", affects=["area:rollup"])
    adr = _adr(consequences=[csq])
    propose(
        tmp_path / "events",
        adr,
        {"33": {"number": 33, "state": "OPEN", "labels": ["area:rollup"]}},
        adr_rel_path="docs/adr/0002-x.md",
        proposed_by="geuben",
        area_set=AREAS,
        plan_areas_by_issue={},
    )
    events = EventStore(tmp_path / "events").load().events
    assert [(e.target, e.status, e.reason) for e in events] == [("#33", "proposed", "area")]


def test_compute_candidates_emits_one_candidate_per_consequence_target():
    adr = Adr(
        id=2,
        title="T",
        status="accepted",
        date="2026-01-01",
        supersedes=[],
        areas=["fares"],
        consequences=[
            _consequence("c-both", "Both ways.", affects=["#33", "area:rollup"]),
            _consequence("c-mention", "See #33.", affects=["area:rollup"]),
            _consequence("c-adrarea", "See #37."),
        ],
    )
    candidates = compute_candidates(
        adr,
        AREA_GRAPH,
        ack_events=[],
        adr_rel_path="docs/adr/0002-x.md",
        area_set=AREAS,
        plan_areas_by_issue=PLAN_AREAS,
    )
    assert sorted((c["source"], c["target"], c["reason"]) for c in candidates) == [
        ("adr:0002#c-adrarea", "#37", "adr-area"),
        ("adr:0002#c-both", "#33", "affects"),
        ("adr:0002#c-both", "#34", "area"),
        ("adr:0002#c-mention", "#33", "area"),
        ("adr:0002#c-mention", "#34", "area"),
    ]


def test_compute_candidates_routes_adr_areas_for_consequences_without_affects():
    adr = Adr(
        id=2,
        title="T",
        status="accepted",
        date="2026-01-01",
        supersedes=[],
        areas=["fares"],
        consequences=[
            _consequence("volume", "Rides per dock."),
            _consequence("dst", "Local days vary.", affects=["#40"]),
        ],
    )
    candidates = compute_candidates(
        adr,
        AREA_GRAPH,
        ack_events=[],
        adr_rel_path="docs/adr/0002-x.md",
        area_set=AREAS,
        plan_areas_by_issue=PLAN_AREAS,
    )
    assert {(c["source"], c["target"], c["status"], c["reason"]) for c in candidates} == {
        ("adr:0002#volume", "#37", "proposed", "adr-area"),
        ("adr:0002#dst", "#40", "pending", "affects"),
    }


def test_compute_candidates_routes_affects_area_to_in_area_issues():
    csq = _consequence(
        "reprice", "Re-pricing uses the rollup.", affects=["area:rollup", "area:typo"]
    )
    adr = _adr(consequences=[csq])
    candidates = compute_candidates(
        adr,
        AREA_GRAPH,
        ack_events=[],
        adr_rel_path="docs/adr/0002-x.md",
        area_set=AREAS,
        plan_areas_by_issue=PLAN_AREAS,
    )
    detail = "docs/adr/0002-x.md#reprice"
    summary = "Re-pricing uses the rollup."
    assert [
        (c["source"], c["target"], c["status"], c["reason"], c["kind"], c["summary"], c["detail"])
        for c in candidates
    ] == [
        ("adr:0002#reprice", "#33", "proposed", "area", "decision", summary, detail),
        ("adr:0002#reprice", "#34", "proposed", "area", "decision", summary, detail),
    ]


def test_propose_writes_events_and_returns_list(tmp_path):
    events_dir = tmp_path / "events"
    counter = [0]

    def fake_now():
        return "2026-09-13T00:00:00Z"

    def fake_id():
        counter[0] += 1
        return f"0000000000000000000000000{counter[0]:01d}"

    # ADR with two consequences affecting two distinct open issues
    csq1 = _consequence("c1", "Decision one", affects=["#29"])
    csq2 = _consequence("c2", "Decision two", affects=["#31"])
    adr = _adr(consequences=[csq1, csq2])

    result = propose(
        events_dir,
        adr,
        GRAPH_ISSUES,
        adr_rel_path="docs/adr/0002-per-trip.md",
        proposed_by="geuben",
        now=fake_now,
        new_id=fake_id,
    )

    assert len(list(events_dir.glob("*.yaml"))) == 2
    proposed = result["proposed"]
    assert len(proposed) == 2
    targets = {p["target"] for p in proposed}
    assert targets == {"#29", "#31"}
    for p in proposed:
        assert "id" in p
        assert "target" in p
        assert "reason" in p
        assert "status" in p


def test_review_confirms_and_dismisses_proposals(tmp_path):
    from perturb.events import EventStore

    events_dir = tmp_path / "events"
    events_dir.mkdir()
    counter = [0]

    def fake_now():
        return "2026-09-13T00:00:00Z"

    def fake_id():
        counter[0] += 1
        return f"P{counter[0]}"

    store = EventStore(events_dir, now=fake_now, new_id=fake_id)
    ev1 = store.create(
        source="adr:0002#c1",
        target="#29",
        kind="decision",
        summary="s1",
        proposed_by="geuben",
        reason="affects",
        status="proposed",
    )
    ev2 = store.create(
        source="adr:0002#c2",
        target="#31",
        kind="decision",
        summary="s2",
        proposed_by="geuben",
        reason="mentions",
        status="proposed",
    )

    responses = iter(["a", "d"])

    def fake_read(_prompt=""):
        return next(responses)

    collected = []
    result = review(store, [ev1, ev2], read=fake_read, write=collected.append)

    assert result["confirmed"] == [ev1.id]
    assert result["dismissed"] == [ev2.id]

    events = {e.id: e for e in store.load().events}
    assert events[ev1.id].status == "pending"
    assert events[ev2.id].status == "dismissed"


def test_resolve_adr_path_globs_and_refuses_when_absent(tmp_path):
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0002-per-trip.md").write_text("# ADR 0002")

    path = resolve_adr_path(tmp_path, "0002")
    assert path.name == "0002-per-trip.md"

    import pytest

    with pytest.raises(Refusal) as exc_info:
        resolve_adr_path(tmp_path, "0009")
    assert exc_info.value.reason == "adr_not_found"


# --- friction propose tests ---


def test_parse_friction_commits_extracts_shas():
    text = (
        "## Cycle 1\n"
        "  - `9561a8c97` [refactor] refactor: x (1 files)\n"
        "  - `dce012791` [green] feat: y (2 files)\n"
        "Plan blob: `b144518a...`\n"
    )
    assert parse_friction_commits(text) == ["9561a8c97", "dce012791"]


def test_read_declared_paths_unions_files_stub_and_ancillary():
    plan_text = (
        "---\n"
        'ancillary_files: ["docs/x.md"]\n'
        "cycles:\n"
        "  - n: 1\n"
        '    files: ["src/a.py"]\n'
        "  - n: 2\n"
        '    files: ["src/b.py"]\n'
        '    stub_expected: ["src/b.py", "src/c.py"]\n'
        "---\n"
        "body\n"
    )
    assert read_declared_paths(plan_text) == {"src/a.py", "src/b.py", "src/c.py", "docs/x.md"}


def test_files_touched_outside_subtracts_declared():
    calls = []

    def fake_runner(argv, **kwargs):
        calls.append(argv)
        sha = argv[-1]
        if sha == "sha1":
            stdout = "src/declared.py\nsrc/drift.py\n"
        else:
            stdout = "docs/note.md\n"
        return types.SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    result = files_touched_outside(["sha1", "sha2"], {"src/declared.py"}, runner=fake_runner)
    assert result == {"src/drift.py", "docs/note.md"}
    assert calls == [
        ["git", "show", "--name-only", "--format=", "sha1"],
        ["git", "show", "--name-only", "--format=", "sha2"],
    ]


def test_files_touched_outside_refuses_unreachable_sha():
    import pytest

    def fake_runner(argv, **kwargs):
        return types.SimpleNamespace(returncode=128, stdout="", stderr="fatal: bad object deadbeef")

    with pytest.raises(Refusal) as exc_info:
        files_touched_outside(["deadbeef"], set(), runner=fake_runner)
    assert exc_info.value.reason == "friction_commits_unreachable"
    assert "deadbeef" in exc_info.value.detail


def test_compute_friction_candidates_routes_touched_areas_to_open_issues():
    from perturb.areas import Area, AreaSet

    area_set = AreaSet(
        [
            Area("alpha", ["src/alpha/**"], "area:alpha"),
            Area("beta", ["src/beta/**"], "area:beta"),
        ],
        [],
    )
    touched_outside = {"src/alpha/x.py", "src/beta/y.py"}
    graph_issues = {
        "60": {"number": 60, "state": "OPEN", "labels": ["area:alpha"]},
        "61": {"number": 61, "state": "OPEN", "labels": []},
        "62": {"number": 62, "state": "CLOSED", "labels": ["area:alpha"]},
        "48": {"number": 48, "state": "OPEN", "labels": ["area:alpha"]},
        "45": {"number": 45, "state": "OPEN", "labels": ["epic"]},
        "63": {"number": 63, "state": "OPEN", "labels": ["area:gamma"]},
    }
    plan_areas_by_issue = {"61": ["beta"]}

    candidates = compute_friction_candidates(
        touched_outside,
        area_set,
        graph_issues,
        plan_areas_by_issue,
        source_ref="friction:w",
        source_number=48,
        friction_rel_path="tasks/friction-logs/w-friction.md",
    )

    assert {c["target"] for c in candidates} == {"#60", "#61"}
    for c in candidates:
        assert c["kind"] == "friction"
        assert c["status"] == "proposed"
        assert c["reason"] == "touches"
        assert c["source"] == "friction:w"
        assert c["detail"] == "tasks/friction-logs/w-friction.md"
    summary_by_target = {c["target"]: c["summary"] for c in candidates}
    assert "area:alpha" in summary_by_target["#60"]
    assert "area:beta" in summary_by_target["#61"]


def test_compute_friction_candidates_empty_areaset_yields_nothing():
    from perturb.areas import AreaSet

    candidates = compute_friction_candidates(
        {"src/alpha/x.py"},
        AreaSet([], []),
        {"60": {"number": 60, "state": "OPEN", "labels": ["area:alpha"]}},
        {},
        source_ref="friction:w",
        source_number=48,
        friction_rel_path="tasks/friction-logs/w-friction.md",
    )
    assert candidates == []


def test_propose_friction_writes_events_and_refuses_missing_log(tmp_path):
    import pytest

    repo_root = tmp_path
    events_dir = tmp_path / "perturb" / "events"
    events_dir.mkdir(parents=True)

    # Friction log with one commit SHA
    (repo_root / "tasks" / "friction-logs").mkdir(parents=True)
    (repo_root / "tasks" / "friction-logs" / "w-friction.md").write_text(
        "  - `deadbeef1` [green] feat: something (1 files)\n"
    )

    # Plan file with closes: 48 and one cycle
    (repo_root / "tasks" / "w.md").write_text(
        '---\ncloses: 48\ncycles:\n  - n: 1\n    files: ["src/w.py"]\n---\nbody\n'
    )

    # Areas file
    (repo_root / "perturb").mkdir(exist_ok=True)
    (repo_root / "perturb" / "areas.yaml").write_text(
        'areas:\n  alpha:\n    paths:\n      - "src/alpha/**"\n'
    )

    graph_issues = {
        "70": {"number": 70, "state": "OPEN", "labels": ["area:alpha"], "plan": None},
    }

    counter = [0]

    def fake_now():
        return "2026-09-13T00:00:00Z"

    def fake_id():
        counter[0] += 1
        return f"00000000000000000000000{counter[0]:01d}"

    def fake_runner(argv, **kwargs):
        sha = argv[-1]
        if sha == "deadbeef1":
            return types.SimpleNamespace(returncode=0, stdout="src/alpha/new.py\n", stderr="")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    result = propose_friction(
        repo_root,
        events_dir,
        "w",
        graph_issues,
        runner=fake_runner,
        proposed_by="geuben",
        now=fake_now,
        new_id=fake_id,
    )

    assert len(result["proposed"]) == 1
    assert result["proposed"][0]["target"] == "#70"
    assert result["proposed"][0]["reason"] == "touches"
    assert len(list(events_dir.glob("*.yaml"))) == 1

    # Refuses missing log
    with pytest.raises(Refusal) as exc_info:
        propose_friction(
            repo_root,
            events_dir,
            "does-not-exist",
            {},
            runner=fake_runner,
            proposed_by="geuben",
        )
    assert exc_info.value.reason == "friction_log_not_found"


def test_propose_friction_excludes_source_issue_when_plan_closes_matches(tmp_path):
    """plan_path.exists() drives source_number: the closes: issue must be absent from proposals."""
    repo_root = tmp_path
    events_dir = tmp_path / "perturb" / "events"
    events_dir.mkdir(parents=True)

    (repo_root / "tasks" / "friction-logs").mkdir(parents=True)
    (repo_root / "tasks" / "friction-logs" / "w-friction.md").write_text(
        "  - `deadbeef1` [green] feat: something (1 files)\n"
    )
    (repo_root / "tasks" / "w.md").write_text(
        '---\ncloses: 48\ncycles:\n  - n: 1\n    files: ["src/w.py"]\n---\nbody\n'
    )
    (repo_root / "perturb").mkdir(exist_ok=True)
    (repo_root / "perturb" / "areas.yaml").write_text(
        'areas:\n  alpha:\n    paths:\n      - "src/alpha/**"\n'
    )

    graph_issues = {
        "70": {"number": 70, "state": "OPEN", "labels": ["area:alpha"], "plan": None},
        "48": {"number": 48, "state": "OPEN", "labels": ["area:alpha"], "plan": None},
    }

    def fake_runner(argv, **kwargs):
        if argv[-1] == "deadbeef1":
            return types.SimpleNamespace(returncode=0, stdout="src/alpha/new.py\n", stderr="")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    result = propose_friction(
        repo_root,
        events_dir,
        "w",
        graph_issues,
        runner=fake_runner,
        proposed_by="geuben",
    )

    targets = {p["target"] for p in result["proposed"]}
    assert "#70" in targets
    assert "#48" not in targets


def test_propose_friction_reads_issue_plan_areas_when_plan_file_present(tmp_path):
    """if plan_path_issue.exists(): routes an issue via its plan's areas: field."""
    repo_root = tmp_path
    events_dir = tmp_path / "perturb" / "events"
    events_dir.mkdir(parents=True)

    (repo_root / "tasks" / "friction-logs").mkdir(parents=True)
    (repo_root / "tasks" / "friction-logs" / "w-friction.md").write_text(
        "  - `deadbeef1` [green] feat: something (1 files)\n"
    )
    (repo_root / "tasks" / "w.md").write_text(
        '---\ncloses: 99\ncycles:\n  - n: 1\n    files: ["src/w.py"]\n---\nbody\n'
    )
    (repo_root / "perturb").mkdir(exist_ok=True)
    # Only area beta is declared
    (repo_root / "perturb" / "areas.yaml").write_text(
        'areas:\n  beta:\n    paths:\n      - "src/beta/**"\n'
    )
    # touched file is in beta
    # Issue 80 has no beta label but its plan declares beta via areas:
    (repo_root / "tasks" / "issue-80.md").write_text("---\nareas: [beta]\n---\nbody\n")

    graph_issues = {
        "80": {
            "number": 80,
            "state": "OPEN",
            "labels": [],
            "plan": "tasks/issue-80.md",
        },
    }

    def fake_runner(argv, **kwargs):
        if argv[-1] == "deadbeef1":
            return types.SimpleNamespace(returncode=0, stdout="src/beta/new.py\n", stderr="")
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    result = propose_friction(
        repo_root,
        events_dir,
        "w",
        graph_issues,
        runner=fake_runner,
        proposed_by="geuben",
    )

    targets = {p["target"] for p in result["proposed"]}
    assert "#80" in targets


# --- plan source tests (cycles 1-5) ---

_PLAN_TEXT_C1 = """\
---
closes: 47
cycles: []
---

## Context

This section must be ignored entirely.

## Design decisions (locked)

1. First decision mentioning #12 here.
2. Second decision with no ref.

## Deliberate scope cuts (do not build)

- moves to #34 and also cuts this feature.
"""

_PLAN_TEXT_EMPTY = """\
---
closes: 47
---

## Context

No decision or scope sections here.
"""


def test_parse_plan_entries_extracts_decision_and_scope_entries():
    entries = parse_plan_entries(_PLAN_TEXT_C1)
    assert len(entries) == 3
    kinds = [e["kind"] for e in entries]
    assert kinds == ["decision", "decision", "scope"]
    for e in entries[:2]:
        assert e["anchor"] == "design-decisions-locked"
    assert entries[2]["anchor"] == "deliberate-scope-cuts-do-not-build"
    assert "#12" in entries[0]["text"]
    assert "moves to #34" in entries[2]["text"]
    assert parse_plan_entries(_PLAN_TEXT_EMPTY) == []


_PLAN_TEXT_CONTINUATION = """\
---
closes: 47
---

## Design decisions (locked)

1. First decision spans two
   lines and mentions #12.
2. Second decision is single-line.
"""


def test_parse_plan_entries_joins_continuation_lines():
    entries = parse_plan_entries(_PLAN_TEXT_CONTINUATION)
    assert len(entries) == 2
    assert "#12" in entries[0]["text"]
    assert "lines" in entries[0]["text"]
    assert "spans two" in entries[0]["text"]


_PLAN_TEXT_DEDUP = """\
---
closes: 47
---

## Design decisions (locked)

1. First entry mentions #60.
2. Second entry also mentions #60.
"""


def test_compute_plan_candidates_deduplicates_same_target_same_kind():
    graph = {"60": {"number": 60, "state": "OPEN", "labels": [], "epic": None}}
    candidates = compute_plan_candidates(
        _PLAN_TEXT_DEDUP,
        graph,
        source_ref="plan:p",
        source_number=99,
        plan_rel_path="tasks/p.md",
    )
    targets = [c["target"] for c in candidates]
    assert targets.count("#60") == 1


_GRAPH_C2 = {
    "60": {"number": 60, "state": "OPEN", "labels": [], "epic": None},
    "45": {"number": 45, "state": "OPEN", "labels": ["epic"], "epic": None},
    "61": {"number": 61, "state": "OPEN", "labels": [], "epic": 45},
    "62": {"number": 62, "state": "OPEN", "labels": [], "epic": None},
    "63": {"number": 63, "state": "CLOSED", "labels": [], "epic": None},
    "47": {"number": 47, "state": "OPEN", "labels": [], "epic": None},
}

_PLAN_TEXT_C2 = """\
---
closes: 47
---

## Design decisions (locked)

1. Decision mentioning #60, #45 (epic), #47 (self) and #999 (off-graph) and #63 (closed).

## Deliberate scope cuts (do not build)

- moves to #62.
"""


def test_compute_plan_candidates_routes_refs_to_targets_by_section():
    candidates = compute_plan_candidates(
        _PLAN_TEXT_C2,
        _GRAPH_C2,
        source_ref="plan:p",
        source_number=47,
        plan_rel_path="tasks/p.md",
    )
    pairs = {(c["target"], c["kind"]) for c in candidates}
    assert pairs == {("#60", "decision"), ("#61", "decision"), ("#62", "scope")}
    for c in candidates:
        assert c["status"] == "proposed"
        assert c["reason"] == "mentions"
        assert c["source"] == "plan:p"
        assert c["summary"]
    decision_cs = [c for c in candidates if c["kind"] == "decision"]
    scope_cs = [c for c in candidates if c["kind"] == "scope"]
    for c in decision_cs:
        assert c["detail"].endswith("#design-decisions-locked")
    for c in scope_cs:
        assert c["detail"].endswith("#deliberate-scope-cuts-do-not-build")


_GRAPH_C3 = {
    "35": {"number": 35, "state": "OPEN", "labels": [], "epic": None},
    "13": {"number": 13, "state": "OPEN", "labels": [], "epic": None},
}

_PLAN_TEXT_C3 = """\
---
closes: 39
---

## Design decisions (locked)

1. the parser plan (#35) and another repo's issue [#13](https://github.com/example/other-repo/issues/13).
"""


def test_compute_plan_candidates_excludes_url_link_refs():
    candidates = compute_plan_candidates(
        _PLAN_TEXT_C3,
        _GRAPH_C3,
        source_ref="plan:p",
        source_number=39,
        plan_rel_path="tasks/p.md",
    )
    targets = {c["target"] for c in candidates}
    assert targets == {"#35"}


def test_propose_plan_writes_events_and_refuses_missing_plan(tmp_path):
    import pytest

    repo_root = tmp_path
    events_dir = tmp_path / "perturb" / "events"
    events_dir.mkdir(parents=True)

    (repo_root / "tasks").mkdir()
    (repo_root / "tasks" / "p.md").write_text(
        "---\ncloses: 47\n---\n\n## Design decisions (locked)\n\n1. Mention #70.\n"
    )

    graph_issues = {
        "70": {"number": 70, "state": "OPEN", "labels": [], "epic": None},
    }

    counter = [0]

    def fake_now():
        return "2026-09-13T00:00:00Z"

    def fake_id():
        counter[0] += 1
        return f"00000000000000000000000{counter[0]:01d}"

    result = propose_plan(
        repo_root,
        events_dir,
        "p",
        graph_issues,
        proposed_by="geuben",
        now=fake_now,
        new_id=fake_id,
    )

    yaml_files = list(events_dir.glob("*.yaml"))
    assert len(yaml_files) == 1
    assert len(result["proposed"]) == 1
    assert result["proposed"][0]["target"] == "#70"
    assert result["proposed"][0]["kind"] == "decision"

    with pytest.raises(Refusal) as exc_info:
        propose_plan(repo_root, events_dir, "does-not-exist", {}, proposed_by="geuben")
    assert exc_info.value.reason == "plan_not_found"


_AUDIT_ITEMS_DOC = """\
- [ ] **[CRITICAL]:** a1
- [ ] **[CRITICAL]** a2
- [x] **[CRITICAL]**: a3
- [X] **[PLANNING DEBT]:** a4
  - [ ] **[CRITICAL]** a5
- [ ] **[CRITICAL / MINOR]:** r1
- [ ] **[MINOR]** r2
- [ ] **[HIGH]** r3
- **[CRITICAL]** r4
### 3.2 Baseline capture — CRITICAL r5
| 1.1 | col | **CRITICAL impact** | r6
"""


_AREA_ALPHA = Area("alpha", ["src/alpha/**"], "area:alpha")
_AREA_BETA = Area("beta", ["src/beta/**"], "area:beta")
_AREA_SET_AB = AreaSet([_AREA_ALPHA, _AREA_BETA], [])

_AUDIT_GRAPH_C3 = {
    "70": {"number": 70, "state": "OPEN", "labels": ["area:alpha"], "epic": None},
    "71": {"number": 71, "state": "OPEN", "labels": [], "epic": None},
    "72": {"number": 72, "state": "OPEN", "labels": ["area:beta"], "epic": None},
    "73": {"number": 73, "state": "CLOSED", "labels": ["area:alpha"], "epic": None},
    "74": {"number": 74, "state": "OPEN", "labels": ["epic", "area:alpha"], "epic": None},
    "49": {"number": 49, "state": "OPEN", "labels": ["area:alpha"], "epic": None},
}
_PLAN_AREAS_C3 = {"71": ["alpha"]}


def test_propose_audit_rerun_is_idempotent(tmp_path):
    from perturb.propose import propose_audit

    repo = tmp_path
    (repo / "perturb").mkdir()
    (repo / "perturb" / "areas.yaml").write_text(
        "areas:\n  alpha:\n    paths:\n      - src/alpha/**\n"
    )
    (repo / "tasks").mkdir()
    (repo / "tasks" / "other.md").write_text("---\ncloses: 70\nareas: [alpha]\n---\n\n")
    (repo / "tasks" / "friction-audits").mkdir(parents=True)
    (repo / "tasks" / "friction-audits" / "w-audit.md").write_text(
        "- [ ] **[CRITICAL]** fix `src/alpha/x.py`\n- [ ] **[PLANNING DEBT]:** rule for grill-me\n"
    )
    events_dir = repo / "perturb" / "events"
    graph_issues = {
        "70": {"number": 70, "state": "OPEN", "labels": [], "epic": None, "plan": "tasks/other.md"},
    }

    counter = [0]

    def fake_now():
        return "2026-09-15T00:00:00Z"

    def fake_id():
        counter[0] += 1
        return f"0000000000000000000000000000{counter[0]:02d}"

    propose_audit(
        repo, events_dir, "w", graph_issues, proposed_by="geuben", now=fake_now, new_id=fake_id
    )
    propose_audit(repo, events_dir, "w", graph_issues, proposed_by="geuben")

    yaml_files = list(events_dir.glob("*.yaml"))
    assert len(yaml_files) == 2


def test_propose_audit_falls_back_to_plan_declared_files(tmp_path):
    from perturb.events import EventStore
    from perturb.propose import propose_audit

    repo = tmp_path
    (repo / "perturb").mkdir()
    (repo / "perturb" / "areas.yaml").write_text(
        "areas:\n"
        "  alpha:\n    paths:\n      - src/alpha/**\n"
        "  beta:\n    paths:\n      - src/beta/**\n"
    )
    (repo / "tasks").mkdir()
    plan_text = "---\ncloses: 49\ncycles:\n  - n: 1\n    files: [src/beta/y.py]\n---\n\n"
    (repo / "tasks" / "w.md").write_text(plan_text)
    (repo / "tasks" / "friction-audits").mkdir(parents=True)
    (repo / "tasks" / "friction-audits" / "w-audit.md").write_text(
        "- [ ] **[CRITICAL]** no paths here\n"
    )
    events_dir = repo / "perturb" / "events"
    graph_issues = {
        "72": {"number": 72, "state": "OPEN", "labels": ["area:beta"], "epic": None, "plan": None},
    }
    propose_audit(repo, events_dir, "w", graph_issues, proposed_by="geuben")

    store = EventStore(events_dir)
    events = store.load().events
    assert {e.target for e in events} == {"#72"}


def test_propose_audit_falls_back_to_plan_front_matter_areas(tmp_path):
    from perturb.events import EventStore
    from perturb.propose import propose_audit

    repo = tmp_path
    (repo / "perturb").mkdir()
    (repo / "perturb" / "areas.yaml").write_text(
        "areas:\n"
        "  alpha:\n    paths:\n      - src/alpha/**\n"
        "  beta:\n    paths:\n      - src/beta/**\n"
    )
    (repo / "tasks").mkdir()
    (repo / "tasks" / "w.md").write_text("---\ncloses: 49\nareas: [beta]\n---\n\n")
    (repo / "tasks" / "friction-audits").mkdir(parents=True)
    (repo / "tasks" / "friction-audits" / "w-audit.md").write_text(
        "- [ ] **[CRITICAL]** no paths here\n"
    )
    events_dir = repo / "perturb" / "events"
    graph_issues = {
        "72": {"number": 72, "state": "OPEN", "labels": ["area:beta"], "epic": None, "plan": None},
    }
    propose_audit(repo, events_dir, "w", graph_issues, proposed_by="geuben")

    store = EventStore(events_dir)
    events = store.load().events
    assert {e.target for e in events} == {"#72"}


def test_propose_audit_writes_events_and_dismisses_noted_candidates(tmp_path):
    from perturb.events import EventStore
    from perturb.propose import propose_audit

    repo = tmp_path
    (repo / "perturb").mkdir()
    (repo / "perturb" / "areas.yaml").write_text(
        "areas:\n  alpha:\n    paths:\n      - src/alpha/**\n"
    )
    (repo / "tasks").mkdir()
    (repo / "tasks" / "other.md").write_text("---\ncloses: 70\nareas: [alpha]\n---\n\n")
    (repo / "tasks" / "friction-audits").mkdir(parents=True)
    (repo / "tasks" / "friction-audits" / "w-audit.md").write_text(
        "- [ ] **[CRITICAL]** fix `src/alpha/x.py`\n- [ ] **[PLANNING DEBT]:** rule for grill-me\n"
    )
    events_dir = repo / "perturb" / "events"
    graph_issues = {
        "70": {"number": 70, "state": "OPEN", "labels": [], "epic": None, "plan": "tasks/other.md"},
    }

    counter = [0]

    def fake_now():
        return "2026-09-15T00:00:00Z"

    def fake_id():
        counter[0] += 1
        return f"0000000000000000000000000000{counter[0]:02d}"

    propose_audit(
        repo, events_dir, "w", graph_issues, proposed_by="geuben", now=fake_now, new_id=fake_id
    )

    store = EventStore(events_dir)
    events = store.load().events
    by_target = {e.target: e for e in events}
    assert set(by_target) == {"#70", "area:planning"}
    assert by_target["#70"].status == "proposed"
    assert by_target["area:planning"].status == "dismissed"
    assert by_target["area:planning"].ack["note"] == (
        "area:planning not declared in perturb/areas.yaml"
    )


def test_propose_audit_refuses_missing_audit(tmp_path):
    import pytest

    from perturb.propose import propose_audit

    with pytest.raises(Refusal) as exc_info:
        propose_audit(
            tmp_path,
            tmp_path / "perturb" / "events",
            "does-not-exist",
            {},
            proposed_by="geuben",
        )
    assert exc_info.value.reason == "audit_not_found"


def test_compute_audit_candidates_marks_planning_debt_dismissed_when_area_undeclared():
    from perturb.propose import compute_audit_candidates

    audit = "- [ ] **[PLANNING DEBT]:** rule for grill-me\n"
    area_set = AreaSet([_AREA_ALPHA], [])
    result = compute_audit_candidates(
        audit,
        area_set,
        {},
        {},
        fallback_areas=set(),
        source_ref="audit:w",
        source_number=49,
        audit_rel_path="tasks/friction-audits/w-audit.md",
    )
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["target"] == "area:planning"
    expected_note = "area:planning not declared in perturb/areas.yaml"
    assert result["candidates"][0]["dismiss_note"] == expected_note
    assert result["no_target"] == []


def test_compute_audit_candidates_routes_planning_debt_to_planning_area():
    from perturb.propose import compute_audit_candidates

    area_planning = Area("planning", ["docs/**"], "area:planning")
    area_set = AreaSet([area_planning, _AREA_ALPHA], [])
    audit = "- [ ] **[PLANNING DEBT]:** plan missed `src/alpha/x.py` fixture, see #70\n"
    graph = {"70": {"number": 70, "state": "OPEN", "labels": ["area:alpha"], "epic": None}}
    result = compute_audit_candidates(
        audit,
        area_set,
        graph,
        {},
        fallback_areas=set(),
        source_ref="audit:w",
        source_number=49,
        audit_rel_path="tasks/friction-audits/w-audit.md",
    )
    assert result["candidates"] == [
        {
            "source": "audit:w",
            "target": "area:planning",
            "kind": "friction",
            "status": "proposed",
            "reason": "area",
            "summary": "plan missed `src/alpha/x.py` fixture, see #70",
            "detail": "tasks/friction-audits/w-audit.md",
        }
    ]
    assert "dismiss_note" not in result["candidates"][0]
    assert result["no_target"] == []


def test_compute_audit_candidates_reports_critical_item_with_no_target():
    from perturb.propose import compute_audit_candidates

    audit = "- [ ] **[CRITICAL]** route to #80\n- [ ] **[CRITICAL]** nobody owns this\n"
    area_set = AreaSet([], [])
    graph = {"80": {"number": 80, "state": "OPEN", "labels": [], "epic": None}}
    result = compute_audit_candidates(
        audit,
        area_set,
        graph,
        {},
        fallback_areas=set(),
        source_ref="audit:w",
        source_number=49,
        audit_rel_path="tasks/friction-audits/w-audit.md",
    )
    assert result["no_target"] == [{"level": "CRITICAL", "summary": "nobody owns this"}]


def test_compute_audit_candidates_targets_mentioned_issues():
    from perturb.propose import compute_audit_candidates

    audit = (
        "- [ ] **[CRITICAL]** see #80, epic #45, closed #81, self #49, "
        "missing #999 and [#13](https://github.com/example/other-repo/issues/13)\n"
    )
    area_set = AreaSet([], [])
    graph = {
        "80": {"number": 80, "state": "OPEN", "labels": [], "epic": None},
        "45": {"number": 45, "state": "OPEN", "labels": ["epic"], "epic": None},
        "82": {"number": 82, "state": "OPEN", "labels": [], "epic": 45},
        "81": {"number": 81, "state": "CLOSED", "labels": [], "epic": None},
        "49": {"number": 49, "state": "OPEN", "labels": [], "epic": None},
        "13": {"number": 13, "state": "OPEN", "labels": [], "epic": None},
    }
    result = compute_audit_candidates(
        audit,
        area_set,
        graph,
        {},
        fallback_areas=set(),
        source_ref="audit:w",
        source_number=49,
        audit_rel_path="tasks/friction-audits/w-audit.md",
    )
    pairs = {(c["target"], c["reason"]) for c in result["candidates"]}
    assert pairs == {("#80", "mentions"), ("#82", "mentions")}


def test_compute_audit_candidates_falls_back_to_plan_areas():
    from perturb.propose import compute_audit_candidates

    audit = "- [ ] **[CRITICAL]** fix `FakeSocialTokenVerifier` coupling\n"
    graph = {
        "70": {"number": 70, "state": "OPEN", "labels": ["area:alpha"], "epic": None},
        "72": {"number": 72, "state": "OPEN", "labels": ["area:beta"], "epic": None},
    }
    result = compute_audit_candidates(
        audit,
        _AREA_SET_AB,
        graph,
        {},
        fallback_areas={"beta"},
        source_ref="audit:w",
        source_number=49,
        audit_rel_path="tasks/friction-audits/w-audit.md",
    )
    assert {c["target"] for c in result["candidates"]} == {"#72"}


def test_compute_audit_candidates_strips_line_suffix_from_cited_paths():
    from perturb.propose import compute_audit_candidates

    area_core = Area("core", ["src/perturb/propose.py"], "area:core")
    area_set = AreaSet([area_core], [])
    audit = "- [ ] **[CRITICAL]** fix `src/perturb/propose.py:159-166` coupling\n"
    graph = {"70": {"number": 70, "state": "OPEN", "labels": ["area:core"], "epic": None}}
    result = compute_audit_candidates(
        audit,
        area_set,
        graph,
        {},
        fallback_areas=set(),
        source_ref="audit:w",
        source_number=49,
        audit_rel_path="tasks/friction-audits/w-audit.md",
    )
    assert {c["target"] for c in result["candidates"]} == {"#70"}


def test_compute_audit_candidates_routes_critical_item_by_cited_paths():
    from perturb.propose import compute_audit_candidates

    audit = "- [ ] **[CRITICAL]** fix `src/alpha/x.py` coupling\n"
    result = compute_audit_candidates(
        audit,
        _AREA_SET_AB,
        _AUDIT_GRAPH_C3,
        _PLAN_AREAS_C3,
        fallback_areas=set(),
        source_ref="audit:w",
        source_number=49,
        audit_rel_path="tasks/friction-audits/w-audit.md",
    )
    pairs = {(c["target"], c["reason"]) for c in result["candidates"]}
    assert pairs == {("#70", "area"), ("#71", "area")}
    for c in result["candidates"]:
        assert c["kind"] == "friction"
        assert c["status"] == "proposed"
        assert c["source"] == "audit:w"
        assert c["detail"] == "tasks/friction-audits/w-audit.md"
        assert "fix" in c["summary"]
    assert result["no_target"] == []


def test_parse_audit_items_joins_continuation_lines():
    doc = (
        "- [ ] **[CRITICAL]** refactor the\n"
        "  seam in `src/alpha/x.py`\n"
        "  before release\n"
        "\n"
        "- [ ] **[MINOR]** other\n"
    )
    result = parse_audit_items(doc)
    assert result == [
        {"level": "CRITICAL", "text": "refactor the seam in `src/alpha/x.py` before release"},
    ]


def test_parse_audit_items_accepts_level_tag_forms_and_rejects_others():
    result = parse_audit_items(_AUDIT_ITEMS_DOC)
    assert result == [
        {"level": "CRITICAL", "text": "a1"},
        {"level": "CRITICAL", "text": "a2"},
        {"level": "CRITICAL", "text": "a3"},
        {"level": "PLANNING DEBT", "text": "a4"},
        {"level": "CRITICAL", "text": "a5"},
    ]


def test_audit_issue_title_truncates_at_a_word_boundary():
    from perturb.propose import audit_issue_title

    cases = {
        "short": "nobody owns this",
        "exactly_72": "x" * 72,
        "long_with_space": "a" * 70 + " bbbbbbbbbb",
        "long_no_space": "c" * 80,
        "keeps_backticks": "fix `src/x.py`",
    }
    expected = {
        "short": "nobody owns this",
        "exactly_72": "x" * 72,
        "long_with_space": "a" * 70 + "…",
        "long_no_space": "c" * 72 + "…",
        "keeps_backticks": "fix `src/x.py`",
    }
    assert {k: audit_issue_title(v) for k, v in cases.items()} == expected


def test_propose_audit_moves_already_raised_items_out_of_no_target(tmp_path):
    from perturb.events import EventStore
    from perturb.propose import propose_audit

    repo = tmp_path
    (repo / "perturb").mkdir()
    (repo / "perturb" / "areas.yaml").write_text(
        'areas:\n  alpha:\n    paths:\n      - "src/alpha/**"\n'
    )
    (repo / "tasks").mkdir()
    (repo / "tasks" / "friction-audits").mkdir(parents=True)
    (repo / "tasks" / "friction-audits" / "w-audit.md").write_text(
        "- [ ] **[CRITICAL]** nobody owns this\n- [ ] **[CRITICAL]** also unowned\n"
    )
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)
    store = EventStore(events_dir)
    store.create(
        source="audit:w",
        target="#88",
        kind="friction",
        summary="nobody owns this",
        proposed_by="geuben",
        reason="manual",
        status="pending",
    )
    store.create(
        source="audit:w",
        target="#70",
        kind="friction",
        summary="also unowned",
        proposed_by="geuben",
        reason="area",
        status="proposed",
    )

    result = propose_audit(repo, events_dir, "w", {}, proposed_by="geuben")
    assert (result["no_target"], result.get("already_raised")) == (
        [{"level": "CRITICAL", "summary": "also unowned"}],
        [{"level": "CRITICAL", "summary": "nobody owns this", "target": "#88"}],
    )


def test_raise_no_target_issues_creates_issue_and_pending_event(tmp_path):
    from perturb.events import EventStore
    from perturb.propose import raise_no_target_issues

    events_dir = tmp_path / "events"
    events_dir.mkdir()
    store = EventStore(events_dir)

    calls = []

    def create_issue(title, body):
        calls.append((title, body))
        return 88

    result = raise_no_target_issues(
        store,
        [{"level": "CRITICAL", "summary": "nobody owns this"}],
        source_ref="audit:w",
        audit_rel_path="tasks/friction-audits/w-audit.md",
        proposed_by="geuben",
        create_issue=create_issue,
        read=lambda _p: "a",
        write=lambda _s: None,
    )

    assert (
        calls,
        [
            (e.source, e.target, e.kind, e.summary, e.reason, e.status, e.detail)
            for e in store.load().events
        ],
        [c["target"] for c in result["created"]],
    ) == (
        [
            (
                "nobody owns this",
                "nobody owns this\n\n"
                "From `tasks/friction-audits/w-audit.md` (`perturb propose audit:w`).",
            )
        ],
        [
            (
                "audit:w",
                "#88",
                "friction",
                "nobody owns this",
                "manual",
                "pending",
                "tasks/friction-audits/w-audit.md",
            )
        ],
        ["#88"],
    )


def test_raise_no_target_issues_creates_only_on_accept(tmp_path):
    from perturb.events import EventStore
    from perturb.propose import raise_no_target_issues

    answers = ["a", "accept", " A\n", "ACCEPT", "s", "skip", "d", "dismiss", "", "y", "create"]
    outcome = {}
    for i, answer in enumerate(answers):
        events_dir = tmp_path / str(i)
        events_dir.mkdir()
        store = EventStore(events_dir)
        call_count = [0]

        def create_issue(title, body, _cc=call_count):
            _cc[0] += 1
            return 88

        result = raise_no_target_issues(
            store,
            [{"level": "CRITICAL", "summary": "nobody owns this"}],
            source_ref="audit:w",
            audit_rel_path="tasks/friction-audits/w-audit.md",
            proposed_by="geuben",
            create_issue=create_issue,
            read=lambda _p, a=answer: a,
            write=lambda _s: None,
        )
        outcome[answer] = (call_count[0], len(result["created"]), result["skipped"])

    expected = {
        "a": (1, 1, []),
        "accept": (1, 1, []),
        " A\n": (1, 1, []),
        "ACCEPT": (1, 1, []),
        "s": (0, 0, ["nobody owns this"]),
        "skip": (0, 0, ["nobody owns this"]),
        "d": (0, 0, ["nobody owns this"]),
        "dismiss": (0, 0, ["nobody owns this"]),
        "": (0, 0, ["nobody owns this"]),
        "y": (0, 0, ["nobody owns this"]),
        "create": (0, 0, ["nobody owns this"]),
    }
    assert outcome == expected


def test_proposed_just_written_keeps_only_written_proposed_events(tmp_path):
    from perturb.events import EventStore
    from perturb.propose import proposed_just_written

    events_dir = tmp_path / "events"
    events_dir.mkdir()
    ids = iter(["P1", "P2", "P3", "P4"])
    store = EventStore(events_dir, new_id=lambda: next(ids))
    store.create(
        source="adr:0002#c",
        target="#29",
        kind="decision",
        summary="s1",
        proposed_by="geuben",
        reason="mentions",
        status="proposed",
    )
    store.create(
        source="adr:0002#c",
        target="#29",
        kind="decision",
        summary="s2",
        proposed_by="geuben",
        reason="mentions",
        status="pending",
    )
    store.create(
        source="adr:0002#c",
        target="#29",
        kind="decision",
        summary="s3",
        proposed_by="geuben",
        reason="mentions",
        status="proposed",
    )
    store.create(
        source="adr:0002#c",
        target="#29",
        kind="decision",
        summary="s4",
        proposed_by="geuben",
        reason="mentions",
        status="proposed",
    )
    store.dismiss("P4", by="geuben")

    written = [
        {"id": "P1", "status": "proposed"},
        {"id": "P2", "status": "pending"},
        {"id": "P4", "status": "proposed"},
    ]
    assert [e.id for e in proposed_just_written(store.load().events, written)] == ["P1"]


def test_parse_friction_commits_reads_front_matter_commits_and_rendered_lines():
    from perturb.propose import parse_friction_commits

    text = (
        "---\nplan: tasks/p.md\ncommits:\n  - abc1234\n  - 'def5678'\n  - not-a-sha\n---\n\n"
        "# Friction log\n\n- `abc1234` [red] test: x\n- `9876fed` [green] feat: y\n"
    )
    assert parse_friction_commits(text) == ["abc1234", "def5678", "9876fed"]


def test_read_declared_paths_accepts_a_top_level_files_list():
    from perturb.propose import read_declared_paths

    plan = "---\ncloses: 3\nfiles: [src/a.py, docs/b.md]\ncycles:\n  - files: [src/c.py]\n---\n"
    assert read_declared_paths(plan) == {"src/a.py", "docs/b.md", "src/c.py"}


def test_propose_sources_follow_the_configured_paths(tmp_path):
    from perturb.config import Config
    from perturb.events import EventStore
    from perturb.propose import propose_audit, propose_friction, propose_plan

    config = Config(
        plan="plans/{slug}.md", friction_log="runs/{slug}.log.md", audit="reviews/{slug}.md"
    )
    (tmp_path / "plans").mkdir()
    (tmp_path / "plans" / "p.md").write_text(
        "---\ncloses: 1\n---\n\n## Design decisions (locked)\n\n1. Share the parser with #2.\n"
    )
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "p.log.md").write_text("---\ncommits: [abc1234]\n---\n")
    (tmp_path / "reviews").mkdir()
    (tmp_path / "reviews" / "p.md").write_text("- [ ] **[CRITICAL]** the parser leaks into #2\n")
    (tmp_path / "perturb").mkdir()
    (tmp_path / "perturb" / "areas.yaml").write_text("areas:\n  x:\n    paths: ['src/**']\n")
    graph = {
        "1": {"number": 1, "state": "OPEN", "labels": [], "epic": None},
        "2": {"number": 2, "state": "OPEN", "labels": ["area:x"], "epic": None},
    }
    events = tmp_path / "perturb" / "events"

    def runner(argv, capture_output=True, text=True):
        assert argv == ["git", "show", "--name-only", "--format=", "abc1234"]

        class R:
            returncode = 0
            stdout = "src/x.py\n"

        return R()

    propose_plan(tmp_path, events, "p", graph, proposed_by="t", config=config)
    propose_friction(tmp_path, events, "p", graph, runner=runner, proposed_by="t", config=config)
    propose_audit(tmp_path, events, "p", graph, proposed_by="t", config=config)

    details = sorted((e.source, e.target, e.detail) for e in EventStore(events).load().events)
    assert details == [
        ("audit:p", "#2", "reviews/p.md"),
        ("friction:p", "#2", "runs/p.log.md"),
        ("plan:p", "#2", "plans/p.md#design-decisions-locked"),
    ]
