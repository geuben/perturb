def subtree(issues, epic):
    included = set()
    queue = [epic]
    while queue:
        n = queue.pop()
        if n in included:
            continue
        included.add(n)
        for issue in issues.values():
            if issue["epic"] == n:
                queue.append(issue["number"])
    return included


def render_mermaid(issues, *, epic=None):
    if epic is not None:
        included_set = subtree(issues, epic)
    else:
        included_set = {int(k) for k in issues}
    included = sorted(included_set)
    lines = ["graph TD"]
    for n in included:
        issue = issues[str(n)]
        label = issue["title"].replace('"', "&quot;")
        lines.append(f'  N{n}["#{n} {label}"]')
    for n in included:
        parent = issues[str(n)]["epic"]
        if parent is not None and parent in included_set:
            lines.append(f"  N{parent} --> N{n}")
    for n in included:
        for b in sorted(issues[str(n)]["blocks"]):
            if b in included_set:
                lines.append(f"  N{n} -->|blocks| N{b}")
    closed = [n for n in included if issues[str(n)]["state"] == "CLOSED"]
    if closed:
        lines.append("  classDef closed fill:#eee,stroke:#999,color:#999;")
        lines.append("  class " + ",".join(f"N{n}" for n in closed) + " closed;")
    return "\n".join(lines) + "\n"


def render_dot(issues, *, epic=None):
    if epic is not None:
        included_set = subtree(issues, epic)
    else:
        included_set = {int(k) for k in issues}
    included = sorted(included_set)
    lines = ["digraph perturb {"]
    for n in included:
        issue = issues[str(n)]
        label = issue["title"].replace('"', '\\"')
        if issue["state"] == "CLOSED":
            lines.append(
                f'  N{n} [label="#{n} {label}", style=dashed,'
                f' color="#999999", fontcolor="#999999"];'
            )
        else:
            lines.append(f'  N{n} [label="#{n} {label}"];')
    for n in included:
        parent = issues[str(n)]["epic"]
        if parent is not None and parent in included_set:
            lines.append(f"  N{parent} -> N{n};")
    for n in included:
        for b in sorted(issues[str(n)]["blocks"]):
            if b in included_set:
                lines.append(f'  N{n} -> N{b} [label="blocks"];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_graph(data):
    return data["text"]
