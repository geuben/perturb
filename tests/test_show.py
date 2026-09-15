import pytest

from perturb.envelope import Refusal
from perturb.refs import parse_ref
from perturb.show import render_show, show


def _graph_issue(
    number,
    *,
    title="t",
    state="OPEN",
    labels=None,
    epic=None,
    plan=None,
    planned=False,
    ready=False,
    blocked_by=None,
    blocks=None,
):
    return {
        "number": number,
        "title": title,
        "state": state,
        "labels": labels or [],
        "epic": epic,
        "plan": plan,
        "planned": planned,
        "ready": ready,
        "blocked_by": blocked_by or [],
        "blocks": blocks or [],
        "unblocks": 0,
    }


def test_show_issue_assembles_node_view_with_blocker_states():
    issues = {
        "10": _graph_issue(10, state="OPEN"),
        "20": _graph_issue(20, state="CLOSED"),
        "29": _graph_issue(
            29,
            title="example issue",
            state="OPEN",
            labels=["task", "ready-to-implement"],
            epic=1,
            plan="tasks/show-verb.md",
            planned=True,
            ready=False,
            blocked_by=[10, 20],
            blocks=[30],
        ),
        "30": _graph_issue(30, state="OPEN"),
    }
    result = show(parse_ref("29"), graph_issues=issues)
    assert result == {
        "kind": "issue",
        "number": 29,
        "title": "example issue",
        "state": "OPEN",
        "labels": ["task", "ready-to-implement"],
        "epic": 1,
        "ready": False,
        "planned": True,
        "plan": "tasks/show-verb.md",
        "blocked_by": [
            {"number": 10, "state": "OPEN"},
            {"number": 20, "state": "CLOSED"},
        ],
        "blocking": [30],
    }


def test_show_plan_returns_issue_and_declared_files(tmp_path):
    plan_text = (
        "---\ncloses: 42\nfiles: [src/b.py]\nancillary_files: [docs/d.md]\n"
        "cycles:\n  - {n: 1, files: [src/a.py], stub_expected: [src/c.py]}\n---\n# body\n"
    )
    slug = "my-plan"
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / f"{slug}.md").write_text(plan_text)
    result = show(parse_ref(f"plan:{slug}"), repo_root=tmp_path)
    assert result == {
        "kind": "plan",
        "slug": slug,
        "issue": 42,
        "files": ["docs/d.md", "src/a.py", "src/b.py", "src/c.py"],
    }


def test_show_unknown_issue_refuses():
    with pytest.raises(Refusal) as exc_info:
        show(parse_ref("999"), graph_issues={})
    assert exc_info.value.reason == "unknown_issue"


def test_show_missing_plan_refuses(tmp_path):
    (tmp_path / "tasks").mkdir()
    with pytest.raises(Refusal) as exc_info:
        show(parse_ref("plan:nope"), repo_root=tmp_path)
    assert exc_info.value.reason == "plan_not_found"


def test_show_unsupported_ref_kind_refuses():
    with pytest.raises(Refusal) as exc_info:
        show(parse_ref("adr:2"))
    assert exc_info.value.reason == "unsupported_ref"


def test_render_show_issue_matches_documented_layout():
    data = {
        "kind": "issue",
        "number": 29,
        "title": "example issue",
        "state": "OPEN",
        "labels": ["task"],
        "epic": 1,
        "ready": False,
        "planned": True,
        "plan": "tasks/show-verb.md",
        "blocked_by": [
            {"number": 10, "state": "OPEN"},
            {"number": 20, "state": "CLOSED"},
        ],
        "blocking": [30],
    }
    result = render_show(data)
    expected = (
        "#29  example issue\n"
        "  state: OPEN\n"
        "  ready: False\n"
        "  planned: True\n"
        "  epic: #1\n"
        "  labels: task\n"
        "  plan: tasks/show-verb.md\n"
        "  blocked by:\n"
        "    #10 (open)\n"
        "    #20 (closed)\n"
        "  blocking: #30\n"
        "  events: (added by the ledger epic)\n"
    )
    assert result == expected


def test_render_show_plan_matches_documented_layout():
    data = {"kind": "plan", "slug": "my-plan", "issue": 42, "files": ["src/a.py", "src/b.py"]}
    result = render_show(data)
    expected = "plan:my-plan\n  issue: #42\n  files:\n    src/a.py\n    src/b.py\n"
    assert result == expected


def test_render_show_plan_without_declared_files_says_none():
    data = {"kind": "plan", "slug": "my-plan", "issue": 42, "files": []}
    assert render_show(data) == "plan:my-plan\n  issue: #42\n  files: none\n"


def test_show_plan_follows_a_custom_plan_pattern(tmp_path):
    from perturb.config import Config

    (tmp_path / "plans").mkdir()
    (tmp_path / "plans" / "p-plan.md").write_text("---\ncloses: 5\n---\n")
    config = Config(plan="plans/{slug}-plan.md")
    result = show(parse_ref("plan:p"), repo_root=tmp_path, config=config)
    assert result == {"kind": "plan", "slug": "p", "issue": 5, "files": []}
    with pytest.raises(Refusal) as exc_info:
        show(parse_ref("plan:q"), repo_root=tmp_path, config=config)
    assert exc_info.value.reason == "plan_not_found"
