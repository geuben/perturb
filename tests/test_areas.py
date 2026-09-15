from pathlib import Path

from perturb.areas import Area, AreaSet, load_areas, read_plan_areas


def _write_yaml(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "areas.yaml"
    p.write_text(text)
    return p


# ---------------------------------------------------------------------------
# Cycle 1: load_areas parses a well-formed areas.yaml; default issues_label
# ---------------------------------------------------------------------------


def test_load_parses_declarations_with_default_label(tmp_path):
    yaml_text = """
areas:
  ledger:
    paths:
      - src/perturb/ledger.py
      - src/perturb/ledger/**
"""
    path = _write_yaml(tmp_path, yaml_text)
    result = load_areas(path)
    assert result.errors == []
    assert len(result.areas) == 1
    area = result.areas[0]
    assert area.slug == "ledger"
    assert area.paths == ["src/perturb/ledger.py", "src/perturb/ledger/**"]
    assert area.issues_label == "area:ledger"


# ---------------------------------------------------------------------------
# Cycle 2: explicit issues_label overrides the area:<slug> default
# ---------------------------------------------------------------------------


def test_load_preserves_explicit_issues_label(tmp_path):
    yaml_text = """
areas:
  rides:
    paths:
      - docs/rides/**
    issues_label: area:rd
"""
    path = _write_yaml(tmp_path, yaml_text)
    result = load_areas(path)
    assert result.errors == []
    assert len(result.areas) == 1
    assert result.areas[0].issues_label == "area:rd"


# ---------------------------------------------------------------------------
# Cycle 3: a missing areas.yaml loads to an empty AreaSet with no error
# ---------------------------------------------------------------------------


def test_load_missing_file_is_empty(tmp_path):
    path = tmp_path / "areas.yaml"
    result = load_areas(path)
    assert result.areas == []
    assert result.errors == []


# ---------------------------------------------------------------------------
# Cycle 4: a malformed areas.yaml records an error and does not raise
# ---------------------------------------------------------------------------


def test_load_malformed_records_error(tmp_path):
    path = _write_yaml(tmp_path, "- item1\n- item2\n")
    result = load_areas(path)
    assert result.areas == []
    assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# Cycle 5: an area entry without paths is skipped; valid entries still load
# ---------------------------------------------------------------------------


def test_load_entry_without_paths_is_skipped(tmp_path):
    yaml_text = """
areas:
  ok:
    paths:
      - src/**
  bad:
    description: no paths key here
"""
    path = _write_yaml(tmp_path, yaml_text)
    result = load_areas(path)
    assert [a.slug for a in result.areas] == ["ok"]
    assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# Cycle 6: touches maps a file to an area via gitwildmatch glob semantics
# ---------------------------------------------------------------------------


def test_touches_matches_glob_forms():
    area = Area(
        slug="docs",
        paths=["docs/**", "src/perturb/*.py", "src/perturb/events.py", "migrations/*ride*"],
        issues_label="area:docs",
    )
    area_set = AreaSet(areas=[area], errors=[])

    cases = [
        ("docs/a/b.md", True),
        ("docs/x.md", True),
        ("docsX/x.md", False),
        ("src/perturb/sync.py", True),
        ("src/perturb/sub/x.py", False),
        ("migrations/003_ride.sql", True),
        ("migrations/003_fare.sql", False),
    ]
    for file, expected in cases:
        result = area_set.touches([file])
        if expected:
            assert "docs" in result, f"expected {file!r} to match 'docs'"
        else:
            assert "docs" not in result, f"expected {file!r} NOT to match 'docs'"


# ---------------------------------------------------------------------------
# Cycle 7: touches unions overlapping areas
# ---------------------------------------------------------------------------


def test_touches_returns_all_matching_areas():
    areas_area = Area(slug="areas", paths=["src/perturb/areas.py"], issues_label="area:areas")
    cli_area = Area(slug="cli", paths=["src/perturb/*.py"], issues_label="area:cli")
    area_set = AreaSet(areas=[areas_area, cli_area], errors=[])
    result = area_set.touches(["src/perturb/areas.py"])
    assert result == {"areas", "cli"}


# ---------------------------------------------------------------------------
# Cycle 8: in_area resolves an area:<slug> label via issues_label
# ---------------------------------------------------------------------------


def _label_area_set() -> AreaSet:
    return AreaSet(
        areas=[
            Area(slug="ledger", paths=[], issues_label="area:ledger"),
            Area(slug="rides", paths=[], issues_label="area:rd"),
        ],
        errors=[],
    )


def test_in_area_from_labels():
    area_set = _label_area_set()
    result = area_set.in_area(labels=["area:ledger", "area:rd", "bug"])
    assert result == {"ledger", "rides"}


# ---------------------------------------------------------------------------
# Cycle 9: in_area resolves declared plan areas and ignores undeclared names
# ---------------------------------------------------------------------------


def test_in_area_from_plan_areas():
    area_set = _label_area_set()
    result = area_set.in_area(plan_areas=["ledger", "nope"])
    assert result == {"ledger"}


# ---------------------------------------------------------------------------
# Cycle 10: read_plan_areas returns the areas list from plan front-matter
# ---------------------------------------------------------------------------


def test_read_plan_areas_parses_frontmatter():
    plan_text = "---\nareas: [fares, rollup]\ntitle: some plan\n---\n\n# body here\n"
    result = read_plan_areas(plan_text)
    assert result == ["fares", "rollup"]


# ---------------------------------------------------------------------------
# Cycle 11: read_plan_areas returns [] when front-matter or areas key absent
# ---------------------------------------------------------------------------


def test_read_plan_areas_empty_when_absent():
    no_areas_key = "---\ntitle: some plan\n---\n\n# body\n"
    assert read_plan_areas(no_areas_key) == []

    no_frontmatter = "# No front matter at all\n\nJust a body.\n"
    assert read_plan_areas(no_frontmatter) == []

    non_dict_fm = "---\n- item1\n- item2\n---\n\n# body\n"
    assert read_plan_areas(non_dict_fm) == []


# ---------------------------------------------------------------------------
# Pseudo-mutation coverage: uncovered guards
# ---------------------------------------------------------------------------


def test_load_areas_dict_with_non_dict_areas(tmp_path):
    path = _write_yaml(tmp_path, "areas:\n  - foo\n  - bar\n")
    result = load_areas(path)
    assert result.areas == []
    assert len(result.errors) == 1
