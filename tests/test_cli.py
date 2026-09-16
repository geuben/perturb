import argparse
import json

from perturb import __version__
from perturb.cli import main


def test_version_flag_prints_package_version(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_ref_verb_emits_json_envelope(capsys):
    code = main(["ref", "29", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    envelope = json.loads(captured.out)
    assert envelope["ok"] is True
    assert envelope["verb"] == "ref"
    assert envelope["data"] == {"ref": "#29", "kind": "issue", "id": "29"}


def test_ref_verb_renders_text_by_default(capsys):
    code = main(["ref", "adr:2"])
    assert code == 0
    assert capsys.readouterr().out == "ref: adr:0002\nkind: adr\nid: 0002\n"


def test_unknown_verb_returns_usage_exit_code(capsys):
    code = main(["nope"])
    assert code == 2
    assert "ref" in capsys.readouterr().err


def test_bad_ref_returns_usage_exit_code_with_accepted_forms(capsys):
    code = main(["ref", "bogus"])
    assert code == 2
    assert "tasks/<slug>.md" in capsys.readouterr().err


def _make_runner_result(returncode, stdout, stderr=""):
    class R:
        pass

    r = R()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def _make_cli_transport(pages):
    class CliTransport:
        def __init__(self):
            self._pages = list(pages)
            self._idx = 0

        def runner(self, argv, capture_output=True, text=True):
            if argv == ["git", "rev-parse", "--show-toplevel"]:
                return _make_runner_result(0, "/repo\n")
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            page = self._pages[self._idx]
            self._idx += 1
            return page

    return CliTransport()


def _make_page(nodes, has_next=False):
    return {
        "repository": {
            "issues": {
                "pageInfo": {"hasNextPage": has_next, "endCursor": None},
                "nodes": nodes,
            }
        }
    }


CLI_ISSUE = {
    "number": 1,
    "title": "CLI Issue",
    "state": "OPEN",
    "updatedAt": "2026-09-01T00:00:00Z",
    "labels": {"nodes": []},
    "parent": None,
    "blockedBy": {"nodes": []},
    "blocking": {"nodes": []},
    "body": "",
}


def test_sync_verb_reports_counts_with_injected_transport(tmp_path, capsys):
    transport = _make_cli_transport([_make_page([CLI_ISSUE])])
    code = main(["sync", "--json"], transport=transport, root=tmp_path)
    assert code == 0
    captured = capsys.readouterr()
    envelope = json.loads(captured.out)
    assert envelope["ok"] is True
    assert envelope["verb"] == "sync"
    data = envelope["data"]
    assert data["fetched"] == 1
    assert data["issues"] == 1
    assert "synced_at" in data
    assert envelope["synced_at"] == data["synced_at"]


def test_sync_verb_refuses_when_github_unreachable(tmp_path, capsys):
    from perturb.github import GitHubError

    class FailTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            return _make_runner_result(0, "https://github.com/geuben/x\n")

        def graphql(self, query, variables):
            raise GitHubError("github_unreachable", "connect: network is unreachable")

    code = main(["sync", "--json"], transport=FailTransport(), root=tmp_path)
    assert code == 1
    captured = capsys.readouterr()
    envelope = json.loads(captured.out)
    assert envelope == {
        "ok": False,
        "verb": "sync",
        "reason": "github_unreachable",
        "detail": "connect: network is unreachable",
    }
    assert not (tmp_path / "github.json").exists()


def test_sync_verb_refuses_no_github_remote(tmp_path, capsys):
    class TopLevelFailTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv == ["git", "rev-parse", "--show-toplevel"]:
                return _make_runner_result(1, "", "fatal: not a git repository")
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(1, "", "fatal: no such remote 'origin'")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            raise AssertionError("should not reach graphql")

    class ConfigFailTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(1, "", "fatal: no such remote 'origin'")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            raise AssertionError("should not reach graphql")

    class NonGitHubTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://gitlab.com/foo/bar\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            raise AssertionError("should not reach graphql")

    cases = [
        (TopLevelFailTransport(), None, "fatal: not a git repository"),
        (ConfigFailTransport(), tmp_path, "fatal: no such remote 'origin'"),
        (
            NonGitHubTransport(),
            tmp_path,
            "not a recognised GitHub remote: https://gitlab.com/foo/bar",
        ),
    ]

    for i, (transport, repo_root, expected_detail) in enumerate(cases):
        code = main(["sync", "--json"], transport=transport, root=tmp_path, repo_root=repo_root)
        assert code == 1, f"case {i + 1}: expected exit 1"
        captured = capsys.readouterr()
        envelope = json.loads(captured.out)
        assert envelope == {
            "ok": False,
            "verb": "sync",
            "reason": "no_github_remote",
            "detail": expected_detail,
        }, f"case {i + 1}: wrong envelope"

    assert not (tmp_path / "github.json").exists()


def test_sync_full_flag_repages_past_cursor(tmp_path, capsys):
    from perturb import __version__

    cursor = "2026-09-11T00:00:00Z"
    meta = {"cursor": cursor, "perturb_version": __version__, "synced_at": "2026-01-01T00:00:00Z"}
    (tmp_path / "meta.json").write_text(json.dumps(meta))
    (tmp_path / "github.json").write_text('{"issues": {}}')

    node_a = {
        "number": 1,
        "title": "A",
        "state": "OPEN",
        "updatedAt": "2026-09-10T00:00:00Z",
        "labels": {"nodes": []},
        "parent": None,
        "blockedBy": {"nodes": []},
        "blocking": {"nodes": []},
        "body": "",
    }
    node_b = {
        "number": 2,
        "title": "B",
        "state": "OPEN",
        "updatedAt": "2026-09-09T00:00:00Z",
        "labels": {"nodes": []},
        "parent": None,
        "blockedBy": {"nodes": []},
        "blocking": {"nodes": []},
        "body": "",
    }
    page1 = _make_page([node_a], has_next=True)
    page2 = _make_page([node_b])

    class CountTransport:
        def __init__(self):
            self._pages = [page1, page2, page1, page2]
            self._idx = 0
            self.calls = 0

        def runner(self, argv, capture_output=True, text=True):
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            return _make_runner_result(0, "https://github.com/geuben/x\n")

        def graphql(self, query, variables):
            self.calls += 1
            page = self._pages[self._idx % len(self._pages)]
            self._idx += 1
            return page

    transport = CountTransport()
    main(["sync", "--json"], transport=transport, root=tmp_path)
    calls_without_full = transport.calls

    transport2 = CountTransport()
    main(["sync", "--full", "--json"], transport=transport2, root=tmp_path)
    calls_with_full = transport2.calls

    assert calls_without_full == 1
    assert calls_with_full == 2


def test_sync_verb_emits_unblock_event(tmp_path, capsys):
    repo = tmp_path / "repo"
    perturb_root = repo / ".perturb"
    perturb_root.mkdir(parents=True)

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
    (perturb_root / "github.json").write_text(json.dumps(prev_cache))

    issue_10_closed = {
        "number": 10,
        "title": "Issue 10",
        "state": "CLOSED",
        "updatedAt": "2026-09-12T00:00:00Z",
        "labels": {"nodes": []},
        "parent": None,
        "blockedBy": {"nodes": []},
        "blocking": {"nodes": []},
        "body": "",
    }
    issue_29_ready = {
        "number": 29,
        "title": "Issue 29",
        "state": "OPEN",
        "updatedAt": "2026-09-12T00:00:00Z",
        "labels": {"nodes": []},
        "parent": None,
        "blockedBy": {"nodes": [{"number": 10, "state": "CLOSED"}]},
        "blocking": {"nodes": []},
        "body": "",
    }
    transport = _make_cli_transport([_make_page([issue_10_closed, issue_29_ready])])

    code = main(["sync", "--json"], transport=transport, root=perturb_root, repo_root=repo)
    assert code == 0

    events_dir = repo / "perturb" / "events"
    yaml_files = list(events_dir.glob("*.yaml")) if events_dir.exists() else []
    assert len(yaml_files) == 1


def test_sync_verb_derives_graph_and_reports_ready_count(tmp_path, capsys):
    repo = tmp_path / "repo"
    tasks = repo / "tasks"
    tasks.mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    (tasks / "plan.md").write_text("---\ncloses: 1\n---\n# plan")

    issue_1 = {**CLI_ISSUE, "labels": {"nodes": [{"name": "ready-to-implement"}]}}
    transport = _make_cli_transport([_make_page([issue_1])])

    code = main(
        ["sync", "--json"],
        transport=transport,
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 0
    captured = capsys.readouterr()
    envelope = json.loads(captured.out)
    assert envelope["data"]["ready"] == 1

    graph_path = perturb_root / "graph.json"
    assert graph_path.exists()
    graph = json.loads(graph_path.read_text())
    assert graph["head"] == "abc123"
    assert graph["issues"]["1"]["planned"] is True


def test_json_flag_before_verb_is_honoured(capsys):
    code = main(["--json", "ref", "29"])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["data"]["ref"] == "#29"


def test_inbox_verb_emits_pending_events_as_json(tmp_path, capsys):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)

    ids29 = iter(["ID1"])
    times29 = iter(["2026-09-01T10:00:00Z"])
    store29 = EventStore(events_dir, now=lambda: next(times29), new_id=lambda: next(ids29))
    e1 = store29.create(
        source="#4",
        target="#29",
        kind="decision",
        summary="s1",
        proposed_by="x",
        reason="r",
        status="pending",
    )

    ids30 = iter(["ID2"])
    times30 = iter(["2026-09-01T11:00:00Z"])
    store30 = EventStore(events_dir, now=lambda: next(times30), new_id=lambda: next(ids30))
    store30.create(
        source="#4",
        target="#30",
        kind="decision",
        summary="s2",
        proposed_by="x",
        reason="r",
        status="pending",
    )

    code = main(["inbox", "29", "--json"], repo_root=repo)
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["data"]["target"] == "#29"
    assert len(data["data"]["pending"]) == 1
    assert data["data"]["pending"][0]["id"] == e1.id
    assert data["data"]["proposed"] == []
    assert "warnings" not in data["data"]
    assert data["synced_at"] is None


def test_inbox_include_proposed_flag_crosses_boundary(tmp_path, capsys):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)

    ids = iter(["ID1"])
    times = iter(["2026-09-01T10:00:00Z"])
    store = EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids))
    e_prop = store.create(
        source="#4",
        target="#29",
        kind="decision",
        summary="p1",
        proposed_by="x",
        reason="r",
        status="proposed",
    )

    code = main(["inbox", "29", "--json"], repo_root=repo)
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["data"]["proposed"] == []

    code = main(["inbox", "29", "--include", "proposed", "--json"], repo_root=repo)
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data["data"]["proposed"]) == 1
    assert data["data"]["proposed"][0]["id"] == e_prop.id


