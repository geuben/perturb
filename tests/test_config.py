import pytest

from perturb.config import Config, ConfigError, load_config, match_slug


def _write(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text)
    return path


def test_missing_or_comment_only_config_gives_the_defaults(tmp_path):
    assert load_config(tmp_path / "config.yaml") == Config()
    assert load_config(_write(tmp_path, "# only comments\n")) == Config()
    assert Config() == Config(
        plan="tasks/{slug}.md",
        friction_log="tasks/friction-logs/{slug}-friction.md",
        audit="tasks/friction-audits/{slug}-audit.md",
        ready_to_implement_label="ready-to-implement",
        epic_label="epic",
    )


def test_config_overrides_only_the_keys_it_sets(tmp_path):
    path = _write(
        tmp_path,
        "paths:\n  plan: plans/{slug}/plan.md\n  audit: reviews/{slug}.md\n"
        "labels:\n  ready_to_implement: ready-to-build\n",
    )
    assert load_config(path) == Config(
        plan="plans/{slug}/plan.md",
        audit="reviews/{slug}.md",
        ready_to_implement_label="ready-to-build",
    )


def test_path_helpers_substitute_the_slug():
    config = Config(friction_log="runs/{slug}.md")
    assert config.plan_path("x") == "tasks/x.md"
    assert config.friction_log_path("x") == "runs/x.md"
    assert config.audit_path("x") == "tasks/friction-audits/x-audit.md"


def test_match_slug_extracts_the_slug_or_returns_none():
    assert match_slug("plans/{slug}/plan.md", "plans/fare-schema/plan.md") == "fare-schema"
    assert match_slug("tasks/{slug}.md", "tasks/a/b.md") is None
    assert match_slug("tasks/{slug}.md", "other/a.md") is None


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("paths: [x]\n", "'paths' must be a mapping"),
        ("paths:\n  plan: tasks/plan.md\n", "exactly once"),
        ("paths:\n  plan: tasks/{slug}/{slug}.md\n", "exactly once"),
        ("paths:\n  plan: /abs/{slug}.md\n", "relative path"),
        ("paths:\n  plan: ../up/{slug}.md\n", "relative path"),
        ("paths:\n  plan: tasks/*/{slug}.md\n", "glob"),
        ("paths:\n  plans: tasks/{slug}.md\n", "unknown paths key"),
        ("labels:\n  ready_to_implement: ''\n", "non-empty string"),
        ("labels:\n  ready_to_implement: 3\n", "non-empty string"),
        ("tracker: github\n", "unknown key"),
        ("- a\n", "expected a mapping"),
        ("paths: {plan: [\n", "not valid YAML"),
    ],
)
def test_invalid_config_raises_with_a_clear_message(tmp_path, text, fragment):
    with pytest.raises(ConfigError) as exc_info:
        load_config(_write(tmp_path, text))
    assert fragment in str(exc_info.value)


def test_labels_are_trimmed(tmp_path):
    config = load_config(_write(tmp_path, "labels:\n  epic: ' initiative '\n"))
    assert config.epic_label == "initiative"


def test_fingerprint_changes_with_any_setting():
    assert Config().fingerprint() == Config().fingerprint()
    assert Config().fingerprint() != Config(epic_label="initiative").fingerprint()
    assert Config().fingerprint() != Config(plan="plans/{slug}.md").fingerprint()
