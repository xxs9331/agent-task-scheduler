from datetime import UTC, datetime
from pathlib import Path

from agent_task_scheduler.events import append_observation_event
from agent_task_scheduler.history import (
    append_publish_history,
    export_publish_history,
)


def test_that_appending_publish_history_creates_a_stable_event_record() -> None:
    state: dict[str, object] = {"publish_history": []}

    event = append_publish_history(
        state,
        event_type="published",
        project_id="project-a",
        task_id="task-a",
        change_summary={"created_fields": ["task_id"]},
        now=lambda: datetime(2026, 7, 13, 4, 0, tzinfo=UTC),
        event_id_factory=lambda: "event-1",
    )

    assert event == {
        "event_id": "event-1",
        "event_type": "published",
        "occurred_at": "2026-07-13T04:00:00+00:00",
        "project_id": "project-a",
        "task_id": "task-a",
        "change_summary": {"created_fields": ["task_id"]},
    }
    assert state["publish_history"] == [event]


def test_that_exporting_publish_history_writes_json_lines_without_mutating_state(
    tmp_path: Path,
) -> None:
    state: dict[str, object] = {
        "publish_history": [
            {
                "event_id": "event-1",
                "event_type": "published",
                "occurred_at": "2026-07-13T04:00:00+00:00",
                "project_id": "project-a",
                "task_id": "task-a",
                "change_summary": {},
            }
        ]
    }
    export_path = tmp_path / "history.jsonl"

    exported_count = export_publish_history(state, export_path=export_path)

    assert exported_count == 1
    assert export_path.read_text(encoding="utf-8") == (
        '{"change_summary": {}, "event_id": "event-1", "event_type": "published", '
        '"occurred_at": "2026-07-13T04:00:00+00:00", "project_id": "project-a", '
        '"task_id": "task-a"}\n'
    )
    assert len(state["publish_history"]) == 1


def test_that_observation_log_failure_returns_a_rebuild_warning_without_mutating_history(
    tmp_path: Path,
) -> None:
    history = [
        {
            "event_id": "event-1",
            "event_type": "published",
            "occurred_at": "2026-07-13T04:00:00+00:00",
            "project_id": "project-a",
            "task_id": "task-a",
            "change_summary": {},
        }
    ]

    warning = append_observation_event(
        event=history[0],
        events_path=tmp_path,
    )

    assert warning == {
        "code": "OBSERVATION_LOG_WARNING",
        "message": "state committed; observation log append failed",
        "rebuild_from": "publish_history",
    }
    assert history == [
        {
            "event_id": "event-1",
            "event_type": "published",
            "occurred_at": "2026-07-13T04:00:00+00:00",
            "project_id": "project-a",
            "task_id": "task-a",
            "change_summary": {},
        }
    ]
