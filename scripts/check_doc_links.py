"""Fail when a relative Markdown link or its #anchor does not resolve.

Checks every tracked `.md` file. External links (http, mailto) are not fetched.
"""

import re
import subprocess
import sys
from pathlib import Path

LINK = re.compile(r"\]\(([^)\s]+)\)")
CODE = re.compile(r"````.*?````|```.*?```|`[^`\n]*`", re.S)


def slug(heading: str) -> str:
    text = re.sub(r"[^\w\s-]", "", heading.strip().lower())
    return re.sub(r"\s", "-", text)


def anchors(path: Path) -> set[str]:
    found = set()
    in_fence = False
    for line in path.read_text().splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and line.startswith("#"):
            found.add(slug(line.lstrip("#")))
    return found


_SKIP_DIRS = {"tasks/friction-logs"}


def main() -> int:
    tracked = subprocess.run(
        ["git", "ls-files", "*.md"], capture_output=True, text=True, check=True
    ).stdout.split()
    problems = []
    for name in tracked:
        if any(name.startswith(d + "/") for d in _SKIP_DIRS):
            continue
        source = Path(name)
        for match in LINK.finditer(CODE.sub("", source.read_text())):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            path_part, _, anchor = target.partition("#")
            resolved = (source.parent / path_part) if path_part else source
            if not resolved.exists():
                problems.append(f"{name}: missing {target}")
            elif anchor and resolved.suffix == ".md" and anchor not in anchors(resolved):
                problems.append(f"{name}: no heading for {target}")
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