def test_inbox_verb_renders_text_layout_by_default(tmp_path, capsys):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)

    ids = iter(["ID1"])
    times = iter(["2026-09-01T10:00:00Z"])
    store = EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids))
    store.create(
        source="#4",
        target="#29",
        kind="decision",
        summary="s1",
        proposed_by="x",
        reason="r",
        detail="docs/missing.md",
        status="pending",
    )

    code = main(["inbox", "29"], repo_root=repo)
    assert code == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("Inbox for #29  (1 pending, 0 proposed)\n")
    assert captured.err == "warning: detail not found: docs/missing.md\n"


def _make_issue_node(
    number, *, title="T", state="OPEN", labels=None, parent=None, blocked_by=None, blocking=None
):
    return {
        "number": number,
        "title": title or f"Issue {number}",
        "state": state,
        "updatedAt": "2026-09-01T00:00:00Z",
        "labels": {"nodes": [{"name": n} for n in (labels or [])]},
        "parent": {"number": parent} if parent else None,
        "blockedBy": {"nodes": [{"number": n, "state": "OPEN"} for n in (blocked_by or [])]},
        "blocking": {"nodes": [{"number": n, "state": "OPEN"} for n in (blocking or [])]},
        "body": "",
    }


def test_next_verb_refuses_when_github_unreachable(tmp_path, capsys):
    from perturb.github import GitHubError

    class FailTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            return _make_runner_result(0, "https://github.com/geuben/x\n")

        def graphql(self, query, variables):
            raise GitHubError("github_unreachable", "connect: network is unreachable")

    code = main(["next", "--json"], transport=FailTransport(), root=tmp_path)
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope == {
        "ok": False,
        "verb": "next",
        "reason": "github_unreachable",
        "detail": "connect: network is unreachable",
    }


