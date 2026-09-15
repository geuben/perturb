import re
from pathlib import Path

import yaml

from perturb.events import EventStore
from perturb.refs import parse_ref


def slugify_heading(text):
    text = text.lstrip("#").strip()
    text = text.replace("`", "")
    text = text.lower()
    text = re.sub(r"[^a-z0-9 \-]", "", text)
    text = re.sub(r" +", "-", text)
    return text


def resolve_excerpt(repo_root, detail):
    if "#" in detail:
        path_part, anchor = detail.split("#", 1)
    else:
        path_part, anchor = detail, None

    file_path = Path(repo_root) / path_part
    if not file_path.exists():
        return (None, f"detail not found: {path_part}")

    lines = file_path.read_text().splitlines()

    if anchor is None:
        return ("\n".join(lines[:12]), None)

    # Rule 3: heading anchor
    target_level = 0
    section_lines = []
    in_section = False
    for line in lines:
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            if in_section:
                if level <= target_level:
                    break
            else:
                slug = slugify_heading(line)
                if slug == anchor:
                    target_level = level
                    in_section = True
                    continue
        if in_section:
            section_lines.append(line)

    if in_section:
        # strip leading/trailing blank lines
        while section_lines and not section_lines[0].strip():
            section_lines.pop(0)
        while section_lines and not section_lines[-1].strip():
            section_lines.pop()
        return ("\n".join(section_lines[:12]), None)

    # Rule 4: consequence id anchor
    excerpt = _resolve_consequence_anchor(lines, anchor)
    if excerpt is not None:
        excerpt_lines = excerpt.splitlines()
        return ("\n".join(excerpt_lines[:12]), None)

    return (None, f"anchor not found: {path_part}#{anchor}")


def _resolve_consequence_anchor(lines, anchor):
    # find ## Consequences section
    cons_start = None
    for i, line in enumerate(lines):
        if line.startswith("#") and slugify_heading(line) == "consequences":
            cons_start = i + 1
            break
    if cons_start is None:
        return None

    # collect section lines until next heading
    section = []
    for line in lines[cons_start:]:
        if line.startswith("#"):
            break
        section.append(line)

    # strip optional ```yaml fence (the only documented fenced form; bare YAML also accepted)
    text = "\n".join(section).strip()
    if text.startswith("```yaml"):
        text = text[len("```yaml") :].lstrip("\n")
        if text.endswith("```"):
            text = text[:-3].rstrip()

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None

    if not isinstance(data, list):
        return None

    for item in data:
        if isinstance(item, dict) and item.get("id") == anchor:
            return str(item.get("text", ""))

    return None


def inbox(events_dir, repo_root, target, *, include_proposed=False):
    canonical = str(parse_ref(target))
    store = EventStore(Path(events_dir))
    result = store.load()

    warnings = []
    for err in result.errors:
        warnings.append(f"unreadable event file: {err.path}")

    pending = []
    proposed = []
    for event in result.events:
        if event.target != canonical:
            continue
        if event.status == "pending":
            excerpt, warn = (None, None)
            if event.detail:
                excerpt, warn = resolve_excerpt(repo_root, event.detail)
                if warn:
                    warnings.append(warn)
            pending.append(
                {
                    "id": event.id,
                    "kind": event.kind,
                    "source": event.source,
                    "at": event.at,
                    "reason": event.reason,
                    "summary": event.summary,
                    "detail": event.detail,
                    "excerpt": excerpt,
                }
            )
        elif event.status == "proposed" and include_proposed:
            proposed.append(
                {
                    "id": event.id,
                    "kind": event.kind,
                    "source": event.source,
                    "at": event.at,
                    "reason": event.reason,
                    "summary": event.summary,
                    "detail": event.detail,
                    "excerpt": None,
                }
            )

    pending.sort(key=lambda e: (e["at"], e["id"]), reverse=True)
    if include_proposed:
        proposed.sort(key=lambda e: (e["at"], e["id"]), reverse=True)

    return {
        "target": canonical,
        "pending": pending,
        "proposed": proposed,
        "warnings": warnings,
    }


def render_inbox(data):
    target = data["target"]
    pending = data["pending"]
    proposed = data["proposed"]
    n_pending = len(pending)
    n_proposed = len(proposed)
    lines = [f"Inbox for {target}  ({n_pending} pending, {n_proposed} proposed)"]

    def _render_item(item):
        item_lines = []
        date = item["at"][:10]
        header = (
            f"[{item['id']}] {item['kind']} from {item['source']}"
            f"  ({date}, reason: {item['reason']})"
        )
        item_lines.append(header)
        item_lines.append(f"  {item['summary']}")
        if item["excerpt"]:
            for eline in item["excerpt"].splitlines():
                item_lines.append(f"  > {eline}")
        if item["detail"]:
            item_lines.append(f"  {item['detail']}")
        return item_lines

    for item in pending:
        lines.append("")
        lines.extend(_render_item(item))

    if proposed:
        lines.append("")
        lines.append(f"Proposed ({n_proposed})")
        for item in proposed:
            lines.append("")
            lines.extend(_render_item(item))

    return "\n".join(lines) + "\n"
