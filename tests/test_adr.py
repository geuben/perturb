import pytest

from perturb.adr import (
    Adr,
    AdrError,
    Consequence,
    migrate_adr,
    parse_adr,
    parse_supersedes_ref,
)

ADR_WELL_FORMED = """\
---
id: 2
title: Store rides at per-trip grain
status: accepted
date: 2026-09-08
supersedes: [adr:0001]
areas: [rides, rollup]
---

## Context

Some context prose.

## Decision

The decision prose.

## Consequences

```yaml
- id: volume
  text: 40000 rides per dock per year.
  kind: decision

- id: dst
  text: Local days have 46, 48 or 50 periods.
  affects: ["#27", "area:rollup"]
  kind: scope

- id: reprice
  text: Re-pricing any period against any fare plan is the same function.
  kind: decision
```
"""


def test_parses_well_formed_adr():
    adr = parse_adr(ADR_WELL_FORMED)
    assert adr == Adr(
        id=2,
        title="Store rides at per-trip grain",
        status="accepted",
        date="2026-09-08",
        supersedes=["adr:0001"],
        areas=["rides", "rollup"],
        consequences=[
            Consequence(
                id="volume",
                text="40000 rides per dock per year.",
                affects=[],
                kind="decision",
            ),
            Consequence(
                id="dst",
                text="Local days have 46, 48 or 50 periods.",
                affects=["#27", "area:rollup"],
                kind="scope",
            ),
            Consequence(
                id="reprice",
                text="Re-pricing any period against any fare plan is the same function.",
                affects=[],
                kind="decision",
            ),
        ],
    )


PROSE_ADR_CYCLE1 = """\
# ADR 0002 — Store rides at per-trip grain

**Status:** accepted · 2026-09-08

## Context

Some context prose.

## Decision

The decision prose.

## Consequences

- Data fits on a single node.
- The parser is tested by #35 upstream.
- Costs are recalculated monthly via [#13](https://github.com/x/y/issues/13).
"""


PROSE_ADR_CYCLE2 = """\
# ADR 0003 — Aggregate at dock level

**Status:** accepted · 2026-08-01

## Context

MARKER_CONTEXT: aggregation is always at the dock level.

## Decision

MARKER_DECISION: the aggregation key is (dock_id, period).

## Consequences

- Results are deterministic.
"""

PROSE_CYCLE2_BODY = (
    "## Context\n\nMARKER_CONTEXT: aggregation is always at the dock level.\n\n"
    "## Decision\n\nMARKER_DECISION: the aggregation key is (dock_id, period).\n"
)


PROSE_ADR_CYCLE3 = """\
# ADR 0004 — Use consistent grain

**Status:** accepted · 2026-08-15

## Consequences

- The system stores each ride precisely.
- The system stores each ride redundantly.
"""


PROSE_ADR_SUBSECTION = """\
# ADR 0005 — Complex consequences

**Status:** accepted · 2026-09-13

## Consequences

### Type mapping

- First outcome described.
- Second outcome described.
"""


def test_migrate_skips_subsection_headings_in_consequences():
    adr = parse_adr(migrate_adr(PROSE_ADR_SUBSECTION, adr_id=5)[0])
    texts = [c.text for c in adr.consequences]
    assert texts == ["First outcome described.", "Second outcome described."]


def test_migrate_refuses_already_structured_adr():
    with pytest.raises(AdrError) as exc_info:
        migrate_adr(ADR_WELL_FORMED, adr_id=2)
    assert exc_info.value.reason == "already_structured"


def test_migrate_dedupes_colliding_consequence_ids():
    adr = parse_adr(migrate_adr(PROSE_ADR_CYCLE3, adr_id=4)[0])
    ids = [c.id for c in adr.consequences]
    assert ids == ["the-system-stores-each-ride", "the-system-stores-each-ride-2"]


def test_migrate_preserves_context_and_decision():
    result, warnings = migrate_adr(PROSE_ADR_CYCLE2, adr_id=3)
    assert PROSE_CYCLE2_BODY in result
    assert warnings == []


def test_migrate_carries_a_whole_adr_supersedes_line():
    text = (
        "# ADR 0006 — Use DuckDB\n\n"
        "**Status:** accepted · 2026-09-10\n"
        "**Supersedes:** [ADR 0003](0003-typescript-stack.md) and ADR 4\n\n"
        "## Context\n\nPROSE.\n\n## Consequences\n\n- X happens.\n"
    )
    result, warnings = migrate_adr(text, adr_id=6)
    assert parse_adr(result).supersedes == ["adr:0003", "adr:0004"]
    assert "**Supersedes:**" not in result
    assert warnings == []


