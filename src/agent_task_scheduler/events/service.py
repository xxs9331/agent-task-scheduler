"""Append optional observation records after authoritative state commits."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path


_OBSERVATION_LOG_WARNING = {
    "code": "OBSERVATION_LOG_WARNING",
    "message": "state committed; observation log append failed",
    "rebuild_from": "publish_history",
}


def append_observation_event(
    *, event: Mapping[str, object], events_path: Path | None
) -> dict[str, str] | None:
    """Append an observation record, returning a warning if logging is unavailable.

    The caller invokes this only after atomically committing authoritative state.
    Therefore logging errors never trigger a rollback.
    """
    if events_path is None:
        return None
    try:
        with events_path.open("a", encoding="utf-8") as events_file:
            events_file.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
            events_file.write("\n")
    except OSError:
        return dict(_OBSERVATION_LOG_WARNING)
    return None
