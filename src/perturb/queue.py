from perturb.graph import is_epic


def _epic_match(v, epic):
    return epic is None or v["epic"] == epic


def _fmt_row(row):
    epic = f"#{row['epic']}" if row["epic"] is not None else ""
    return [f"#{row['number']}", row["title"], str(row["unblocks"]), epic]


def _render_table(headers, rows):
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))
    lines = ["  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)).rstrip()]
    for row in rows:
        lines.append("  ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row)).rstrip())
    return lines


def next_issues(issues, *, epic=None, limit=5):
    rows = [v for v in issues.values() if v["ready"] and not v["planned"] and _epic_match(v, epic)]
    rows.sort(key=lambda r: (-r["unblocks"], r["number"]))
    return rows[:limit]


def ready_issues(issues, *, epic=None, include_all=False):
    rows = [v for v in issues.values() if v["ready"] and _epic_match(v, epic)]
    rows.sort(key=lambda r: (-r["unblocks"], r["number"]))
    blocked = []
    if include_all:
        for v in issues.values():
            if v["ready"] or is_epic(v) or v.get("state") != "OPEN":
                continue
            if not _epic_match(v, epic):
                continue
            open_blockers = [
                n for n in v["blocked_by"] if issues.get(str(n), {}).get("state", "OPEN") == "OPEN"
            ]
            if not open_blockers:
                continue
            blocked.append({**v, "open_blocked_by": open_blockers})
        blocked.sort(key=lambda r: (-r["unblocks"], r["number"]))
    return {"ready": rows, "blocked": blocked}


def render_next(data):
    headers = ["#", "issue", "title", "unblocks", "epic"]
    rows = [[str(rank)] + _fmt_row(row) for rank, row in enumerate(data["issues"], start=1)]
    return "\n".join(_render_table(headers, rows)) + "\n"


def render_ready(data):
    headers = ["issue", "title", "unblocks", "epic"]
    rows = [_fmt_row(row) for row in data["ready"]]
    lines = _render_table(headers, rows)
    if data["blocked"]:
        lines += ["", "Blocked", ""]
        for brow in data["blocked"]:
            blockers = " ".join(f"#{n}" for n in brow["open_blocked_by"])
            lines.append(f"#{brow['number']}  {brow['title']}  blocked by {blockers}")
    return "\n".join(lines) + "\n"
