import re
from pathlib import Path

import yaml

from perturb.adr import classify_adr_filename, parse_supersedes_ref
from perturb.areas import load_areas, read_plan_areas
from perturb.config import Config
from perturb.envelope import Refusal
from perturb.events import EventStore
from perturb.graph import is_epic, parse_plan_closes


def _issue_num(ref):
    return ref.lstrip("#")


def _is_open_non_epic(issue):
    return issue["state"] == "OPEN" and not is_epic(issue)


def _expand_issue_ref(num, graph_issues):
    issue = graph_issues.get(num)
    if issue is None:
        return []
    if is_epic(issue):
        return [
            f"#{k}"
            for k, v in graph_issues.items()
            if v.get("epic") == issue["number"] and _is_open_non_epic(v)
        ]
    if _is_open_non_epic(issue):
        return [f"#{num}"]
    return []


def compute_candidates(
    adr, graph_issues, ack_events, *, adr_rel_path, area_set=None, plan_areas_by_issue=None
):
    candidates = []

    _plan_areas = plan_areas_by_issue if plan_areas_by_issue is not None else {}
    _csq_covered: dict[str, set] = {}

    for csq in adr.consequences:
        seen_affects = set()
        for ref in csq.affects:
            num = _issue_num(ref)
            for target in _expand_issue_ref(num, graph_issues):
                if target in seen_affects:
                    continue
                seen_affects.add(target)
                candidates.append(
                    {
                        "target": target,
                        "status": "pending",
                        "reason": "affects",
                        "kind": csq.kind,
                        "summary": csq.text,
                        "detail": f"{adr_rel_path}#{csq.id}",
                        "source": f"adr:{adr.id:04d}#{csq.id}",
                    }
                )

        seen_area: set = set()
        seen_adr_area: set = set()
        if area_set is not None:
            for ref in csq.affects:
                if not ref.startswith("area:"):
                    continue
                slug = ref[len("area:") :]
                for key in sorted(graph_issues, key=int):
                    issue = graph_issues[key]
                    if not _is_open_non_epic(issue):
                        continue
                    in_areas = area_set.in_area(
                        labels=issue.get("labels", []),
                        plan_areas=_plan_areas.get(key, []),
                    )
                    if slug not in in_areas:
                        continue
                    target = f"#{key}"
                    if target in seen_affects or target in seen_area:
                        continue
                    seen_area.add(target)
                    candidates.append(
                        {
                            "target": target,
                            "status": "proposed",
                            "reason": "area",
                            "kind": csq.kind,
                            "summary": csq.text,
                            "detail": f"{adr_rel_path}#{csq.id}",
                            "source": f"adr:{adr.id:04d}#{csq.id}",
                        }
                    )

            if not csq.affects:
                for slug in adr.areas:
                    for key in sorted(graph_issues, key=int):
                        issue = graph_issues[key]
                        if not _is_open_non_epic(issue):
                            continue
                        in_areas = area_set.in_area(
                            labels=issue.get("labels", []),
                            plan_areas=_plan_areas.get(key, []),
                        )
                        if slug not in in_areas:
                            continue
                        target = f"#{key}"
                        if target in seen_affects or target in seen_area or target in seen_adr_area:
                            continue
                        seen_adr_area.add(target)
                        candidates.append(
                            {
                                "target": target,
                                "status": "proposed",
                                "reason": "adr-area",
                                "kind": csq.kind,
                                "summary": csq.text,
                                "detail": f"{adr_rel_path}#{csq.id}",
                                "source": f"adr:{adr.id:04d}#{csq.id}",
                            }
                        )

        _csq_covered[csq.id] = seen_affects | seen_area | seen_adr_area

    # Supersedes pass: for each adr:M in adr.supersedes, find distinct targets of acked events
    # whose source is "adr:<MMMM>" or "adr:<MMMM>#...", or exactly "adr:<MMMM>#<id>" when a
    # single consequence is superseded, and emit pending supersede/supersedes
    for superseded_ref in adr.supersedes:
        parsed_ref = parse_supersedes_ref(superseded_ref)
        if parsed_ref is None:
            continue
        number, consequence_id = parsed_ref
        prefix = f"adr:{number:04d}"
        summary = adr.title
        if consequence_id is not None:
            summary = f"{adr.title} (supersedes {prefix}#{consequence_id})"
        seen_supersede = set()
        for ev in ack_events:
            if ev.status != "acknowledged":
                continue
            src = ev.source
            if consequence_id is not None:
                if src != f"{prefix}#{consequence_id}":
                    continue
            elif src != prefix and not src.startswith(prefix + "#"):
                continue
            target_num = ev.target.lstrip("#")
            issue = graph_issues.get(target_num)
            if issue is None or not _is_open_non_epic(issue):
                continue
            if ev.target in seen_supersede:
                continue
            seen_supersede.add(ev.target)
            candidates.append(
                {
                    "target": ev.target,
                    "status": "pending",
                    "reason": "supersedes",
                    "kind": "supersede",
                    "summary": summary,
                    "detail": adr_rel_path,
                    "source": f"adr:{adr.id:04d}",
                }
            )

    # Amends pass: for each adr:M in adr.amends, find distinct open non-epic targets of acked
    # events whose source is "adr:<MMMM>" or starts with "adr:<MMMM>#" (whole), or equals
    # "adr:<MMMM>#id" (anchored), and emit pending amend/amends candidates
    for amends_ref in adr.amends:
        parsed_ref = parse_supersedes_ref(amends_ref)
        if parsed_ref is None:
            continue
        number, consequence_id = parsed_ref
        prefix = f"adr:{number:04d}"
        summary = adr.title
        if consequence_id is not None:
            summary = f"{adr.title} (amends {prefix}#{consequence_id})"
        seen_amend = set()
        for ev in ack_events:
            if ev.status != "acknowledged":
                continue
            src = ev.source
            if consequence_id is not None:
                if src != f"{prefix}#{consequence_id}":
                    continue
            elif src != prefix and not src.startswith(prefix + "#"):
                continue
            target_num = ev.target.lstrip("#")
            issue = graph_issues.get(target_num)
            if issue is None or not _is_open_non_epic(issue):
                continue
            if ev.target in seen_amend:
                continue
            seen_amend.add(ev.target)
            candidates.append(
                {
                    "target": ev.target,
                    "status": "pending",
                    "reason": "amends",
                    "kind": "amend",
                    "summary": summary,
                    "detail": adr_rel_path,
                    "source": f"adr:{adr.id:04d}",
                }
            )

    # Deprecated pass: when this ADR is deprecated, target its own acknowledgers
    if adr.status == "deprecated":
        own_prefix = f"adr:{adr.id:04d}"
        seen_deprecated = set()
        for ev in ack_events:
            if ev.status != "acknowledged":
                continue
            src = ev.source
            if src != own_prefix and not src.startswith(own_prefix + "#"):
                continue
            target_num = ev.target.lstrip("#")
            issue = graph_issues.get(target_num)
            if issue is None or not _is_open_non_epic(issue):
                continue
            if ev.target in seen_deprecated:
                continue
            seen_deprecated.add(ev.target)
            candidates.append(
                {
                    "target": ev.target,
                    "status": "pending",
                    "reason": "deprecated",
                    "kind": "supersede",
                    "summary": adr.title,
                    "detail": adr_rel_path,
                    "source": own_prefix,
                }
            )

    # In-text mention pass: find #N refs in consequence text, skip already-covered targets
    for csq in adr.consequences:
        covered = _csq_covered.get(csq.id) or set()
        if not covered:
            for ref in csq.affects:
                num = _issue_num(ref)
                for target in _expand_issue_ref(num, graph_issues):
                    covered.add(target)

        seen_mentions = set()
        for m in re.finditer(r"#(\d+)", csq.text):
            num = m.group(1)
            for target in _expand_issue_ref(num, graph_issues):
                if target in covered or target in seen_mentions:
                    continue
                seen_mentions.add(target)
                candidates.append(
                    {
                        "target": target,
                        "status": "proposed",
                        "reason": "mentions",
                        "kind": csq.kind,
                        "summary": csq.text,
                        "detail": f"{adr_rel_path}#{csq.id}",
                        "source": f"adr:{adr.id:04d}#{csq.id}",
                    }
                )

    return candidates


