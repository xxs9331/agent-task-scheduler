from agent_task_scheduler.core.scheduler import SchedulerCore


def test_that_core_delegates_a_lifecycle_claim_without_cli_parsing() -> None:
    state = {
        "schema_version": 1,
        "project_id": "example",
        "tasks": {
            "task-a": {
                "task_id": "task-a",
                "status": "ready",
                "agent_type": "task_executor",
                "depends_on": [],
                "conflict_domain": "core",
                "preferred_worker": "window-a",
                "worker_prompt": {},
                "created_at": "2026-07-13T02:00:00+00:00",
            }
        },
        "publish_history": [],
        "staff_model": {
            "staff": {
                "window-a": {
                    "can_execute_tasks": True,
                    "allowed_agent_types": ["task_executor"],
                    "allowed_task_kinds": ["unclassified"],
                    "required_metadata_by_kind": {},
                }
            }
        },
    }
    core = SchedulerCore()

    receipt = core.claim(state, task_id="task-a", worker_id="window-a")

    assert receipt["ok"] is True
    assert state["tasks"]["task-a"]["owner"] == "window-a"


def test_that_core_exposes_all_remaining_lifecycle_operations() -> None:
    core = SchedulerCore()

    for operation in (
        "status",
        "ready",
        "next",
        "describe",
        "heartbeat",
        "complete",
        "retry",
        "resume",
        "continue_task",
        "block",
        "fail",
        "release_expired",
    ):
        assert callable(getattr(core, operation))