def test_migrate_keeps_and_warns_about_a_partial_supersedes_line():
    line = "**Supersedes:** the storage engine half of [ADR 0003](0003-typescript-stack.md)"
    text = (
        "# ADR 0005 — Use DuckDB\n\n"
        f"**Status:** accepted · 2026-09-10\n{line}\n\n"
        "## Context\n\nPROSE.\n\n## Consequences\n\n- X happens.\n"
    )
    result, warnings = migrate_adr(text, adr_id=5)
    assert parse_adr(result).supersedes == []
    assert line in result.split("## Context")[0]
    assert len(warnings) == 1
    assert "Supersedes" in warnings[0] and "adr:0003#" in warnings[0]


def test_migrate_keeps_preamble_prose_and_warns_about_a_status_annotation():
    text = (
        "# ADR 0003 — TypeScript stack\n\n"
        "**Status:** superseded · 2026-08-01 · **storage engine superseded by ADR 0005**\n\n"
        "> The language decision below stands.\n> Postgres does not.\n\n"
        "## Context\n\nPROSE.\n\n## Consequences\n\n- X happens.\n"
    )
    result, warnings = migrate_adr(text, adr_id=3)
    preamble = result.split("## Context")[0]
    assert "> The language decision below stands.\n> Postgres does not.\n" in preamble
    assert "**Status:**" not in result
    assert len(warnings) == 1
    assert "storage engine superseded by ADR 0005" in warnings[0]
    assert parse_adr(result).status == "superseded"


@pytest.mark.parametrize(
    "entry, expected",
    [
        ("adr:0003", (3, None)),
        ("adr:3", (3, None)),
        ("adr:0003#postgres-over-sqlite", (3, "postgres-over-sqlite")),
        ("ADR 3", None),
        ("adr:0003#", None),
        ("0003", None),
    ],
)
def test_parse_supersedes_ref(entry, expected):
    assert parse_supersedes_ref(entry) == expected


def test_migrate_roundtrips_through_parser():
    result, _warnings = migrate_adr(PROSE_ADR_CYCLE1, adr_id=2)
    adr = parse_adr(result)
    assert adr == Adr(
        id=2,
        title="Store rides at per-trip grain",
        status="accepted",
        date="2026-09-08",
        supersedes=[],
        areas=[],
        consequences=[
            Consequence(
                id="data-fits-on-a-single",
                text="Data fits on a single node.",
                affects=[],
                kind="decision",
            ),
            Consequence(
                id="the-parser-is-tested-by",
                text="The parser is tested by #35 upstream.",
                affects=["#35"],
                kind="decision",
            ),
            Consequence(
                id="costs-are-recalculated-monthly-via",
                text="Costs are recalculated monthly via [#13](https://github.com/x/y/issues/13).",
                affects=["#13"],
                kind="decision",
            ),
        ],
    )


def test_migrate_strips_a_hyphen_and_colon_adr_prefix_from_the_title():
    text = (
        "# ADR-0021: Render at the display's resolution\n\n"
        "**Status:** Accepted · 2026-09-10\n\n"
        "## Context\n\nPROSE.\n\n## Consequences\n\n- X happens.\n"
    )
    result, _warnings = migrate_adr(text, adr_id=21)
    assert parse_adr(result).title == "Render at the display's resolution"


@pytest.mark.parametrize(
    "title",
    [
        "Rollback: A/B slots with a health gate",
        "'quoted' start",
        "#1 priority - ship it",
        "yes",
        "Slint over QML — and LVGL",
    ],
)
def test_migrate_title_survives_yaml_special_characters(title):
    text = (
        f"# ADR 0008 — {title}\n\n"
        "**Status:** accepted · 2026-09-10\n\n"
        "## Context\n\nPROSE.\n\n## Consequences\n\n- X happens.\n"
    )
    result, _warnings = migrate_adr(text, adr_id=8)
    assert parse_adr(result).title == title
    assert title in result.split("---")[1], "the title stays readable, not escaped"


@pytest.mark.parametrize("follower", ["> A quote straight after the status.", "## Context"])
def test_migrate_ends_the_status_line_at_a_quote_or_heading(follower):
    text = (
        "# ADR 0021 — Resolution\n\n"
        f"**Status:** accepted · 2026-09-10\n{follower}\n\n"
        "## Context\n\nPROSE.\n\n## Consequences\n\n- X happens.\n"
    )
    result, warnings = migrate_adr(text, adr_id=21)
    assert (follower in result, warnings) == (True, [])