def propose(
    events_dir,
    adr,
    graph_issues,
    *,
    adr_rel_path,
    proposed_by,
    area_set=None,
    plan_areas_by_issue=None,
    now=None,
    new_id=None,
):
    events_path = Path(events_dir)
    events_path.mkdir(parents=True, exist_ok=True)
    store = EventStore(events_path, now=now, new_id=new_id)
    ack_events = store.load().events
    candidates = compute_candidates(
        adr,
        graph_issues,
        ack_events,
        adr_rel_path=adr_rel_path,
        area_set=area_set,
        plan_areas_by_issue=plan_areas_by_issue,
    )

    created = []
    for c in candidates:
        event = store.create(
            source=c["source"],
            target=c["target"],
            kind=c["kind"],
            summary=c["summary"],
            proposed_by=proposed_by,
            reason=c["reason"],
            detail=c.get("detail"),
            status=c["status"],
        )
        created.append(
            {
                "id": event.id,
                "target": event.target,
                "reason": event.reason,
                "status": event.status,
            }
        )

    return {"proposed": created}


def resolve_adr_path(repo_root, ref_id):
    try:
        ref_int = int(ref_id)
    except ValueError:
        raise Refusal("adr_not_found", f"cannot parse ADR ref: {ref_id!r}") from None

    padded = f"{ref_int:04d}"
    matches = [
        p
        for p in sorted(Path(repo_root, "docs", "adr").glob("*.md"))
        if classify_adr_filename(p.name) == ("adr", ref_int)
    ]
    if not matches:
        raise Refusal("adr_not_found", f"no ADR file found for {padded}")
    if len(matches) > 1:
        raise Refusal("adr_ambiguous", f"multiple ADR files match {padded}: {matches}")
    return matches[0]


