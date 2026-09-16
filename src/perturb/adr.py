import datetime
import json
import re
from dataclasses import dataclass, field

import yaml


class AdrError(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class Consequence:
    id: str
    text: str
    affects: list
    kind: str


@dataclass(frozen=True)
class Adr:
    id: int
    title: str
    status: str
    date: str
    supersedes: list
    areas: list
    consequences: list
    superseded_by: str | None = None
    no_propagation: bool = False
    no_propagation_reason: str | None = None
    amends: list = field(default_factory=list)
    amended_by: list = field(default_factory=list)


_SUPERSEDES_REF = re.compile(r"adr:(\d+)(?:#([A-Za-z0-9][\w.-]*))?")
_PROSE_ADR_REF = re.compile(r"\bADR[\s:-]*(\d+)", re.IGNORECASE)
_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MARKDOWN_LINK_TARGET = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_ISSUE_URL = re.compile(r"/issues/\d+")
_PULL_REQUEST_BEFORE = re.compile(r"\b(?:PR|pull request)\s*$", re.IGNORECASE)
_TITLE_PREFIX = re.compile(r"^ADR[\s-]*\d+\s*[:—–-]\s*", re.IGNORECASE)
_STATUS_SEPARATORS = " \t·•|,;—–-"
_SL_SEGMENT_SEP = re.compile(r"[·•|;]")
_SL_REASON_SEP = re.compile(r" [—–] |: ")
_SL_ADR_MATCH = re.compile(r"(?:ADR[\s:-]*)?\b(\d+)\b", re.IGNORECASE)
_SL_AMENDS_VERB = re.compile(r"^(?:amends|extends)\s+", re.IGNORECASE)
_SL_AMENDED_WORD = re.compile(r"\b(?:amended|extended)\b", re.IGNORECASE)
_SL_BY_WORD = re.compile(r"\bby\b", re.IGNORECASE)


def parse_supersedes_ref(entry) -> tuple[int, str | None] | None:
    """`adr:NNNN` → (N, None); `adr:NNNN#consequence-id` → (N, id); anything else → None."""
    if not isinstance(entry, str):
        return None
    m = _SUPERSEDES_REF.fullmatch(entry)
    if m is None:
        return None
    return int(m.group(1)), m.group(2)


def _whole_status_refs(text: str) -> list[int] | None:
    """Return ADR numbers when `text` (after MD-link stripping) is a whole status-line ref list."""
    plain = _MARKDOWN_LINK.sub(r"\1", text)
    numbers = [int(m.group(1)) for m in _SL_ADR_MATCH.finditer(plain)]
    if not numbers:
        return None
    rest = _SL_ADR_MATCH.sub("", plain)
    rest = re.sub(r"\band\b|\s|[,&]", "", rest, flags=re.IGNORECASE)
    return numbers if not rest else None


def _parse_status_relations(annotation: str) -> tuple[list[str], list[str]]:
    """Extract amends and amended_by from a status-line annotation."""
    amends_out: list[str] = []
    amended_by_out: list[str] = []
    for seg in _SL_SEGMENT_SEP.split(annotation):
        seg = seg.strip()
        if not seg:
            continue
        m = _SL_AMENDS_VERB.match(seg)
        if m:
            rest = seg[m.end():]
            text = _SL_REASON_SEP.split(rest, maxsplit=1)[0]
            numbers = _whole_status_refs(text)
            if numbers is not None:
                for n in numbers:
                    ref = f"adr:{n:04d}"
                    if ref not in amends_out:
                        amends_out.append(ref)
            continue
        if _SL_AMENDED_WORD.search(seg):
            last_by = None
            for m_by in _SL_BY_WORD.finditer(seg):
                last_by = m_by
            if last_by:
                rest = seg[last_by.end():]
                text = _SL_REASON_SEP.split(rest, maxsplit=1)[0]
                numbers = _whole_status_refs(text)
                if numbers is not None:
                    for n in numbers:
                        ref = f"adr:{n:04d}"
                        if ref not in amended_by_out:
                            amended_by_out.append(ref)
    return amends_out, amended_by_out


def _whole_adr_numbers(text: str) -> list[int] | None:
    """The ADR numbers a prose Supersedes line names, when it names nothing but whole ADRs."""
    plain = _MARKDOWN_LINK.sub(r"\1", text)
    numbers = [int(n) for n in _PROSE_ADR_REF.findall(plain)]
    rest = re.sub(r"\band\b|[,;&.\s]", "", _PROSE_ADR_REF.sub("", plain), flags=re.IGNORECASE)
    return numbers if numbers and not rest else None


def migrate_adr(text: str, adr_id: int) -> tuple[str, list[str]]:
    """Rewrite a prose ADR in the structured format. Returns the new text and warnings about
    anything that could not be carried into the front-matter."""
    if text.lstrip().startswith("---"):
        raise AdrError("already_structured", "ADR already has front-matter; not re-migrating")

    lines = text.split("\n")
    warnings: list[str] = []
    first_heading = next((i for i, line in enumerate(lines) if line.startswith("## ")), len(lines))
    carried: set[int] = set()

    # Extract title from first # heading, stripping "ADR NNNN [—–-] " prefix
    title = ""
    for i, line in enumerate(lines):
        if line.startswith("# "):
            raw = line[2:].strip()
            title = _TITLE_PREFIX.sub("", raw)
            carried.add(i)
            break

    # Extract status and date from the **Status:** line
    status = ""
    date = ""
    amends_from_status: list[str] = []
    amended_by_from_status: list[str] = []
    for i, line in enumerate(lines):
        if "**Status:**" in line:
            carried.add(i)
            rest = line.split("**Status:**", 1)[1]
            # A long status line wraps; its continuation lines are part of the annotation.
            for j in range(i + 1, first_heading):
                follow = lines[j]
                if not follow.strip() or follow.startswith((">", "**")):
                    break
                carried.add(j)
                rest += " " + follow.strip()
            m_status = re.match(r"\s*([A-Za-z]+)", rest)
            if m_status:
                status = m_status.group(1).lower()
                rest = rest[m_status.end() :]
            m_date = re.search(r"\d{4}-\d{2}-\d{2}", rest)
            if m_date:
                date = m_date.group(0)
                rest = rest[: m_date.start()] + rest[m_date.end() :]
            annotation = rest.strip(_STATUS_SEPARATORS)
            amends_from_status, amended_by_from_status = _parse_status_relations(annotation)
            if annotation:
                warnings.append(
                    f"status line annotation not carried into the front-matter: {annotation}"
                )
            break

    # Carry a **Supersedes:** line naming whole ADRs; keep any other in the body
    supersedes: list[str] = []
    for i, line in enumerate(lines[:first_heading]):
        if "**Supersedes:**" not in line:
            continue
        named = line.split("**Supersedes:**", 1)[1].strip()
        numbers = _whole_adr_numbers(named)
        if numbers is not None:
            supersedes = [f"adr:{n:04d}" for n in numbers]
            carried.add(i)
        else:
            mentioned = _PROSE_ADR_REF.search(_MARKDOWN_LINK.sub(r"\1", named))
            example = f"adr:{int(mentioned.group(1)):04d}" if mentioned else "adr:NNNN"
            warnings.append(
                f"**Supersedes:** line kept in the body, not carried into supersedes: {named}. "
                f'To supersede one consequence, add supersedes: ["{example}#<consequence-id>"]'
            )
        break

    preamble = [line for i, line in enumerate(lines[:first_heading]) if i not in carried]
    while preamble and not preamble[0].strip():
        preamble.pop(0)
    while preamble and not preamble[-1].strip():
        preamble.pop()

    # Extract the Context/Decision body (verbatim slice before ## Consequences)
    body_lines: list[str] = []
    in_body = False
    consequence_lines: list[str] = []
    in_consequences = False
    for line in lines:
        if line.startswith("## Consequences"):
            in_consequences = True
            continue
        if in_consequences and line.startswith("## "):
            break
        if in_consequences:
            consequence_lines.append(line)
            continue
        if not in_body and line.startswith("## ") and not line.startswith("## Consequences"):
            in_body = True
        if in_body:
            body_lines.append(line)

    bullets = _parse_prose_bullets(consequence_lines)

    entries = []
    seen_slugs: dict[str, int] = {}
    for bullet_text in bullets:
        affects = _issue_refs(bullet_text)
        slug = _consequence_slug(bullet_text)
        if slug in seen_slugs:
            seen_slugs[slug] += 1
            slug = f"{slug}-{seen_slugs[slug]}"
        else:
            seen_slugs[slug] = 1
        entry: dict = {"id": slug, "text": bullet_text, "kind": "decision"}
        if affects:
            entry["affects"] = affects
        entries.append(entry)

    fm = (
        f"---\nid: {adr_id}\ntitle: {json.dumps(title, ensure_ascii=False)}\nstatus: {status}\n"
        f"date: {date}\nsupersedes: {json.dumps(supersedes)}\n"
        f"amends: {json.dumps(amends_from_status)}\n"
        f"amended_by: {json.dumps(amended_by_from_status)}\nareas: []\n---\n"
    )
    body = "\n".join(body_lines).rstrip("\n") + "\n" if body_lines else ""
    if preamble:
        body = "\n".join(preamble) + "\n" + ("\n" + body if body else "")
    consequences_yaml = yaml.safe_dump(
        entries, sort_keys=False, default_flow_style=False, allow_unicode=True, width=100
    )
    return f"{fm}\n{body}\n## Consequences\n\n```yaml\n{consequences_yaml}```\n", warnings


def _parse_prose_bullets(lines: list[str]) -> list[str]:
    bullets: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("- "):
            if current:
                bullets.append(" ".join(current))
            current = [line[2:].rstrip()]
        elif line.startswith("### "):
            continue
        elif line.strip() == "":
            if current:
                bullets.append(" ".join(current))
                current = []
        else:
            # A line outside a bullet starts a paragraph: prose consequences are consequences too.
            current.append(line.strip())
    if current:
        bullets.append(" ".join(current))
    return bullets


def _issue_refs(text: str) -> list[str]:
    """The `#N` refs in a prose consequence that name issues. A ref inside a link that points
    somewhere other than an issue (`[Risk #9](../hardware.md#risks)`) is not one, and neither is
    a pull request (`PR #93`)."""
    scrubbed = _MARKDOWN_LINK_TARGET.sub(
        lambda m: m.group(1) if _ISSUE_URL.search(m.group(2)) else "", text
    )
    refs = [
        f"#{m.group(1)}"
        for m in re.finditer(r"#(\d+)", scrubbed)
        if not _PULL_REQUEST_BEFORE.search(scrubbed[: m.start()])
    ]
    return list(dict.fromkeys(refs))


def _consequence_slug(text: str) -> str:
    cleaned = re.sub(r"#\d+", "", text).lower()
    words = re.findall(r"[A-Za-z0-9]+", cleaned)[:5]
    return "-".join(words)


def parse_adr(text: str) -> Adr:
    lines = text.split("\n")
    try:
        first = lines.index("---")
        second = lines.index("---", first + 1)
    except ValueError:
        raise AdrError("bad_frontmatter", "ADR must begin with a --- front-matter block") from None
    raw_fm = "\n".join(lines[first + 1 : second])
    try:
        fm = yaml.safe_load(raw_fm)
    except yaml.YAMLError as exc:
        raise AdrError("bad_frontmatter", f"front-matter is not valid YAML: {exc}") from exc
    if not isinstance(fm, dict):
        raise AdrError("bad_frontmatter", "front-matter parsed to a non-mapping")

    for required_field in ("id", "title", "status", "date"):
        if fm.get(required_field) is None:
            raise AdrError("missing_field", f"required front-matter field '{required_field}' is absent")  # noqa: E501

    date_val = fm.get("date")
    if isinstance(date_val, datetime.date):
        date_val = str(date_val)

    consequences = _parse_consequences(lines[second + 1 :])

    r = fm.get("no-propagation-reason")

    def _as_list(val):
        if val is None:
            return []
        if isinstance(val, list):
            return val
        return [val]

    return Adr(
        id=fm.get("id"),
        title=fm.get("title"),
        status=fm.get("status"),
        date=date_val,
        supersedes=fm.get("supersedes") or [],
        areas=fm.get("areas") or [],
        consequences=consequences,
        superseded_by=fm.get("superseded_by"),
        no_propagation=fm.get("no-propagation") is True,
        no_propagation_reason=r if isinstance(r, str) else None,
        amends=_as_list(fm.get("amends")),
        amended_by=_as_list(fm.get("amended_by")),
    )


def _parse_consequences(lines: list) -> list:
    in_section = False
    section_lines = []
    for line in lines:
        if line.startswith("## Consequences"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            section_lines.append(line)

    content = "\n".join(section_lines)
    # strip optional ```yaml ... ``` fence
    stripped = content.strip()
    if stripped.startswith("```"):
        first_nl = stripped.index("\n")
        stripped = stripped[first_nl + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[: stripped.rfind("```")]

    entries = yaml.safe_load(stripped) or []
    if not isinstance(entries, list):
        raise AdrError("bad_consequences", "Consequences block must be a YAML list")
    result = []
    seen_ids: set[str] = set()
    for entry in entries:
        for required_field in ("id", "text"):
            if entry.get(required_field) is None:
                raise AdrError(
                    "missing_consequence_field",
                    f"consequence missing required field '{required_field}'",
                )
        cid = entry.get("id")
        if cid in seen_ids:
            raise AdrError(
                "duplicate_consequence_id",
                f"consequence id '{cid}' appears more than once",
            )
        seen_ids.add(cid)
        result.append(
            Consequence(
                id=entry.get("id"),
                text=entry.get("text"),
                affects=entry.get("affects") or [],
                kind=entry.get("kind", "decision"),
            )
        )
    return result
