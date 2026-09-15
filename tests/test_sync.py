import itertools
import json

import pytest

from perturb import __version__
from perturb.events import EventStore
from perturb.github import GitHubError
from perturb.sync import SyncResult, newly_ready_unblocks, sync

ISSUE9_BODY = "\n".join(f"line {i}" for i in range(1, 46))  # 45 lines
ISSUE9_BODY_HEAD = "\n".join(f"line {i}" for i in range(1, 41))  # first 40 lines

ISSUE9_UPDATED = "2026-09-10T10:00:00Z"
ISSUE3_UPDATED = "2026-09-08T08:00:00Z"


def _make_page(has_next, end_cursor, nodes):
    return {
        "repository": {
            "issues": {
                "pageInfo": {"hasNextPage": has_next, "endCursor": end_cursor},
                "nodes": nodes,
            }
        }
    }


class FakeTransport:
    def __init__(self, pages):
        self._pages = list(pages)
        self._idx = 0
        self.calls = []

    def graphql(self, query, variables):
        self.calls.append(variables)
        page = self._pages[self._idx]
        self._idx += 1
        return page


PAGE1 = _make_page(
    has_next=True,
    end_cursor="C1",
    nodes=[
        {
            "number": 9,
            "title": "Issue 9",
            "state": "CLOSED",
            "updatedAt": ISSUE9_UPDATED,
            "labels": {"nodes": [{"name": "task"}, {"name": "ready-to-implement"}]},
            "parent": {"number": 8},
            "blockedBy": {"nodes": [{"number": 2, "state": "CLOSED"}]},
            "blocking": {"nodes": [{"number": 18, "state": "OPEN"}]},
            "body": ISSUE9_BODY,
        }
    ],
)

PAGE2 = _make_page(
    has_next=False,
    end_cursor=None,
    nodes=[
        {
            "number": 3,
            "title": "Issue 3",
            "state": "OPEN",
            "updatedAt": ISSUE3_UPDATED,
            "labels": {"nodes": []},
            "parent": None,
            "blockedBy": {"nodes": []},
            "blocking": {"nodes": []},
            "body": "",
        }
    ],
)

EXPECTED_CACHE = {
    "issues": {
        "9": {
            "blockedBy": [{"number": 2, "state": "CLOSED"}],
            "blocking": [{"number": 18, "state": "OPEN"}],
            "body_head": ISSUE9_BODY_HEAD,
            "labels": ["task", "ready-to-implement"],
            "number": 9,
            "parent": 8,
            "state": "CLOSED",
            "title": "Issue 9",
            "updatedAt": ISSUE9_UPDATED,
        },
        "3": {
            "blockedBy": [],
            "blocking": [],
            "body_head": "",
            "labels": [],
            "number": 3,
            "parent": None,
            "state": "OPEN",
            "title": "Issue 3",
            "updatedAt": ISSUE3_UPDATED,
        },
    }
}


ISSUE9_UPDATED_NEW = "2026-09-11T10:00:00Z"


def _write_cache(tmp_path, issues_dict):
    cache = {"issues": {str(k): v for k, v in issues_dict.items()}}
    (tmp_path / "github.json").write_text(json.dumps(cache, indent=1, sort_keys=True))


def _write_meta(tmp_path, cursor):
    meta = {"cursor": cursor, "perturb_version": __version__, "synced_at": "2026-01-01T00:00:00Z"}
    (tmp_path / "meta.json").write_text(json.dumps(meta))


def test_incremental_sync_stops_at_cursor_and_merges(tmp_path):
    existing_9 = {
        "blockedBy": [],
        "blocking": [],
        "body_head": "",
        "labels": [],
        "number": 9,
        "parent": None,
        "state": "OPEN",
        "title": "Old title 9",
        "updatedAt": ISSUE9_UPDATED,
    }
    existing_3 = {
        "blockedBy": [],
        "blocking": [],
        "body_head": "",
        "labels": [],
        "number": 3,
        "parent": None,
        "state": "OPEN",
        "title": "Issue 3",
        "updatedAt": ISSUE3_UPDATED,
    }
    _write_cache(tmp_path, {9: existing_9, 3: existing_3})
    _write_meta(tmp_path, ISSUE3_UPDATED)

    inc_page1 = _make_page(
        has_next=True,
        end_cursor="C2",
        nodes=[
            {
                "number": 9,
                "title": "New title 9",
                "state": "CLOSED",
                "updatedAt": ISSUE9_UPDATED_NEW,
                "labels": {"nodes": []},
                "parent": None,
                "blockedBy": {"nodes": []},
                "blocking": {"nodes": []},
                "body": "",
            },
            {
                "number": 3,
                "title": "Issue 3",
                "state": "OPEN",
                "updatedAt": ISSUE3_UPDATED,
                "labels": {"nodes": []},
                "parent": None,
                "blockedBy": {"nodes": []},
                "blocking": {"nodes": []},
                "body": "",
            },
        ],
    )
    inc_page2 = _make_page(has_next=False, end_cursor=None, nodes=[])

    transport = FakeTransport([inc_page1, inc_page2])
    result = sync(tmp_path, transport, owner="geuben", name="x", now=lambda: "2026-09-12T16:00:00Z")

    assert len(transport.calls) == 1
    cache = json.loads((tmp_path / "github.json").read_text())
    assert cache["issues"]["9"]["title"] == "New title 9"
    assert "3" in cache["issues"]
    assert result.fetched == 2