def test_ready_verb_all_flag_crosses_boundary(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "tasks").mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    node_ready = _make_issue_node(1, title="Ready", blocking=[2])
    node_blocked = _make_issue_node(2, title="Blocked", blocked_by=[1])
    transport = _make_cli_transport([_make_page([node_ready, node_blocked])])

    code = main(
        ["ready", "--all", "--json"],
        transport=transport,
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 0
    data = json.loads(capsys.readouterr().out)["data"]
    assert data["blocked"]
    assert data["blocked"][0]["open_blocked_by"]


def test_ready_verb_emits_ready_group_as_json(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "tasks").mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    (repo / "tasks" / "plan.md").write_text("---\ncloses: 2\n---\n# plan")
    node_1 = _make_issue_node(1, title="Unplanned")
    node_2 = _make_issue_node(2, title="Planned", labels=["ready-to-implement"])
    transport = _make_cli_transport([_make_page([node_1, node_2])])

    code = main(["ready", "--json"], transport=transport, root=perturb_root, repo_root=repo)
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["verb"] == "ready"
    assert "synced_at" in envelope
    data = envelope["data"]
    ready_nums = [r["number"] for r in data["ready"]]
    assert set(ready_nums) == {1, 2}
    assert data["blocked"] == []


def test_next_verb_limit_flag_crosses_boundary(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "tasks").mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    nodes = [_make_issue_node(n, title=f"T{n}") for n in range(1, 4)]
    transport = _make_cli_transport([_make_page(nodes)])

    code = main(
        ["next", "--limit", "1", "--json"],
        transport=transport,
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert len(envelope["data"]["issues"]) == 1


def test_next_verb_renders_table_by_default(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "tasks").mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    node_a = _make_issue_node(10, title="Alpha", blocking=[20])
    node_b = _make_issue_node(20, title="Beta", blocked_by=[10])
    transport = _make_cli_transport([_make_page([node_a, node_b])])

    code = main(["next"], transport=transport, root=perturb_root, repo_root=repo)
    assert code == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0] == "#  issue  title  unblocks  epic"
    assert "#10" in lines[1]
    assert "Alpha" in lines[1]


def test_next_verb_emits_ordered_issues_as_json(tmp_path, capsys):
    repo = tmp_path / "repo"
    tasks = repo / "tasks"
    tasks.mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    node_a = _make_issue_node(10, title="Alpha", blocking=[20])
    node_b = _make_issue_node(20, title="Beta", blocked_by=[10])
    transport = _make_cli_transport([_make_page([node_a, node_b])])

    code = main(["next", "--json"], transport=transport, root=perturb_root, repo_root=repo)
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["verb"] == "next"
    assert "synced_at" in envelope
    issues = envelope["data"]["issues"]
    assert [r["number"] for r in issues] == [10]


# epic #3: #29,#30 ready; #31 blocked by #29; #32 by #30; #33 by #31
EPIC_3_NODES = [
    _make_issue_node(3, title="Example epic", labels=["epic"]),
    _make_issue_node(29, title="Backfill daily rides", parent=3, blocking=[31]),
    _make_issue_node(30, title="Backfill monthly memberships", parent=3, blocking=[32]),
    _make_issue_node(31, title="Compute daily deltas", parent=3, blocked_by=[29], blocking=[33]),
    _make_issue_node(32, title="Monthly report", parent=3, blocked_by=[30]),
    _make_issue_node(33, title="Aggregate annual", parent=3, blocked_by=[31]),
]


def test_ready_epic_3_all_shows_blocked_with_open_blockers(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "tasks").mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    transport = _make_cli_transport([_make_page(EPIC_3_NODES)])
    code = main(
        ["ready", "--epic", "3", "--all", "--json"],
        transport=transport,
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 0
    data = json.loads(capsys.readouterr().out)["data"]
    blocked_nums = [b["number"] for b in data["blocked"]]
    assert blocked_nums == [31, 32, 33]
    by_num = {b["number"]: b["open_blocked_by"] for b in data["blocked"]}
    assert by_num[31] == [29]
    assert by_num[32] == [30]
    assert by_num[33] == [31]


def test_next_epic_3_prints_29_then_30_over_epic_3_fixture(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "tasks").mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    transport = _make_cli_transport([_make_page(EPIC_3_NODES)])
    code = main(["next", "--epic", "3"], transport=transport, root=perturb_root, repo_root=repo)
    assert code == 0
    out = capsys.readouterr().out
    assert "#29" in out
    assert "#30" in out
    assert out.index("#29") < out.index("#30")


def test_inbox_bad_ref_is_usage_error(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "perturb" / "events").mkdir(parents=True)

    code = main(["inbox", "bogus"], repo_root=repo)
    assert code == 2
    assert "tasks/<slug>.md" in capsys.readouterr().err


def test_show_issue_verb_emits_node_view_as_json(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "tasks").mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    node = _make_issue_node(29, title="Backfill daily rides", parent=3)
    transport = _make_cli_transport([_make_page([node])])

    code = main(["show", "29", "--json"], transport=transport, root=perturb_root, repo_root=repo)
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["verb"] == "show"
    assert envelope["synced_at"] is not None
    assert envelope["data"]["kind"] == "issue"
    assert envelope["data"]["number"] == 29


def test_show_issue_verb_renders_text_by_default(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "tasks").mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    node = _make_issue_node(29, title="Backfill daily rides", parent=3)
    transport = _make_cli_transport([_make_page([node])])

    code = main(["show", "29"], transport=transport, root=perturb_root, repo_root=repo)
    assert code == 0
    out = capsys.readouterr().out
    assert out.startswith("#29  Backfill daily rides")


def test_show_issue_refuses_when_github_unreachable(tmp_path, capsys):
    from perturb.github import GitHubError

    class FailTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            return _make_runner_result(0, "https://github.com/geuben/x\n")

        def graphql(self, query, variables):
            raise GitHubError("github_unreachable", "connect: network is unreachable")

    code = main(["show", "29", "--json"], transport=FailTransport(), root=tmp_path)
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope == {
        "ok": False,
        "verb": "show",
        "reason": "github_unreachable",
        "detail": "connect: network is unreachable",
    }


def test_show_refusal_surfaces_as_envelope_through_main(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "tasks").mkdir(parents=True)

    code = main(["show", "plan:missing", "--json"], repo_root=repo)
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is False
    assert envelope["verb"] == "show"
    assert envelope["reason"] == "plan_not_found"


def test_show_bad_ref_is_usage_error(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "tasks").mkdir(parents=True)

    code = main(["show", "bogus"], repo_root=repo)
    assert code == 2
    assert "tasks/<slug>.md" in capsys.readouterr().err


def test_show_plan_verb_is_local_and_emits_plan_view(tmp_path, capsys):
    repo = tmp_path / "repo"
    tasks = repo / "tasks"
    tasks.mkdir(parents=True)
    plan_text = "---\ncloses: 6\nfiles: [src/x.py]\n---\n# body\n"
    (tasks / "show-verb.md").write_text(plan_text)

    code = main(["show", "plan:show-verb", "--json"], repo_root=repo)
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["data"]["kind"] == "plan"
    assert envelope["data"]["issue"] == 6
    assert envelope["data"]["files"] == ["src/x.py"]
    assert "cycles" not in envelope["data"]
    assert envelope["synced_at"] is None


def test_graph_verb_emits_mermaid_json_by_default(tmp_path, capsys):
    repo = tmp_path / "repo"
    tasks = repo / "tasks"
    tasks.mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    node = _make_issue_node(1, title="An issue")
    transport = _make_cli_transport([_make_page([node])])

    code = main(["graph", "--json"], transport=transport, root=perturb_root, repo_root=repo)
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["verb"] == "graph"
    assert envelope["data"]["format"] == "mermaid"
    assert envelope["data"]["text"].startswith("graph TD\n")


def test_graph_verb_renders_text_by_default(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "tasks").mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    node = _make_issue_node(1, title="An issue")
    transport = _make_cli_transport([_make_page([node])])

    code = main(["graph"], transport=transport, root=perturb_root, repo_root=repo)
    assert code == 0
    out = capsys.readouterr().out
    assert out.startswith("graph TD\n")
    assert "ok" not in out


def test_graph_verb_format_dot_emits_dot(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "tasks").mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    node = _make_issue_node(1, title="An issue")
    transport = _make_cli_transport([_make_page([node])])

    code = main(
        ["graph", "--format", "dot", "--json"],
        transport=transport,
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["data"]["format"] == "dot"
    assert envelope["data"]["text"].startswith("digraph perturb {\n")


def test_graph_verb_epic_flag_crosses_boundary(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "tasks").mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    epic = _make_issue_node(1, title="Epic", labels=["epic"])
    child = _make_issue_node(2, title="Child", parent=1)
    other = _make_issue_node(99, title="Unrelated")
    transport = _make_cli_transport([_make_page([epic, child, other])])

    code = main(
        ["graph", "--epic", "1", "--json"],
        transport=transport,
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    text = envelope["data"]["text"]
    assert "N99" not in text
    assert "N1" in text
    assert "N2" in text


def _make_push_transport(pages, *, git_user="geuben"):
    class PushTransport:
        def __init__(self):
            self._pages = list(pages)
            self._idx = 0

        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            if argv == ["git", "config", "user.name"]:
                return _make_runner_result(0, f"{git_user}\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            page = self._pages[self._idx]
            self._idx += 1
            return page

    return PushTransport()


def test_push_verb_creates_pending_event_as_json(tmp_path, capsys):
    issue_29 = _make_issue_node(29)
    transport = _make_push_transport([_make_page([issue_29])])
    root = tmp_path / ".perturb"
    repo_root = tmp_path

    code = main(
        ["push", "--from", "5", "--to", "29", "--kind", "decision", "s", "--json"],
        transport=transport,
        root=root,
        repo_root=repo_root,
    )
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["verb"] == "push"
    assert envelope["synced_at"] is not None
    assert len(envelope["data"]["created"]) == 1

    events_dir = repo_root / "perturb" / "events"
    from perturb.events import EventStore

    events = EventStore(events_dir).load().events
    assert len(events) == 1
    event = events[0]
    assert event.proposed_by == "geuben"
    assert event.reason == "manual"
    assert event.status == "pending"


def test_push_verb_by_flag_overrides_actor(tmp_path, capsys):
    issue_29 = _make_issue_node(29)
    transport = _make_push_transport([_make_page([issue_29])])
    root = tmp_path / ".perturb"
    repo_root = tmp_path

    code = main(
        [
            "push",
            "--from",
            "5",
            "--to",
            "29",
            "--kind",
            "decision",
            "s",
            "--by",
            "adr-bot",
            "--json",
        ],
        transport=transport,
        root=root,
        repo_root=repo_root,
    )
    assert code == 0
    events_dir = repo_root / "perturb" / "events"
    from perturb.events import EventStore

    events = EventStore(events_dir).load().events
    assert events[0].proposed_by == "adr-bot"


def test_push_verb_detail_stored_and_unresolvable_refuses(tmp_path, capsys):
    issue_29 = _make_issue_node(29)
    root = tmp_path / ".perturb"
    repo_root = tmp_path
    docs = repo_root / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# Heading\ncontent")

    transport = _make_push_transport([_make_page([issue_29])])
    code = main(
        [
            "push",
            "--from",
            "5",
            "--to",
            "29",
            "--kind",
            "decision",
            "s",
            "--detail",
            "docs/a.md",
            "--json",
        ],
        transport=transport,
        root=root,
        repo_root=repo_root,
    )
    assert code == 0
    from perturb.events import EventStore

    events = EventStore(repo_root / "perturb" / "events").load().events
    assert events[0].detail == "docs/a.md"

    transport2 = _make_push_transport([_make_page([issue_29])])
    capsys.readouterr()
    code2 = main(
        [
            "push",
            "--from",
            "5",
            "--to",
            "29",
            "--kind",
            "decision",
            "s",
            "--detail",
            "docs/missing.md",
            "--json",
        ],
        transport=transport2,
        root=root,
        repo_root=repo_root,
    )
    assert code2 == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["reason"] == "detail_unresolved"


def test_push_verb_epic_target_refuses_with_children(tmp_path, capsys):
    epic = _make_issue_node(3, labels=["epic"])
    child_29 = _make_issue_node(29, parent=3)
    child_31 = _make_issue_node(31, parent=3)
    transport = _make_push_transport([_make_page([epic, child_29, child_31])])
    root = tmp_path / ".perturb"
    repo_root = tmp_path

    code = main(
        ["push", "--from", "5", "--to", "3", "--kind", "decision", "s", "--json"],
        transport=transport,
        root=root,
        repo_root=repo_root,
    )
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["reason"] == "epic_target"
    assert "#29" in envelope["detail"]
    assert "#31" in envelope["detail"]

    events_dir = repo_root / "perturb" / "events"
    assert not events_dir.exists() or len(list(events_dir.glob("*.yaml"))) == 0


def test_push_verb_new_creates_issue_and_targets_it(tmp_path, capsys):
    issue_page = _make_page([_make_issue_node(29)])

    class PushNewTransport:
        def __init__(self):
            self._pages = [issue_page]
            self._idx = 0
            self.create_issue_calls = []

        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            if argv == ["git", "config", "user.name"]:
                return _make_runner_result(0, "geuben\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            page = self._pages[self._idx]
            self._idx += 1
            return page

        def create_issue(self, *, owner, name, title, body):
            self.create_issue_calls.append(
                {"owner": owner, "name": name, "title": title, "body": body}
            )
            return 77

    transport = PushNewTransport()
    root = tmp_path / ".perturb"
    repo_root = tmp_path

    code = main(
        ["push", "--from", "5", "--new", "New sibling", "--kind", "scope", "s", "--json"],
        transport=transport,
        root=root,
        repo_root=repo_root,
    )
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["verb"] == "push"
    assert len(transport.create_issue_calls) == 1
    call = transport.create_issue_calls[0]
    assert call["title"] == "New sibling"
    assert call["body"] == "s"
    assert call["owner"] == "geuben"

    from perturb.events import EventStore

    events = EventStore(repo_root / "perturb" / "events").load().events
    assert len(events) == 1
    assert events[0].target == "#77"


def test_push_verb_to_and_new_are_mutually_exclusive(capsys):
    code = main(["push", "--from", "5", "--to", "29", "--new", "t", "--kind", "decision", "s"])
    assert code == 2


def test_push_verb_refuses_when_github_unreachable(tmp_path, capsys):
    from perturb.github import GitHubError

    class FailTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            return _make_runner_result(0, "https://github.com/geuben/x\n")

        def graphql(self, query, variables):
            raise GitHubError("github_unreachable", "connect: network is unreachable")

    code = main(
        ["push", "--from", "5", "--to", "29", "--kind", "decision", "s", "--json"],
        transport=FailTransport(),
        root=tmp_path,
    )
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope == {
        "ok": False,
        "verb": "push",
        "reason": "github_unreachable",
        "detail": "connect: network is unreachable",
    }


def test_graph_verb_refuses_when_github_unreachable(tmp_path, capsys):
    from perturb.github import GitHubError

    class FailTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            return _make_runner_result(0, "https://github.com/geuben/x\n")

        def graphql(self, query, variables):
            raise GitHubError("github_unreachable", "connect: network is unreachable")

    code = main(["graph", "--json"], transport=FailTransport(), root=tmp_path)
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope == {
        "ok": False,
        "verb": "graph",
        "reason": "github_unreachable",
        "detail": "connect: network is unreachable",
    }


def _make_ack_transport(
    *, blob_sha="abc123blob", git_user="geuben", status_output="", rev_parse_rc=0
):
    class AckTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv[:2] == ["git", "status"]:
                return _make_runner_result(0, status_output)
            if argv[:2] == ["git", "rev-parse"] and len(argv) > 2 and argv[2].startswith("HEAD:"):
                return _make_runner_result(rev_parse_rc, blob_sha + "\n")
            if argv == ["git", "config", "user.name"]:
                return _make_runner_result(0, f"{git_user}\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            raise AssertionError("ack should not call graphql")

    return AckTransport()


def test_ack_verb_acknowledges_named_id_as_json(tmp_path, capsys):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)
    (repo / "tasks").mkdir()
    (repo / "tasks" / "p.md").write_text("---\ncloses: 42\n---\n")

    ids = iter(["EV1"])
    times = iter(["2026-09-12T00:00:00Z"])
    store = EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids))
    store.create(
        source="#5",
        target="#42",
        kind="decision",
        summary="s",
        detail="docs/x.md",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )

    transport = _make_ack_transport(blob_sha="deadbeef1234")
    code = main(
        ["ack", "42", "EV1", "--plan", "tasks/p.md", "--note", "n", "--json"],
        transport=transport,
        repo_root=repo,
    )
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["verb"] == "ack"
    assert envelope["synced_at"] is None
    assert len(envelope["data"]["acked"]) == 1

    events = EventStore(events_dir).load().events
    event = next(e for e in events if e.id == "EV1")
    assert event.ack["by"] == "geuben"
    assert event.ack["plan"] == "tasks/p.md"
    assert event.ack["plan_blob"] == "deadbeef1234"


def test_ack_verb_refuses_uncommitted_plan(tmp_path, capsys):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)
    (repo / "tasks").mkdir()
    (repo / "tasks" / "p.md").write_text("---\ncloses: 42\n---\n")

    ids = iter(["EV1"])
    times = iter(["2026-09-12T00:00:00Z"])
    EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids)).create(
        source="#5",
        target="#42",
        kind="decision",
        summary="s",
        detail="docs/x.md",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )

    # dirty plan
    transport_dirty = _make_ack_transport(status_output=" M tasks/p.md\n")
    code = main(
        ["ack", "42", "EV1", "--plan", "tasks/p.md", "--note", "n", "--json"],
        transport=transport_dirty,
        repo_root=repo,
    )
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["reason"] == "plan_not_committed"
    assert EventStore(events_dir).load().events[0].status == "pending"

    # never committed
    transport_untracked = _make_ack_transport(rev_parse_rc=128)
    code = main(
        ["ack", "42", "EV1", "--plan", "tasks/p.md", "--note", "n", "--json"],
        transport=transport_untracked,
        repo_root=repo,
    )
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["reason"] == "plan_not_committed"
    assert EventStore(events_dir).load().events[0].status == "pending"


def test_ack_verb_refuses_plan_target_mismatch(tmp_path, capsys):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)
    (repo / "tasks").mkdir()
    (repo / "tasks" / "p.md").write_text("---\ncloses: 99\n---\n")

    ids = iter(["EV1"])
    times = iter(["2026-09-12T00:00:00Z"])
    EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids)).create(
        source="#5",
        target="#42",
        kind="decision",
        summary="s",
        detail="docs/x.md",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )

    transport = _make_ack_transport()
    code = main(
        ["ack", "42", "EV1", "--plan", "tasks/p.md", "--note", "n", "--json"],
        transport=transport,
        repo_root=repo,
    )
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["reason"] == "plan_target_mismatch"
    assert EventStore(events_dir).load().events[0].status == "pending"


