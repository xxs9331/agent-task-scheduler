"""Legacy-compatible lifecycle transitions owned by scheduler-core."""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from datetime import UTC, datetime, timedelta
from typing import cast

State = MutableMapping[str, object]
Task = MutableMapping[str, object]
Receipt = dict[str, object]

_CLAIMABLE_STATUSES = {
    "pending",
    "ready",
    "retry_ready",
    "blocked_waiting_dependency",
    "available",
}
_ACTIVE_STATUSES = {"claimed", "running"}
_DESCRIBE_FIELDS = (
    "status",
    "title",
    "title_zh",
    "description",
    "description_zh",
    "worker_prompt",
    "acceptance_criteria",
    "last_attempt_summary",
    "next_attempt_instruction",
    "writable_files",
    "must_not_touch",
    "read_only_files",
    "depends_on",
    "conflict_domain",
    "artifacts",
    "parent_task",
    "branch",
)


class LifecycleService:
    """Apply legacy task-state transitions without CLI argument parsing."""

    def __init__(
        self,
        now: Callable[[], datetime] | None = None,
        lease_duration: timedelta = timedelta(minutes=5),
    ) -> None:
        self._now = now or _utc_now
        self._lease_duration = lease_duration

    def status(self, state: State) -> Receipt:
        tasks = self._tasks(state)
        return {
            "ok": True,
            "tasks": tasks,
            "active_leases": [
                {"task_id": task_id, "owner": task.get("owner")}
                for task_id, task in tasks.items()
                if self._is_active_lease(task)
            ],
        }

    def ready(self, state: State) -> Receipt:
        return {"ok": True, "tasks": self._ready_task_ids(state)}

    def next(self, state: State, *, worker_id: str) -> Receipt:
        tasks = self._tasks(state)
        profile = self._staff_profiles(state).get(worker_id, {})
        if not bool(profile.get("can_execute_tasks", True)):
            return {
                "ok": False,
                "reason": "staff_cannot_execute_tasks",
                "worker_id": worker_id,
            }

        filtered: list[Receipt] = []
        candidates: list[str] = []
        for task_id in self._ready_task_ids(state):
            reason = self._profile_filter_reason(tasks[task_id], worker_id, profile)
            if reason is not None:
                filtered.append({"task_id": task_id, **reason})
                continue
            candidates.append(task_id)
        if not candidates:
            return {
                "ok": True,
                "worker_id": worker_id,
                "task": None,
                "blocked_candidates": self._blocked_candidates(
                    tasks, worker_id, profile, filtered
                ),
            }

        candidates.sort(
            key=lambda task_id: self._recommendation_rank(
                tasks[task_id], task_id, worker_id
            )
        )
        task_id = candidates[0]
        task = tasks[task_id]
        return {
            "ok": True,
            "worker_id": worker_id,
            "recommended_task_id": task_id,
            "status": task.get("status", "pending"),
            "title": task.get("title"),
            "title_zh": task.get("title_zh"),
            "conflict_domain": task.get("conflict_domain"),
            "preferred_worker": task.get("preferred_worker"),
            "required_worker": task.get("required_worker"),
            "recommendation_rank": {
                "matched_preferred_worker": task.get("preferred_worker") == worker_id,
                "soft_preferred_worker": task.get("preferred_worker"),
            },
        }

    def describe(self, state: State, *, task_id: str) -> Receipt:
        task = self._tasks(state).get(task_id)
        if task is None:
            return self._not_found(task_id)
        return {
            "ok": True,
            "task_id": task_id,
            **{key: task[key] for key in _DESCRIBE_FIELDS if key in task},
        }

    def claim(self, state: State, *, task_id: str, worker_id: str) -> Receipt:
        task = self._tasks(state).get(task_id)
        if task is None:
            return self._not_found(task_id)
        if task.get("status", "pending") not in _CLAIMABLE_STATUSES:
            return {
                "ok": False,
                "reason": "task_not_claimable",
                "task_id": task_id,
                "status": task.get("status"),
            }
        missing = self._dependencies_done(task, self._tasks(state))
        if missing:
            return {
                "ok": False,
                "reason": "dependency_not_satisfied",
                "missing": missing,
            }
        conflict = self._active_conflict(task_id, task, self._tasks(state))
        if conflict is not None:
            return conflict
        self._start(task, worker_id)
        return self._running_receipt(task_id, task)

    def heartbeat(self, state: State, *, task_id: str, worker_id: str) -> Receipt:
        task = self._owned_task(state, task_id, worker_id)
        if "ok" in task:
            return task
        task["status"] = "running"
        task["last_heartbeat_at"] = self._iso_now()
        task["lease_expires_at"] = self._lease_expiry()
        return self._running_receipt(task_id, task)

    def complete(
        self, state: State, *, task_id: str, worker_id: str, summary: str | None = None
    ) -> Receipt:
        task = self._owned_task(state, task_id, worker_id)
        if "ok" in task:
            return task
        task["status"] = "done"
        task["completed_at"] = self._iso_now()
        if summary is not None:
            task["summary"] = summary
        self._clear_lease(task)
        return {"ok": True, "task_id": task_id, "status": "done"}

    def retry(
        self,
        state: State,
        *,
        task_id: str,
        worker_id: str,
        reason: str,
        last_attempt_summary: str,
        next_attempt_instruction: str,
    ) -> Receipt:
        task = self._owned_task(state, task_id, worker_id)
        if "ok" in task:
            return task
        task.update(
            {
                "status": "retry_ready",
                "reason": reason,
                "last_attempt_summary": last_attempt_summary,
                "next_attempt_instruction": next_attempt_instruction,
                "retry_ready_at": self._iso_now(),
            }
        )
        self._clear_lease(task)
        return {"ok": True, "task_id": task_id, "status": "retry_ready"}

    def resume(
        self,
        state: State,
        *,
        task_id: str,
        worker_id: str,
        reason: str,
        last_attempt_summary: str,
        next_attempt_instruction: str,
    ) -> Receipt:
        task = self._tasks(state).get(task_id)
        if task is None:
            return self._not_found(task_id)
        status = task.get("status", "pending")
        if status not in {"blocked", "failed"}:
            return {
                "ok": False,
                "reason": "task_not_terminal",
                "task_id": task_id,
                "status": status,
            }
        if task.get("last_owner") or task.get("owner"):
            task["last_owner"] = task.get("last_owner") or task.get("owner")
        task["previous_terminal_status"] = status
        if "reason" in task:
            task["previous_terminal_reason"] = task["reason"]
        task.update(
            {
                "status": "retry_ready",
                "resume_reason": reason,
                "last_attempt_summary": last_attempt_summary,
                "next_attempt_instruction": next_attempt_instruction,
                "resumed_by": worker_id,
                "resumed_at": self._iso_now(),
                "retry_ready_at": self._iso_now(),
            }
        )
        self._clear_lease(task)
        return {"ok": True, "task_id": task_id, "status": "retry_ready"}

    def continue_task(self, state: State, *, task_id: str, worker_id: str) -> Receipt:
        task = self._tasks(state).get(task_id)
        if task is None:
            return self._not_found(task_id)
        if task.get("status", "pending") != "retry_ready":
            return {
                "ok": False,
                "reason": "task_not_retry_ready",
                "task_id": task_id,
                "status": task.get("status"),
            }
        preferred_worker = task.get("preferred_worker") or task.get("retry_owner")
        if preferred_worker and preferred_worker != worker_id:
            return {
                "ok": False,
                "reason": "worker_not_preferred",
                "task_id": task_id,
                "preferred_worker": preferred_worker,
            }
        attempt = _int_value(task.get("attempt"))
        max_attempts = _int_value(task.get("max_attempts"))
        if task.get("max_attempts") is not None and attempt >= max_attempts:
            return {
                "ok": False,
                "reason": "max_attempts_reached",
                "task_id": task_id,
                "attempt": attempt,
                "max_attempts": max_attempts,
            }
        missing = self._dependencies_done(task, self._tasks(state))
        if missing:
            return {
                "ok": False,
                "reason": "dependency_not_satisfied",
                "missing": missing,
            }
        conflict = self._active_conflict(task_id, task, self._tasks(state))
        if conflict is not None:
            return conflict
        self._start(task, worker_id)
        return self._continue_receipt(task_id, task)

    def block(
        self, state: State, *, task_id: str, worker_id: str, reason: str
    ) -> Receipt:
        return self._terminal(state, task_id, worker_id, reason, "blocked")

    def fail(
        self, state: State, *, task_id: str, worker_id: str, reason: str
    ) -> Receipt:
        return self._terminal(state, task_id, worker_id, reason, "failed")

    def release_expired(self, state: State) -> Receipt:
        tasks = self._tasks(state)
        released: list[str] = []
        for task_id, task in tasks.items():
            if task.get("status") not in _ACTIVE_STATUSES or self._is_active_lease(
                task
            ):
                continue
            self._clear_lease(task)
            task["status"] = (
                "ready"
                if not self._dependencies_done(task, tasks)
                else "blocked_waiting_dependency"
            )
            task["released_at"] = self._iso_now()
            released.append(task_id)
        return {"ok": True, "released": released}

    def _terminal(
        self, state: State, task_id: str, worker_id: str, reason: str, status: str
    ) -> Receipt:
        task = self._owned_task(state, task_id, worker_id)
        if "ok" in task:
            return task
        task.update(
            {
                "status": status,
                "reason": reason,
                "last_owner": worker_id,
                f"{status}_at": self._iso_now(),
            }
        )
        self._clear_lease(task)
        return {"ok": True, "task_id": task_id, "status": status}

    def _tasks(self, state: State) -> dict[str, Task]:
        raw_tasks = state.get("tasks")
        if not isinstance(raw_tasks, MutableMapping):
            state["tasks"] = {}
            return {}
        return {
            str(key): cast(Task, value)
            for key, value in raw_tasks.items()
            if isinstance(value, MutableMapping)
        }

    def _owned_task(self, state: State, task_id: str, worker_id: str) -> Task | Receipt:
        task = self._tasks(state).get(task_id)
        if task is None:
            return self._not_found(task_id)
        if task.get("owner") != worker_id:
            return {"ok": False, "reason": "not_task_owner", "task_id": task_id}
        if not self._is_active_lease(task):
            return {"ok": False, "reason": "lease_expired", "task_id": task_id}
        return task

    def _ready_task_ids(self, state: State) -> list[str]:
        tasks = self._tasks(state)
        return [
            task_id
            for task_id, task in tasks.items()
            if task.get("status", "pending") in _CLAIMABLE_STATUSES
            and not self._dependencies_done(task, tasks)
            and self._active_conflict(task_id, task, tasks) is None
            and not self._is_active_lease(task)
        ]

    def _blocked_candidates(
        self,
        tasks: dict[str, Task],
        worker_id: str,
        profile: Task,
        filtered: list[Receipt],
    ) -> list[Receipt]:
        blocked = list(filtered)
        filtered_ids = {str(item["task_id"]) for item in filtered}
        for task_id, task in tasks.items():
            if task_id in filtered_ids or task.get("status", "pending") == "done":
                continue
            missing = self._dependencies_done(task, tasks)
            if missing:
                blocked.append(
                    {
                        "task_id": task_id,
                        "reason": "dependency_not_satisfied",
                        "missing_dependencies": missing,
                    }
                )
                continue
            conflict = self._active_conflict(task_id, task, tasks)
            if conflict is not None:
                blocked.append(
                    {
                        "task_id": task_id,
                        "reason": "conflict_domain_locked",
                        "conflict_domain": conflict["conflict_domain"],
                        "owner": conflict["owner"],
                    }
                )
                continue
            reason = self._profile_filter_reason(task, worker_id, profile)
            if reason is not None:
                blocked.append({"task_id": task_id, **reason})
        return blocked

    def _dependencies_done(self, task: Task, tasks: dict[str, Task]) -> list[str]:
        dependencies = task.get("depends_on", [])
        if not isinstance(dependencies, list):
            return []
        return [
            str(dependency)
            for dependency in dependencies
            if tasks.get(str(dependency), {}).get("status") != "done"
        ]

    def _active_conflict(
        self, task_id: str, task: Task, tasks: dict[str, Task]
    ) -> Receipt | None:
        domain = task.get("conflict_domain")
        if not domain:
            return None
        for other_id, other_task in tasks.items():
            if (
                other_id != task_id
                and other_task.get("conflict_domain") == domain
                and self._is_active_lease(other_task)
            ):
                return {
                    "ok": False,
                    "reason": "conflict_domain_locked",
                    "conflict_domain": domain,
                    "owner": other_task.get("owner"),
                    "task_id": other_id,
                }
        return None

    def _is_active_lease(self, task: Task) -> bool:
        return (
            task.get("status") in _ACTIVE_STATUSES
            and (
                _parse_datetime(task.get("lease_expires_at"))
                or datetime.min.replace(tzinfo=UTC)
            )
            > self._now()
        )

    def _start(self, task: Task, worker_id: str) -> None:
        task["status"] = "running"
        task["owner"] = worker_id
        task["attempt"] = _int_value(task.get("attempt")) + 1
        task["started_at"] = task.get("started_at", self._iso_now())
        task["last_heartbeat_at"] = self._iso_now()
        task["lease_expires_at"] = self._lease_expiry()

    def _staff_profiles(self, state: State) -> dict[str, Task]:
        model = state.get("staff_model")
        staff = model.get("staff") if isinstance(model, MutableMapping) else None
        return (
            {
                str(key): cast(Task, value)
                for key, value in staff.items()
                if isinstance(value, MutableMapping)
            }
            if isinstance(staff, MutableMapping)
            else {}
        )

    def _profile_filter_reason(
        self, task: Task, worker_id: str, _profile: Task
    ) -> Receipt | None:
        if (
            task.get("required_worker") is not None
            and task.get("required_worker") != worker_id
        ):
            return {
                "reason": "required_worker_mismatch",
                "required_worker": str(task["required_worker"]),
            }
        return None

    def _recommendation_rank(
        self, task: Task, task_id: str, worker_id: str
    ) -> tuple[int, str]:
        return (0 if task.get("preferred_worker") == worker_id else 1, task_id)

    def _continue_receipt(self, task_id: str, task: Task) -> Receipt:
        fields = (
            "worker_prompt",
            "acceptance_criteria",
            "last_attempt_summary",
            "next_attempt_instruction",
            "attempt",
            "max_attempts",
            "writable_files",
            "read_only_files",
            "must_not_touch",
            "lease_expires_at",
        )
        return {
            "ok": True,
            "task_id": task_id,
            "status": "running",
            **{field: task[field] for field in fields if field in task},
        }

    def _running_receipt(self, task_id: str, task: Task) -> Receipt:
        return {
            "ok": True,
            "task_id": task_id,
            "status": "running",
            "owner": task.get("owner"),
            "lease_expires_at": task.get("lease_expires_at"),
        }

    def _clear_lease(self, task: Task) -> None:
        for field in ("owner", "lease_expires_at", "last_heartbeat_at"):
            task.pop(field, None)

    def _lease_expiry(self) -> str:
        return (self._now() + self._lease_duration).astimezone(UTC).isoformat()

    def _iso_now(self) -> str:
        return self._now().astimezone(UTC).isoformat()

    def _not_found(self, task_id: str) -> Receipt:
        return {"ok": False, "reason": "task_not_found", "task_id": task_id}


def _int_value(value: object) -> int:
    try:
        return int(cast(str, value))
    except (TypeError, ValueError):
        return 0


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value
        )
    except ValueError:
        return None
    return (
        parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)