def test_failed_sync_leaves_cache_untouched(tmp_path):
    existing_9 = {
        "blockedBy": [],
        "blocking": [],
        "body_head": "",
        "labels": [],
        "number": 9,
        "parent": None,
        "state": "OPEN",
        "title": "Issue 9",
        "updatedAt": ISSUE9_UPDATED,
    }
    _write_cache(tmp_path, {9: existing_9})
    _write_meta(tmp_path, ISSUE9_UPDATED)
    orig_cache = (tmp_path / "github.json").read_bytes()
    orig_meta = (tmp_path / "meta.json").read_bytes()

    class FailTransport:
        calls = 0

        def graphql(self, query, variables):
            self.calls += 1
            if self.calls == 1:
                return PAGE1
            raise GitHubError("github_unreachable", "boom")

    transport = FailTransport()
    with pytest.raises(GitHubError):
        sync(
            tmp_path,
            transport,
            owner="geuben",
            name="x",
            full=True,
            now=lambda: "2026-09-12T16:00:00Z",
        )

    assert (tmp_path / "github.json").read_bytes() == orig_cache
    assert (tmp_path / "meta.json").read_bytes() == orig_meta


def test_full_sync_ignores_cursor(tmp_path):
    existing_9 = {
        "blockedBy": [],
        "blocking": [],
        "body_head": "",
        "labels": [],
        "number": 9,
        "parent": None,
        "state": "OPEN",
        "title": "Old title 9",
        "updatedAt": ISSUE9_UPDATED,
    }
    existing_3 = {
        "blockedBy": [],
        "blocking": [],
        "body_head": "",
        "labels": [],
        "number": 3,
        "parent": None,
        "state": "OPEN",
        "title": "Issue 3",
        "updatedAt": ISSUE3_UPDATED,
    }
    _write_cache(tmp_path, {9: existing_9, 3: existing_3})
    _write_meta(tmp_path, ISSUE3_UPDATED)

    inc_page1 = _make_page(
        has_next=True,
        end_cursor="C2",
        nodes=[
            {
                "number": 9,
                "title": "New title 9",
                "state": "CLOSED",
                "updatedAt": ISSUE9_UPDATED_NEW,
                "labels": {"nodes": []},
                "parent": None,
                "blockedBy": {"nodes": []},
                "blocking": {"nodes": []},
                "body": "",
            },
            {
                "number": 3,
                "title": "Issue 3",
                "state": "OPEN",
                "updatedAt": ISSUE3_UPDATED,
                "labels": {"nodes": []},
                "parent": None,
                "blockedBy": {"nodes": []},
                "blocking": {"nodes": []},
                "body": "",
            },
        ],
    )
    inc_page2 = _make_page(has_next=False, end_cursor=None, nodes=[])

    transport = FakeTransport([inc_page1, inc_page2])
    sync(
        tmp_path, transport, owner="geuben", name="x", full=True, now=lambda: "2026-09-12T16:00:00Z"
    )

    assert len(transport.calls) == 2


def test_sync_writes_meta_with_cursor_and_synced_at(tmp_path):
    transport = FakeTransport([PAGE1, PAGE2])
    result = sync(tmp_path, transport, owner="geuben", name="x", now=lambda: "2026-09-12T16:00:00Z")

    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta == {
        "cursor": ISSUE9_UPDATED,
        "synced_at": "2026-09-12T16:00:00Z",
        "perturb_version": __version__,
    }
    assert result == SyncResult(fetched=2, total=2, synced_at="2026-09-12T16:00:00Z")