def proposed_just_written(events, written):
    written_ids = {w["id"] for w in written}
    return [e for e in events if e.id in written_ids and e.status == "proposed"]


def review(store, proposed, *, read, write):
    confirmed = []
    dismissed = []
    for event in proposed:
        write(f"[{event.target}] {event.summary} (reason: {event.reason})")
        response = read("> accept / dismiss / skip: ").strip().lower()
        if response in ("a", "accept"):
            store.confirm(event.id)
            confirmed.append(event.id)
        elif response in ("d", "dismiss"):
            store.dismiss(event.id, by=event.proposed_by)
            dismissed.append(event.id)
    return {"confirmed": confirmed, "dismissed": dismissed}


_SHA_RE = re.compile(r"[0-9a-f]{7,40}")


def _front_matter(text):
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}
    try:
        data = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_friction_commits(text):
    """Commit SHAs from a friction log: its front-matter `commits:` list and any rendered
    ``- `<sha>` [phase] ...`` lines, in order and without duplicates."""
    shas = [
        item.strip()
        for item in _front_matter(text).get("commits") or []
        if isinstance(item, str) and _SHA_RE.fullmatch(item.strip())
    ]
    shas += re.findall(r"^\s*-\s*`([0-9a-f]{7,40})`\s*\[", text, re.MULTILINE)
    return list(dict.fromkeys(shas))


def plan_declares_test_ids(plan_text):
    raise NotImplementedError


