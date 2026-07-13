"""Manage publish facts embedded in scheduler state."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, MutableMapping
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


HistoryEvent = dict[str, object]


def append_publish_history(
    state: MutableMapping[str, object],
    *,
    event_type: str,
    project_id: str,
    task_id: str,
    change_summary: Mapping[str, object],
    now: Callable[[], datetime] | None = None,
    event_id_factory: Callable[[], str] | None = None,
) -> HistoryEvent:
    """Append one canonical publish fact to a mutable scheduler state."""
    if event_type not in {"published", "publish_updated"}:
        raise ValueError("unsupported publish history event type")

    history = state.setdefault("publish_history", [])
    if not isinstance(history, list):
        raise ValueError("publish_history must be a list")

    occurred_at = (now or _utc_now)().isoformat()
    event_id = (event_id_factory or _new_event_id)()
    if not event_id:
        raise ValueError("publish history event_id must be non-empty")
    if any(
        isinstance(item, Mapping) and item.get("event_id") == event_id
        for item in history
    ):
        raise ValueError("publish history event_id must be unique")

    event: HistoryEvent = {
        "event_id": event_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "project_id": project_id,
        "task_id": task_id,
        "change_summary": dict(change_summary),
    }
    history.append(event)
    return event


def export_publish_history(state: Mapping[str, object], *, export_path: Path) -> int:
    """Write retained publish facts as deterministic JSON Lines without mutating state."""
    history = state.get("publish_history", [])
    if not isinstance(history, list):
        raise ValueError("publish_history must be a list")

    with export_path.open("w", encoding="utf-8") as export_file:
        for event in history:
            if not isinstance(event, Mapping):
                raise ValueError("publish_history entries must be objects")
            export_file.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
            export_file.write("\n")
    return len(history)


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _new_event_id() -> str:
    return str(uuid4())
