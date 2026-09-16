import re
from pathlib import Path

from perturb.adr import Adr, AdrError, parse_adr, parse_supersedes_ref
from perturb.areas import AreaSet
from perturb.inbox import resolve_excerpt
from perturb.refs import RefError, parse_ref
from perturb.stale import stale_findings


def adr_findings(adr_dir: Path, graph: dict, area_set: AreaSet | None = None) -> list[dict]:
    findings = []
    parsed: dict[int, Adr] = {}

    for path in sorted(adr_dir.glob("*.md")):
        try:
            adr = parse_adr(path.read_text())
        except AdrError as exc:
            findings.append(
                {
                    "kind": "adr_parse",
                    "ref": path.name,
                    "detail": str(exc),
                    "fix": f"fix the front-matter or body of {path.name}",
                }
            )
            continue
        parsed[adr.id] = adr
        m = re.match(r"(\d+)", path.name)
        if m and int(m.group(1)) != adr.id:
            findings.append(
                {
                    "kind": "filename_id_mismatch",
                    "ref": path.name,
                    "detail": f"filename number {int(m.group(1))} != front-matter id {adr.id}",
                    "fix": f"rename the file to {adr.id:04d}-*.md or update the front-matter id",
                }
            )
        if adr.status == "superseded" and not adr.superseded_by:
            findings.append(
                {
                    "kind": "superseded_no_link",
                    "ref": path.name,
                    "detail": "status is superseded but superseded_by is absent",
                    "fix": f"add superseded_by: adr:NNNN to the front-matter of {path.name}",
                }
            )
        for consequence in adr.consequences:
            for affects_entry in consequence.affects:
                try:
                    ref = parse_ref(affects_entry)
                except RefError:
                    continue
                if ref.kind == "issue" and ref.id not in graph.get("issues", {}):
                    findings.append(
                        {
                            "kind": "affects_unresolved",
                            "ref": affects_entry,
                            "detail": f"issue {affects_entry} not found in graph",
                            "fix": (
                                f"perturb sync  # then re-check, or remove "
                                f"{affects_entry} from affects"
                            ),
                        }
                    )
                elif ref.kind == "area" and area_set is not None:
                    declared = {a.slug for a in area_set.areas}
                    if ref.id not in declared:
                        findings.append(
                            {
                                "kind": "affects_unresolved",
                                "ref": affects_entry,
                                "detail": f"area {affects_entry} not declared in areas.yaml",
                                "fix": (
                                    f"add {ref.id} to perturb/areas.yaml, or remove "
                                    f"{affects_entry} from affects"
                                ),
                            }
                        )

    # Supersedes entries must name an ADR in this directory, and a consequence it has
    for adr in parsed.values():
        own = f"adr:{adr.id:04d}"
        for entry in adr.supersedes:
            target_ref = parse_supersedes_ref(entry)
            if target_ref is None:
                findings.append(
                    {
                        "kind": "supersedes_invalid",
                        "ref": str(entry),
                        "detail": f"{own} supersedes {entry!r}, not adr:NNNN or adr:NNNN#id",
                        "fix": f"write it as adr:NNNN or adr:NNNN#<consequence-id> in {own}",
                    }
                )
                continue
            number, consequence_id = target_ref
            target = parsed.get(number)
            if target is None:
                detail = f"{own} supersedes adr:{number:04d}, which is not in {adr_dir}"
            elif consequence_id is not None and consequence_id not in {
                c.id for c in target.consequences
            }:
                detail = f"adr:{number:04d} has no consequence {consequence_id!r}"
            else:
                continue
            findings.append(
                {
                    "kind": "supersedes_unresolved",
                    "ref": str(entry),
                    "detail": detail,
                    "fix": f"correct the supersedes entry {entry!r} in {own}",
                }
            )

    # Amends entries must name an ADR in this directory and an optional consequence it has
    for adr in parsed.values():
        own = f"adr:{adr.id:04d}"
        for entry in adr.amends:
            target_ref = parse_supersedes_ref(entry)
            if target_ref is None:
                findings.append(
                    {
                        "kind": "amends_invalid",
                        "ref": str(entry),
                        "detail": f"{own} amends {entry!r}, not adr:NNNN or adr:NNNN#id",
                        "fix": f"write it as adr:NNNN or adr:NNNN#<consequence-id> in {own}",
                    }
                )
                continue
            number, consequence_id = target_ref
            target = parsed.get(number)
            if target is None:
                detail = f"{own} amends adr:{number:04d}, which is not in {adr_dir}"
            elif consequence_id is not None and consequence_id not in {
                c.id for c in target.consequences
            }:
                detail = f"adr:{number:04d} has no consequence {consequence_id!r}"
            else:
                continue
            findings.append(
                {
                    "kind": "amends_unresolved",
                    "ref": str(entry),
                    "detail": detail,
                    "fix": f"correct the amends entry {entry!r} in {own}",
                }
            )

    # amended_by entries must be whole-ADR refs adr:NNNN (no consequence anchor)
    for adr in parsed.values():
        own = f"adr:{adr.id:04d}"
        for entry in adr.amended_by:
            target_ref = parse_supersedes_ref(entry)
            if target_ref is None or target_ref[1] is not None:
                findings.append(
                    {
                        "kind": "amended_by_unresolved",
                        "ref": str(entry),
                        "detail": (
                            f"{own} has amended_by {entry!r}, "
                            f"which is not adr:NNNN naming an ADR in {adr_dir}"
                        ),
                        "fix": f"write it as adr:NNNN naming the amending ADR in {own}",
                    }
                )
                continue
            number, _ = target_ref
            if parsed.get(number) is None:
                findings.append(
                    {
                        "kind": "amended_by_unresolved",
                        "ref": str(entry),
                        "detail": (
                            f"{own} has amended_by {entry!r}, "
                            f"which is not adr:NNNN naming an ADR in {adr_dir}"
                        ),
                        "fix": f"write it as adr:NNNN naming the amending ADR in {own}",
                    }
                )

    # amended_by_missing: amends entry on M requires N to list M in amended_by
    for adr in parsed.values():
        own_number = adr.id
        own = f"adr:{own_number:04d}"
        for entry in adr.amends:
            target_ref = parse_supersedes_ref(entry)
            if target_ref is None:
                continue  # already reported as amends_invalid
            number, consequence_id = target_ref
            target = parsed.get(number)
            if target is None:
                continue  # already reported as amends_unresolved
            if consequence_id is not None and consequence_id not in {
                c.id for c in target.consequences
            }:
                continue  # already reported as amends_unresolved
            target_amended_by_numbers = {
                parse_supersedes_ref(e)[0]
                for e in target.amended_by
                if parse_supersedes_ref(e) is not None and parse_supersedes_ref(e)[1] is None
            }
            if own_number not in target_amended_by_numbers:
                findings.append(
                    {
                        "kind": "amended_by_missing",
                        "ref": str(entry),
                        "detail": (
                            f"{own} amends {entry} but adr:{number:04d} "
                            f"does not list {own} in amended_by"
                        ),
                        "fix": f"add {own} to amended_by in adr:{number:04d}",
                    }
                )

    # amend_backlink: amended_by adr:M requires ADR M to have amends entry for this ADR
    for adr in parsed.values():
        own_number = adr.id
        own = f"adr:{own_number:04d}"
        for entry in adr.amended_by:
            target_ref = parse_supersedes_ref(entry)
            if target_ref is None or target_ref[1] is not None:
                continue  # already reported as amended_by_unresolved
            number, _ = target_ref
            amender = parsed.get(number)
            if amender is None:
                continue  # already reported as amended_by_unresolved
            amender_amends_numbers = {
                parse_supersedes_ref(e)[0]
                for e in amender.amends
                if parse_supersedes_ref(e) is not None
            }
            if own_number not in amender_amends_numbers:
                findings.append(
                    {
                        "kind": "amend_backlink",
                        "ref": own,
                        "detail": (
                            f"{own} has amended_by adr:{number:04d} "
                            f"but adr:{number:04d} does not amend {own}"
                        ),
                        "fix": (
                            f"add {own} or {own}#<consequence-id> "
                            f"to the amends list of adr:{number:04d}"
                        ),
                    }
                )

    # Backlink check: superseded_by target must list this ADR in its supersedes
    for adr in parsed.values():
        if not adr.superseded_by:
            continue
        try:
            target_ref = parse_ref(adr.superseded_by)
        except RefError:
            continue
        if target_ref.kind != "adr":
            continue
        target_id = int(target_ref.id)
        target = parsed.get(target_id)
        if target is None:
            continue
        expected_back = f"adr:{adr.id:04d}"
        if expected_back not in target.supersedes:
            findings.append(
                {
                    "kind": "supersede_backlink",
                    "ref": f"adr:{adr.id:04d}",
                    "detail": (
                        f"adr:{adr.id:04d} has superseded_by adr:{target_id:04d} "
                        f"but adr:{target_id:04d} does not list adr:{adr.id:04d} in supersedes"
                    ),
                    "fix": (f"add adr:{adr.id:04d} to the supersedes list of adr:{target_id:04d}"),
                }
            )

    return findings


