from copy import deepcopy
from datetime import UTC, datetime

from agent_task_scheduler.publish.service import PublishService


def test_that_create_publishes_a_dependency_batch_atomically() -> None:
    state = _state()

    receipt = PublishService(now=_fixed_now, event_id_factory=_event_ids()).publish(
        state,
        envelope={
            "input_schema_version": 1,
            "project_id": "example",
            "operation": "create",
            "tasks": [
                _create_task("first"),
                _create_task("second", depends_on=["first"]),
            ],
        },
        update=False,
    )

    assert receipt == {
        "ok": True,
        "operation": "create",
        "task_ids": ["first", "second"],
    }
    assert state["tasks"]["first"]["status"] == "ready"
    assert state["tasks"]["second"]["status"] == "blocked_waiting_dependency"
    assert state["tasks"]["first"]["created_at"] == "2026-07-13T04:00:00+00:00"
    assert [event["event_type"] for event in state["publish_history"]] == [
        "published",
        "published",
    ]


def test_that_invalid_dependency_leaves_the_entire_create_batch_unchanged() -> None:
    state = _state()
    before = deepcopy(state)

    receipt = PublishService().publish(
        state,
        envelope={
            "input_schema_version": 1,
            "project_id": "example",
            "operation": "create",
            "tasks": [
                _create_task("first"),
                _create_task("second", depends_on=["missing"]),
            ],
        },
        update=False,
    )

    assert receipt["ok"] is False
    assert receipt["error"]["code"] == "DEPENDENCY_INVALID"
    assert state == before


def test_that_update_is_whitelisted_and_recalculates_dependency_status() -> None:
    state = _state()
    state["tasks"] = {
        "upstream": {**_create_task("upstream"), "status": "done", "created_at": "old"},
        "task": {**_create_task("task"), "status": "ready", "created_at": "old"},
    }

    receipt = PublishService(now=_fixed_now, event_id_factory=_event_ids()).publish(
        state,
        envelope={
            "input_schema_version": 1,
            "project_id": "example",
            "operation": "update",
            "tasks": [{"task_id": "task", "patch": {"depends_on": ["upstream"]}}],
        },
        update=True,
    )

    assert receipt["ok"] is True
    assert state["tasks"]["task"]["status"] == "ready"
    assert state["tasks"]["task"]["created_at"] == "old"
    assert state["publish_history"][0]["event_type"] == "publish_updated"


def test_that_mode_mismatch_and_reserved_update_field_do_not_mutate_state() -> None:
    state = _state()
    before = deepcopy(state)
    service = PublishService()

    mismatch = service.publish(
        state,
        envelope={
            "input_schema_version": 1,
            "project_id": "example",
            "operation": "update",
            "tasks": [],
        },
        update=False,
    )
    forbidden = service.publish(
        state,
        envelope={
            "input_schema_version": 1,
            "project_id": "example",
            "operation": "update",
            "tasks": [{"task_id": "task", "patch": {"status": "done"}}],
        },
        update=True,
    )

    assert mismatch["error"]["code"] == "PUBLISH_OPERATION_MISMATCH"
    assert forbidden["error"]["code"] == "INPUT_SCHEMA_INVALID"
    assert state == before


def _state() -> dict[str, object]:
    return {
        "schema_version": 1,
        "project_id": "example",
        "tasks": {},
        "publish_history": [],
    }


def _create_task(
    task_id: str, *, depends_on: list[str] | None = None
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "agent_type": "task_executor",
        "depends_on": depends_on or [],
        "conflict_domain": "core",
        "preferred_worker": "worker",
        "worker_prompt": {},
    }


def _fixed_now() -> datetime:
    return datetime(2026, 7, 13, 4, 0, tzinfo=UTC)


def _event_ids():
    values = iter(["event-1", "event-2"])
    return lambda: next(values)
