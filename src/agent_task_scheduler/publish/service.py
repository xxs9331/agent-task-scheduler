"""Validate and atomically apply strict publish envelopes."""

from __future__ import annotations

from collections.abc import Callable, Mapping, MutableMapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from agent_task_scheduler.history import append_publish_history


Receipt = dict[str, object]
_CREATE_FIELDS = {
    "task_id",
    "agent_type",
    "depends_on",
    "conflict_domain",
    "preferred_worker",
    "required_worker",
    "writable_files",
    "worker_prompt",
    "title",
    "description",
    "metadata",
}
_REQUIRED_CREATE_FIELDS = {
    "task_id",
    "agent_type",
    "depends_on",
    "conflict_domain",
    "preferred_worker",
    "worker_prompt",
    "metadata",
}
_UPDATE_FIELDS = _CREATE_FIELDS - {"task_id", "required_worker"}
_UPDATABLE_STATUSES = {"ready", "blocked_waiting_dependency"}


class PublishService:
    """Own create/update validation and all-or-nothing state mutations."""

    def __init__(
        self,
        *,
        now: Callable[[], datetime] | None = None,
        event_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._now = now or _utc_now
        self._event_id_factory = event_id_factory or _new_event_id

    def publish(
        self,
        state: MutableMapping[str, object],
        *,
        envelope: object,
        update: bool,
    ) -> Receipt:
        """Validate an envelope before replacing state with its complete result."""
        expected_operation = "update" if update else "create"
        parsed, error = self._validate_envelope(envelope, expected_operation)
        if error is not None:
            return error
        assert parsed is not None
        if state.get("schema_version") != 1:
            return _failure(
                "STATE_SCHEMA_UNSUPPORTED", "unsupported state schema version"
            )
        if state.get("project_id") != parsed["project_id"]:
            return _failure("PROJECT_ID_MISMATCH", "state project does not match input")

        proposed = deepcopy(dict(state))
        tasks = proposed.get("tasks")
        if not isinstance(tasks, dict):
            return _failure("INPUT_SCHEMA_INVALID", "state tasks must be an object")
        receipt = (
            self._apply_update(proposed, parsed["tasks"])
            if update
            else self._apply_create(proposed, parsed["tasks"])
        )
        if receipt["ok"] is False:
            return receipt
        graph_error = _validate_dependency_graph(tasks)
        if graph_error is not None:
            return graph_error
        state.clear()
        state.update(proposed)
        return receipt

    def _validate_envelope(
        self, envelope: object, expected_operation: str
    ) -> tuple[dict[str, Any] | None, Receipt | None]:
        if not isinstance(envelope, Mapping):
            return None, _failure(
                "INPUT_SCHEMA_INVALID", "publish envelope must be an object"
            )
        if envelope.get("operation") != expected_operation:
            return None, _failure(
                "PUBLISH_OPERATION_MISMATCH", "CLI mode and envelope operation disagree"
            )
        if envelope.get("input_schema_version") != 1:
            return None, _failure(
                "INPUT_SCHEMA_INVALID", "unsupported input schema version"
            )
        project_id = envelope.get("project_id")
        tasks = envelope.get("tasks")
        if (
            not isinstance(project_id, str)
            or not project_id
            or not isinstance(tasks, list)
            or not tasks
        ):
            return None, _failure(
                "INPUT_SCHEMA_INVALID", "project_id and non-empty tasks are required"
            )
        if set(envelope) != {
            "input_schema_version",
            "project_id",
            "operation",
            "tasks",
        }:
            return None, _failure(
                "INPUT_SCHEMA_INVALID", "publish envelope contains unknown fields"
            )
        return {"project_id": project_id, "tasks": tasks}, None

    def _apply_create(
        self, proposed: dict[str, object], items: list[object]
    ) -> Receipt:
        tasks = proposed["tasks"]
        assert isinstance(tasks, dict)
        normalized: list[dict[str, object]] = []
        task_ids: set[str] = set()
        for item in items:
            task, error = _normalize_create(item)
            if error is not None:
                return error
            assert task is not None
            task_id = task["task_id"]
            assert isinstance(task_id, str)
            if task_id in task_ids or task_id in tasks:
                return _failure(
                    "TASK_ID_DUPLICATE", "task_id already exists or repeats in batch"
                )
            task_ids.add(task_id)
            normalized.append(task)
        now = _iso(self._now())
        for task in normalized:
            task["created_at"] = now
            task["status"] = "ready"
            tasks[task["task_id"]] = task
        for task in normalized:
            task["status"] = _derived_status(task, tasks)
            append_publish_history(
                proposed,
                event_type="published",
                project_id=str(proposed["project_id"]),
                task_id=str(task["task_id"]),
                change_summary={"operation": "create", "changed_fields": sorted(task)},
                now=self._now,
                event_id_factory=self._event_id_factory,
            )
        return {
            "ok": True,
            "operation": "create",
            "task_ids": [task["task_id"] for task in normalized],
        }

    def _apply_update(
        self, proposed: dict[str, object], items: list[object]
    ) -> Receipt:
        tasks = proposed["tasks"]
        assert isinstance(tasks, dict)
        task_ids: set[str] = set()
        changes: list[tuple[str, dict[str, object]]] = []
        for item in items:
            if not isinstance(item, Mapping) or set(item) != {"task_id", "patch"}:
                return _failure(
                    "INPUT_SCHEMA_INVALID",
                    "update item must contain task_id and patch only",
                )
            task_id, patch = item.get("task_id"), item.get("patch")
            if (
                not isinstance(task_id, str)
                or not task_id
                or task_id in task_ids
                or not isinstance(patch, Mapping)
            ):
                return _failure(
                    "INPUT_SCHEMA_INVALID", "invalid update task_id or patch"
                )
            task_ids.add(task_id)
            normalized_patch, error = _normalize_patch(patch)
            if error is not None:
                return error
            assert normalized_patch is not None
            current = tasks.get(task_id)
            if (
                not isinstance(current, dict)
                or current.get("status") not in _UPDATABLE_STATUSES
            ):
                return _failure(
                    "TASK_UPDATE_FORBIDDEN", "update target is not eligible"
                )
            changes.append((task_id, normalized_patch))
        for task_id, patch in changes:
            tasks[task_id].update(patch)
        for task_id, patch in changes:
            task = tasks[task_id]
            task["status"] = _derived_status(task, tasks)
            append_publish_history(
                proposed,
                event_type="publish_updated",
                project_id=str(proposed["project_id"]),
                task_id=task_id,
                change_summary={"operation": "update", "changed_fields": sorted(patch)},
                now=self._now,
                event_id_factory=self._event_id_factory,
            )
        return {
            "ok": True,
            "operation": "update",
            "task_ids": [task_id for task_id, _ in changes],
        }


def _normalize_create(item: object) -> tuple[dict[str, object] | None, Receipt | None]:
    if (
        not isinstance(item, Mapping)
        or set(item) - _CREATE_FIELDS
        or set(item) < _REQUIRED_CREATE_FIELDS
    ):
        return None, _failure("INPUT_SCHEMA_INVALID", "invalid create task fields")
    task = dict(item)
    if not _valid_task_fields(task):
        return None, _failure("INPUT_SCHEMA_INVALID", "invalid create task values")
    return task, None


def _normalize_patch(
    patch: Mapping[object, object],
) -> tuple[dict[str, object] | None, Receipt | None]:
    if not patch or set(patch) - _UPDATE_FIELDS:
        return None, _failure(
            "INPUT_SCHEMA_INVALID", "update patch contains forbidden fields"
        )
    normalized = dict(patch)
    if not _valid_task_fields(normalized, partial=True):
        return None, _failure("INPUT_SCHEMA_INVALID", "invalid update patch values")
    return normalized, None


def _valid_task_fields(task: Mapping[str, object], *, partial: bool = False) -> bool:
    string_fields = {
        "task_id",
        "agent_type",
        "conflict_domain",
        "preferred_worker",
        "required_worker",
        "title",
        "description",
    }
    for field in string_fields & set(task):
        if not isinstance(task[field], str) or not task[field]:
            return False
    if "depends_on" in task and (
        not isinstance(task["depends_on"], list)
        or not all(isinstance(value, str) and value for value in task["depends_on"])
    ):
        return False
    if "writable_files" in task and (
        not isinstance(task["writable_files"], list)
        or not all(isinstance(value, str) and value for value in task["writable_files"])
    ):
        return False
    valid_mappings = all(
        not isinstance(task.get(field), bool) and isinstance(task.get(field), Mapping)
        for field in ("worker_prompt", "metadata")
        if field in task
    )
    return valid_mappings and (
        "metadata" not in task or _valid_team_mode_metadata(task["metadata"])
    )


def _valid_team_mode_metadata(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    team_mode = value.get("team_mode")
    return (
        isinstance(team_mode, Mapping)
        and isinstance(team_mode.get("kind"), str)
        and bool(str(team_mode["kind"]).strip())
    )


def _validate_dependency_graph(tasks: Mapping[str, object]) -> Receipt | None:
    graph: dict[str, list[str]] = {}
    for task_id, raw_task in tasks.items():
        if not isinstance(raw_task, Mapping) or not isinstance(
            raw_task.get("depends_on"), list
        ):
            return _failure("DEPENDENCY_INVALID", "task dependencies must be a list")
        dependencies = raw_task["depends_on"]
        if any(
            not isinstance(dependency, str)
            or dependency not in tasks
            or dependency == task_id
            for dependency in dependencies
        ):
            return _failure(
                "DEPENDENCY_INVALID", "dependency is missing or self-referential"
            )
        graph[str(task_id)] = list(dependencies)
    visited: set[str] = set()
    active: set[str] = set()

    def visit(task_id: str) -> bool:
        if task_id in active:
            return True
        if task_id in visited:
            return False
        visited.add(task_id)
        active.add(task_id)
        cyclic = any(visit(dependency) for dependency in graph[task_id])
        active.remove(task_id)
        return cyclic

    return (
        _failure("DEPENDENCY_INVALID", "dependency graph contains a cycle")
        if any(visit(task_id) for task_id in graph)
        else None
    )


def _derived_status(task: Mapping[str, object], tasks: Mapping[str, object]) -> str:
    dependencies = task.get("depends_on", [])
    return (
        "ready"
        if all(
            isinstance(tasks.get(dep), Mapping) and tasks[dep].get("status") == "done"
            for dep in dependencies
        )
        else "blocked_waiting_dependency"
    )


def _failure(code: str, message: str) -> Receipt:
    return {"ok": False, "error": {"code": code, "message": message}}


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_event_id() -> str:
    return str(uuid4())