def event_findings(events: list, graph: dict, repo_root: Path) -> list[dict]:
    findings = []
    for event in events:
        if event.detail:
            _excerpt, warning = resolve_excerpt(repo_root, event.detail)
            if warning is not None:
                findings.append(
                    {
                        "kind": "dead_anchor",
                        "ref": event.id,
                        "detail": warning,
                        "fix": f"update the detail field of event {event.id}",
                    }
                )
        if event.status == "pending":
            try:
                ref = parse_ref(event.target)
            except RefError:
                ref = None
            if (
                ref is not None
                and ref.kind == "issue"
                and graph.get("issues", {}).get(ref.id, {}).get("state") == "CLOSED"
            ):
                findings.append(
                    {
                        "kind": "pending_on_closed",
                        "ref": event.target,
                        "detail": (
                            f"event {event.id} is pending but its target {event.target} is closed"
                        ),
                        "fix": (f"perturb dismiss {event.id}  # issue {event.target} is closed"),
                    }
                )
    return findings


def stale_check_findings(planned: list, events: list) -> list[dict]:
    findings = []
    for s in stale_findings(planned, events):
        findings.append(
            {
                "kind": "stale_plan",
                "ref": f"#{s['issue']}",
                "detail": f"plan {s['plan']} has {len(s['stale_events'])} stale event(s)",
                "fix": f"perturb ack  # or update the plan for #{s['issue']}",
            }
        )
    return findings


