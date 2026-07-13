from datetime import UTC, datetime

from agent_task_scheduler.lifecycle.service import LifecycleService


def test_that_claiming_a_ready_task_assigns_owner_and_lease() -> None:
    state = _state_with_ready_task()
    service = LifecycleService(now=_fixed_now)

    receipt = service.claim(state, task_id="task-a", worker_id="window-a")

    task = state["tasks"]["task-a"]
    assert receipt["ok"] is True
    assert task["status"] == "running"
    assert task["owner"] == "window-a"
    assert task["lease_expires_at"] == "2026-07-13T03:05:00+00:00"


def test_that_heartbeat_by_task_owner_extends_an_active_lease() -> None:
    state = _state_with_running_task()
    service = LifecycleService(now=_fixed_now)

    receipt = service.heartbeat(state, task_id="task-a", worker_id="window-a")

    assert receipt["ok"] is True
    assert state["tasks"]["task-a"]["lease_expires_at"] == "2026-07-13T03:05:00+00:00"


def test_that_completing_a_running_task_clears_its_lease() -> None:
    state = _state_with_running_task()
    service = LifecycleService(now=_fixed_now)

    receipt = service.complete(state, task_id="task-a", worker_id="window-a")

    task = state["tasks"]["task-a"]
    assert receipt["ok"] is True
    assert task["status"] == "done"
    assert "owner" not in task
    assert "lease_expires_at" not in task
    assert task["completed_at"] == "2026-07-13T03:00:00+00:00"


def test_that_status_and_ready_expose_only_unblocked_and_unleased_tasks() -> None:
    state = _state_with_ready_task()
    state["tasks"]["done"] = {"status": "done"}
    state["tasks"]["dependent"] = {
        **state["tasks"]["task-a"],
        "task_id": "dependent",
        "depends_on": ["done"],
        "conflict_domain": "other",
    }
    state["tasks"]["locked"] = {
        **state["tasks"]["task-a"],
        "task_id": "locked",
        "status": "running",
        "owner": "window-b",
        "lease_expires_at": "2026-07-13T03:05:00+00:00",
    }
    state["tasks"]["conflicted"] = {
        **state["tasks"]["task-a"],
        "task_id": "conflicted",
        "conflict_domain": "core",
    }
    service = LifecycleService(now=_fixed_now)

    status = service.status(state)
    ready = service.ready(state)

    assert status["active_leases"] == [{"task_id": "locked", "owner": "window-b"}]
    assert ready == {"ok": True, "tasks": ["dependent"]}


def test_that_next_filters_required_worker_before_recommending_ready_task() -> None:
    state = _state_with_ready_task()
    state["tasks"]["task-a"]["required_worker"] = "window-b"
    state["tasks"]["task-b"] = {
        **state["tasks"]["task-a"],
        "task_id": "task-b",
        "required_worker": "window-a",
        "preferred_worker": "window-a",
    }
    service = LifecycleService(now=_fixed_now)

    receipt = service.next(state, worker_id="window-a")

    assert receipt["ok"] is True
    assert receipt["recommended_task_id"] == "task-b"


def test_that_next_reports_structured_blocked_candidates_when_no_task_is_routable() -> (
    None
):
    state = _state_with_ready_task()
    state["tasks"]["task-a"]["depends_on"] = ["missing"]
    service = LifecycleService(now=_fixed_now)

    receipt = service.next(state, worker_id="window-a")

    assert receipt == {
        "ok": True,
        "worker_id": "window-a",
        "task": None,
        "blocked_candidates": [
            {
                "task_id": "task-a",
                "reason": "dependency_not_satisfied",
                "missing_dependencies": ["missing"],
            }
        ],
    }


def test_that_describe_returns_selected_task_fields_and_retry_records_handoff() -> None:
    state = _state_with_running_task()
    state["tasks"]["task-a"]["worker_prompt"] = {"goal": "verify"}
    service = LifecycleService(now=_fixed_now)

    description = service.describe(state, task_id="task-a")
    retry = service.retry(
        state,
        task_id="task-a",
        worker_id="window-a",
        reason="needs evidence",
        last_attempt_summary="partial",
        next_attempt_instruction="retry focused tests",
    )

    task = state["tasks"]["task-a"]
    assert description["worker_prompt"] == {"goal": "verify"}
    assert retry == {"ok": True, "task_id": "task-a", "status": "retry_ready"}
    assert task["last_attempt_summary"] == "partial"
    assert "owner" not in task


def test_that_resume_and_continue_restore_terminal_task_with_new_lease() -> None:
    state = _state_with_ready_task()
    task = state["tasks"]["task-a"]
    task.update({"status": "blocked", "reason": "upstream", "last_owner": "window-a"})
    service = LifecycleService(now=_fixed_now)

    resumed = service.resume(
        state,
        task_id="task-a",
        worker_id="window-a",
        reason="upstream complete",
        last_attempt_summary="blocked",
        next_attempt_instruction="continue",
    )
    continued = service.continue_task(state, task_id="task-a", worker_id="window-a")

    assert resumed == {"ok": True, "task_id": "task-a", "status": "retry_ready"}
    assert continued["ok"] is True
    assert task["status"] == "running"
    assert task["attempt"] == 1


def test_that_continue_rejects_retry_ready_task_at_max_attempts() -> None:
    state = _state_with_ready_task()
    task = state["tasks"]["task-a"]
    task.update({"status": "retry_ready", "attempt": 2, "max_attempts": 2})
    service = LifecycleService(now=_fixed_now)

    receipt = service.continue_task(state, task_id="task-a", worker_id="window-a")

    assert receipt == {
        "ok": False,
        "reason": "max_attempts_reached",
        "task_id": "task-a",
        "attempt": 2,
        "max_attempts": 2,
    }


def test_that_block_fail_and_release_expired_clear_leases_with_legacy_statuses() -> (
    None
):
    state = _state_with_running_task()
    state["tasks"]["task-b"] = {
        **state["tasks"]["task-a"],
        "task_id": "task-b",
        "owner": "window-b",
    }
    state["tasks"]["expired"] = {
        **state["tasks"]["task-a"],
        "task_id": "expired",
        "lease_expires_at": "2026-07-13T02:59:00+00:00",
    }
    service = LifecycleService(now=_fixed_now)

    blocked = service.block(
        state, task_id="task-a", worker_id="window-a", reason="waiting"
    )
    failed = service.fail(
        state, task_id="task-b", worker_id="window-b", reason="bad input"
    )
    released = service.release_expired(state)

    assert blocked == {"ok": True, "task_id": "task-a", "status": "blocked"}
    assert failed == {"ok": True, "task_id": "task-b", "status": "failed"}
    assert released == {"ok": True, "released": ["expired"]}
    assert state["tasks"]["expired"]["status"] == "ready"


def _state_with_ready_task() -> dict[str, object]:
    return {
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
    }


def _state_with_running_task() -> dict[str, object]:
    state = _state_with_ready_task()
    task = state["tasks"]["task-a"]
    assert isinstance(task, dict)
    task.update(
        {
            "status": "running",
            "owner": "window-a",
            "lease_expires_at": "2026-07-13T03:30:00+00:00",
        }
    )
    return state


def _fixed_now() -> datetime:
    return datetime(2026, 7, 13, 3, 0, tzinfo=UTC)
