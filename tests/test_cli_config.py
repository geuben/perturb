import json

from perturb.cli import main


def _config(repo, text):
    (repo / "perturb").mkdir(parents=True, exist_ok=True)
    (repo / "perturb" / "config.yaml").write_text(text)


def _result(returncode, stdout):
    class R:
        pass

    r = R()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = ""
    return r


def _node(number, *, labels=()):
    return {
        "number": number,
        "title": f"Issue {number}",
        "state": "OPEN",
        "updatedAt": "2026-09-01T00:00:00Z",
        "labels": {"nodes": [{"name": n} for n in labels]},
        "parent": None,
        "blockedBy": {"nodes": []},
        "blocking": {"nodes": []},
        "body": "",
    }


class _Transport:
    def __init__(self, nodes):
        self._nodes = nodes

    def runner(self, argv, capture_output=True, text=True):
        if argv[:3] == ["git", "config", "--get"]:
            return _result(0, "https://github.com/geuben/x\n")
        if argv == ["git", "rev-parse", "HEAD"]:
            return _result(0, "abc123\n")
        raise AssertionError(f"unexpected argv: {argv!r}")

    def graphql(self, query, variables):
        page_info = {"hasNextPage": False, "endCursor": None}
        return {"repository": {"issues": {"pageInfo": page_info, "nodes": self._nodes}}}


def test_invalid_config_refuses_with_config_invalid(tmp_path, capsys):
    _config(tmp_path, "paths:\n  plan: tasks/plan.md\n")
    code = main(["show", "plan:x", "--json"], repo_root=tmp_path)
    envelope = json.loads(capsys.readouterr().out)
    assert (code, envelope["ok"], envelope["reason"]) == (1, False, "config_invalid")
    assert "{slug}" in envelope["detail"]


def test_invalid_config_refuses_before_syncing(tmp_path, capsys):
    _config(tmp_path, "labels:\n  epic: ''\n")
    code = main(
        ["next", "--json"],
        transport=_Transport([]),
        root=tmp_path / ".perturb",
        repo_root=tmp_path,
    )
    envelope = json.loads(capsys.readouterr().out)
    assert (code, envelope["reason"]) == (1, "config_invalid")
    assert not (tmp_path / ".perturb" / "github.json").exists()


def test_ref_and_show_follow_the_configured_plan_pattern(tmp_path, capsys):
    _config(tmp_path, "paths:\n  plan: plans/{slug}/plan.md\n")
    (tmp_path / "plans" / "fare-schema").mkdir(parents=True)
    (tmp_path / "plans" / "fare-schema" / "plan.md").write_text("---\ncloses: 7\n---\n")

    assert main(["ref", "plans/fare-schema/plan.md", "--json"], repo_root=tmp_path) == 0
    assert json.loads(capsys.readouterr().out)["data"]["ref"] == "plan:fare-schema"

    assert main(["show", "plans/fare-schema/plan.md", "--json"], repo_root=tmp_path) == 0
    assert json.loads(capsys.readouterr().out)["data"]["issue"] == 7


def test_next_uses_the_configured_ready_to_implement_and_epic_labels(tmp_path, capsys):
    _config(tmp_path, "labels:\n  ready_to_implement: ready-to-build\n  epic: initiative\n")
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "p3.md").write_text("---\ncloses: 3\n---\n")
    nodes = [
        _node(1, labels=["initiative"]),
        _node(2, labels=["epic"]),
        _node(3, labels=["ready-to-build"]),
        _node(4),
    ]
    code = main(
        ["next", "--json"],
        transport=_Transport(nodes),
        root=tmp_path / ".perturb",
        repo_root=tmp_path,
    )
    issues = json.loads(capsys.readouterr().out)["data"]["issues"]
    assert code == 0
    assert [i["number"] for i in issues] == [2, 4]