def render_check(findings: list[dict]) -> str:
    if not findings:
        return "ok\n"
    lines = []
    for f in findings:
        lines.append(f"{f['kind']}  {f['ref']}  {f['detail']}")
        lines.append(f"  fix: {f['fix']}")
    return "\n".join(lines) + "\n"


def unpropagated_adr_findings(adr_dir: Path, events: list) -> list[dict]:
    findings = []
    for path in sorted(adr_dir.glob("*.md")):
        try:
            adr = parse_adr(path.read_text())
        except AdrError:
            continue
        if adr.status != "accepted":
            continue
        padded = f"adr:{adr.id:04d}"
        if adr.no_propagation:
            reason = adr.no_propagation_reason
            if reason is None or not reason.strip():
                findings.append(
                    {
                        "kind": "no_propagation_without_reason",
                        "ref": path.name,
                        "detail": "no-propagation: true needs a non-empty no-propagation-reason",
                        "fix": (
                            f'add no-propagation-reason: "<why>" to the front-matter of {path.name}'
                        ),
                    }
                )
            continue
        has_event = any(e.source == padded or e.source.startswith(padded + "#") for e in events)
        if not has_event:
            findings.append(
                {
                    "kind": "adr_unpropagated",
                    "ref": path.name,
                    "detail": f"accepted ADR {padded} has no events and no no-propagation flag",
                    "fix": (
                        f"perturb propose {padded}"
                        f"  # or set no-propagation: true and no-propagation-reason in {path.name}"
                    ),
                }
            )
    return findings
