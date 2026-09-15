import pytest


def test_init_ledger_areas_template_loads_with_no_areas(tmp_path):
    from perturb.areas import AreaSet, load_areas
    from perturb.init import init_ledger

    init_ledger(tmp_path)

    assert load_areas(tmp_path / "perturb" / "areas.yaml") == AreaSet(areas=[], errors=[])


def test_init_ledger_areas_template_example_uncomments_to_a_valid_area(tmp_path):
    from perturb.areas import Area, AreaSet, load_areas
    from perturb.init import init_ledger

    init_ledger(tmp_path)

    lines = (tmp_path / "perturb" / "areas.yaml").read_text().splitlines()
    example = []
    in_example = False
    for line in lines:
        if line == "# areas:":
            in_example = True
        if in_example:
            if line == "#":
                break
            example.append(line[2:])

    (tmp_path / "example.yaml").write_text("\n".join(example) + "\n")
    assert load_areas(tmp_path / "example.yaml") == AreaSet(
        areas=[
            Area(
                slug="rides",
                paths=["src/core/rides/**", "migrations/*ride*"],
                issues_label="area:rides",
            )
        ],
        errors=[],
    )


def test_init_ledger_readme_links_design_docs_on_github(tmp_path):
    from perturb.init import init_ledger

    init_ledger(tmp_path)

    text = (tmp_path / "perturb" / "README.md").read_text()
    assert all(
        url in text
        for url in (
            "https://github.com/geuben/perturb/blob/main/docs/configuration.md",
            "https://github.com/geuben/perturb/blob/main/docs/concepts.md",
        )
    )


def test_init_ledger_creates_only_missing_entries(tmp_path):
    from perturb.init import init_ledger

    (tmp_path / "perturb").mkdir()
    original = 'areas:\n  mine:\n    paths: ["x/**"]\n'
    (tmp_path / "perturb" / "areas.yaml").write_text(original)

    result = init_ledger(tmp_path)

    assert (tmp_path / "perturb" / "areas.yaml").read_text() == original
    assert result == {
        "created": ["perturb/config.yaml", "perturb/README.md", "perturb/events/", ".gitignore"],
        "existing": ["perturb/areas.yaml"],
    }


def test_init_ledger_leaves_existing_events_dir_untouched(tmp_path):
    from perturb.init import init_ledger

    (tmp_path / "perturb").mkdir()
    (tmp_path / "perturb" / "areas.yaml").write_text("areas: {}\n")
    (tmp_path / "perturb" / "README.md").write_text("mine\n")
    (tmp_path / "perturb" / "events").mkdir()
    (tmp_path / "perturb" / "events" / "01ABC.yaml").write_text("id: 01ABC\n")

    result = init_ledger(tmp_path)

    assert result == {
        "created": ["perturb/config.yaml", ".gitignore"],
        "existing": ["perturb/areas.yaml", "perturb/README.md", "perturb/events/"],
    }
    assert not (tmp_path / "perturb" / "events" / ".gitkeep").exists()


def test_init_ledger_creates_only_the_planning_store_and_gitignore(tmp_path):
    from perturb.init import init_ledger

    init_ledger(tmp_path)

    created = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert created == [
        ".gitignore",
        "perturb/README.md",
        "perturb/areas.yaml",
        "perturb/config.yaml",
        "perturb/events/.gitkeep",
    ]


def test_init_ledger_creates_gitignore_listing_the_cache(tmp_path):
    from perturb.init import init_ledger

    result = init_ledger(tmp_path)

    assert (tmp_path / ".gitignore").read_text() == ".perturb/\n"
    assert result["created"][-1] == ".gitignore"


def test_init_ledger_appends_the_cache_to_an_existing_gitignore(tmp_path):
    from perturb.init import init_ledger

    (tmp_path / ".gitignore").write_text("node_modules/\n*.log")

    result = init_ledger(tmp_path)

    assert (tmp_path / ".gitignore").read_text() == "node_modules/\n*.log\n.perturb/\n"
    assert ".gitignore" in result["created"]
    assert ".gitignore" not in result["existing"]


@pytest.mark.parametrize("entry", [".perturb/", ".perturb", "/.perturb/", "/.perturb"])
def test_init_ledger_reports_an_existing_cache_entry_without_duplicating(tmp_path, entry):
    from perturb.init import init_ledger

    original = f"dist/\n  {entry}  \n*.log\n"
    (tmp_path / ".gitignore").write_text(original)

    result = init_ledger(tmp_path)

    assert (tmp_path / ".gitignore").read_text() == original
    assert result["existing"][-1] == ".gitignore"
    assert ".gitignore" not in result["created"]


def test_init_ledger_config_template_is_the_defaults_commented_or_not(tmp_path):
    from perturb.config import Config, load_config
    from perturb.init import init_ledger

    init_ledger(tmp_path)
    path = tmp_path / "perturb" / "config.yaml"
    assert load_config(path) == Config()

    uncommented = [
        line[2:]
        for line in path.read_text().splitlines()
        if line.startswith("# ") and line[2:].startswith(("paths:", "labels:", "  "))
    ]
    (tmp_path / "uncommented.yaml").write_text("\n".join(uncommented) + "\n")
    assert len(uncommented) == 7
    assert load_config(tmp_path / "uncommented.yaml") == Config()
