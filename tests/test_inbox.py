from perturb.events import EventStore
from perturb.inbox import inbox, render_inbox, resolve_excerpt, slugify_heading


def test_slugify_heading_matches_github_anchors():
    cases = [
        ("## Consequences", "consequences"),
        ("## Design decisions (locked)", "design-decisions-locked"),
        ("### `perturb inbox <ref> [--include proposed]`", "perturb-inbox-ref---include-proposed"),
        ("# Envelope and refs", "envelope-and-refs"),
    ]
    for heading, expected in cases:
        assert slugify_heading(heading) == expected, f"slugify_heading({heading!r}) != {expected!r}"


def test_resolve_excerpt_heading_anchor_returns_section_capped(tmp_path):
    bullet_lines = [f"- item {i}" for i in range(1, 16)]
    content = "\n".join(
        [
            "## Context",
            "line one",
            "line two",
            "## Consequences",
            "",
            *bullet_lines,
            "",
            "## After",
            "last line",
        ]
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "x.md").write_text(content)

    excerpt, warning = resolve_excerpt(tmp_path, "docs/x.md#consequences")
    assert warning is None
    assert excerpt == "\n".join(bullet_lines[:12])


def test_resolve_excerpt_consequence_anchor_fenced_or_bare(tmp_path):
    bare_content = "\n".join(
        [
            "## Consequences",
            "- id: refund-grain",
            "  text: Refunds carry a grain column.",
            "- id: other",
            "  text: Something else.",
        ]
    )
    fenced_content = "\n".join(
        [
            "## Consequences",
            "```yaml",
            "- id: refund-grain",
            "  text: Refunds carry a grain column.",
            "- id: other",
            "  text: Something else.",
            "```",
        ]
    )
    (tmp_path / "bare.md").write_text(bare_content)
    (tmp_path / "fenced.md").write_text(fenced_content)

    for filename in ("bare.md", "fenced.md"):
        excerpt, warning = resolve_excerpt(tmp_path, f"{filename}#refund-grain")
        assert warning is None, f"{filename}: expected no warning"
        assert excerpt == "Refunds carry a grain column.", f"{filename}: wrong excerpt"


def test_resolve_excerpt_without_anchor_returns_file_head(tmp_path):
    all_lines = [f"line {i}" for i in range(1, 21)]
    (tmp_path / "notes.md").write_text("\n".join(all_lines))

    excerpt, warning = resolve_excerpt(tmp_path, "notes.md")
    assert warning is None
    assert excerpt == "\n".join(all_lines[:12])


def test_resolve_excerpt_failure_modes_return_warnings(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "x.md").write_text("## Context\nsome content\n")

    # missing file
    excerpt, warning = resolve_excerpt(tmp_path, "docs/missing.md")
    assert excerpt is None
    assert warning == "detail not found: docs/missing.md"

    # existing file, unknown anchor
    excerpt, warning = resolve_excerpt(tmp_path, "docs/x.md#nope")
    assert excerpt is None
    assert warning == "anchor not found: docs/x.md#nope"


def test_inbox_lists_pending_for_target_newest_first(tmp_path):
    events_dir = tmp_path / "events"
    events_dir.mkdir()
    docs = tmp_path / "docs"
    docs.mkdir()
    # two-line consequences section
    (docs / "x.md").write_text("## Consequences\n- first line\n- second line\n")

    ids = iter(["ID1", "ID2", "ID3", "ID4", "ID5"])
    times = iter(
        [
            "2026-09-01T10:00:00Z",  # T1 (e1)
            "2026-09-02T10:00:00Z",  # T2 (e2, newer)
            "2026-09-01T12:00:00Z",  # e3
            "2026-09-01T13:00:00Z",  # e4
            "2026-09-01T14:00:00Z",  # e5
            "2026-09-01T15:00:00Z",  # acknowledge timestamp
        ]
    )
    store = EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids))

    e1 = store.create(
        source="#4",
        target="#29",
        kind="decision",
        summary="e1",
        proposed_by="x",
        reason="r",
        detail="docs/x.md#consequences",
        status="pending",
    )
    e2 = store.create(
        source="#4",
        target="#29",
        kind="decision",
        summary="e2",
        proposed_by="x",
        reason="r",
        status="pending",
    )
    store.create(
        source="#4",
        target="#29",
        kind="decision",
        summary="e3",
        proposed_by="x",
        reason="r",
        status="proposed",
    )
    store.create(
        source="#4",
        target="#30",
        kind="decision",
        summary="e4",
        proposed_by="x",
        reason="r",
        status="pending",
    )
    e5 = store.create(
        source="#4",
        target="#29",
        kind="decision",
        summary="e5",
        proposed_by="x",
        reason="r",
        status="pending",
    )
    store.acknowledge(e5.id, by="x", plan="tasks/x.md", plan_blob="abc", note="")

    result = inbox(events_dir, tmp_path, "#29")
    pending_ids = [e["id"] for e in result["pending"]]
    assert pending_ids == [e2.id, e1.id], f"order wrong: {pending_ids}"
    assert result["proposed"] == []
    assert result["warnings"] == []
    assert result["pending"][1]["excerpt"] == "- first line\n- second line"


