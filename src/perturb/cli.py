"""Entry point: parses the command line and wires each verb to its module; see docs/cli.md."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

import perturb.ack as _ack_module
from perturb.adr import AdrError, migrate_adr
from perturb.areas import load_areas
from perturb.check import (
    adr_findings,
    event_findings,
    render_check,
    stale_check_findings,
    unpropagated_adr_findings,
)
from perturb.config import Config, ConfigError, load_config
from perturb.envelope import Refusal, dispatch, dispatch_gate
from perturb.events import EventStore
from perturb.github import GhTransport, GitHubError, RepoError, parse_repo_url
from perturb.graph import ensure_graph, parse_plan_closes
from perturb.graph_export import render_dot, render_graph, render_mermaid
from perturb.inbox import inbox, render_inbox
from perturb.propose import (
    _plan_areas_by_issue,
    propose,
    propose_audit,
    propose_friction,
    propose_plan,
    proposed_just_written,
    raise_no_target_issues,
    resolve_adr_path,
)
from perturb.propose import review as review_proposals
from perturb.push import push, resolve_targets, validate_detail
from perturb.queue import next_issues, ready_issues, render_next, render_ready
from perturb.refs import RefError, parse_ref
from perturb.show import render_show, show
from perturb.stale import render_stale, stale_findings
from perturb.sync import sync


def _make_parser() -> argparse.ArgumentParser:
    parent = argparse.ArgumentParser(add_help=False)
    # SUPPRESS so the subparser copy of the flag does not overwrite a value the
    # top-level parser already set: `perturb --json ref 29` and `perturb ref 29 --json`
    # both work.
    parent.add_argument(
        "--json",
        action="store_true",
        dest="json_out",
        default=argparse.SUPPRESS,
        help="print one JSON envelope instead of text",
    )

    parser = argparse.ArgumentParser(
        prog="perturb",
        parents=[parent],
        description=(
            "Planning ledger for agent-driven development: the issue graph, each issue's inbox "
            "of decisions, and a gate that fails when a plan is stale. "
            "Run `perturb <verb> --help` for a verb's options; full reference: "
            "https://github.com/geuben/perturb/blob/main/docs/cli.md"
        ),
    )
    parser.add_argument(
        "--version", action="version", version=_get_version(), help="print the version and exit"
    )

    subs = parser.add_subparsers(dest="verb", metavar="<verb>")

    def verb(group, name, summary, description=None):
        return group.add_parser(
            name, parents=[parent], help=summary, description=description or summary
        )

    by_help = "who is recorded as doing this (default: git config user.name)"

    ref_parser = verb(
        subs,
        "ref",
        "resolve a ref and print what it names",
        "Resolve a ref and print its kind and id. Local; never contacts GitHub.",
    )
    ref_parser.add_argument(
        "ref_text",
        metavar="ref",
        help="29 or '#29', adr:NNNN, plan:<slug> or a plan path, friction:<slug>, audit:<slug>, "
        "area:<slug>",
    )

    sync_parser = verb(
        subs,
        "sync",
        "sync issues from GitHub into the local cache",
        "Fetch issues, sub-issues and blocked-by links into .perturb/, and record an unblock "
        "event for each blocker that closed. Other verbs that read the graph sync first.",
    )
    sync_parser.add_argument(
        "--full",
        action="store_true",
        default=False,
        help="refetch every issue instead of only those updated since the last sync",
    )

    inbox_parser = verb(
        subs,
        "inbox",
        "list the events waiting for an issue",
        "List an issue's pending events, quoting the text each event's detail points at.",
    )
    inbox_parser.add_argument("ref_text", metavar="issue", help="the issue, such as 32")
    inbox_parser.add_argument(
        "--include", choices=["proposed"], help="also list events in this status"
    )

    next_parser = verb(
        subs,
        "next",
        "list ready, unplanned issues, the ones that unblock the most first",
        "List issues that are open, not epics, unblocked and not yet planned, ordered by how "
        "many open issues each would unblock, then by number.",
    )
    next_parser.add_argument("--epic", type=int, default=None, help="only issues under this epic")
    next_parser.add_argument(
        "--limit", type=int, default=5, help="show at most this many (default 5)"
    )

    ready_parser = verb(
        subs,
        "ready",
        "list issues whose blockers are all closed",
        "List open, non-epic issues whose blockers are all closed.",
    )
    ready_parser.add_argument("--epic", type=int, default=None, help="only issues under this epic")
    ready_parser.add_argument(
        "--all",
        dest="include_all",
        action="store_true",
        default=False,
        help="also list blocked issues and what blocks them",
    )

    show_parser = verb(
        subs,
        "show",
        "show one issue or plan",
        "Show an issue's state, labels, epic, plan and blockers, or a plan's issue and "
        "declared files.",
    )
    show_parser.add_argument("ref_text", metavar="ref", help="an issue such as 32, or plan:<slug>")

    graph_parser = verb(
        subs,
        "graph",
        "draw the issue graph",
        "Print the issue graph, with epics, sub-issues and blocked-by links, as a diagram.",
    )
    graph_parser.add_argument("--epic", type=int, default=None, help="only this epic's issues")
    graph_parser.add_argument(
        "--format",
        choices=["mermaid", "dot"],
        default="mermaid",
        help="diagram format (default mermaid)",
    )

    push_parser = verb(
        subs,
        "push",
        "record an event for other issues to absorb",
        "Record a pending event from a source to one or more open issues: a decision that "
        "constrains them, a scope change, friction, or a supersession.",
    )
    push_parser.add_argument(
        "--from",
        dest="source",
        required=True,
        help="where the event comes from, such as 31, adr:0002 or plan:<slug>",
    )
    push_to_or_new = push_parser.add_mutually_exclusive_group(required=True)
    push_to_or_new.add_argument(
        "--to", nargs="+", metavar="ISSUE", help="the issues the event is for"
    )
    push_to_or_new.add_argument(
        "--new",
        dest="new_title",
        metavar="TITLE",
        help="create a GitHub issue with this title and record the event on it",
    )
    push_parser.add_argument(
        "--kind",
        choices=["decision", "scope", "friction", "supersede"],
        required=True,
        help="what kind of change the event is",
    )
    push_parser.add_argument("summary", help="the event, in one sentence")
    push_parser.add_argument(
        "--detail",
        default=None,
        metavar="PATH#ANCHOR",
        help="the text behind the event, which inbox quotes; must exist",
    )
    push_parser.add_argument("--by", dest="by", default=None, help=by_help)

    ack_parser = verb(
        subs,
        "ack",
        "record that a committed plan absorbed an issue's events",
        "Acknowledge pending events for an issue, pinning the committed version of the plan "
        "that absorbed them. The plan must be committed and its closes: must name the issue.",
    )
    ack_parser.add_argument("target", metavar="issue", help="the issue whose events these are")
    ack_parser.add_argument(
        "event_ids", nargs="*", metavar="event-id", help="the events to acknowledge, or use --all"
    )
    ack_parser.add_argument("--plan", required=True, help="the committed plan that absorbed them")
    ack_parser.add_argument("--note", required=True, help="where in the plan the events went")
    ack_parser.add_argument("--by", dest="by", default=None, help=by_help)
    ack_parser.add_argument(
        "--all",
        dest="all_pending",
        action="store_true",
        default=False,
        help="acknowledge every pending event for the issue",
    )

    stale_parser = verb(
        subs,
        "stale",
        "fail when a planned issue has events its plan hasn't absorbed",
        "Exit 1 when a planned issue has a pending event newer than its plan, or an "
        "acknowledgement made against an older version of the plan.",
    )
    stale_parser.add_argument(
        "ref_text",
        nargs="?",
        default=None,
        metavar="issue",
        help="the issue to check (default: every planned issue)",
    )

    verb(
        subs,
        "check",
        "lint the whole ledger, for CI",
        "Exit 1 on ADRs that break the format or were never propagated, pending events on "
        "closed issues, event details that no longer resolve, and stale plans.",
    )

    propose_parser = verb(
        subs,
        "propose",
        "propose events from an ADR, plan, friction log or audit",
        "Read a source and write the events it implies: pending for issues an ADR names in "
        "affects or supersedes, proposed for everything else.",
    )
    propose_parser.add_argument(
        "source_ref",
        metavar="source",
        help="adr:NNNN, plan:<slug>, friction:<slug> or audit:<slug>",
    )
    propose_parser.add_argument(
        "--review",
        action="store_true",
        default=False,
        help="accept, dismiss or skip each proposal interactively",
    )
    propose_parser.add_argument("--by", dest="by", default=None, help=by_help)

    adr_parser = verb(subs, "adr", "work with ADR files", "Work with ADR files.")
    adr_subs = adr_parser.add_subparsers(dest="adr_cmd", metavar="<command>")
    adr_migrate_parser = verb(
        adr_subs,
        "migrate",
        "rewrite a prose ADR in the structured format, in place",
        "Rewrite a prose ADR in the structured format, in place. The id comes from the "
        "filename; anything that can't be carried into the front-matter is kept or warned "
        "about.",
    )
    adr_migrate_parser.add_argument("file", help="the ADR's Markdown file")

    confirm_parser = verb(
        subs,
        "confirm",
        "promote proposed events to pending",
        "Confirm proposed events, so they count in their target's inbox and stale gate.",
    )
    confirm_parser.add_argument(
        "event_ids", nargs="*", metavar="event-id", help="the events to confirm"
    )
    confirm_parser.add_argument(
        "--source",
        dest="source",
        default=None,
        help="select the proposals from this source, such as adr:0002 (with --all)",
    )
    confirm_parser.add_argument(
        "--all",
        dest="all_selected",
        action="store_true",
        default=False,
        help="confirm every proposal selected by --source",
    )

    dismiss_parser = verb(
        subs,
        "dismiss",
        "dismiss events that don't apply to their target",
        "Dismiss events. A dismissed event is kept, so the same proposal is not raised again.",
    )
    dismiss_parser.add_argument(
        "event_ids", nargs="+", metavar="event-id", help="the events to dismiss"
    )
    dismiss_parser.add_argument("--note", dest="note", default=None, help="why they don't apply")

    verb(
        subs,
        "init",
        "set up perturb/ and ignore the .perturb/ cache",
        "Create perturb/ (areas.yaml, config.yaml, README.md, events/) and add .perturb/ to "
        ".gitignore. Never overwrites an existing file. Local; never contacts GitHub.",
    )

    return parser


def _get_version() -> str:
    from perturb import __version__

    return __version__


def _ref_error(verb, exc):
    print(f"perturb {verb}: {exc}", file=sys.stderr)
    return 2


def _handle_ref(args, warn, config):
    ref = parse_ref(args.ref_text, plan_pattern=config.plan)
    return {"ref": str(ref), "kind": ref.kind, "id": ref.id}


def _get_repo(runner):
    result = runner(["git", "config", "--get", "remote.origin.url"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RepoError(result.stderr.strip())
    return parse_repo_url(result.stdout.strip())


def _local_repo_root(repo_root):
    if repo_root is not None:
        return Path(repo_root)
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return Path(result.stdout.strip()) if result.returncode == 0 else None


def _load_repo_config(repo_root):
    if repo_root is None:
        return Config()
    try:
        return load_config(Path(repo_root) / "perturb" / "config.yaml")
    except ConfigError as exc:
        raise Refusal("config_invalid", str(exc)) from exc


def _refuse(verb, exc, json_out):
    def _handler(warn, _exc=exc):
        raise _exc

    return dispatch(verb, _handler, json_out=json_out, out=sys.stdout, err=sys.stderr)


def _resolve_roots(runner, root, repo_root):
    if root is None or repo_root is None:
        result = runner(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        if result.returncode != 0:
            raise RepoError(result.stderr.strip())
        toplevel = Path(result.stdout.strip())
        _root = Path(root) if root is not None else toplevel / ".perturb"
        _repo_root = Path(repo_root) if repo_root is not None else toplevel
    else:
        _root = Path(root)
        _repo_root = Path(repo_root)
    return _root, _repo_root


def _synced_graph(transport, root, repo_root, *, full=False):
    try:
        _root, _repo_root = _resolve_roots(transport.runner, root, repo_root)
        config = _load_repo_config(_repo_root)
        owner, name = _get_repo(transport.runner)
        events_dir = _repo_root / "perturb" / "events"
        sync_result = sync(
            _root,
            transport,
            owner=owner,
            name=name,
            full=full,
            events_dir=events_dir,
            epic_label=config.epic_label,
        )
    except RepoError as exc:
        raise Refusal("no_github_remote", str(exc)) from exc
    except GitHubError as exc:
        raise Refusal(exc.reason, exc.detail) from exc
    head = transport.runner(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    graph = ensure_graph(_root, _repo_root, head, config)
    return graph, sync_result


def main(argv: list[str] | None = None, *, transport=None, root=None, repo_root=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    parser = _make_parser()

    try:
        parsed = parser.parse_args(args)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2

    if parsed.verb is None:
        parser.print_usage(sys.stderr)
        return 2

    json_out = getattr(parsed, "json_out", False)

    if parsed.verb == "ref":
        try:
            ref_config = _load_repo_config(_local_repo_root(repo_root))
        except Refusal as exc:
            return _refuse("ref", exc, json_out)
        try:
            return dispatch(
                "ref",
                lambda warn: _handle_ref(parsed, warn, ref_config),
                json_out=json_out,
                out=sys.stdout,
                err=sys.stderr,
            )
        except RefError as exc:
            return _ref_error("ref", exc)

    if parsed.verb == "sync":
        _transport = transport if transport is not None else GhTransport()

        try:
            graph, sync_result = _synced_graph(_transport, root, repo_root, full=parsed.full)
        except Refusal as exc:

            def _refusal_handler(warn, _exc=exc):
                raise _exc

            return dispatch(
                "sync",
                _refusal_handler,
                json_out=json_out,
                out=sys.stdout,
                err=sys.stderr,
            )

        ready_count = sum(1 for issue in graph["issues"].values() if issue.get("ready"))

        def _sync_handler(warn):
            return {
                "fetched": sync_result.fetched,
                "issues": sync_result.total,
                "ready": ready_count,
                "synced_at": sync_result.synced_at,
            }

        return dispatch(
            "sync",
            _sync_handler,
            json_out=json_out,
            out=sys.stdout,
            err=sys.stderr,
            synced_at=sync_result.synced_at,
        )

    if parsed.verb == "next":
        _transport = transport if transport is not None else GhTransport()
        try:
            graph, sync_result = _synced_graph(_transport, root, repo_root)
        except Refusal as exc:

            def _next_refusal(warn, _exc=exc):
                raise _exc

            return dispatch(
                "next", _next_refusal, json_out=json_out, out=sys.stdout, err=sys.stderr
            )

        issues = next_issues(graph["issues"], epic=parsed.epic, limit=parsed.limit)

        def _next_handler(warn):
            return {
                "issues": [
                    {
                        "number": r["number"],
                        "title": r["title"],
                        "unblocks": r["unblocks"],
                        "epic": r["epic"],
                    }
                    for r in issues
                ]
            }

        return dispatch(
            "next",
            _next_handler,
            json_out=json_out,
            out=sys.stdout,
            err=sys.stderr,
            synced_at=sync_result.synced_at,
            render=render_next,
        )

    if parsed.verb == "ready":
        _transport = transport if transport is not None else GhTransport()
        try:
            graph, sync_result = _synced_graph(_transport, root, repo_root)
        except Refusal as exc:

            def _ready_refusal(warn, _exc=exc):
                raise _exc

            return dispatch(
                "ready", _ready_refusal, json_out=json_out, out=sys.stdout, err=sys.stderr
            )

        result = ready_issues(graph["issues"], epic=parsed.epic, include_all=parsed.include_all)

        def _ready_handler(warn):
            return {
                "ready": [
                    {
                        "number": r["number"],
                        "title": r["title"],
                        "unblocks": r["unblocks"],
                        "epic": r["epic"],
                    }
                    for r in result["ready"]
                ],
                "blocked": [
                    {
                        "number": b["number"],
                        "title": b["title"],
                        "unblocks": b["unblocks"],
                        "epic": b["epic"],
                        "open_blocked_by": b["open_blocked_by"],
                    }
                    for b in result["blocked"]
                ],
            }

        return dispatch(
            "ready",
            _ready_handler,
            json_out=json_out,
            out=sys.stdout,
            err=sys.stderr,
            synced_at=sync_result.synced_at,
            render=render_ready,
        )

    if parsed.verb == "show":
        _local_root = _local_repo_root(repo_root)
        try:
            show_config = _load_repo_config(_local_root)
        except Refusal as exc:
            return _refuse("show", exc, json_out)
        try:
            ref = parse_ref(parsed.ref_text, plan_pattern=show_config.plan)
        except RefError as exc:
            return _ref_error("show", exc)

        if ref.kind == "issue":
            _transport = transport if transport is not None else GhTransport()
            try:
                graph, sync_result = _synced_graph(_transport, root, repo_root)
            except Refusal as exc:

                def _show_sync_refusal(warn, _exc=exc):
                    raise _exc

                return dispatch(
                    "show", _show_sync_refusal, json_out=json_out, out=sys.stdout, err=sys.stderr
                )

            def _show_handler(warn):
                return show(ref, graph_issues=graph["issues"])

            return dispatch(
                "show",
                _show_handler,
                json_out=json_out,
                out=sys.stdout,
                err=sys.stderr,
                synced_at=sync_result.synced_at,
                render=render_show,
            )

        _repo_root = _local_root if _local_root is not None else Path("")

        def _show_plan_handler(warn):
            return show(ref, repo_root=_repo_root, config=show_config)

        return dispatch(
            "show",
            _show_plan_handler,
            json_out=json_out,
            out=sys.stdout,
            err=sys.stderr,
            synced_at=None,
            render=render_show,
        )

    if parsed.verb == "inbox":
        if repo_root is None:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
            )
            _repo_root = Path(result.stdout.strip())
        else:
            _repo_root = Path(repo_root)

        try:
            inbox_config = _load_repo_config(_repo_root)
        except Refusal as exc:
            return _refuse("inbox", exc, json_out)
        try:
            ref = parse_ref(parsed.ref_text, plan_pattern=inbox_config.plan)
        except RefError as exc:
            return _ref_error("inbox", exc)

        include_proposed = parsed.include == "proposed"
        events_dir = _repo_root / "perturb" / "events"

        def _inbox_handler(warn):
            inbox_result = inbox(
                events_dir, _repo_root, str(ref), include_proposed=include_proposed
            )
            for w in inbox_result["warnings"]:
                warn(w)
            return {k: v for k, v in inbox_result.items() if k != "warnings"}

        return dispatch(
            "inbox",
            _inbox_handler,
            json_out=json_out,
            out=sys.stdout,
            err=sys.stderr,
            render=render_inbox,
            synced_at=None,
        )

    if parsed.verb == "confirm":
        if repo_root is None:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
            )
            _repo_root = Path(result.stdout.strip())
        else:
            _repo_root = Path(repo_root)

        events_dir = _repo_root / "perturb" / "events"

        source = None
        if parsed.source is not None:
            try:
                confirm_config = _load_repo_config(_repo_root)
            except Refusal as exc:
                return _refuse("confirm", exc, json_out)
            try:
                source = str(parse_ref(parsed.source, plan_pattern=confirm_config.plan))
            except RefError as exc:
                return _ref_error("confirm", exc)

        def _confirm_handler(warn):
            from perturb import transitions

            return transitions.confirm(
                events_dir,
                event_ids=parsed.event_ids,
                source=source,
                all_selected=parsed.all_selected,
            )

        return dispatch(
            "confirm",
            _confirm_handler,
            json_out=json_out,
            out=sys.stdout,
            err=sys.stderr,
            synced_at=None,
        )

    if parsed.verb == "dismiss":
        _transport = transport if transport is not None else GhTransport()
        if repo_root is None:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
            )
            _repo_root = Path(result.stdout.strip())
        else:
            _repo_root = Path(repo_root)

        events_dir = _repo_root / "perturb" / "events"
        actor = _transport.runner(
            ["git", "config", "user.name"], capture_output=True, text=True
        ).stdout.strip()

        def _dismiss_handler(warn):
            from perturb import transitions

            return transitions.dismiss(
                events_dir,
                event_ids=parsed.event_ids,
                by=actor,
                note=parsed.note,
            )

        return dispatch(
            "dismiss",
            _dismiss_handler,
            json_out=json_out,
            out=sys.stdout,
            err=sys.stderr,
            synced_at=None,
        )

    if parsed.verb == "graph":
        _transport = transport if transport is not None else GhTransport()
        try:
            graph, sync_result = _synced_graph(_transport, root, repo_root)
        except Refusal as exc:

            def _graph_refusal(warn, _exc=exc):
                raise _exc

            return dispatch(
                "graph", _graph_refusal, json_out=json_out, out=sys.stdout, err=sys.stderr
            )

        def _graph_handler(warn):
            issues = graph["issues"]
            fmt = parsed.format
            epic = parsed.epic
            if fmt == "mermaid":
                text = render_mermaid(issues, epic=epic)
            else:
                text = render_dot(issues, epic=epic)
            return {"format": fmt, "text": text}

        return dispatch(
            "graph",
            _graph_handler,
            json_out=json_out,
            out=sys.stdout,
            err=sys.stderr,
            render=render_graph,
            synced_at=sync_result.synced_at,
        )

    if parsed.verb == "push":
        _transport = transport if transport is not None else GhTransport()
        try:
            graph, sync_result = _synced_graph(_transport, root, repo_root)
        except Refusal as exc:

            def _push_refusal(warn, _exc=exc):
                raise _exc

            return dispatch(
                "push", _push_refusal, json_out=json_out, out=sys.stdout, err=sys.stderr
            )

        _root, _repo_root = _resolve_roots(_transport.runner, root, repo_root)
        events_dir = _repo_root / "perturb" / "events"
        source = str(parse_ref(parsed.source, plan_pattern=_load_repo_config(_repo_root).plan))
        actor = (
            parsed.by
            if parsed.by
            else _transport.runner(
                ["git", "config", "user.name"], capture_output=True, text=True
            ).stdout.strip()
        )
        owner, name = _get_repo(_transport.runner)

        def _push_handler(warn):
            if parsed.new_title is not None:
                try:
                    new_num = _transport.create_issue(
                        owner=owner,
                        name=name,
                        title=parsed.new_title,
                        body=parsed.summary,
                    )
                except GitHubError as exc:
                    raise Refusal(exc.reason, exc.detail) from exc
                _targets = [f"#{new_num}"]
            else:
                _targets = resolve_targets(graph["issues"], parsed.to)
            if parsed.detail:
                validate_detail(_repo_root, parsed.detail)
            return push(
                events_dir,
                source=source,
                targets=_targets,
                kind=parsed.kind,
                summary=parsed.summary,
                detail=parsed.detail,
                proposed_by=actor,
            )

        return dispatch(
            "push",
            _push_handler,
            json_out=json_out,
            out=sys.stdout,
            err=sys.stderr,
            synced_at=sync_result.synced_at,
        )

    if parsed.verb == "propose":
        from perturb.adr import parse_adr

        _transport = transport if transport is not None else GhTransport()
        try:
            graph, sync_result = _synced_graph(_transport, root, repo_root)
        except Refusal as exc:

            def _propose_refusal(warn, _exc=exc):
                raise _exc

            return dispatch(
                "propose", _propose_refusal, json_out=json_out, out=sys.stdout, err=sys.stderr
            )

        _root, _repo_root = _resolve_roots(_transport.runner, root, repo_root)
        events_dir = _repo_root / "perturb" / "events"
        actor = (
            parsed.by
            if parsed.by
            else _transport.runner(
                ["git", "config", "user.name"], capture_output=True, text=True
            ).stdout.strip()
        )

        config = _load_repo_config(_repo_root)
        source_ref = parsed.source_ref
        ref = parse_ref(source_ref, plan_pattern=config.plan)

        if ref.kind == "plan":

            def _propose_handler(warn):
                result = propose_plan(
                    _repo_root,
                    events_dir,
                    ref.id,
                    graph["issues"],
                    proposed_by=actor,
                    config=config,
                )
                if parsed.review:
                    store = EventStore(events_dir)
                    proposed_events = proposed_just_written(store.load().events, result["proposed"])
                    review_proposals(store, proposed_events, read=input, write=print)
                return result

            return dispatch(
                "propose",
                _propose_handler,
                json_out=json_out,
                out=sys.stdout,
                err=sys.stderr,
                synced_at=sync_result.synced_at,
            )

        if ref.kind == "friction":

            def _propose_handler(warn):
                result = propose_friction(
                    _repo_root,
                    events_dir,
                    ref.id,
                    graph["issues"],
                    runner=_transport.runner,
                    proposed_by=actor,
                    config=config,
                )
                if parsed.review:
                    store = EventStore(events_dir)
                    proposed_events = proposed_just_written(store.load().events, result["proposed"])
                    review_proposals(store, proposed_events, read=input, write=print)
                return result

            return dispatch(
                "propose",
                _propose_handler,
                json_out=json_out,
                out=sys.stdout,
                err=sys.stderr,
                synced_at=sync_result.synced_at,
            )

        if ref.kind == "audit":

            def _propose_handler(warn):
                result = propose_audit(
                    _repo_root,
                    events_dir,
                    ref.id,
                    graph["issues"],
                    proposed_by=actor,
                    config=config,
                )
                if parsed.review:
                    store = EventStore(events_dir)
                    loaded = store.load().events
                    review_queue = proposed_just_written(loaded, result["proposed"])
                    seen = {e.id for e in review_queue}
                    for e in loaded:
                        if e.source == f"friction:{ref.id}" and e.status == "proposed":
                            if e.id not in seen:
                                seen.add(e.id)
                                review_queue.append(e)
                    review_proposals(store, review_queue, read=input, write=print)
                    if result["no_target"]:
                        owner, name = _get_repo(_transport.runner)
                        try:
                            raised = raise_no_target_issues(
                                store,
                                result["no_target"],
                                source_ref=f"audit:{ref.id}",
                                audit_rel_path=config.audit_path(ref.id),
                                proposed_by=actor,
                                create_issue=lambda title, body: _transport.create_issue(
                                    owner=owner, name=name, title=title, body=body
                                ),
                                read=input,
                                write=print,
                            )
                        except GitHubError as exc:
                            raise Refusal(exc.reason, exc.detail) from exc
                        for summary in raised["skipped"]:
                            warn(f"no target; `perturb push --new`: {summary}")
                else:
                    for entry in result.get("no_target", []):
                        warn(f"no target; `perturb push --new`: {entry['summary']}")
                return result

            return dispatch(
                "propose",
                _propose_handler,
                json_out=json_out,
                out=sys.stdout,
                err=sys.stderr,
                synced_at=sync_result.synced_at,
            )

        # adr path (unchanged)
        adr_path = resolve_adr_path(_repo_root, ref.id)
        adr = parse_adr(adr_path.read_text())
        adr_rel_path = str(adr_path.relative_to(_repo_root))

        _area_set = load_areas(_repo_root / "perturb" / "areas.yaml")
        _plan_areas = _plan_areas_by_issue(_repo_root, graph["issues"])

        def _propose_handler(warn):
            result = propose(
                events_dir,
                adr,
                graph["issues"],
                adr_rel_path=adr_rel_path,
                proposed_by=actor,
                area_set=_area_set,
                plan_areas_by_issue=_plan_areas,
            )
            if parsed.review:
                store = EventStore(events_dir)
                proposed_events = proposed_just_written(store.load().events, result["proposed"])
                review_proposals(store, proposed_events, read=input, write=print)
            return result

        return dispatch(
            "propose",
            _propose_handler,
            json_out=json_out,
            out=sys.stdout,
            err=sys.stderr,
            synced_at=sync_result.synced_at,
        )

    if parsed.verb == "ack":
        _transport = transport if transport is not None else GhTransport()

        try:
            ref = parse_ref(parsed.target)
        except RefError as exc:
            return _ref_error("ack", exc)

        if repo_root is None:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
            )
            _repo_root = Path(result.stdout.strip())
        else:
            _repo_root = Path(repo_root)

        status_result = _transport.runner(
            ["git", "status", "--porcelain", "--", parsed.plan], capture_output=True, text=True
        )
        rev_parse_result = _transport.runner(
            ["git", "rev-parse", f"HEAD:{parsed.plan}"], capture_output=True, text=True
        )
        if status_result.stdout.strip() or rev_parse_result.returncode != 0:

            def _plan_not_committed(warn):
                raise Refusal("plan_not_committed", f"{parsed.plan} is not committed and clean")

            return dispatch(
                "ack",
                _plan_not_committed,
                json_out=json_out,
                out=sys.stdout,
                err=sys.stderr,
            )
        plan_blob = rev_parse_result.stdout.strip()

        plan_text = (_repo_root / parsed.plan).read_text()
        plan_closes = parse_plan_closes(plan_text)
        if plan_closes != int(ref.id):

            def _plan_target_mismatch(warn):
                raise Refusal(
                    "plan_target_mismatch", f"{parsed.plan} closes #{plan_closes}, not #{ref.id}"
                )

            return dispatch(
                "ack",
                _plan_target_mismatch,
                json_out=json_out,
                out=sys.stdout,
                err=sys.stderr,
            )

        actor = (
            parsed.by
            if parsed.by
            else _transport.runner(
                ["git", "config", "user.name"], capture_output=True, text=True
            ).stdout.strip()
        )

        events_dir = _repo_root / "perturb" / "events"

        def _ack_handler(warn):
            return _ack_module.ack(
                events_dir,
                target=str(ref),
                event_ids=parsed.event_ids,
                all_pending=parsed.all_pending,
                plan=parsed.plan,
                plan_blob=plan_blob,
                by=actor,
                note=parsed.note,
            )

        return dispatch(
            "ack",
            _ack_handler,
            json_out=json_out,
            out=sys.stdout,
            err=sys.stderr,
            synced_at=None,
            render=_ack_module.render_ack,
        )

    if parsed.verb == "stale":
        if parsed.ref_text is not None:
            try:
                ref = parse_ref(parsed.ref_text)
            except RefError as exc:
                return _ref_error("stale", exc)
        else:
            ref = None

        _transport = transport if transport is not None else GhTransport()
        try:
            graph, sync_result = _synced_graph(_transport, root, repo_root)
        except Refusal as exc:

            def _stale_refusal(warn, _exc=exc):
                raise _exc

            return dispatch(
                "stale", _stale_refusal, json_out=json_out, out=sys.stdout, err=sys.stderr
            )

        _, _repo_root = _resolve_roots(_transport.runner, root, repo_root)
        runner = _transport.runner

        planned = []
        for issue_str, issue in graph["issues"].items():
            if not issue.get("planned"):
                continue
            plan_path = issue["plan"]
            log_result = runner(
                ["git", "log", "-1", "--format=%ct", "--", plan_path],
                capture_output=True,
                text=True,
            )
            commit_epoch_str = log_result.stdout.strip()
            if not commit_epoch_str:
                continue
            blob_result = runner(
                ["git", "rev-parse", f"HEAD:{plan_path}"],
                capture_output=True,
                text=True,
            )
            current_blob = blob_result.stdout.strip()
            if not current_blob:
                continue
            planned.append(
                {
                    "issue": int(issue_str),
                    "plan": plan_path,
                    "commit_epoch": int(commit_epoch_str),
                    "current_blob": current_blob,
                }
            )

        target = int(ref.id) if ref is not None else None
        events_dir = _repo_root / "perturb" / "events"
        events = EventStore(events_dir).load().events if events_dir.exists() else []

        findings = stale_findings(planned, events, target=target)
        return dispatch_gate(
            "stale",
            findings,
            reason="stale",
            json_out=json_out,
            out=sys.stdout,
            err=sys.stderr,
            synced_at=sync_result.synced_at,
            render=render_stale,
        )

    if parsed.verb == "check":
        _transport = transport if transport is not None else GhTransport()
        try:
            graph, sync_result = _synced_graph(_transport, root, repo_root)
        except Refusal as exc:

            def _check_refusal(warn, _exc=exc):
                raise _exc

            return dispatch(
                "check", _check_refusal, json_out=json_out, out=sys.stdout, err=sys.stderr
            )

        _, _repo_root = _resolve_roots(_transport.runner, root, repo_root)
        runner = _transport.runner

        planned = []
        for issue_str, issue in graph["issues"].items():
            if not issue.get("planned"):
                continue
            plan_path = issue["plan"]
            log_result = runner(
                ["git", "log", "-1", "--format=%ct", "--", plan_path],
                capture_output=True,
                text=True,
            )
            commit_epoch_str = log_result.stdout.strip()
            if not commit_epoch_str:
                continue
            blob_result = runner(
                ["git", "rev-parse", f"HEAD:{plan_path}"],
                capture_output=True,
                text=True,
            )
            current_blob = blob_result.stdout.strip()
            if not current_blob:
                continue
            planned.append(
                {
                    "issue": int(issue_str),
                    "plan": plan_path,
                    "commit_epoch": int(commit_epoch_str),
                    "current_blob": current_blob,
                }
            )

        events_dir = _repo_root / "perturb" / "events"
        events = EventStore(events_dir).load().events if events_dir.exists() else []

        check_findings: list = []
        area_set = load_areas(_repo_root / "perturb" / "areas.yaml")
        adr_dir = _repo_root / "docs" / "adr"
        if adr_dir.exists():
            check_findings += adr_findings(adr_dir, graph, area_set=area_set)
            check_findings += unpropagated_adr_findings(adr_dir, events)
        check_findings += event_findings(events, graph, _repo_root)
        check_findings += stale_check_findings(planned, events)

        return dispatch_gate(
            "check",
            check_findings,
            reason="check",
            json_out=json_out,
            out=sys.stdout,
            err=sys.stderr,
            synced_at=sync_result.synced_at,
            render=render_check,
        )

    if parsed.verb == "adr":
        if getattr(parsed, "adr_cmd", None) == "migrate":
            file_path = Path(parsed.file)
            m = re.match(r"^(\d+)", file_path.name)
            adr_id = int(m.group(1)) if m else 0

            def _adr_migrate_handler(warn):
                text = file_path.read_text()
                from perturb.adr import parse_adr

                try:
                    result, migrate_warnings = migrate_adr(text, adr_id=adr_id)
                    # Parse before writing: a result that doesn't parse must not replace the ADR.
                    adr_obj = parse_adr(result)
                except AdrError as exc:
                    raise Refusal(exc.reason, exc.detail) from exc
                file_path.write_text(result)
                for warning in migrate_warnings:
                    warn(warning)
                return {"path": str(file_path), "consequences": len(adr_obj.consequences)}

            return dispatch(
                "adr migrate",
                _adr_migrate_handler,
                json_out=json_out,
                out=sys.stdout,
                err=sys.stderr,
            )

    if parsed.verb == "init":
        from perturb.init import init_ledger

        def _init_handler(warn):
            if repo_root is None:
                result = subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    raise Refusal("not_a_git_repo", result.stderr.strip())
                _root = Path(result.stdout.strip())
            else:
                _root = Path(repo_root)
            return init_ledger(_root)

        return dispatch(
            "init",
            _init_handler,
            json_out=json_out,
            out=sys.stdout,
            err=sys.stderr,
            synced_at=None,
        )

    return 2