def test_ack_verb_by_flag_overrides_actor(tmp_path, capsys):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)
    (repo / "tasks").mkdir()
    (repo / "tasks" / "p.md").write_text("---\ncloses: 42\n---\n")

    ids = iter(["EV1"])
    times = iter(["2026-09-12T00:00:00Z"])
    EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids)).create(
        source="#5",
        target="#42",
        kind="decision",
        summary="s",
        detail="docs/x.md",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )

    transport = _make_ack_transport()
    code = main(
        ["ack", "42", "EV1", "--plan", "tasks/p.md", "--note", "n", "--by", "adr-bot", "--json"],
        transport=transport,
        repo_root=repo,
    )
    assert code == 0
    events = EventStore(events_dir).load().events
    assert events[0].ack["by"] == "adr-bot"


def test_ack_verb_all_flag_crosses_boundary(tmp_path, capsys):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)
    (repo / "tasks").mkdir()
    (repo / "tasks" / "p.md").write_text("---\ncloses: 42\n---\n")

    ids = iter(["EV1", "EV2"])
    times = iter(["2026-09-12T00:00:00Z", "2026-09-12T00:00:01Z"])
    store = EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids))
    store.create(
        source="#5",
        target="#42",
        kind="decision",
        summary="s1",
        detail="docs/x.md",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )
    store.create(
        source="#5",
        target="#42",
        kind="decision",
        summary="s2",
        detail="docs/x.md",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )

    transport = _make_ack_transport()
    code = main(
        ["ack", "42", "--all", "--plan", "tasks/p.md", "--note", "n", "--json"],
        transport=transport,
        repo_root=repo,
    )
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert len(envelope["data"]["acked"]) == 2


