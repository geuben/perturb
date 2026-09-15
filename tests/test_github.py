import pytest

from perturb.github import (
    GhTransport,
    GitHubError,
    RepoError,
    build_graphql_argv,
    gh_command,
    parse_repo_url,
)


def test_parse_repo_url_accepts_documented_remote_forms():
    forms = [
        "https://github.com/geuben/x",
        "https://github.com/geuben/x.git",
        "git@github.com:geuben/x.git",
        "ssh://git@github.com/geuben/x.git",
        "https://github.com/geuben/x/",
        "https://github.com/geuben/x.git/",
    ]
    for url in forms:
        assert parse_repo_url(url) == ("geuben", "x"), f"failed for {url!r}"


def test_parse_repo_url_rejects_non_github_remote():
    url = "https://gitlab.com/geuben/x.git"
    with pytest.raises(RepoError, match=url):
        parse_repo_url(url)


def test_build_graphql_argv_omits_after_when_none():
    base = ["gh", "api", "graphql", "-f", "query=Q", "-F", "owner=geuben", "-F", "name=x"]
    assert build_graphql_argv("Q", "geuben", "x", None) == base
    assert build_graphql_argv("Q", "geuben", "x", "C") == base + ["-F", "after=C"]


def _recording_runner(calls):
    def fake_runner(argv, capture_output=True, text=True):
        calls.append(argv)

        class R:
            returncode = 0
            stdout = (
                "https://github.com/geuben/x/issues/7\n" if argv[1] == "issue" else '{"data": {}}'
            )
            stderr = ""

        return R()

    return fake_runner


def test_gh_command_defaults_to_gh_when_perturb_gh_is_unset_or_blank():
    assert gh_command({}) == "gh"
    assert gh_command({"PERTURB_GH": ""}) == "gh"
    assert gh_command({"PERTURB_GH": "   "}) == "gh"


def test_gh_command_uses_perturb_gh_verbatim_after_trimming():
    assert gh_command({"PERTURB_GH": "ghx"}) == "ghx"
    assert gh_command({"PERTURB_GH": " /opt/My Tools/gh-wrapper \n"}) == "/opt/My Tools/gh-wrapper"


def test_gh_command_reads_the_process_environment_by_default(monkeypatch):
    monkeypatch.setenv("PERTURB_GH", "ghx")
    assert gh_command() == "ghx"
    monkeypatch.delenv("PERTURB_GH")
    assert gh_command() == "gh"


def test_transport_calls_gh_when_perturb_gh_is_unset():
    calls = []
    transport = GhTransport(runner=_recording_runner(calls), env={})
    transport.graphql("Q", {"owner": "geuben", "name": "x", "after": None})
    transport.create_issue(owner="geuben", name="x", title="t", body="b")
    assert [argv[0] for argv in calls] == ["gh", "gh"]


def test_transport_calls_the_command_named_in_perturb_gh():
    calls = []
    transport = GhTransport(runner=_recording_runner(calls), env={"PERTURB_GH": "ghx"})
    transport.graphql("Q", {"owner": "geuben", "name": "x", "after": "C"})
    transport.create_issue(owner="geuben", name="x", title="t", body="b")
    assert calls == [
        build_graphql_argv("Q", "geuben", "x", "C", binary="ghx"),
        ["ghx", "issue", "create", "--repo", "geuben/x", "--title", "t", "--body", "b"],
    ]


def test_transport_returns_data_on_success():
    calls = []

    def fake_runner(argv, capture_output=True, text=True):
        calls.append(argv)

        class R:
            returncode = 0
            stdout = '{"data": {"repository": {"x": 1}}}'
            stderr = ""

        return R()

    transport = GhTransport(runner=fake_runner, env={})
    result = transport.graphql("Q", {"owner": "geuben", "name": "x", "after": None})
    assert result == {"repository": {"x": 1}}
    assert calls == [build_graphql_argv("Q", "geuben", "x", None)]


def _make_runner(returncode, stdout, stderr):
    def fake_runner(argv, capture_output=True, text=True):
        class R:
            pass

        r = R()
        r.returncode = returncode
        r.stdout = stdout
        r.stderr = stderr
        return r

    return fake_runner


def test_transport_create_issue_parses_number():
    calls = []

    def fake_runner(argv, capture_output=True, text=True):
        calls.append(argv)

        class R:
            returncode = 0
            stdout = "https://github.com/geuben/x/issues/42\n"
            stderr = ""

        return R()

    transport = GhTransport(runner=fake_runner, env={})
    number = transport.create_issue(owner="geuben", name="x", title="t", body="b")
    assert number == 42
    expected_argv = ["gh", "issue", "create", "--repo", "geuben/x", "--title", "t", "--body", "b"]
    assert calls == [expected_argv]


def test_transport_failure_modes_map_to_reasons():
    cases = [
        (1, '{"errors":[{"message":"Field nope"}]}', "gh: something", "github_error", "Field nope"),
        (
            1,
            "",
            "connect: network is unreachable",
            "github_unreachable",
            "connect: network is unreachable",
        ),
        (0, "not json", "", "github_unreachable", "unparseable response"),
    ]
    for returncode, stdout, stderr, expected_reason, expected_detail in cases:
        transport = GhTransport(runner=_make_runner(returncode, stdout, stderr), env={})
        with pytest.raises(GitHubError) as exc_info:
            transport.graphql("Q", {"owner": "geuben", "name": "x", "after": None})
        err = exc_info.value
        assert err.reason == expected_reason, f"wrong reason for {(returncode, stdout)!r}"
        assert err.detail == expected_detail, f"wrong detail for {(returncode, stdout)!r}"


def test_transport_create_issue_raises_github_error_on_failure():
    transport = GhTransport(runner=_make_runner(1, "", "boom\n"), env={})
    with pytest.raises(GitHubError) as exc_info:
        transport.create_issue(owner="o", name="n", title="t", body="b")
    assert (exc_info.value.reason, exc_info.value.detail) == ("github_error", "boom")


def test_transport_refuses_when_the_cli_cannot_be_run():
    def missing(argv, capture_output=True, text=True):
        raise FileNotFoundError(2, "No such file or directory", argv[0])

    transport = GhTransport(runner=missing, env={"PERTURB_GH": "no-such-gh"})
    for call in (
        lambda: transport.graphql("Q", {"owner": "o", "name": "n", "after": None}),
        lambda: transport.create_issue(owner="o", name="n", title="t", body="b"),
    ):
        with pytest.raises(GitHubError) as exc_info:
            call()
        assert exc_info.value.reason == "github_unreachable"
        assert "'no-such-gh'" in exc_info.value.detail
        assert "PERTURB_GH" in exc_info.value.detail