def read_declared_paths(plan_text):
    parts = plan_text.split("---", 2)
    if len(parts) < 3:
        return set()
    try:
        fm = yaml.safe_load(parts[1])
    except Exception:
        return set()
    if not isinstance(fm, dict):
        return set()
    paths = set()
    for item in fm.get("files", []) or []:
        paths.add(item)
    for item in fm.get("ancillary_files", []) or []:
        paths.add(item)
    for cycle in fm.get("cycles", []) or []:
        if not isinstance(cycle, dict):
            continue
        for f in cycle.get("files", []) or []:
            paths.add(f)
        for f in cycle.get("stub_expected", []) or []:
            paths.add(f)
    return paths


def files_touched_outside(shas, declared, *, runner):
    touched = set()
    for sha in shas:
        result = runner(
            ["git", "show", "--name-only", "--format=", sha],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise Refusal("friction_commits_unreachable", f"commit SHA unreachable: {sha}")
        for line in result.stdout.splitlines():
            if line.strip():
                touched.add(line.strip())
    return touched - declared


def compute_friction_candidates(
    touched_outside,
    area_set,
    graph_issues,
    plan_areas_by_issue,
    *,
    source_ref,
    source_number,
    friction_rel_path,
):
    touched_areas = area_set.touches(touched_outside)
    if not touched_areas:
        return []
    candidates = []
    for key, issue in graph_issues.items():
        if not _is_open_non_epic(issue):
            continue
        if issue.get("number") == source_number or int(key) == source_number:
            continue
        issue_areas = area_set.in_area(
            labels=issue.get("labels", []),
            plan_areas=plan_areas_by_issue.get(key, []),
        )
        overlap = issue_areas & touched_areas
        if not overlap:
            continue
        summary = (
            f"{source_ref} touched {', '.join('area:' + a for a in sorted(overlap))}"
            " outside its plan"
        )
        candidates.append(
            {
                "target": f"#{key}",
                "kind": "friction",
                "status": "proposed",
                "reason": "touches",
                "source": source_ref,
                "summary": summary,
                "detail": friction_rel_path,
            }
        )
    return candidates


def _plan_areas_by_issue(repo_root, graph_issues):
    result = {}
    for key, issue in graph_issues.items():
        plan_file = issue.get("plan")
        if plan_file:
            plan_path_issue = Path(repo_root) / plan_file
            if plan_path_issue.exists():
                result[key] = read_plan_areas(plan_path_issue.read_text())
    return result


def propose_friction(
    repo_root,
    events_dir,
    slug,
    graph_issues,
    *,
    runner,
    proposed_by,
    now=None,
    new_id=None,
    config=None,
):
    config = config or Config()
    repo_root = Path(repo_root)
    friction_rel_path = config.friction_log_path(slug)
    friction_path = repo_root / friction_rel_path
    plan_path = repo_root / config.plan_path(slug)
    if not friction_path.exists():
        raise Refusal("friction_log_not_found", f"no friction log at {friction_path}")

    log_text = friction_path.read_text()
    shas = parse_friction_commits(log_text)

    plan_text = plan_path.read_text() if plan_path.exists() else ""
    declared = read_declared_paths(plan_text)
    source_number = parse_plan_closes(plan_text) or 0

    touched_outside = files_touched_outside(shas, declared, runner=runner)
    area_set = load_areas(repo_root / "perturb" / "areas.yaml")

    plan_areas_by_issue = _plan_areas_by_issue(repo_root, graph_issues)

    source_ref = f"friction:{slug}"
    candidates = compute_friction_candidates(
        touched_outside,
        area_set,
        graph_issues,
        plan_areas_by_issue,
        source_ref=source_ref,
        source_number=source_number,
        friction_rel_path=friction_rel_path,
    )

    events_path = Path(events_dir)
    events_path.mkdir(parents=True, exist_ok=True)
    store = EventStore(events_path, now=now, new_id=new_id)

    created = []
    for c in candidates:
        event = store.create(
            source=c["source"],
            target=c["target"],
            kind=c["kind"],
            summary=c["summary"],
            proposed_by=proposed_by,
            reason=c["reason"],
            detail=c.get("detail"),
            status=c["status"],
        )
        created.append(
            {
                "id": event.id,
                "target": event.target,
                "reason": event.reason,
                "status": event.status,
            }
        )

    return {"proposed": created}


def _slugify_heading(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9 -]", "", text)
    return text.replace(" ", "-")


_DECISION_PREFIX = "Design decisions"
_SCOPE_PREFIX = "Deliberate scope cuts"
_ENTRY_RE = re.compile(r"^\s*(\d+\.|-)\s")


def parse_plan_entries(plan_text):
    entries = []
    in_section = False
    current_kind = None
    current_anchor = None
    current_lines = None
    past_frontmatter = False
    fm_count = 0

    def flush():
        if current_lines is not None and current_kind is not None:
            text = " ".join(current_lines).strip()
            if text:
                entries.append({"kind": current_kind, "anchor": current_anchor, "text": text})

    for line in plan_text.splitlines():
        if not past_frontmatter:
            if line.strip() == "---":
                fm_count += 1
                if fm_count == 2:
                    past_frontmatter = True
            continue

        if line.startswith("## "):
            flush()
            current_lines = None
            heading = line[3:].strip()
            if heading.startswith(_DECISION_PREFIX):
                in_section = True
                current_kind = "decision"
                current_anchor = _slugify_heading(heading)
            elif heading.startswith(_SCOPE_PREFIX):
                in_section = True
                current_kind = "scope"
                current_anchor = _slugify_heading(heading)
            else:
                in_section = False
                current_kind = None
                current_anchor = None
            continue

        if not in_section:
            continue

        if _ENTRY_RE.match(line):
            flush()
            text = _ENTRY_RE.sub("", line, count=1).strip()
            current_lines = [text]
        elif current_lines is not None and line.strip():
            current_lines.append(line.strip())
        elif current_lines is not None and not line.strip():
            pass  # blank lines between items are allowed

    flush()
    return entries


def compute_plan_candidates(plan_text, graph_issues, *, source_ref, source_number, plan_rel_path):
    candidates = []
    seen = set()
    for entry in parse_plan_entries(plan_text):
        text = re.sub(r"\[[^\]]*\]\(https?://[^)]*\)", "", entry["text"])
        nums = re.findall(r"#(\d+)", text)
        for num in nums:
            for target in _expand_issue_ref(num, graph_issues):
                if target == f"#{source_number}":
                    continue
                key = (target, entry["kind"])
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    {
                        "source": source_ref,
                        "target": target,
                        "kind": entry["kind"],
                        "status": "proposed",
                        "reason": "mentions",
                        "summary": text,
                        "detail": f"{plan_rel_path}#{entry['anchor']}",
                    }
                )
    return candidates


