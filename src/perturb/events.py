from __future__ import annotations

import dataclasses
import datetime
import hashlib
from pathlib import Path
from typing import Any

import yaml

from perturb.ids import new_ulid


class TransitionError(Exception):
    pass


class EventNotFound(KeyError):
    pass


@dataclasses.dataclass(frozen=True)
class Event:
    id: str
    at: str
    source: str
    target: str
    kind: str
    summary: str
    detail: str | None
    proposed_by: str
    reason: str
    status: str
    ack: dict | None = None


@dataclasses.dataclass
class LoadError:
    path: Path
    message: str


@dataclasses.dataclass
class LoadResult:
    events: list[Event]
    errors: list[LoadError]


def _default_now() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _idempotence_key(source: str, target: str, kind: str, summary: str) -> tuple:
    digest = hashlib.sha256(summary.encode()).hexdigest()
    return (source, target, kind, digest)


def _event_to_dict(event: Event) -> dict:
    d: dict[str, Any] = {
        "id": event.id,
        "at": event.at,
        "source": event.source,
        "target": event.target,
        "kind": event.kind,
        "summary": event.summary,
        "detail": event.detail,
        "proposed_by": event.proposed_by,
        "reason": event.reason,
        "status": event.status,
    }
    if event.ack is not None:
        d["ack"] = event.ack
    return d


def _dict_to_event(d: dict) -> Event:
    return Event(
        id=d["id"],
        at=d["at"],
        source=d["source"],
        target=d["target"],
        kind=d["kind"],
        summary=d["summary"],
        detail=d.get("detail"),
        proposed_by=d["proposed_by"],
        reason=d["reason"],
        status=d["status"],
        ack=d.get("ack"),
    )


def _dump(data: dict) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


_REQUIRED_KEYS = {
    "id",
    "at",
    "source",
    "target",
    "kind",
    "summary",
    "proposed_by",
    "reason",
    "status",
}


class EventStore:
    def __init__(self, root: Path, *, now=None, new_id=None):
        self._root = Path(root)
        self._now = now or _default_now
        self._new_id = new_id or new_ulid

    def create(
        self,
        *,
        source: str,
        target: str,
        kind: str,
        summary: str,
        proposed_by: str,
        reason: str,
        detail: str | None = None,
        status: str = "proposed",
    ) -> Event:
        if status not in ("proposed", "pending"):
            raise ValueError(f"status must be 'proposed' or 'pending', got {status!r}")

        key = _idempotence_key(source, target, kind, summary)
        for path in self._root.glob("*.yaml"):
            try:
                data = yaml.safe_load(path.read_text())
                if not isinstance(data, dict):
                    continue
                existing = _dict_to_event(data)
                existing_key = _idempotence_key(
                    existing.source, existing.target, existing.kind, existing.summary
                )
                if existing_key == key:
                    return existing
            except Exception:
                continue

        event_id = self._new_id()
        event = Event(
            id=event_id,
            at=self._now(),
            source=source,
            target=target,
            kind=kind,
            summary=summary,
            detail=detail,
            proposed_by=proposed_by,
            reason=reason,
            status=status,
        )
        path = self._root / f"{event_id}.yaml"
        path.write_text(_dump(_event_to_dict(event)))
        return event

    def load(self) -> LoadResult:
        events = []
        errors = []
        for path in sorted(self._root.glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text())
                if not isinstance(data, dict):
                    raise ValueError("not a mapping")
                missing = _REQUIRED_KEYS - data.keys()
                if missing:
                    raise ValueError(f"missing keys: {missing}")
                events.append(_dict_to_event(data))
            except Exception as exc:
                errors.append(LoadError(path=path, message=str(exc)))
        return LoadResult(events=events, errors=errors)

    def _read_event(self, event_id: str) -> tuple[Event, Path]:
        path = self._root / f"{event_id}.yaml"
        if not path.exists():
            raise EventNotFound(event_id)
        data = yaml.safe_load(path.read_text())
        return _dict_to_event(data), path

    def _write_event(self, event: Event, path: Path) -> None:
        path.write_text(_dump(_event_to_dict(event)))

    def confirm(self, event_id: str) -> Event:
        event, path = self._read_event(event_id)
        if event.status != "proposed":
            raise TransitionError(f"confirm: event {event_id} is {event.status!r}, not 'proposed'")
        updated = dataclasses.replace(event, status="pending")
        self._write_event(updated, path)
        return updated

    def dismiss(self, event_id: str, *, by: str, note: str | None = None) -> Event:
        event, path = self._read_event(event_id)
        if event.status not in ("proposed", "pending"):
            raise TransitionError(
                f"dismiss: event {event_id} is {event.status!r}, not 'proposed' or 'pending'"
            )
        ack = {"at": self._now(), "by": by, "note": note}
        updated = dataclasses.replace(event, status="dismissed", ack=ack)
        self._write_event(updated, path)
        return updated

    def acknowledge(self, event_id: str, *, by: str, plan: str, plan_blob: str, note: str) -> Event:
        event, path = self._read_event(event_id)
        if event.status not in ("pending", "acknowledged"):
            raise TransitionError(
                f"acknowledge: event {event_id} is {event.status!r}, "
                "not 'pending' or 'acknowledged'"
            )
        ack = {"at": self._now(), "by": by, "plan": plan, "plan_blob": plan_blob, "note": note}
        updated = dataclasses.replace(event, status="acknowledged", ack=ack)
        self._write_event(updated, path)
        return updated