def test_migrate_treats_a_wrapped_status_line_as_one_annotation():
    text = (
        "# ADR 0021 — Render at the display's resolution\n\n"
        "**Status:** Accepted · 2026-09-10 · amends [ADR-0002](0002-slint.md)'s\n"
        '"2560x720 on VideoCore IV" premise · extended to physical geometry by\n'
        "[0022](0022-panel-geometry.md)\n\n"
        "> A preamble quote.\n\n"
        "## Context\n\nPROSE.\n\n## Consequences\n\n- X happens.\n"
    )
    result, warnings = migrate_adr(text, adr_id=21)
    preamble = result.split("## Context")[0]
    assert "premise" not in preamble
    assert "0022-panel-geometry.md" not in preamble
    assert "> A preamble quote." in preamble
    assert len(warnings) == 1
    assert "2560x720 on VideoCore IV" in warnings[0] and "0022-panel-geometry.md" in warnings[0]
    assert parse_adr(result).status == "accepted"


@pytest.mark.parametrize(
    "bullet, affects",
    [
        ("Recorded in [Risk #9](../hardware.md#known-risks).", []),
        ("The divider change needed a rebuild (PR #93).", []),
        ("Landed in pr #93.", []),
        ("Tightened in pull request #93, tracked by #84.", ["#84"]),
        ("Tracked by [#13](https://github.com/x/y/issues/13).", ["#13"]),
        ("See [the follow-up, #40](https://github.com/x/y/issues/40).", ["#40"]),
    ],
)
def test_migrate_only_extracts_refs_that_name_issues(bullet, affects):
    text = (
        "# ADR 0021 — Resolution\n\n"
        "**Status:** accepted · 2026-09-10\n\n"
        f"## Context\n\nPROSE.\n\n## Consequences\n\n- {bullet}\n"
    )
    adr = parse_adr(migrate_adr(text, adr_id=21)[0])
    assert adr.consequences[0].affects == affects


def test_migrate_reads_each_consequence_paragraph_as_a_consequence():
    text = (
        "# ADR 0015 — Validated config\n\n"
        "**Status:** accepted · 2026-09-09\n\n"
        "## Context\n\nPROSE.\n\n## Consequences\n\n"
        "**Gains.** Bad config is caught\non the development machine.\n\n"
        "**Costs, accepted.** A fallback theme has to exist, tracked by #40.\n\n"
        "- A trailing bullet.\n"
        "- Another bullet.\n"
    )
    adr = parse_adr(migrate_adr(text, adr_id=15)[0])
    assert [(c.text, c.affects) for c in adr.consequences] == [
        ("**Gains.** Bad config is caught on the development machine.", []),
        ("**Costs, accepted.** A fallback theme has to exist, tracked by #40.", ["#40"]),
        ("A trailing bullet.", []),
        ("Another bullet.", []),
    ]


def test_absent_frontmatter_raises():
    text = "## Context\n\nNo front-matter here.\n"
    with pytest.raises(AdrError):
        parse_adr(text)


def test_missing_required_frontmatter_field_raises():
    text = (
        "---\nid: 2\nstatus: accepted\ndate: 2026-09-08\n---\n\n"
        "## Consequences\n\n```yaml\n- id: volume\n  text: Some text.\n  kind: decision\n```\n"
    )
    with pytest.raises(AdrError):
        parse_adr(text)


def test_missing_required_consequence_field_raises():
    text = (
        "---\nid: 2\ntitle: A title\nstatus: accepted\ndate: 2026-09-08\n---\n\n"
        "## Consequences\n\n```yaml\n- id: volume\n```\n"
    )
    with pytest.raises(AdrError):
        parse_adr(text)


def test_duplicate_consequence_id_raises():
    text = (
        "---\nid: 2\ntitle: A title\nstatus: accepted\ndate: 2026-09-08\n---\n\n"
        "## Consequences\n\n```yaml\n"
        "- id: volume\n  text: First.\n  kind: decision\n\n"
        "- id: volume\n  text: Duplicate.\n  kind: decision\n```\n"
    )
    with pytest.raises(AdrError):
        parse_adr(text)


def test_consequence_kind_defaults_to_decision():
    text = (
        "---\nid: 2\ntitle: A title\nstatus: accepted\ndate: 2026-09-08\n---\n\n"
        "## Consequences\n\n```yaml\n- id: volume\n  text: Some text.\n```\n"
    )
    adr = parse_adr(text)
    assert adr.consequences[0].kind == "decision"


def test_optional_frontmatter_lists_default_empty():
    text = (
        "---\nid: 2\ntitle: A title\nstatus: accepted\ndate: 2026-09-08\n---\n\n"
        "## Consequences\n\n```yaml\n- id: volume\n  text: Some text.\n  kind: decision\n```\n"
    )
    adr = parse_adr(text)
    assert (adr.supersedes, adr.areas) == ([], [])


def test_superseded_by_is_parsed():
    text = (
        "---\nid: 2\ntitle: A title\nstatus: superseded\ndate: 2026-09-08\n"
        "superseded_by: adr:0001\n---\n\n"
        "## Consequences\n\n```yaml\n- id: v\n  text: Some text.\n  kind: decision\n```\n"
    )
    adr = parse_adr(text)
    assert adr.superseded_by == "adr:0001"