def propose_plan(
    repo_root, events_dir, slug, graph_issues, *, proposed_by, now=None, new_id=None, config=None
):
    config = config or Config()
    plan_rel_path = config.plan_path(slug)
    plan_path = Path(repo_root) / plan_rel_path
    if not plan_path.exists():
        raise Refusal("plan_not_found", f"plan file not found: {plan_path}")

    plan_text = plan_path.read_text()
    source_number = parse_plan_closes(plan_text) or 0
    source_ref = f"plan:{slug}"

    candidates = compute_plan_candidates(
        plan_text,
        graph_issues,
        source_ref=source_ref,
        source_number=source_number,
        plan_rel_path=plan_rel_path,
    )

    events_path = Path(events_dir)
    events_path.mkdir(parents=True, exist_ok=True)
    store = EventStore(events_path, now=now, new_id=new_id)

    created = []
    for c in candidates:
        event = store.create(
            source=c["source"],
            target=c["target"],
            kind=c["kind"],
            summary=c["summary"],
            proposed_by=proposed_by,
            reason=c["reason"],
            detail=c.get("detail"),
            status=c["status"],
        )
        created.append(
            {
                "id": event.id,
                "target": event.target,
                "kind": event.kind,
                "reason": event.reason,
                "status": event.status,
            }
        )

    return {"proposed": created}


