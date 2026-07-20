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

    receipt = service.heartbeat(
        state,
        task_id="task-a",
        worker_id="window-a",
        lease_id="lease-current",
    )

    assert receipt["ok"] is True
    assert state["tasks"]["task-a"]["lease_expires_at"] == "2026-07-13T03:05:00+00:00"


def test_that_completing_a_running_task_clears_its_lease() -> None:
    state = _state_with_running_task()
    service = LifecycleService(now=_fixed_now)

    receipt = service.complete(
        state,
        task_id="task-a",
        worker_id="window-a",
        lease_id="lease-current",
        summary="verified",
    )

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


def test_that_claim_rejects_unknown_and_non_executable_workers_atomically() -> None:
    state = _state_with_ready_task()
    state["staff_model"] = {
        "staff": {
            "window-a": _worker_profile(),
            "publisher": _worker_profile(can_execute_tasks=False),
        }
    }
    service = LifecycleService(now=_fixed_now)

    unknown = service.claim(state, task_id="task-a", worker_id="unknown")
    publisher = service.claim(state, task_id="task-a", worker_id="publisher")

    assert unknown == {
        "ok": False,
        "reason": "unknown_worker",
        "task_id": "task-a",
        "worker_id": "unknown",
    }
    assert publisher == {
        "ok": False,
        "reason": "staff_cannot_execute_tasks",
        "task_id": "task-a",
        "worker_id": "publisher",
    }
    assert state["tasks"]["task-a"]["status"] == "ready"


def test_that_claim_rechecks_required_worker_agent_type_kind_and_fallback_metadata() -> (
    None
):
    state = _state_with_ready_task()
    task = state["tasks"]["task-a"]
    task.update(
        {
            "required_worker": "role-p",
            "metadata": {"team_mode": {"kind": "pm_fallback"}},
        }
    )
    state["staff_model"] = {
        "staff": {
            "window-a": _worker_profile(),
            "role-p": _worker_profile(
                allowed_task_kinds=["pm_fallback"],
                required_metadata_by_kind={
                    "pm_fallback": [
                        "fallback_authorization.original_task_id",
                        "fallback_authorization.user_authorization",
                        "fallback_authorization.return_gate_task_id",
                    ]
                },
            ),
        }
    }
    service = LifecycleService(now=_fixed_now)

    wrong_worker = service.claim(state, task_id="task-a", worker_id="window-a")
    missing_metadata = service.claim(state, task_id="task-a", worker_id="role-p")
    task["metadata"]["fallback_authorization"] = {
        "original_task_id": "",
        "user_authorization": "   ",
        "return_gate_task_id": [],
    }
    empty_metadata = service.claim(state, task_id="task-a", worker_id="role-p")
    task["metadata"]["fallback_authorization"] = {
        "original_task_id": "original",
        "user_authorization": "approved",
        "return_gate_task_id": "gate",
    }
    accepted = service.claim(state, task_id="task-a", worker_id="role-p")

    assert wrong_worker["reason"] == "required_worker_mismatch"
    assert missing_metadata == {
        "ok": False,
        "reason": "required_metadata_missing",
        "task_id": "task-a",
        "worker_id": "role-p",
        "missing": [
            "fallback_authorization.original_task_id",
            "fallback_authorization.user_authorization",
            "fallback_authorization.return_gate_task_id",
        ],
    }
    assert empty_metadata == missing_metadata
    assert accepted["ok"] is True


def test_that_product_manager_can_claim_bounded_pm_debug_work() -> None:
    state = _state_with_ready_task()
    task = state["tasks"]["task-a"]
    task.update(
        {
            "required_worker": "product_manager",
            "metadata": {"team_mode": {"kind": "pm_debug"}},
            "writable_files": ["src/service.py", "tests/test_service.py"],
            "worker_prompt": {
                "problem": "Reproduce and repair the cross-module runtime failure.",
                "writable_scope": ["src/service.py", "tests/test_service.py"],
                "verification": ["pytest tests/test_service.py"],
            },
        }
    )
    state["staff_model"] = {
        "staff": {
            "product_manager": _worker_profile(allowed_task_kinds=["pm_debug"]),
            "window-a": _worker_profile(),
        }
    }
    service = LifecycleService(now=_fixed_now)

    wrong_worker = service.claim(state, task_id="task-a", worker_id="window-a")
    accepted = service.claim(
        state, task_id="task-a", worker_id="product_manager"
    )

    assert wrong_worker["reason"] == "required_worker_mismatch"
    assert accepted["ok"] is True
    assert state["tasks"]["task-a"]["owner"] == "product_manager"