def test_inbox_include_proposed_adds_separate_list(tmp_path):
    events_dir = tmp_path / "events"
    events_dir.mkdir()

    ids = iter(["ID1", "ID2", "ID3", "ID4", "ID5"])
    times = iter(
        [
            "2026-09-01T10:00:00Z",
            "2026-09-02T10:00:00Z",
            "2026-09-01T12:00:00Z",
            "2026-09-01T13:00:00Z",
            "2026-09-01T14:00:00Z",
            "2026-09-01T15:00:00Z",
        ]
    )
    store = EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids))

    e1 = store.create(
        source="#4",
        target="#29",
        kind="decision",
        summary="e1",
        proposed_by="x",
        reason="r",
        status="pending",
    )
    e2 = store.create(
        source="#4",
        target="#29",
        kind="decision",
        summary="e2",
        proposed_by="x",
        reason="r",
        status="pending",
    )
    e3 = store.create(
        source="#4",
        target="#29",
        kind="decision",
        summary="e3",
        proposed_by="x",
        reason="r",
        status="proposed",
    )
    store.create(
        source="#4",
        target="#30",
        kind="decision",
        summary="e4",
        proposed_by="x",
        reason="r",
        status="pending",
    )
    e5 = store.create(
        source="#4",
        target="#29",
        kind="decision",
        summary="e5",
        proposed_by="x",
        reason="r",
        status="pending",
    )
    store.acknowledge(e5.id, by="x", plan="tasks/x.md", plan_blob="abc", note="")

    result = inbox(events_dir, tmp_path, "#29", include_proposed=True)
    pending_ids = [e["id"] for e in result["pending"]]
    assert pending_ids == [e2.id, e1.id]
    proposed_ids = [e["id"] for e in result["proposed"]]
    assert proposed_ids == [e3.id]


def test_inbox_collects_excerpt_warnings(tmp_path):
    events_dir = tmp_path / "events"
    events_dir.mkdir()

    ids = iter(["ID1"])
    times = iter(["2026-09-01T10:00:00Z"])
    store = EventStore(events_dir, now=lambda: next(times), new_id=lambda: next(ids))

    store.create(
        source="#4",
        target="#29",
        kind="decision",
        summary="e1",
        proposed_by="x",
        reason="r",
        detail="docs/missing.md",
        status="pending",
    )

    result = inbox(events_dir, tmp_path, "#29")
    assert result["pending"][0]["excerpt"] is None
    assert result["warnings"] == ["detail not found: docs/missing.md"]


def test_render_inbox_matches_documented_layout():
    summary = "Backfilled days remain daily-grain, marked source='logbook-backfill'"
    excerpt_lines = [
        "Backfilled days from the logbook remain daily-grain with a pre-computed split, and are",
        "marked `source='logbook-backfill'` so they are never re-priced as if they were recorded",
        "per trip.",
    ]
    data = {
        "target": "#29",
        "pending": [
            {
                "id": "01J9Q7K2M4X8",
                "kind": "decision",
                "source": "adr:0002#backfill-grain",
                "at": "2026-09-08T16:02:11Z",
                "reason": "affects",
                "summary": summary,
                "detail": "docs/adr/0002-per-trip-grain.md#consequences",
                "excerpt": "\n".join(excerpt_lines),
            }
        ],
        "proposed": [
            {
                "id": "01J9Q7K2M4X9",
                "kind": "decision",
                "source": "adr:0003",
                "at": "2026-09-09T10:00:00Z",
                "reason": "affects",
                "summary": "A proposed change",
                "detail": None,
                "excerpt": None,
            }
        ],
        "warnings": [],
    }
    expected = (
        "Inbox for #29  (1 pending, 1 proposed)\n"
        "\n"
        "[01J9Q7K2M4X8] decision from adr:0002#backfill-grain  (2026-09-08, reason: affects)\n"
        f"  {summary}\n"
        "  > Backfilled days from the logbook remain daily-grain with a pre-computed split,"
        " and are\n"
        "  > marked `source='logbook-backfill'` so they are never re-priced as if they were"
        " recorded\n"
        "  > per trip.\n"
        "  docs/adr/0002-per-trip-grain.md#consequences\n"
        "\n"
        "Proposed (1)\n"
        "\n"
        "[01J9Q7K2M4X9] decision from adr:0003  (2026-09-09, reason: affects)\n"
        "  A proposed change\n"
    )
    assert render_inbox(data) == expected