_AUDIT_ITEM_RE = re.compile(
    r"^\s*- \[[ xX]\] \*\*\[(CRITICAL|PLANNING DEBT)\](?::\*\*|\*\*:?)\s*(.*)$"
)


def audit_issue_title(text, max_len=72):
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    cut = truncated.rfind(" ")
    if cut == -1:
        return truncated + "…"
    return truncated[:cut].rstrip() + "…"


def raise_no_target_issues(
    store,
    no_target,
    *,
    source_ref,
    audit_rel_path,
    proposed_by,
    create_issue,
    read,
    write,
):
    created = []
    skipped = []
    for item in no_target:
        summary = item["summary"]
        write(f"[no target] {summary}")
        answer = read("> accept (create issue) / skip: ").strip().lower()
        if answer not in ("a", "accept"):
            skipped.append(summary)
            continue
        title = audit_issue_title(summary)
        body = f"{summary}\n\nFrom `{audit_rel_path}` (`perturb propose {source_ref}`)."
        number = create_issue(title, body)
        target = f"#{number}"
        event = store.create(
            source=source_ref,
            target=target,
            kind="friction",
            summary=summary,
            proposed_by=proposed_by,
            reason="manual",
            detail=audit_rel_path,
            status="pending",
        )
        created.append({"id": event.id, "target": target, "summary": summary})
    return {"created": created, "skipped": skipped}


def parse_audit_items(audit_text):
    items = []
    current = None
    current_indent = 0
    for line in audit_text.splitlines():
        m = _AUDIT_ITEM_RE.match(line)
        if m:
            if current is not None:
                items.append(current)
            bullet_indent = len(line) - len(line.lstrip())
            current = {"level": m.group(1), "text": m.group(2).strip(), "_indent": bullet_indent}
            current_indent = bullet_indent
        elif current is not None:
            if not line.strip():
                items.append(current)
                current = None
            elif line.startswith(("-", "#", "|")):
                items.append(current)
                current = None
            else:
                stripped = line.lstrip()
                line_indent = len(line) - len(stripped)
                if line_indent > current_indent and stripped:
                    current["text"] = current["text"] + " " + stripped
    if current is not None:
        items.append(current)
    return [{"level": i["level"], "text": i["text"]} for i in items]


def compute_audit_candidates(
    audit_text,
    area_set,
    graph_issues,
    plan_areas_by_issue,
    *,
    fallback_areas,
    source_ref,
    source_number,
    audit_rel_path,
):
    items = parse_audit_items(audit_text)
    candidates = []
    no_target = []
    planning_declared = any(a.slug == "planning" for a in area_set.areas)
    for item in items:
        if item["level"] == "PLANNING DEBT":
            candidate = {
                "source": source_ref,
                "target": "area:planning",
                "kind": "friction",
                "status": "proposed",
                "reason": "area",
                "summary": item["text"],
                "detail": audit_rel_path,
            }
            if not planning_declared:
                candidate["dismiss_note"] = "area:planning not declared in perturb/areas.yaml"
            candidates.append(candidate)
            continue
        if item["level"] != "CRITICAL":
            continue
        raw_spans = re.findall(r"`([^`\s]+)`", item["text"])
        spans = [re.sub(r":\d+(-\d+)?$", "", s) for s in raw_spans]
        item_areas = area_set.touches(spans)
        if not item_areas:
            item_areas = fallback_areas
        area_targets = []
        for key in sorted(graph_issues, key=lambda k: int(k)):
            issue = graph_issues[key]
            if not _is_open_non_epic(issue):
                continue
            if issue.get("number") == source_number or int(key) == source_number:
                continue
            issue_areas = area_set.in_area(
                labels=issue.get("labels", []),
                plan_areas=plan_areas_by_issue.get(key, []),
            )
            if issue_areas & item_areas:
                area_targets.append(f"#{key}")
        stripped_text = re.sub(r"\[[^\]]*\]\(https?://[^)]*\)", "", item["text"])
        seen_mention = set()
        mention_targets = []
        for m in re.finditer(r"#(\d+)", stripped_text):
            for target in _expand_issue_ref(m.group(1), graph_issues):
                if target == f"#{source_number}":
                    continue
                if target in seen_mention:
                    continue
                seen_mention.add(target)
                mention_targets.append(target)
        for target in mention_targets:
            candidates.append(
                {
                    "source": source_ref,
                    "target": target,
                    "kind": "friction",
                    "status": "proposed",
                    "reason": "mentions",
                    "summary": item["text"],
                    "detail": audit_rel_path,
                }
            )
        item_candidates_before = len(candidates)
        for target in area_targets:
            if target not in seen_mention:
                candidates.append(
                    {
                        "source": source_ref,
                        "target": target,
                        "kind": "friction",
                        "status": "proposed",
                        "reason": "area",
                        "summary": item["text"],
                        "detail": audit_rel_path,
                    }
                )
        if len(candidates) == item_candidates_before and not mention_targets:
            no_target.append({"level": "CRITICAL", "summary": item["text"]})
    return {"candidates": candidates, "no_target": no_target}


