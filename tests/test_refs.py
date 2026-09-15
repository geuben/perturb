import pytest

from perturb.refs import Ref, RefError, parse_ref


def test_issue_ref_accepts_hash_and_bare_number():
    assert parse_ref("#29") == Ref("issue", "29")
    assert parse_ref("29") == Ref("issue", "29")
    assert str(parse_ref("29")) == "#29"


def test_documented_forms_parse_to_canonical_refs():
    cases = [
        ("adr:0002", Ref("adr", "0002"), "adr:0002"),
        ("adr:2", Ref("adr", "0002"), "adr:0002"),
        ("plan:fare-schema", Ref("plan", "fare-schema"), "plan:fare-schema"),
        ("tasks/fare-schema.md", Ref("plan", "fare-schema"), "plan:fare-schema"),
        ("friction:fare-schema", Ref("friction", "fare-schema"), "friction:fare-schema"),
        ("audit:fare-schema", Ref("audit", "fare-schema"), "audit:fare-schema"),
        ("area:fares", Ref("area", "fares"), "area:fares"),
    ]
    for text, expected_ref, expected_str in cases:
        ref = parse_ref(text)
        assert ref == expected_ref, f"{text!r} -> {ref!r}, want {expected_ref!r}"
        assert str(ref) == expected_str, f"str({text!r}) -> {str(ref)!r}, want {expected_str!r}"


def test_unknown_form_raises_ref_error_naming_accepted_forms():
    with pytest.raises(RefError) as exc_info:
        parse_ref("bogus")
    msg = str(exc_info.value)
    assert "adr:0002" in msg
    assert "tasks/<slug>.md" in msg


def test_plan_path_form_follows_a_custom_plan_pattern():
    pattern = "plans/{slug}/plan.md"
    ref = parse_ref("plans/fare-schema/plan.md", plan_pattern=pattern)
    assert ref == Ref("plan", "fare-schema")
    with pytest.raises(RefError) as exc_info:
        parse_ref("tasks/fare-schema.md", plan_pattern=pattern)
    assert "plans/<slug>/plan.md" in str(exc_info.value)