def _issue(number, state, labels, blocked_by):
    return {
        "number": number,
        "state": state,
        "labels": labels,
        "blockedBy": [{"number": n, "state": s} for n, s in blocked_by],
        "blocking": [],
        "body_head": "",
        "parent": None,
        "title": f"Issue {number}",
        "updatedAt": "2026-09-10T00:00:00Z",
    }


def _blocked_node(number, state, blocked_by_pairs):
    return {
        "number": number,
        "title": f"Issue {number}",
        "state": state,
        "updatedAt": "2026-09-10T00:00:00Z",
        "labels": {"nodes": []},
        "parent": None,
        "blockedBy": {"nodes": [{"number": n, "state": s} for n, s in blocked_by_pairs]},
        "blocking": {"nodes": []},
        "body": "",
    }


def test_sync_emits_pending_unblock_event(tmp_path):
    events_dir = tmp_path / "events"
    prev_cache = {
        "issues": {
            "29": {
                "number": 29,
                "state": "OPEN",
                "labels": [],
                "blockedBy": [{"number": 10, "state": "OPEN"}],
                "blocking": [],
                "body_head": "",
                "parent": None,
                "title": "Issue 29",
                "updatedAt": "2026-09-10T00:00:00Z",
            },
            "10": {
                "number": 10,
                "state": "OPEN",
                "labels": [],
                "blockedBy": [],
                "blocking": [],
                "body_head": "",
                "parent": None,
                "title": "Issue 10",
                "updatedAt": "2026-09-10T00:00:00Z",
            },
        }
    }
    (tmp_path / "github.json").write_text(json.dumps(prev_cache))

    page = _make_page(
        has_next=False,
        end_cursor=None,
        nodes=[
            _blocked_node(10, "CLOSED", []),
            _blocked_node(29, "OPEN", [(10, "CLOSED")]),
        ],
    )
    transport = FakeTransport([page])
    counter = itertools.count(1)
    sync(
        tmp_path,
        transport,
        owner="geuben",
        name="x",
        full=True,
        now=lambda: "2026-09-12T00:00:00Z",
        events_dir=events_dir,
        new_id=lambda: f"event-{next(counter):04d}",
    )

    yaml_files = list(events_dir.glob("*.yaml"))
    assert len(yaml_files) == 1

    store = EventStore(events_dir)
    result = store.load()
    assert not result.errors
    assert len(result.events) == 1
    ev = result.events[0]
    assert ev.kind == "unblock"
    assert ev.target == "#29"
    assert ev.source == "#10"
    assert ev.proposed_by == "perturb sync"
    assert ev.reason == "blocks"
    assert ev.status == "pending"
    assert ev.summary == "#10 closed; this issue is now ready"


def test_sync_unblock_is_idempotent_across_syncs(tmp_path):
    events_dir = tmp_path / "events"
    prev_cache = {
        "issues": {
            "29": {
                "number": 29,
                "state": "OPEN",
                "labels": [],
                "blockedBy": [{"number": 10, "state": "OPEN"}],
                "blocking": [],
                "body_head": "",
                "parent": None,
                "title": "Issue 29",
                "updatedAt": "2026-09-10T00:00:00Z",
            },
            "10": {
                "number": 10,
                "state": "OPEN",
                "labels": [],
                "blockedBy": [],
                "blocking": [],
                "body_head": "",
                "parent": None,
                "title": "Issue 10",
                "updatedAt": "2026-09-10T00:00:00Z",
            },
        }
    }
    (tmp_path / "github.json").write_text(json.dumps(prev_cache))

    page = _make_page(
        has_next=False,
        end_cursor=None,
        nodes=[
            _blocked_node(10, "CLOSED", []),
            _blocked_node(29, "OPEN", [(10, "CLOSED")]),
        ],
    )
    counter = itertools.count(1)

    # First sync — emits the event
    sync(
        tmp_path,
        FakeTransport([page]),
        owner="geuben",
        name="x",
        full=True,
        now=lambda: "2026-09-12T00:00:00Z",
        events_dir=events_dir,
        new_id=lambda: f"event-{next(counter):04d}",
    )
    assert len(list(events_dir.glob("*.yaml"))) == 1

    # Second sync (same page) — prev now shows #29 as ready; no new event
    sync(
        tmp_path,
        FakeTransport([page]),
        owner="geuben",
        name="x",
        full=True,
        now=lambda: "2026-09-12T00:01:00Z",
        events_dir=events_dir,
        new_id=lambda: f"event-{next(counter):04d}",
    )
    assert len(list(events_dir.glob("*.yaml"))) == 1


