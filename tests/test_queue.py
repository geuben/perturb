from perturb.queue import next_issues, ready_issues, render_next, render_ready  # noqa: F401


def _issue(
    number, *, ready=True, planned=False, epic=None, unblocks=0, blocked_by=None, state="OPEN"
):
    return {
        "number": number,
        "title": f"Issue {number}",
        "ready": ready,
        "planned": planned,
        "epic": epic,
        "unblocks": unblocks,
        "blocked_by": blocked_by or [],
        "state": state,
        "labels": [],
    }


def test_render_ready_matches_documented_layout():
    data_with_blocked = {
        "ready": [
            {"number": 5, "title": "Alpha", "unblocks": 2, "epic": 3},
        ],
        "blocked": [
            {"number": 12, "title": "Beta", "unblocks": 0, "epic": 3, "open_blocked_by": [5]},
        ],
    }
    result = render_ready(data_with_blocked)
    lines = result.splitlines()
    assert lines[0] == "issue  title  unblocks  epic"
    assert lines[1] == "#5     Alpha  2         #3"
    assert lines[2] == ""
    assert lines[3] == "Blocked"
    assert lines[4] == ""
    assert lines[5] == "#12  Beta  blocked by #5"
    assert result.endswith("\n")

    data_no_blocked = {
        "ready": [{"number": 5, "title": "Alpha", "unblocks": 2, "epic": None}],
        "blocked": [],
    }
    assert "Blocked" not in render_ready(data_no_blocked)


def test_render_next_matches_documented_layout():
    data = {
        "issues": [
            {"number": 5, "title": "Alpha", "unblocks": 2, "epic": 3},
            {"number": 12, "title": "Beta", "unblocks": 1, "epic": None},
        ]
    }
    result = render_next(data)
    lines = result.splitlines()
    assert lines[0] == "#  issue  title  unblocks  epic"
    assert lines[1] == "1  #5     Alpha  2         #3"
    assert lines[2] == "2  #12    Beta   1"
    assert result.endswith("\n")


def test_ready_issues_epic_filters_both_groups():
    issues = {
        "10": _issue(10, ready=True, epic=1, unblocks=0),
        "20": _issue(20, ready=True, epic=2, unblocks=0),
        "50": _issue(50, ready=False, state="OPEN", epic=1),
        "60": _issue(60, ready=False, state="OPEN", epic=2),
        "70": _issue(70, ready=False, state="OPEN", epic=1, blocked_by=[50]),
        "80": _issue(80, ready=False, state="OPEN", epic=2, blocked_by=[60]),
    }
    result = ready_issues(issues, epic=1, include_all=True)
    ready_nums = [i["number"] for i in result["ready"]]
    blocked_nums = [i["number"] for i in result["blocked"]]
    assert ready_nums == [10]
    assert blocked_nums == [70]


def test_ready_issues_all_appends_blocked_with_open_blockers():
    issues = {
        "10": _issue(10, ready=True, planned=False),
        "50": _issue(50, ready=False, state="OPEN"),  # open blocker
        "60": _issue(60, ready=False, state="CLOSED"),  # closed blocker
        "70": _issue(70, ready=False, blocked_by=[50, 60]),
    }
    result = ready_issues(issues, include_all=True)
    blocked = result["blocked"]
    assert len(blocked) == 1
    assert blocked[0]["number"] == 70
    assert blocked[0]["open_blocked_by"] == [50]
    assert [i["number"] for i in result["ready"]] == [10]


def test_ready_issues_includes_planned_and_no_blocked_by_default():
    issues = {
        "10": _issue(10, ready=True, planned=False, unblocks=1),
        "20": _issue(20, ready=True, planned=True, unblocks=3),
        "30": _issue(30, ready=False, planned=False),
    }
    result = ready_issues(issues)
    numbers = [i["number"] for i in result["ready"]]
    assert set(numbers) == {10, 20}
    assert numbers == [20, 10]  # ordered by -unblocks then number
    assert result["blocked"] == []


def test_next_issues_limit_defaults_to_five_and_overrides():
    issues = {str(n): _issue(n, ready=True, planned=False) for n in range(1, 8)}
    assert len(next_issues(issues)) == 5
    assert len(next_issues(issues, limit=2)) == 2


def test_next_issues_epic_filters_to_direct_children():
    issues = {
        "10": _issue(10, ready=True, planned=False, epic=1, unblocks=0),
        "20": _issue(20, ready=True, planned=False, epic=2, unblocks=0),
        "30": _issue(30, ready=True, planned=False, epic=1, unblocks=0),
    }
    result = [i["number"] for i in next_issues(issues, epic=1)]
    assert set(result) == {10, 30}
    assert 20 not in result


def test_next_issues_orders_ready_unplanned_by_unblocks_then_number():
    issues = {
        "10": _issue(10, ready=True, planned=False, unblocks=1),
        "20": _issue(20, ready=True, planned=False, unblocks=2),
        "30": _issue(30, ready=True, planned=True, unblocks=5),
        "40": _issue(40, ready=False, unblocks=3),
    }
    result = [i["number"] for i in next_issues(issues)]
    assert result == [20, 10]


def test_ready_all_skips_issues_the_graph_marked_as_epics():
    from perturb.queue import ready_issues

    def _row(number, *, is_epic, blocked_by):
        return {
            "number": number,
            "title": "t",
            "state": "OPEN",
            "ready": not blocked_by,
            "planned": False,
            "epic": None,
            "labels": ["initiative"],
            "is_epic": is_epic,
            "blocked_by": blocked_by,
            "unblocks": 0,
        }

    blocker = _row(2, is_epic=False, blocked_by=[])
    as_epic = {"1": _row(1, is_epic=True, blocked_by=[2]), "2": blocker}
    as_task = {"1": _row(1, is_epic=False, blocked_by=[2]), "2": blocker}
    assert ready_issues(as_epic, include_all=True)["blocked"] == []
    assert [b["number"] for b in ready_issues(as_task, include_all=True)["blocked"]] == [1]