def propose_audit(
    repo_root, events_dir, slug, graph_issues, *, proposed_by, now=None, new_id=None, config=None
):
    config = config or Config()
    repo_root = Path(repo_root)
    audit_rel_path = config.audit_path(slug)
    audit_path = repo_root / audit_rel_path
    if not audit_path.exists():
        raise Refusal("audit_not_found", f"no audit file at {audit_path}")

    audit_text = audit_path.read_text()
    plan_path = repo_root / config.plan_path(slug)
    plan_text = plan_path.read_text() if plan_path.exists() else ""
    source_number = parse_plan_closes(plan_text) or 0
    area_set = load_areas(repo_root / "perturb" / "areas.yaml")
    plan_areas_by_issue = _plan_areas_by_issue(repo_root, graph_issues)

    source_ref = f"audit:{slug}"
    plan_areas = read_plan_areas(plan_text)
    if plan_areas:
        fallback_areas = set(plan_areas)
    else:
        fallback_areas = area_set.touches(read_declared_paths(plan_text))
    result = compute_audit_candidates(
        audit_text,
        area_set,
        graph_issues,
        plan_areas_by_issue,
        fallback_areas=fallback_areas,
        source_ref=source_ref,
        source_number=source_number,
        audit_rel_path=audit_rel_path,
    )

    events_path = Path(events_dir)
    events_path.mkdir(parents=True, exist_ok=True)
    store = EventStore(events_path, now=now, new_id=new_id)

    proposed = []
    for c in result["candidates"]:
        event = store.create(
            source=c["source"],
            target=c["target"],
            kind=c["kind"],
            summary=c["summary"],
            proposed_by=proposed_by,
            reason=c["reason"],
            detail=c.get("detail"),
            status=c["status"],
        )
        if c.get("dismiss_note") and event.status == "proposed":
            event = store.dismiss(event.id, by=proposed_by, note=c["dismiss_note"])
        proposed.append(
            {
                "id": event.id,
                "target": event.target,
                "kind": event.kind,
                "reason": event.reason,
                "status": event.status,
            }
        )

    existing = store.load().events
    no_target = []
    already_raised = []
    for item in result["no_target"]:
        match = next(
            (
                e
                for e in existing
                if e.source == source_ref
                and e.kind == "friction"
                and e.reason == "manual"
                and e.summary == item["summary"]
                and e.target.startswith("#")
            ),
            None,
        )
        if match:
            already_raised.append(
                {"level": item["level"], "summary": item["summary"], "target": match.target}
            )
        else:
            no_target.append(item)

    return {"proposed": proposed, "no_target": no_target, "already_raised": already_raised}
