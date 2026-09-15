import json
from io import StringIO

from perturb.envelope import Refusal, dispatch, dispatch_gate, render_text


def test_dispatch_prints_success_envelope_as_json():
    out = StringIO()
    err = StringIO()
    code = dispatch("x", lambda warn: {"a": 1}, json_out=True, out=out, err=err)
    assert code == 0
    envelope = json.loads(out.getvalue())
    assert envelope == {
        "ok": True,
        "verb": "x",
        "synced_at": None,
        "data": {"a": 1},
        "warnings": [],
    }


def test_dispatch_collects_handler_warnings():
    def handler(warn):
        warn("cache is cold")
        return {}

    out = StringIO()
    err = StringIO()
    dispatch("x", handler, json_out=True, out=out, err=err)
    envelope = json.loads(out.getvalue())
    assert envelope["warnings"] == ["cache is cold"]


def test_dispatch_renders_refusal_with_exit_1():
    def handler(warn):
        raise Refusal("github_unreachable", "gh exited 1")

    out = StringIO()
    err = StringIO()
    code = dispatch("x", handler, json_out=True, out=out, err=err)
    assert code == 1
    envelope = json.loads(out.getvalue())
    assert envelope == {
        "ok": False,
        "verb": "x",
        "reason": "github_unreachable",
        "detail": "gh exited 1",
    }


def test_render_text_prints_dict_data_as_key_value_lines():
    envelope = {
        "ok": True,
        "verb": "x",
        "synced_at": None,
        "data": {"ref": "#29", "kind": "issue"},
        "warnings": [],
    }
    assert render_text(envelope) == "ref: #29\nkind: issue\n"


def test_dispatch_includes_supplied_synced_at():
    out = StringIO()
    err = StringIO()
    code = dispatch(
        "x", lambda warn: {}, json_out=True, out=out, err=err, synced_at="2026-09-12T16:00:00Z"
    )
    assert code == 0
    envelope = json.loads(out.getvalue())
    assert envelope["synced_at"] == "2026-09-12T16:00:00Z"


def test_render_text_prints_list_data_as_one_item_per_line():
    envelope = {"ok": True, "verb": "x", "synced_at": None, "data": ["#29", "#30"], "warnings": []}
    assert render_text(envelope) == "#29\n#30\n"


def test_dispatch_uses_supplied_render_in_text_mode():
    out = StringIO()
    err = StringIO()
    code = dispatch(
        "x",
        lambda warn: {"a": 1},
        json_out=False,
        out=out,
        err=err,
        render=lambda d: f"custom {d['a']}\n",
    )
    assert code == 0
    assert out.getvalue() == "custom 1\n"


def test_dispatch_prints_warnings_to_err_in_text_mode():
    def handler(warn):
        warn("careful")
        return {"a": 1}

    out = StringIO()
    err = StringIO()
    dispatch("x", handler, json_out=False, out=out, err=err)
    assert err.getvalue() == "warning: careful\n"
    assert out.getvalue() == "a: 1\n"


def test_dispatch_gate_ok_when_empty_refuses_when_findings():
    out = StringIO()
    err = StringIO()
    code = dispatch_gate("stale", [], reason="stale", json_out=True, out=out, err=err)
    assert code == 0
    envelope = json.loads(out.getvalue())
    assert envelope["ok"] is True
    assert envelope["verb"] == "stale"
    assert envelope["synced_at"] is None
    assert envelope["data"] == []

    findings = [{"issue": 29}]
    out = StringIO()
    err = StringIO()
    code = dispatch_gate("stale", findings, reason="stale", json_out=True, out=out, err=err)
    assert code == 1
    envelope = json.loads(out.getvalue())
    assert envelope["ok"] is False
    assert envelope["reason"] == "stale"
    assert envelope["data"] == findings
