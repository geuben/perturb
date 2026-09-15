import json


class Refusal(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def dispatch(verb, handler, *, json_out, out, err, synced_at=None, render=None):
    warnings = []
    try:
        data = handler(warnings.append)
    except Refusal as exc:
        envelope = {"ok": False, "verb": verb, "reason": exc.reason, "detail": exc.detail}
        if json_out:
            print(json.dumps(envelope), file=out)
        else:
            print(f"perturb {verb}: {exc.reason}: {exc.detail}", file=err)
        return 1
    envelope = {
        "ok": True,
        "verb": verb,
        "synced_at": synced_at,
        "data": data,
        "warnings": warnings,
    }
    if json_out:
        print(json.dumps(envelope), file=out)
    else:
        text = render(data) if render is not None else render_text(envelope)
        print(text, file=out, end="")
        for w in warnings:
            print(f"warning: {w}", file=err)
    return 0


def dispatch_gate(verb, findings, *, reason, json_out, out, err, synced_at=None, render=None):
    if not findings:
        envelope = {"ok": True, "verb": verb, "synced_at": synced_at, "data": []}
        if json_out:
            print(json.dumps(envelope), file=out)
        return 0
    if json_out:
        envelope = {
            "ok": False,
            "verb": verb,
            "synced_at": synced_at,
            "reason": reason,
            "data": findings,
        }
        print(json.dumps(envelope), file=out)
    else:
        if render is not None:
            print(render(findings), file=out, end="")
    return 1


def render_text(envelope: dict) -> str:
    data = envelope["data"]
    if isinstance(data, dict):
        return "".join(f"{k}: {v}\n" for k, v in data.items())
    if isinstance(data, list):
        return "".join(f"{item}\n" for item in data)
    return str(data)
