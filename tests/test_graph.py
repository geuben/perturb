import json

from perturb.config import Config
from perturb.graph import (
    derive,
    ensure_graph,
    is_epic,
    load_plans,
    parse_plan_closes,
    write_graph,
)


def test_parse_plan_closes_handles_documented_shapes():
    assert parse_plan_closes("---\ncloses: 4\ncycles: []\n---\n# x") == 4
    assert parse_plan_closes("# no front matter") is None
    assert parse_plan_closes("---\ncycles: []\n---\n") is None
    assert parse_plan_closes("---\ncloses: four\n---\n") is None
    assert parse_plan_closes("---\ncloses: [unclosed\n---\n") is None


def test_load_plans_maps_closes_to_relative_paths(tmp_path):
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    (tasks / "README.md").write_text("# no front matter")
    (tasks / "b-plan.md").write_text("---\ncloses: 4\n---\n# b")
    (tasks / "a-plan.md").write_text("---\ncloses: 9\n---\n# a")
    (tasks / "dup.md").write_text("---\ncloses: 4\n---\n# dup")

    plans, warnings = load_plans(tmp_path)
    assert plans == {4: "tasks/b-plan.md", 9: "tasks/a-plan.md"}
    assert warnings == ["#4: tasks/b-plan.md and tasks/dup.md"]


def _issue(number, *, state="OPEN", labels=None, parent=None, blocked_by=None, blocking=None):
    return {
        "number": number,
        "title": f"Issue {number}",
        "state": state,
        "labels": labels or [],
        "parent": parent,
        "blockedBy": [{"number": n, "state": s} for n, s in (blocked_by or [])],
        "blocking": [{"number": n, "state": s} for n, s in (blocking or [])],
        "body_head": "",
        "updatedAt": "",
    }


def test_ensure_graph_rederives_on_head_or_cache_change(tmp_path):
    repo = tmp_path / "repo"
    root = repo / ".perturb"
    root.mkdir(parents=True)
    (repo / "tasks").mkdir()

    github_data = {"issues": {"1": _issue(1)}}
    (root / "github.json").write_text(json.dumps(github_data))
    ensure_graph(root, repo, head="abc")

    graph_path = root / "graph.json"
    raw = json.loads(graph_path.read_text())
    raw["marker"] = 1
    graph_path.write_text(json.dumps(raw))

    result = ensure_graph(root, repo, head="def")
    assert result.get("marker") is None
    assert json.loads(graph_path.read_text())["head"] == "def"

    ensure_graph(root, repo, head="abc")
    raw2 = json.loads(graph_path.read_text())
    raw2["marker"] = 1
    graph_path.write_text(json.dumps(raw2))

    github_data2 = {"issues": {"1": _issue(1), "2": _issue(2)}}
    (root / "github.json").write_text(json.dumps(github_data2))
    result2 = ensure_graph(root, repo, head="abc")
    assert result2.get("marker") is None
    assert "2" in result2["issues"]


def test_ensure_graph_skips_when_unchanged(tmp_path):
    repo = tmp_path / "repo"
    root = repo / ".perturb"
    root.mkdir(parents=True)
    (repo / "tasks").mkdir()

    github_data = {"issues": {"1": _issue(1)}}
    (root / "github.json").write_text(json.dumps(github_data))

    ensure_graph(root, repo, head="abc")

    graph_path = root / "graph.json"
    raw = json.loads(graph_path.read_text())
    raw["marker"] = 1
    graph_path.write_text(json.dumps(raw))

    result2 = ensure_graph(root, repo, head="abc")
    assert result2.get("marker") == 1
    assert json.loads(graph_path.read_text()).get("marker") == 1


def test_write_graph_records_head_and_cache_hash(tmp_path):
    issue_data = {"1": {"number": 1}}
    write_graph(tmp_path, issues=issue_data, head="abc", cache_hash="deadbeef", warnings=[])
    graph = json.loads((tmp_path / "graph.json").read_text())
    assert graph == {
        "cache_hash": "deadbeef",
        "head": "abc",
        "issues": {"1": {"number": 1}},
        "warnings": [],
    }


def test_unblocks_counts_transitive_open_downstream_with_cycle():
    # A(1) blocks B(2); B blocks C(3,CLOSED) and D(4); C blocks E(5); D blocks A (cycle)
    cache = {
        "1": _issue(1, blocking=[(2, "OPEN")], blocked_by=[(4, "OPEN")]),
        "2": _issue(2, blocked_by=[(1, "OPEN")], blocking=[(3, "CLOSED"), (4, "OPEN")]),
        "3": _issue(3, state="CLOSED", blocked_by=[(2, "OPEN")], blocking=[(5, "OPEN")]),
        "4": _issue(4, blocked_by=[(2, "OPEN")], blocking=[(1, "OPEN")]),
        "5": _issue(5, blocked_by=[(3, "CLOSED")]),
    }
    result = derive(cache, {})
    # B, D, E; C traversed but not counted; A not counted for itself
    assert result["1"]["unblocks"] == 3
    assert result["2"]["unblocks"] == 3  # D, E, A
    assert result["3"]["unblocks"] == 1  # E
    assert result["4"]["unblocks"] == 3  # A, B, E
    assert result["5"]["unblocks"] == 0


