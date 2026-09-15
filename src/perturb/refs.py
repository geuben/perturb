import re
from dataclasses import dataclass

from perturb.config import DEFAULT_PLAN_PATTERN, SLUG_PATTERN, SLUG_PLACEHOLDER, match_slug


class RefError(ValueError):
    pass


@dataclass(frozen=True)
class Ref:
    kind: str
    id: str

    def __str__(self) -> str:
        if self.kind == "issue":
            return f"#{self.id}"
        return f"{self.kind}:{self.id}"


_SLUG = SLUG_PATTERN


def _accepted_forms(plan_pattern: str) -> str:
    plan_path = plan_pattern.replace(SLUG_PLACEHOLDER, "<slug>")
    return (
        f"#29, 29, adr:0002, plan:<slug>, {plan_path}, friction:<slug>, audit:<slug>, area:<slug>"
    )


def parse_ref(text: str, *, plan_pattern: str = DEFAULT_PLAN_PATTERN) -> Ref:
    if re.fullmatch(r"#?\d+", text):
        return Ref("issue", text.lstrip("#"))
    m = re.fullmatch(r"adr:(\d+)", text)
    if m:
        return Ref("adr", m.group(1).zfill(4))
    for kind in ("plan", "friction", "audit", "area"):
        m = re.fullmatch(rf"{kind}:({_SLUG})", text)
        if m:
            return Ref(kind, m.group(1))
    slug = match_slug(plan_pattern, text)
    if slug is not None:
        return Ref("plan", slug)
    raise RefError(f"unrecognised ref {text!r}; accepted forms: {_accepted_forms(plan_pattern)}")