def test_sync_first_sync_emits_no_unblock(tmp_path):
    events_dir = tmp_path / "events"
    # No github.json — empty previous cache (first sync)
    page = _make_page(
        has_next=False,
        end_cursor=None,
        nodes=[_blocked_node(29, "OPEN", [(10, "CLOSED")])],
    )
    transport = FakeTransport([page])
    sync(
        tmp_path,
        transport,
        owner="geuben",
        name="x",
        full=True,
        now=lambda: "2026-09-12T00:00:00Z",
        events_dir=events_dir,
    )
    assert not events_dir.exists()


def test_newly_ready_unblocks_ignores_non_transitions():
    # (a) still blocked: one blocker remains OPEN in new
    prev_still = {"5": _issue(5, "OPEN", [], [(10, "OPEN"), (11, "OPEN")])}
    new_still = {"5": _issue(5, "OPEN", [], [(10, "CLOSED"), (11, "OPEN")])}

    # (b) already ready in prev: no OPEN blocker in prev
    prev_ready = {"5": _issue(5, "OPEN", [], [(10, "CLOSED")])}
    new_ready = {"5": _issue(5, "OPEN", [], [(10, "CLOSED")])}

    # (c) absent from prev: new issue not in previous cache
    prev_absent = {}
    new_absent = {"5": _issue(5, "OPEN", [], [(10, "CLOSED")])}

    # (d) epic-labelled issue whose blocker closed
    prev_epic = {"5": _issue(5, "OPEN", ["epic"], [(10, "OPEN")])}
    new_epic = {"5": _issue(5, "OPEN", ["epic"], [(10, "CLOSED")])}

    assert newly_ready_unblocks(prev_still, new_still) == []
    assert newly_ready_unblocks(prev_ready, new_ready) == []
    assert newly_ready_unblocks(prev_absent, new_absent) == []
    assert newly_ready_unblocks(prev_epic, new_epic) == []


def test_newly_ready_unblocks_emits_entry_for_transition():
    prev = {
        "29": _issue(29, "OPEN", [], [(10, "OPEN"), (11, "OPEN")]),
    }
    new = {
        "29": _issue(29, "OPEN", [], [(10, "CLOSED"), (11, "CLOSED")]),
    }
    assert newly_ready_unblocks(prev, new) == [
        {
            "target": "#29",
            "source": "#10",
            "summary": "#10 closed; this issue is now ready",
        }
    ]


def test_newly_ready_unblocks_source_is_lowest_newly_closed_not_pre_existing():
    # #7 was already CLOSED in prev — only #10 was OPEN in prev and is now CLOSED.
    # Source must be #10, not #7 (which was pre-existing).
    prev = {"5": _issue(5, "OPEN", [], [(7, "CLOSED"), (10, "OPEN")])}
    new = {"5": _issue(5, "OPEN", [], [(7, "CLOSED"), (10, "CLOSED")])}
    assert newly_ready_unblocks(prev, new) == [
        {"target": "#5", "source": "#10", "summary": "#10 closed; this issue is now ready"}
    ]


def test_newly_ready_unblocks_skips_if_either_state_has_epic_label():
    # prev has epic, new does not (label removed between syncs) — still skipped
    prev_prev_epic = {"5": _issue(5, "OPEN", ["epic"], [(10, "OPEN")])}
    new_no_epic = {"5": _issue(5, "OPEN", [], [(10, "CLOSED")])}
    assert newly_ready_unblocks(prev_prev_epic, new_no_epic) == []

    # prev does not have epic, new does (label added between syncs) — still skipped
    prev_no_epic = {"5": _issue(5, "OPEN", [], [(10, "OPEN")])}
    new_new_epic = {"5": _issue(5, "OPEN", ["epic"], [(10, "CLOSED")])}
    assert newly_ready_unblocks(prev_no_epic, new_new_epic) == []


def test_first_sync_writes_reduced_cache_from_all_pages(tmp_path):
    transport = FakeTransport([PAGE1, PAGE2])
    sync(tmp_path, transport, owner="geuben", name="x", now=lambda: "2026-09-12T16:00:00Z")

    cache = json.loads((tmp_path / "github.json").read_text())
    assert cache == EXPECTED_CACHE

    assert len(transport.calls) == 2
    assert transport.calls[0]["after"] is None
    assert transport.calls[1]["after"] == "C1"


def test_newly_ready_unblocks_honours_a_configured_epic_label():
    prev = {"5": _issue(5, "OPEN", ["initiative"], [(10, "OPEN")])}
    new = {"5": _issue(5, "OPEN", ["initiative"], [(10, "CLOSED")])}
    assert newly_ready_unblocks(prev, new, epic_label="initiative") == []
    assert len(newly_ready_unblocks(prev, new)) == 1