def test_that_claim_rejects_overlapping_writable_paths_even_across_domains() -> None:
    state = _state_with_ready_task()
    state["tasks"]["task-a"]["worker_prompt"] = {
        "writable_scope": ["src/parlant/core/**"]
    }
    state["tasks"]["active"] = {
        **state["tasks"]["task-a"],
        "task_id": "active",
        "status": "running",
        "owner": "window-b",
        "conflict_domain": "different-domain",
        "worker_prompt": {"writable_scope": ["src/parlant/core/engines/alpha.py"]},
        "lease_id": "active-lease",
        "lease_expires_at": "2026-07-13T03:30:00+00:00",
    }
    service = LifecycleService(now=_fixed_now)

    receipt = service.claim(state, task_id="task-a", worker_id="window-a")

    assert receipt["ok"] is False
    assert receipt["reason"] == "writable_path_locked"
    assert receipt["task_id"] == "active"


def test_that_stale_lease_token_cannot_heartbeat_or_complete_a_new_attempt() -> None:
    lease_ids = iter(["lease-old", "lease-new"])
    state = _state_with_ready_task()
    service = LifecycleService(now=_fixed_now, lease_id_factory=lambda: next(lease_ids))

    first_claim = service.claim(state, task_id="task-a", worker_id="window-a")
    state["tasks"]["task-a"]["lease_expires_at"] = "2026-07-13T02:59:00+00:00"
    service.release_expired(state)
    second_claim = service.claim(state, task_id="task-a", worker_id="window-a")
    stale_heartbeat = service.heartbeat(
        state,
        task_id="task-a",
        worker_id="window-a",
        lease_id=first_claim["lease_id"],
    )
    stale_complete = service.complete(
        state,
        task_id="task-a",
        worker_id="window-a",
        lease_id=first_claim["lease_id"],
        summary="stale process",
    )

    assert first_claim["lease_id"] == "lease-old"
    assert second_claim["lease_id"] == "lease-new"
    assert stale_heartbeat["reason"] == "stale_lease"
    assert stale_complete["reason"] == "stale_lease"
    assert state["tasks"]["task-a"]["status"] == "running"


def test_that_terminal_receipt_records_fence_attempt_summary_and_release() -> None:
    state = _state_with_ready_task()
    service = LifecycleService(now=_fixed_now, lease_id_factory=lambda: "lease-1")

    claim = service.claim(state, task_id="task-a", worker_id="window-a")
    missing_summary = service.complete(
        state,
        task_id="task-a",
        worker_id="window-a",
        lease_id=claim["lease_id"],
    )
    completed = service.complete(
        state,
        task_id="task-a",
        worker_id="window-a",
        lease_id=claim["lease_id"],
        summary="all focused tests passed",
    )

    assert missing_summary == {
        "ok": False,
        "reason": "summary_required",
        "task_id": "task-a",
    }
    assert completed == {
        "ok": True,
        "task_id": "task-a",
        "status": "done",
        "owner": "window-a",
        "attempt": 1,
        "lease_id": "lease-1",
        "completed_at": "2026-07-13T03:00:00+00:00",
        "summary": "all focused tests passed",
        "lease_released": True,
    }
    assert state["tasks"]["task-a"]["completion_receipt"] == completed


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
        lease_id="lease-current",
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
        state,
        task_id="task-a",
        worker_id="window-a",
        lease_id="lease-current",
        reason="waiting",
    )
    failed = service.fail(
        state,
        task_id="task-b",
        worker_id="window-b",
        lease_id="lease-current",
        reason="bad input",
    )
    released = service.release_expired(state)

    assert blocked["ok"] is True
    assert blocked["status"] == "blocked"
    assert blocked["lease_released"] is True
    assert failed["ok"] is True
    assert failed["status"] == "failed"
    assert failed["lease_released"] is True
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
        "staff_model": {
            "staff": {"window-a": _worker_profile(), "window-b": _worker_profile()}
        },
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
            "lease_id": "lease-current",
            "lease_metadata": {},
        }
    )
    return state


def _fixed_now() -> datetime:
    return datetime(2026, 7, 13, 3, 0, tzinfo=UTC)


def _worker_profile(
    *,
    can_execute_tasks: bool = True,
    allowed_task_kinds: list[str] | None = None,
    required_metadata_by_kind: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    return {
        "can_execute_tasks": can_execute_tasks,
        "allowed_agent_types": ["task_executor"],
        "allowed_task_kinds": allowed_task_kinds or ["unclassified", "implementation"],
        "required_metadata_by_kind": required_metadata_by_kind or {},
    }