def test_no_propagation_flag_and_reason_are_parsed():
    base = (
        "---\nid: 2\ntitle: A title\nstatus: accepted\ndate: 2026-09-08\n"
        "{extra}"
        "---\n\n## Consequences\n\n```yaml\n- id: v\n  text: ok.\n  kind: decision\n```\n"
    )
    cases = {
        "absent": ("", (False, None)),
        "true_with_reason": (
            "no-propagation: true\nno-propagation-reason: prose only\n",
            (True, "prose only"),
        ),
        "yes": ("no-propagation: yes\n", (True, None)),
        "quoted_true": ('no-propagation: "true"\n', (False, None)),
        "false": ("no-propagation: false\n", (False, None)),
        "reason_only": ("no-propagation-reason: why\n", (False, "why")),
        "non_str_reason": ("no-propagation: true\nno-propagation-reason: 42\n", (True, None)),
    }
    outcome = {}
    for case, (extra_fm, _) in cases.items():
        adr = parse_adr(base.format(extra=extra_fm))
        outcome[case] = (adr.no_propagation, adr.no_propagation_reason)
    expected = {case: exp for case, (_, exp) in cases.items()}
    assert outcome == expected


_MIGRATE_TMPL = (
    "# ADR 0021 — Resolution\n\n"
    "**Status:** Accepted · 2026-09-10 · {annotation}\n\n"
    "## Context\n\nPROSE.\n\n"
    "## Consequences\n\n- X happens.\n"
)


@pytest.mark.parametrize(
    "annotation, relations",
    [
        ("amends ADR 0008", (["adr:0008"], [])),
        ("amends [ADR-0008](0008-shape.md)", (["adr:0008"], [])),
        ("Extends ADR:4 and [0005](0005-x.md)", (["adr:0004", "adr:0005"], [])),
        ("amends 8, ADR 9 & ADR-10", (["adr:0008", "adr:0009", "adr:0010"], [])),
        (
            "amends [ADR-0008](0008-shape.md) — an integration no longer solely owns the presented shape",  # noqa: E501
            (["adr:0008"], []),
        ),
        ("extends ADR 0008: adds panel geometry", (["adr:0008"], [])),
        ("amended by ADR 0021", ([], ["adr:0021"])),
        ("resolution premise amended by 0021", ([], ["adr:0021"])),
        ("extended to physical geometry by [0022](0022-panel-geometry.md)", ([], ["adr:0022"])),
        ("amends ADR 0008 · amended by ADR 0023", (["adr:0008"], ["adr:0023"])),
        # rejected forms — carry nothing
        ("amends ADR-0002's premise", ([], [])),
        ("amends ADR-0008#shape", ([], [])),
        ("amends [the shape section](0008-shape.md#shape)", ([], [])),
        ("amended by the 2024 review", ([], [])),
        ("amended in review", ([], [])),
        ("storage engine superseded by ADR 0005", ([], [])),
    ],
)
def test_migrate_carries_whole_adr_relations_from_the_status_line(annotation, relations):
    text = _MIGRATE_TMPL.format(annotation=annotation)
    migrated, _ = migrate_adr(text, adr_id=21)
    adr = parse_adr(migrated)
    assert (adr.amends, adr.amended_by) == relations


def test_amends_and_amended_by_are_parsed():
    base = (
        "---\nid: 2\ntitle: A title\nstatus: accepted\ndate: 2026-09-08\n"
        "{extra}"
        "---\n\n## Consequences\n\n```yaml\n- id: v\n  text: ok.\n  kind: decision\n```\n"
    )
    cases = {
        "absent": ("", ([], [])),
        "both": (
            'amends: ["adr:0008", "adr:0003#shape"]\namended_by: ["adr:0021"]\n',
            (["adr:0008", "adr:0003#shape"], ["adr:0021"]),
        ),
        "string_amends": ("amends: adr:0008\n", (["adr:0008"], [])),
        "string_amended_by": ("amended_by: adr:0021\n", ([], ["adr:0021"])),
        "non_str_amends": ("amends: 42\n", ([42], [])),
        "null_amends": ("amends: null\n", ([], [])),
    }
    outcome = {}
    for case, (extra_fm, _) in cases.items():
        adr = parse_adr(base.format(extra=extra_fm))
        outcome[case] = (adr.amends, adr.amended_by)
    expected = {case: exp for case, (_, exp) in cases.items()}
    assert outcome == expected


def test_non_list_consequences_raises():
    text = (
        "---\nid: 2\ntitle: A title\nstatus: accepted\ndate: 2026-09-08\n---\n\n"
        "## Consequences\n\n```yaml\nkind: mapping\ntext: not a list\n```\n"
    )
    with pytest.raises(AdrError):
        parse_adr(text)