def test_planned_flag_requires_plan_and_label():
    def _single(number, labels=None):
        return {str(number): _issue(number, labels=labels or [])}

    ready = ["ready-to-implement"]
    assert derive(_single(1, labels=ready), {1: "tasks/p.md"})["1"]["planned"] is True
    assert derive(_single(2), {2: "tasks/p.md"})["2"]["planned"] is False
    assert derive(_single(3, labels=ready), {})["3"]["planned"] is False
    assert derive(_single(4, labels=["hardened"]), {4: "tasks/p.md"})["4"]["planned"] is False


def test_ready_flag_over_documented_cases():
    def _single(number, **kwargs):
        return {str(number): _issue(number, **kwargs)}

    assert derive(_single(1), {})["1"]["ready"] is True
    assert derive(_single(2, blocked_by=[(9, "CLOSED")]), {})["2"]["ready"] is True
    assert derive(_single(3, blocked_by=[(9, "OPEN"), (10, "CLOSED")]), {})["3"]["ready"] is False
    assert derive(_single(4, labels=["epic"]), {})["4"]["ready"] is False
    assert derive(_single(5, state="CLOSED"), {})["5"]["ready"] is False


def test_derive_builds_structural_edges():
    # Issue 3's blocking is [], so blocks=[4] can only come from issue 4's blockedBy=[3]
    cache = {
        "3": _issue(3, parent=1, blocked_by=[(2, "CLOSED")], blocking=[]),
        "4": _issue(4, parent=1, blocked_by=[(3, "OPEN")], blocking=[]),
        "1": _issue(1, labels=["epic"]),
    }
    plans = {4: "tasks/x.md"}
    result = derive(cache, plans)

    assert result["3"]["epic"] == 1
    assert result["3"]["blocked_by"] == [2]
    assert result["3"]["blocks"] == [4]
    assert result["3"]["plan"] is None

    assert result["4"]["blocks"] == []
    assert result["4"]["blocked_by"] == [3]
    assert result["4"]["plan"] == "tasks/x.md"

    assert result["1"]["blocks"] == []


def test_load_plans_follows_a_custom_plan_pattern(tmp_path):
    (tmp_path / "plans" / "fare-schema").mkdir(parents=True)
    (tmp_path / "plans" / "fare-schema" / "plan.md").write_text("---\ncloses: 7\n---\n")
    (tmp_path / "plans" / "notes.md").write_text("---\ncloses: 8\n---\n")
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "old.md").write_text("---\ncloses: 9\n---\n")

    plans, warnings = load_plans(tmp_path, "plans/{slug}/plan.md")
    assert (plans, warnings) == ({7: "plans/fare-schema/plan.md"}, [])


def test_derive_uses_the_configured_ready_to_implement_and_epic_labels():
    cache = {
        "1": _issue(1, labels=["ready-to-build"]),
        "2": _issue(2, labels=["ready-to-implement"]),
        "3": _issue(3, labels=["initiative"]),
        "4": _issue(4, labels=["epic"]),
    }
    plans = {1: "tasks/a.md", 2: "tasks/b.md"}
    result = derive(
        cache, plans, ready_to_implement_label="ready-to-build", epic_label="initiative"
    )
    assert [result[k]["planned"] for k in "1234"] == [True, False, False, False]
    assert [result[k]["is_epic"] for k in "1234"] == [False, False, True, False]
    assert [result[k]["ready"] for k in "1234"] == [True, True, False, True]


def test_is_epic_prefers_the_derived_flag_over_labels():
    assert is_epic({"is_epic": True, "labels": []}) is True
    assert is_epic({"is_epic": False, "labels": ["epic"]}) is False
    assert is_epic({"labels": ["epic"]}) is True
    assert is_epic({"labels": []}) is False


def test_ensure_graph_rederives_when_the_config_changes(tmp_path):
    repo = tmp_path / "repo"
    root = repo / ".perturb"
    root.mkdir(parents=True)
    (repo / "tasks").mkdir()
    (repo / "tasks" / "p.md").write_text("---\ncloses: 1\n---\n")
    github_data = {"issues": {"1": _issue(1, labels=["ready-to-build"])}}
    (root / "github.json").write_text(json.dumps(github_data))

    assert ensure_graph(root, repo, head="abc")["issues"]["1"]["planned"] is False
    custom = Config(ready_to_implement_label="ready-to-build")
    assert ensure_graph(root, repo, head="abc", config=custom)["issues"]["1"]["planned"] is True
