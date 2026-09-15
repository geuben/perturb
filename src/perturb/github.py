import json
import os
import re
import subprocess

DEFAULT_GH = "gh"


class RepoError(ValueError):
    pass


class GitHubError(Exception):
    def __init__(self, reason, detail=""):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def parse_repo_url(url):
    url = url.rstrip("/")
    patterns = [
        r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
        r"git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        r"ssh://git@github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        m = re.match(pattern, url)
        if m:
            return m.group(1), m.group(2)
    raise RepoError(f"not a recognised GitHub remote: {url}")


def gh_command(env=None):
    """The GitHub CLI to call: `PERTURB_GH` if set and non-empty, otherwise `gh`.

    One command name or path, which must accept `gh`'s arguments. A wrapper that needs
    arguments of its own belongs in a script, so shell commands can use it too.
    """
    env = os.environ if env is None else env
    return env.get("PERTURB_GH", "").strip() or DEFAULT_GH


def build_graphql_argv(query, owner, name, after, binary=DEFAULT_GH):
    argv = [
        binary,
        "api",
        "graphql",
        "-f",
        f"query={query}",
        "-F",
        f"owner={owner}",
        "-F",
        f"name={name}",
    ]
    if after is not None:
        argv += ["-F", f"after={after}"]
    return argv


class GhTransport:
    def __init__(self, runner=None, env=None):
        self.runner = runner if runner is not None else subprocess.run
        self.binary = gh_command(env)

    def _run(self, argv):
        try:
            return self.runner(argv, capture_output=True, text=True)
        except OSError as exc:
            raise GitHubError(
                "github_unreachable",
                f"cannot run GitHub CLI {self.binary!r} ({exc.strerror or exc}); "
                "install gh or set PERTURB_GH",
            ) from None

    def graphql(self, query, variables):
        argv = build_graphql_argv(
            query,
            variables["owner"],
            variables["name"],
            variables.get("after"),
            binary=self.binary,
        )
        result = self._run(argv)
        try:
            parsed = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            if result.returncode != 0:
                raise GitHubError("github_unreachable", result.stderr.strip()) from None
            raise GitHubError("github_unreachable", "unparseable response") from None
        if result.returncode != 0:
            errors = parsed.get("errors", [])
            detail = errors[0]["message"] if errors else result.stderr.strip()
            raise GitHubError("github_error", detail)
        if "data" not in parsed:
            raise GitHubError("github_unreachable", "unparseable response")
        return parsed["data"]

    def create_issue(self, *, owner, name, title, body):
        argv = [
            self.binary,
            "issue",
            "create",
            "--repo",
            f"{owner}/{name}",
            "--title",
            title,
            "--body",
            body,
        ]
        result = self._run(argv)
        if result.returncode != 0:
            raise GitHubError("github_error", result.stderr.strip())
        url = result.stdout.strip()
        return int(url.rstrip("/").rsplit("/", 1)[-1])