def test_ack_bad_ref_is_usage_error(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()

    code = main(["ack", "bogus", "--all", "--plan", "tasks/p.md", "--note", "n"], repo_root=repo)
    assert code == 2
    captured = capsys.readouterr()
    assert "tasks/" in captured.err or "perturb ack" in captured.err


def _make_stale_transport(pages, *, commit_epoch="1000", blob="BLOBSHA"):
    class StaleTransport:
        def __init__(self):
            self._pages = list(pages)
            self._idx = 0

        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            if len(argv) >= 3 and argv[:2] == ["git", "log"] and "--format=%ct" in argv:
                return _make_runner_result(0, f"{commit_epoch}\n")
            if len(argv) >= 3 and argv[:2] == ["git", "rev-parse"] and argv[2].startswith("HEAD:"):
                return _make_runner_result(0, f"{blob}\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            page = self._pages[self._idx]
            self._idx += 1
            return page

    return StaleTransport()


def test_stale_verb_gates_on_exit_code(tmp_path, capsys):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    tasks_dir = repo / "tasks"
    tasks_dir.mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)

    (tasks_dir / "p.md").write_text("---\ncloses: 1\n---\n")

    # commit_epoch = 1000; event at is epoch 1001 (after commit)
    newer_at = "1970-01-01T00:16:41Z"  # epoch 1001

    issue_1 = {**CLI_ISSUE, "number": 1, "labels": {"nodes": [{"name": "ready-to-implement"}]}}

    # Case (i): stale — pending event after plan commit → exit 1
    ids = iter(["EV-STALE"])
    times = iter([newer_at])
    store = EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids))
    store.create(
        source="#4",
        target="#1",
        kind="spike",
        summary="stale event",
        proposed_by="bot",
        reason="test",
        status="pending",
    )

    transport = _make_stale_transport([_make_page([issue_1])], commit_epoch="1000")
    code = main(
        ["stale", "--json"],
        transport=transport,
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is False
    assert envelope["reason"] == "stale"
    assert len(envelope["data"]) == 1
    assert envelope["data"][0]["issue"] == 1

    # Case (ii): clean — no events directory at all → exit 0
    repo2 = tmp_path / "repo2"
    tasks_dir2 = repo2 / "tasks"
    tasks_dir2.mkdir(parents=True)
    perturb_root2 = repo2 / ".perturb"
    perturb_root2.mkdir()
    (tasks_dir2 / "p.md").write_text("---\ncloses: 1\n---\n")

    transport2 = _make_stale_transport([_make_page([issue_1])], commit_epoch="1000")
    code = main(
        ["stale", "--json"],
        transport=transport2,
        root=perturb_root2,
        repo_root=repo2,
    )
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["data"] == []


def test_stale_verb_ref_restricts_to_one_issue(tmp_path, capsys):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    tasks_dir = repo / "tasks"
    tasks_dir.mkdir(parents=True)
    perturb_root = repo / ".perturb"
    perturb_root.mkdir()
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)

    (tasks_dir / "p1.md").write_text("---\ncloses: 1\n---\n")
    (tasks_dir / "p2.md").write_text("---\ncloses: 2\n---\n")

    newer_at = "1970-01-01T00:16:41Z"  # epoch 1001, commit_epoch=1000

    issue_1 = {**CLI_ISSUE, "number": 1, "labels": {"nodes": [{"name": "ready-to-implement"}]}}
    issue_2 = {**CLI_ISSUE, "number": 2, "labels": {"nodes": [{"name": "ready-to-implement"}]}}

    ids = iter(["EV-1", "EV-2"])
    times = iter([newer_at, newer_at])
    store = EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids))
    store.create(
        source="#4",
        target="#1",
        kind="spike",
        summary="e1",
        proposed_by="bot",
        reason="test",
        status="pending",
    )
    store.create(
        source="#4",
        target="#2",
        kind="spike",
        summary="e2",
        proposed_by="bot",
        reason="test",
        status="pending",
    )

    def _runner(argv, capture_output=True, text=True):
        if argv[:3] == ["git", "config", "--get"]:
            return _make_runner_result(0, "https://github.com/geuben/x\n")
        if argv == ["git", "rev-parse", "HEAD"]:
            return _make_runner_result(0, "abc123\n")
        if len(argv) >= 3 and argv[:2] == ["git", "log"] and "--format=%ct" in argv:
            return _make_runner_result(0, "1000\n")
        if len(argv) >= 3 and argv[:2] == ["git", "rev-parse"] and argv[2].startswith("HEAD:"):
            return _make_runner_result(0, "BLOB\n")
        raise AssertionError(f"unexpected argv: {argv!r}")

    class T:
        def runner(self, *a, **kw):
            return _runner(*a, **kw)

        def graphql(self, q, v):
            return _make_page([issue_1, issue_2])

    code = main(
        ["stale", "2", "--json"],
        transport=T(),
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert len(envelope["data"]) == 1
    assert envelope["data"][0]["issue"] == 2


def test_stale_verb_refuses_when_github_unreachable(tmp_path, capsys):
    from perturb.github import GitHubError

    class FailTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            return _make_runner_result(0, "https://github.com/geuben/x\n")

        def graphql(self, query, variables):
            raise GitHubError("github_unreachable", "connect: network is unreachable")

    code = main(["stale", "--json"], transport=FailTransport(), root=tmp_path)
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope == {
        "ok": False,
        "verb": "stale",
        "reason": "github_unreachable",
        "detail": "connect: network is unreachable",
    }


def test_stale_bad_ref_is_usage_error(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    code = main(["stale", "bogus"], repo_root=repo)
    assert code == 2
    assert "tasks/<slug>.md" in capsys.readouterr().err


def test_check_verb_clean_repo_exits_zero(tmp_path, capsys):
    repo = tmp_path / "repo"
    perturb_root = repo / ".perturb"
    perturb_root.mkdir(parents=True)

    transport = _make_cli_transport([_make_page([CLI_ISSUE])])
    code = main(["check", "--json"], transport=transport, root=perturb_root, repo_root=repo)
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["data"] == []


def test_check_verb_reports_finding_and_exits_one(tmp_path, capsys):
    repo = tmp_path / "repo"
    perturb_root = repo / ".perturb"
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    perturb_root.mkdir(parents=True)
    (adr_dir / "0002-x.md").write_text(
        "---\nid: 2\nstatus: accepted\ndate: 2026-09-08\n---\n\n"
        "## Consequences\n\n```yaml\n- id: v\n  text: ok.\n  kind: decision\n```\n"
    )

    transport = _make_cli_transport([_make_page([CLI_ISSUE])])
    code = main(["check", "--json"], transport=transport, root=perturb_root, repo_root=repo)
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is False
    assert len(envelope["data"]) >= 1
    assert envelope["data"][0]["kind"] == "adr_parse"


def test_check_verb_flags_undeclared_area_refs(tmp_path, capsys):
    repo = tmp_path / "repo"
    perturb_root = repo / ".perturb"
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    perturb_root.mkdir(parents=True)
    (adr_dir / "0002-x.md").write_text(
        "---\nid: 2\ntitle: A title\nstatus: accepted\ndate: 2026-09-08\n---\n\n"
        "## Consequences\n\n```yaml\n"
        '- id: v\n  text: ok.\n  kind: decision\n  affects: ["area:unknown-slug"]\n'
        "```\n"
    )
    (repo / "perturb").mkdir(parents=True)
    (repo / "perturb" / "areas.yaml").write_text(
        "areas:\n  auth:\n    paths:\n      - src/auth.py\n"
    )

    transport = _make_cli_transport([_make_page([CLI_ISSUE])])
    code = main(["check", "--json"], transport=transport, root=perturb_root, repo_root=repo)
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert any(
        f["kind"] == "affects_unresolved" and "area:unknown-slug" in f["ref"]
        for f in envelope["data"]
    )

    # Without areas.yaml, all area: refs are unresolved (no declared areas)
    (repo / "perturb" / "areas.yaml").unlink()
    transport2 = _make_cli_transport([_make_page([CLI_ISSUE])])
    capsys.readouterr()
    code2 = main(["check", "--json"], transport=transport2, root=perturb_root, repo_root=repo)
    assert code2 == 1
    envelope2 = json.loads(capsys.readouterr().out)
    assert any(
        f["kind"] == "affects_unresolved" and "area:unknown-slug" in f["ref"]
        for f in envelope2["data"]
    )


def test_check_verb_reports_unpropagated_adr(tmp_path, capsys):
    repo = tmp_path / "repo"
    perturb_root = repo / ".perturb"
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    perturb_root.mkdir(parents=True)
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)

    def _adr_text(i, status):
        return (
            f"---\nid: {i}\ntitle: T{i}\nstatus: {status}\ndate: 2026-09-08\n---\n\n"
            "## Consequences\n\n```yaml\n- id: v\n  text: ok.\n  kind: decision\n```\n"
        )

    (adr_dir / "0002-b.md").write_text(_adr_text(2, "accepted"))
    (adr_dir / "0003-c.md").write_text(_adr_text(3, "accepted"))

    from perturb.events import EventStore

    EventStore(events_dir).create(
        source="adr:0002#v",
        target="#1",
        kind="decision",
        summary="ok.",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )

    transport = _make_cli_transport([_make_page([CLI_ISSUE])])
    code = main(["check", "--json"], transport=transport, root=perturb_root, repo_root=repo)
    envelope = json.loads(capsys.readouterr().out)
    assert (code, [(f["kind"], f["ref"]) for f in envelope["data"]]) == (
        1,
        [("adr_unpropagated", "0003-c.md")],
    )


def test_adr_migrate_rewrites_file_in_place(tmp_path, capsys):
    path = tmp_path / "0007-some-decision.md"
    path.write_text(
        "# ADR 0007 — Some decision\n\n"
        "**Status:** accepted · 2026-09-01\n\n"
        "## Context\n\nContext prose.\n\n"
        "## Decision\n\nDecision prose.\n\n"
        "## Consequences\n\n"
        "- Outcome A happens.\n"
    )
    rc = main(["adr", "migrate", str(path), "--json"])
    assert rc == 0
    from perturb.adr import parse_adr

    adr = parse_adr(path.read_text())
    assert adr.id == 7
    assert len(adr.consequences) > 0
    assert json.loads(capsys.readouterr().out)["warnings"] == []


def test_adr_migrate_warns_about_a_supersedes_line_it_cannot_carry(tmp_path, capsys):
    path = tmp_path / "0005-duckdb.md"
    path.write_text(
        "# ADR 0005 — DuckDB\n\n"
        "**Status:** accepted · 2026-09-01\n"
        "**Supersedes:** the storage engine half of [ADR 0003](0003-typescript-stack.md)\n\n"
        "## Context\n\nContext prose.\n\n"
        "## Consequences\n\n"
        "- Outcome A happens.\n"
    )
    rc = main(["adr", "migrate", str(path), "--json"])
    envelope = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert len(envelope["warnings"]) == 1
    assert "Supersedes" in envelope["warnings"][0]
    assert "the storage engine half of" in path.read_text()


def test_adr_migrate_leaves_the_file_untouched_when_the_result_does_not_parse(tmp_path, capsys):
    path = tmp_path / "0009-no-status.md"
    original = "# ADR 0009 — No status line\n\n## Context\n\nProse.\n\n## Consequences\n\n- A.\n"
    path.write_text(original)
    rc = main(["adr", "migrate", str(path), "--json"])
    envelope = json.loads(capsys.readouterr().out)
    assert (rc, envelope["ok"], envelope["reason"]) == (1, False, "missing_field")
    assert path.read_text() == original


def _all_parsers(parser):
    yield parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                yield from _all_parsers(sub)


def test_every_verb_has_a_description_and_every_argument_has_help():
    from perturb.cli import _make_parser

    missing = []
    for p in _all_parsers(_make_parser()):
        if p.prog != "perturb" and not p.description:
            missing.append(f"{p.prog}: description")
        for action in p._actions:
            if isinstance(action, argparse._SubParsersAction):
                missing += [
                    f"{p.prog} {choice.dest}: help"
                    for choice in action._choices_actions
                    if not choice.help
                ]
            elif not action.help or action.help == argparse.SUPPRESS:
                missing.append(f"{p.prog} {action.dest}: help")
    assert missing == []


def _make_propose_transport(pages):
    class ProposeTransport:
        def __init__(self):
            self._pages = list(pages)
            self._idx = 0

        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            page = self._pages[self._idx]
            self._idx += 1
            return page

    return ProposeTransport()


STRUCTURED_ADR_TEXT = """\
---
id: 2
title: Per-trip sync
status: accepted
date: 2026-09-13
supersedes: []
areas: []
---

## Context

Some context.

## Decision

The decision.

## Consequences

```yaml
- id: c1
  text: Issue 29 must be updated.
  affects: ["#29"]
  kind: decision
```
"""


def test_propose_adr_writes_events_and_emits_json(tmp_path, capsys):
    repo = tmp_path / "repo"
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0002-per-trip.md").write_text(STRUCTURED_ADR_TEXT)

    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    issue_29 = _make_issue_node(29, title="Issue 29")
    transport = _make_propose_transport([_make_page([issue_29])])

    code = main(
        ["propose", "adr:2", "--by", "geuben", "--json"],
        transport=transport,
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["verb"] == "propose"
    assert len(envelope["data"]["proposed"]) > 0

    events_dir = repo / "perturb" / "events"
    assert len(list(events_dir.glob("*.yaml"))) > 0


STRUCTURED_ADR_WITH_MENTION = """\
---
id: 2
title: Per-trip sync
status: accepted
date: 2026-09-13
supersedes: []
areas: []
---

## Context

Some context.

## Decision

The decision.

## Consequences

```yaml
- id: c1
  text: "See `#29` for details."
  affects: []
  kind: decision
```
"""


def test_propose_review_walks_proposals_interactively(tmp_path, capsys, monkeypatch):
    repo = tmp_path / "repo"
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0002-per-trip.md").write_text(STRUCTURED_ADR_WITH_MENTION)

    perturb_root = repo / ".perturb"
    perturb_root.mkdir()

    issue_29 = _make_issue_node(29, title="Issue 29")
    transport = _make_propose_transport([_make_page([issue_29])])

    monkeypatch.setattr("builtins.input", lambda *_: "a")

    code = main(
        ["propose", "adr:2", "--by", "geuben", "--review"],
        transport=transport,
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 0

    from perturb.events import EventStore

    events_dir = repo / "perturb" / "events"
    events = EventStore(events_dir).load().events
    assert len(events) == 1
    assert events[0].status == "pending"


def test_dismiss_verb_dismisses_event_and_records_by(tmp_path, capsys):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)

    store = EventStore(events_dir, new_id=lambda: "EV1")
    store.create(
        source="plan:x",
        target="#13",
        kind="decision",
        summary="s1",
        proposed_by="geuben",
        reason="affects",
        status="pending",
    )

    class DismissTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv == ["git", "config", "user.name"]:
                return _make_runner_result(0, "geuben\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            raise AssertionError("dismiss should not call graphql")

    code = main(
        ["dismiss", "EV1", "--note", "already done", "--json"],
        transport=DismissTransport(),
        repo_root=repo,
    )
    assert code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is True
    assert data["verb"] == "dismiss"
    assert data["synced_at"] is None
    assert len(data["data"]["dismissed"]) == 1

    reload = EventStore(events_dir)
    loaded = {e.id: e for e in reload.load().events}
    assert loaded["EV1"].status == "dismissed"
    assert loaded["EV1"].ack["by"] == "geuben"
    assert loaded["EV1"].ack["note"] == "already done"


def test_confirm_verb_source_all_confirms_matching(tmp_path, capsys):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)

    id_iter = iter(["A", "B", "C"])
    store = EventStore(events_dir, new_id=lambda: next(id_iter))
    store.create(
        source="adr:0002#refund-grain",
        target="#13",
        kind="decision",
        summary="s1",
        proposed_by="geuben",
        reason="affects",
        status="proposed",
    )
    store.create(
        source="adr:0002#band-windows",
        target="#31",
        kind="decision",
        summary="s2",
        proposed_by="geuben",
        reason="affects",
        status="proposed",
    )
    store.create(
        source="adr:0003#other",
        target="#40",
        kind="decision",
        summary="s3",
        proposed_by="geuben",
        reason="affects",
        status="proposed",
    )

    code = main(["confirm", "--source", "adr:2", "--all", "--json"], repo_root=repo)
    assert code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is True
    confirmed_ids = {c["id"] for c in data["data"]["confirmed"]}
    assert confirmed_ids == {"A", "B"}

    reload = EventStore(events_dir)
    loaded = {e.id: e for e in reload.load().events}
    assert loaded["A"].status == "pending"
    assert loaded["B"].status == "pending"
    assert loaded["C"].status == "proposed"


def test_confirm_verb_promotes_event_and_emits_json(tmp_path, capsys):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)

    store = EventStore(events_dir, new_id=lambda: "EV1")
    store.create(
        source="plan:x",
        target="#13",
        kind="decision",
        summary="s1",
        proposed_by="geuben",
        reason="affects",
        status="proposed",
    )

    code = main(["confirm", "EV1", "--json"], repo_root=repo)
    assert code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is True
    assert data["verb"] == "confirm"
    assert data["synced_at"] is None
    assert len(data["data"]["confirmed"]) == 1
    assert data["data"]["confirmed"][0]["id"] == "EV1"

    reload = EventStore(events_dir)
    loaded = {e.id: e for e in reload.load().events}
    assert loaded["EV1"].status == "pending"


def test_propose_friction_writes_events_and_emits_json(tmp_path, capsys):
    repo = tmp_path / "repo"
    perturb_root = repo / ".perturb"
    perturb_root.mkdir(parents=True)

    # Seed friction log, plan, areas.yaml
    (repo / "tasks" / "friction-logs").mkdir(parents=True)
    (repo / "tasks" / "friction-logs" / "w-friction.md").write_text(
        "  - `deadbeef1` [green] feat: something (1 files)\n"
    )
    (repo / "tasks" / "w.md").write_text(
        '---\ncloses: 48\ncycles:\n  - n: 1\n    files: ["src/w.py"]\n---\nbody\n'
    )
    (repo / "perturb").mkdir(exist_ok=True)
    (repo / "perturb" / "areas.yaml").write_text(
        'areas:\n  alpha:\n    paths:\n      - "src/alpha/**"\n'
    )

    issue_70 = _make_issue_node(70, title="Issue 70", labels=["area:alpha"])

    class FrictionTransport:
        def __init__(self):
            self._pages = [_make_page([issue_70])]
            self._idx = 0

        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            if argv == ["git", "show", "--name-only", "--format=", "deadbeef1"]:
                return _make_runner_result(0, "src/alpha/new.py\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            page = self._pages[self._idx]
            self._idx += 1
            return page

    transport = FrictionTransport()
    code = main(
        ["propose", "friction:w", "--by", "geuben", "--json"],
        transport=transport,
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["verb"] == "propose"
    assert len(envelope["data"]["proposed"]) == 1
    assert envelope["data"]["proposed"][0]["target"] == "#70"

    events_dir = repo / "perturb" / "events"
    events = list(events_dir.glob("*.yaml"))
    assert len(events) == 1
    import yaml as _yaml

    event_data = _yaml.safe_load(events[0].read_text())
    assert event_data["kind"] == "friction"


def test_propose_plan_writes_events_and_emits_json(tmp_path, capsys):
    repo = tmp_path / "repo"
    perturb_root = repo / ".perturb"
    perturb_root.mkdir(parents=True)

    (repo / "tasks").mkdir(parents=True)
    (repo / "tasks" / "p.md").write_text(
        "---\ncloses: 47\n---\n\n## Design decisions (locked)\n\n1. Mention #70.\n"
    )

    issue_70 = _make_issue_node(70, title="Issue 70")

    class PlanTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            return _make_page([issue_70])

    transport = PlanTransport()
    code = main(
        ["propose", "plan:p", "--by", "geuben", "--json"],
        transport=transport,
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["verb"] == "propose"
    assert len(envelope["data"]["proposed"]) == 1
    assert envelope["data"]["proposed"][0]["target"] == "#70"

    events_dir = repo / "perturb" / "events"
    events = list(events_dir.glob("*.yaml"))
    assert len(events) == 1
    import yaml as _yaml

    event_data = _yaml.safe_load(events[0].read_text())
    assert event_data["kind"] == "decision"


def test_init_refuses_outside_git_repository(tmp_path, capsys, monkeypatch):
    import json

    from perturb.cli import main

    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.chdir(outside)

    code = main(["init", "--json"])
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert (envelope["ok"], envelope["reason"], (outside / "perturb").exists()) == (
        False,
        "not_a_git_repo",
        False,
    )


def test_init_resolves_repo_root_from_git_toplevel(tmp_path, capsys, monkeypatch):
    import subprocess

    from perturb.cli import main

    subprocess.run(["git", "init", "-q", str(tmp_path / "repo")], check=True)
    (tmp_path / "repo" / "sub").mkdir()
    monkeypatch.chdir(tmp_path / "repo" / "sub")

    code = main(["init", "--json"])

    assert (
        code,
        (tmp_path / "repo" / "perturb" / "areas.yaml").exists(),
        (tmp_path / "repo" / "sub" / "perturb").exists(),
    ) == (0, True, False)


def test_init_emits_envelope_with_json_before_or_after_verb(tmp_path, capsys):
    import json

    from perturb.cli import main

    for i, argv in enumerate((["init", "--json"], ["--json", "init"])):
        repo = tmp_path / str(i)
        repo.mkdir()
        code = main(argv, repo_root=repo)
        assert code == 0
        envelope = json.loads(capsys.readouterr().out)
        assert (
            envelope["ok"],
            envelope["verb"],
            envelope["synced_at"],
            envelope["data"],
        ) == (
            True,
            "init",
            None,
            {
                "created": [
                    "perturb/areas.yaml",
                    "perturb/config.yaml",
                    "perturb/README.md",
                    "perturb/events/",
                    ".gitignore",
                ],
                "existing": [],
            },
        )


def test_propose_audit_review_walks_run_friction_proposals(tmp_path, capsys, monkeypatch):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    perturb_root = repo / ".perturb"
    perturb_root.mkdir(parents=True)

    (repo / "perturb").mkdir(parents=True)
    (repo / "perturb" / "areas.yaml").write_text(
        "areas:\n  alpha:\n    paths:\n      - src/alpha/**\n"
    )
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)
    (repo / "tasks").mkdir(parents=True)
    (repo / "tasks" / "friction-audits").mkdir(parents=True)
    (repo / "tasks" / "friction-audits" / "w-audit.md").write_text(
        "- [ ] **[CRITICAL]** fix `src/alpha/x.py`\n"
    )

    store = EventStore(events_dir)
    store.create(
        source="friction:w",
        target="#70",
        kind="friction",
        summary="w touched area:alpha outside its plan",
        proposed_by="geuben",
        reason="touches",
        status="proposed",
    )

    issue_70 = _make_issue_node(70, title="Issue 70", labels=["area:alpha"])

    class ReviewTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            return _make_page([issue_70])

    monkeypatch.setattr("builtins.input", lambda *_: "a")

    code = main(
        ["propose", "audit:w", "--by", "geuben", "--review"],
        transport=ReviewTransport(),
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 0

    events = EventStore(events_dir).load().events
    assert all(e.status == "pending" for e in events)


def test_propose_audit_warns_no_target_for_unrouted_critical_item(tmp_path, capsys):
    repo = tmp_path / "repo"
    perturb_root = repo / ".perturb"
    perturb_root.mkdir(parents=True)

    (repo / "perturb").mkdir(parents=True)
    (repo / "perturb" / "areas.yaml").write_text(
        "areas:\n  alpha:\n    paths:\n      - src/alpha/**\n"
    )
    (repo / "tasks").mkdir(parents=True)
    (repo / "tasks" / "friction-audits").mkdir(parents=True)
    (repo / "tasks" / "friction-audits" / "w-audit.md").write_text(
        "- [ ] **[CRITICAL]** nobody owns this\n"
    )

    class NoTargetTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            return _make_page([])

    code = main(
        ["propose", "audit:w", "--by", "geuben", "--json"],
        transport=NoTargetTransport(),
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["warnings"] == ["no target; `perturb push --new`: nobody owns this"]


def test_propose_audit_writes_events_and_emits_json(tmp_path, capsys):
    import yaml as _yaml

    repo = tmp_path / "repo"
    perturb_root = repo / ".perturb"
    perturb_root.mkdir(parents=True)

    (repo / "perturb").mkdir(parents=True)
    (repo / "perturb" / "areas.yaml").write_text(
        "areas:\n  alpha:\n    paths:\n      - src/alpha/**\n"
    )
    (repo / "tasks").mkdir(parents=True)
    (repo / "tasks" / "friction-audits").mkdir(parents=True)
    (repo / "tasks" / "friction-audits" / "w-audit.md").write_text(
        "- [ ] **[CRITICAL]** fix `src/alpha/x.py`\n"
    )

    issue_70 = _make_issue_node(70, title="Issue 70", labels=["area:alpha"])

    class AuditTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            return _make_page([issue_70])

    transport = AuditTransport()
    code = main(
        ["propose", "audit:w", "--by", "geuben", "--json"],
        transport=transport,
        root=perturb_root,
        repo_root=repo,
    )
    assert code == 0
    envelope = json.loads(capsys.readouterr().out)
    assert envelope["ok"] is True
    assert envelope["verb"] == "propose"
    assert envelope["data"]["proposed"][0]["target"] == "#70"

    events_dir = repo / "perturb" / "events"
    events = list(events_dir.glob("*.yaml"))
    assert len(events) == 1
    event_data = _yaml.safe_load(events[0].read_text())
    assert event_data["kind"] == "friction"
    assert event_data["source"] == "audit:w"


def test_propose_audit_review_creates_issue_for_accepted_no_target_item(tmp_path, monkeypatch):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    (repo / "perturb").mkdir(parents=True)
    (repo / "perturb" / "areas.yaml").write_text(
        "areas:\n  alpha:\n    paths:\n      - src/alpha/**\n"
    )
    (repo / "tasks" / "friction-audits").mkdir(parents=True)
    (repo / "tasks" / "friction-audits" / "w-audit.md").write_text(
        "- [ ] **[CRITICAL]** nobody owns this\n"
    )

    class ReviewTransport:
        def __init__(self):
            self.calls = []

        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            return _make_page([])

        def create_issue(self, **kw):
            self.calls.append(kw)
            return 88

    t = ReviewTransport()
    monkeypatch.setattr("builtins.input", lambda *_: "a")

    code = main(
        ["propose", "audit:w", "--by", "geuben", "--review"],
        transport=t,
        root=repo / ".perturb",
        repo_root=repo,
    )

    events_dir = repo / "perturb" / "events"
    assert (
        code,
        t.calls,
        [(e.target, e.status, e.reason) for e in EventStore(events_dir).load().events],
    ) == (
        0,
        [
            {
                "owner": "geuben",
                "name": "x",
                "title": "nobody owns this",
                "body": (
                    "nobody owns this\n\n"
                    "From `tasks/friction-audits/w-audit.md` (`perturb propose audit:w`)."
                ),
            }
        ],
        [("#88", "pending", "manual")],
    )


def test_propose_audit_review_warns_only_for_items_left_unraised(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "repo"
    (repo / "perturb").mkdir(parents=True)
    (repo / "perturb" / "areas.yaml").write_text(
        "areas:\n  alpha:\n    paths:\n      - src/alpha/**\n"
    )
    (repo / "tasks" / "friction-audits").mkdir(parents=True)
    (repo / "tasks" / "friction-audits" / "w-audit.md").write_text(
        "- [ ] **[CRITICAL]** first unowned\n- [ ] **[CRITICAL]** second unowned\n"
    )

    class ReviewTransport:
        def __init__(self):
            self.calls = []

        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            return _make_page([])

        def create_issue(self, **kw):
            self.calls.append(kw)
            return 88

    t = ReviewTransport()
    answers = iter(["a", "s"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    code = main(
        ["propose", "audit:w", "--by", "geuben", "--review"],
        transport=t,
        root=repo / ".perturb",
        repo_root=repo,
    )
    warnings = [
        line for line in capsys.readouterr().err.splitlines() if line.startswith("warning:")
    ]
    assert (code, warnings) == (
        0,
        ["warning: no target; `perturb push --new`: second unowned"],
    )


def test_propose_audit_review_refuses_github_error_when_issue_creation_fails(
    tmp_path, monkeypatch, capsys
):
    from perturb.events import EventStore
    from perturb.github import GitHubError

    repo = tmp_path / "repo"
    (repo / "perturb").mkdir(parents=True)
    (repo / "perturb" / "areas.yaml").write_text(
        "areas:\n  alpha:\n    paths:\n      - src/alpha/**\n"
    )
    (repo / "tasks" / "friction-audits").mkdir(parents=True)
    (repo / "tasks" / "friction-audits" / "w-audit.md").write_text(
        "- [ ] **[CRITICAL]** nobody owns this\n"
    )
    events_dir = repo / "perturb" / "events"
    events_dir.mkdir(parents=True)

    class FailTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            return _make_page([])

        def create_issue(self, **kw):
            raise GitHubError("github_error", "boom")

    monkeypatch.setattr("builtins.input", lambda *_: "a")

    code = main(
        ["propose", "audit:w", "--by", "geuben", "--review"],
        transport=FailTransport(),
        root=repo / ".perturb",
        repo_root=repo,
    )
    err = capsys.readouterr().err
    assert (
        code,
        "perturb propose: github_error: boom" in err,
        EventStore(events_dir).load().events,
    ) == (1, True, [])


def test_push_verb_new_refuses_github_error_when_issue_creation_fails(tmp_path, capsys):
    from perturb.github import GitHubError

    issue_page = _make_page([_make_issue_node(5)])

    class PushFailTransport:
        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "abc123\n")
            if argv == ["git", "config", "user.name"]:
                return _make_runner_result(0, "geuben\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            return issue_page

        def create_issue(self, *, owner, name, title, body):
            raise GitHubError("github_error", "boom")

    t = PushFailTransport()
    code = main(
        ["push", "--from", "5", "--new", "New sibling", "--kind", "scope", "s", "--json"],
        transport=t,
        root=tmp_path / ".perturb",
        repo_root=tmp_path,
    )
    assert code == 1
    envelope = json.loads(capsys.readouterr().out)
    assert (envelope["ok"], envelope["reason"], envelope["detail"]) == (
        False,
        "github_error",
        "boom",
    )


MIXED_ADR = (
    "---\nid: 2\ntitle: T\nstatus: accepted\ndate: 2026-09-13\n"
    "supersedes: []\nareas: []\n---\n\n"
    "## Consequences\n\n```yaml\n"
    '- id: c1\n  text: "Issue 29 must change; see #31."\n'
    '  kind: decision\n  affects: ["#29"]\n```\n'
)


def test_propose_adr_review_walks_only_proposed_events(tmp_path, monkeypatch):
    from perturb.events import EventStore

    expected = {
        "d": [("#29", "pending", "affects"), ("#31", "dismissed", "mentions")],
        "a": [("#29", "pending", "affects"), ("#31", "pending", "mentions")],
    }

    for answer in ("d", "a"):
        repo = tmp_path / answer
        adr_dir = repo / "docs" / "adr"
        adr_dir.mkdir(parents=True)
        (adr_dir / "0002-t.md").write_text(MIXED_ADR)
        (repo / ".perturb").mkdir()

        prompts = []
        monkeypatch.setattr(
            "builtins.input",
            lambda p="", _a=answer, _ps=prompts: (_ps.append(p), _a)[1],
        )

        transport = _make_propose_transport(
            [_make_page([_make_issue_node(29), _make_issue_node(31)])]
        )
        code = main(
            ["propose", "adr:2", "--by", "geuben", "--review"],
            transport=transport,
            root=repo / ".perturb",
            repo_root=repo,
        )
        events = EventStore(repo / "perturb" / "events").load().events
        row = sorted((e.target, e.status, e.reason) for e in events)
        actual = (answer, code, len(prompts), row)
        assert actual == (answer, 0, 1, expected[answer])


def test_propose_friction_review_confirms_written_proposals(tmp_path, monkeypatch):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    perturb_root = repo / ".perturb"
    perturb_root.mkdir(parents=True)

    (repo / "tasks" / "friction-logs").mkdir(parents=True)
    (repo / "tasks" / "friction-logs" / "w-friction.md").write_text(
        "  - `deadbeef1` [green] feat: something (1 files)\n"
    )
    (repo / "tasks" / "w.md").write_text(
        '---\ncloses: 48\ncycles:\n  - n: 1\n    files: ["src/w.py"]\n---\nbody\n'
    )
    (repo / "perturb").mkdir(exist_ok=True)
    (repo / "perturb" / "areas.yaml").write_text(
        'areas:\n  alpha:\n    paths:\n      - "src/alpha/**"\n'
    )

    issue_70 = _make_issue_node(70, title="Issue 70", labels=["area:alpha"])

    class FrictionTransport:
        def __init__(self):
            self._pages = [_make_page([issue_70])]
            self._idx = 0

        def runner(self, argv, capture_output=True, text=True):
            if argv[:3] == ["git", "config", "--get"]:
                return _make_runner_result(0, "https://github.com/geuben/x\n")
            if argv == ["git", "rev-parse", "HEAD"]:
                return _make_runner_result(0, "deadbeef1\n")
            if argv == ["git", "show", "--name-only", "--format=", "deadbeef1"]:
                return _make_runner_result(0, "src/alpha/new.py\n")
            raise AssertionError(f"unexpected argv: {argv!r}")

        def graphql(self, query, variables):
            page = self._pages[self._idx]
            self._idx += 1
            return page

    monkeypatch.setattr("builtins.input", lambda *_: "a")
    code = main(
        ["propose", "friction:w", "--by", "geuben", "--review"],
        transport=FrictionTransport(),
        root=perturb_root,
        repo_root=repo,
    )
    events = EventStore(repo / "perturb" / "events").load().events
    assert (code, [(e.target, e.status) for e in events]) == (0, [("#70", "pending")])


def test_propose_plan_review_confirms_written_proposals(tmp_path, monkeypatch):
    from perturb.events import EventStore

    repo = tmp_path / "repo"
    perturb_root = repo / ".perturb"
    perturb_root.mkdir(parents=True)
    (repo / "tasks").mkdir(parents=True)
    (repo / "tasks" / "p.md").write_text(
        "---\ncloses: 47\n---\n\n## Design decisions (locked)\n\n1. Mention #70.\n"
    )

    monkeypatch.setattr("builtins.input", lambda *_: "a")
    transport = _make_propose_transport([_make_page([_make_issue_node(70)])])
    code = main(
        ["propose", "plan:p", "--by", "geuben", "--review"],
        transport=transport,
        root=perturb_root,
        repo_root=repo,
    )
    events = EventStore(repo / "perturb" / "events").load().events
    assert (code, [(e.target, e.status) for e in events]) == (0, [("#70", "pending")])


def test_propose_adr_routes_area_affects_to_in_area_issues(tmp_path, capsys):
    repo = tmp_path / "repo"
    adr_dir = repo / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0002-per-trip.md").write_text(
        "---\n"
        "id: 2\n"
        "title: Per-trip\n"
        "status: accepted\n"
        "date: 2026-09-13\n"
        "supersedes: []\n"
        "areas: []\n"
        "---\n\n"
        "## Consequences\n\n"
        "```yaml\n"
        "- id: reprice\n"
        "  text: Re-pricing uses the rollup.\n"
        "  kind: decision\n"
        "  affects: [area:rollup]\n"
        "```\n"
    )
    (repo / ".perturb").mkdir()
    (repo / "perturb" / "areas.yaml").parent.mkdir(parents=True)
    (repo / "perturb" / "areas.yaml").write_text(
        'areas:\n  rollup:\n    paths:\n      - "src/rollup/**"\n'
    )
    (repo / "tasks").mkdir()
    (repo / "tasks" / "p.md").write_text("---\ncloses: 34\nareas: [rollup]\n---\nbody\n")

    t = _make_propose_transport(
        [_make_page([_make_issue_node(33, labels=["area:rollup"]), _make_issue_node(34)])]
    )
    code = main(
        ["propose", "adr:2", "--by", "geuben", "--json"],
        transport=t,
        root=repo / ".perturb",
        repo_root=repo,
    )
    out = json.loads(capsys.readouterr().out)
    assert (
        code,
        sorted((p["target"], p["reason"], p["status"]) for p in out["data"]["proposed"]),
    ) == (0, [("#33", "area", "proposed"), ("#34", "area", "proposed")])


def test_push_verb_accepts_the_amend_kind(tmp_path):
    from perturb.events import EventStore

    issue_29 = _make_issue_node(29)
    transport = _make_push_transport([_make_page([issue_29])])
    root = tmp_path / ".perturb"
    repo_root = tmp_path
    code = main(
        ["push", "--from", "5", "--to", "29", "--kind", "amend", "s", "--json"],
        transport=transport,
        root=root,
        repo_root=repo_root,
    )
    events = EventStore(tmp_path / "perturb" / "events").load().events
    assert (code, [e.kind for e in events]) == (0, ["amend"])
