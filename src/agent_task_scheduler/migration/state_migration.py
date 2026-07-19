from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from agent_task_scheduler.locking import StateLock


class MigrationError(ValueError):
    """Raised when a state cannot be safely migrated."""


SUPPORTED_SCHEMA_VERSION = 1


def migrate_state_document(
    source: dict[str, Any],
    *,
    project_id: str,
) -> tuple[dict[str, Any], list[str]]:
    """Adapt a known scheduler legacy v1 state into the canonical v1 shape."""
    if not isinstance(source, dict):
        raise MigrationError("state must be a JSON object")
    source_version = source.get("schema_version")
    if not isinstance(source_version, int) or isinstance(source_version, bool):
        raise MigrationError("state schema_version must be an integer")
    if source_version != SUPPORTED_SCHEMA_VERSION:
        raise MigrationError(f"unsupported state schema version: {source_version}")
    source_project_id = source.get("project_id")
    if source_project_id is not None and source_project_id != project_id:
        raise MigrationError("state project_id does not match project")
    raw_tasks = source.get("tasks")
    if not isinstance(raw_tasks, dict):
        raise MigrationError("state tasks must be an object")

    changes: list[str] = []
    target: dict[str, Any] = {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "project_id": project_id,
        "tasks": _map_tasks(raw_tasks),
        "publish_history": copy.deepcopy(source.get("publish_history", [])),
    }
    if "publish_history" not in source:
        changes.append("publish_history")
    if "task_order" in source:
        target["task_order"] = copy.deepcopy(source["task_order"])
    else:
        target["task_order"] = list(raw_tasks)
        changes.append("task_order")
    _validate_canonical_state(target)
    return target, changes


def migrate_file(
    state_path: Path,
    *,
    project_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Migrate a state atomically, or return a dry-run receipt without writing."""
    original = state_path.read_bytes()
    try:
        source = json.loads(original)
        migrated, changes = migrate_state_document(source, project_id=project_id)
    except (OSError, json.JSONDecodeError, TypeError, MigrationError) as exc:
        if isinstance(exc, MigrationError):
            raise
        raise MigrationError(str(exc)) from exc
    receipt: dict[str, Any] = {
        "ok": True,
        "operation": "migrate",
        "source_schema_version": source.get("schema_version"),
        "target_schema_version": SUPPORTED_SCHEMA_VERSION,
        "changes": changes,
        "source_format": "scheduler_legacy_v1",
        "mapped_field_counts": {
            "tasks": len(migrated["tasks"]),
            "task_fields": sum(len(task) for task in migrated["tasks"].values()),
        },
        "defaults_applied": [
            change
            for change in changes
            if change
            in {
                "publish_history",
                "task_order",
            }
        ],
        "warnings": [],
    }
    if dry_run:
        return receipt
    lock_path = state_path.with_name(state_path.name + ".lock")
    with StateLock(lock_path):
        # Re-read and reconstruct the complete target under the lock so a
        # concurrent writer cannot be overwritten by a stale preflight result.
        current = state_path.read_bytes()
        source = json.loads(current)
        migrated, changes = migrate_state_document(source, project_id=project_id)
        receipt["source_schema_version"] = source.get("schema_version")
        receipt["changes"] = changes
        receipt["mapped_field_counts"] = {
            "tasks": len(migrated["tasks"]),
            "task_fields": sum(len(task) for task in migrated["tasks"].values()),
        }
        receipt["defaults_applied"] = [
            change for change in changes if change in {"publish_history", "task_order"}
        ]
        _atomic_write(state_path, migrated)
    return receipt


def _map_tasks(raw_tasks: dict[str, Any]) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for task_id, raw_task in raw_tasks.items():
        if not isinstance(task_id, str) or not isinstance(raw_task, dict):
            raise MigrationError("legacy tasks must map string ids to objects")
        task = copy.deepcopy(raw_task)
        task.setdefault("task_id", task_id)
        mapped[task_id] = task
    return mapped


def _validate_canonical_state(state: dict[str, Any]) -> None:
    required = {"schema_version", "project_id", "tasks", "publish_history"}
    if not required.issubset(state):
        raise MigrationError("canonical state is missing required fields")
    tasks = state["tasks"]
    if not isinstance(tasks, dict):
        raise MigrationError("canonical tasks must be an object")
    for task_id, task in tasks.items():
        if not isinstance(task, dict) or task.get("task_id") != task_id:
            raise MigrationError(f"task id mismatch: {task_id}")
        for field in (
            "status",
            "agent_type",
            "depends_on",
            "conflict_domain",
            "preferred_worker",
            "worker_prompt",
            "created_at",
        ):
            if field not in task:
                raise MigrationError(f"task {task_id} missing {field}")
    for task_id, task in tasks.items():
        dependencies = task["depends_on"]
        if not isinstance(dependencies, list) or any(
            dep not in tasks or dep == task_id for dep in dependencies
        ):
            raise MigrationError(f"invalid dependencies for task {task_id}")
    _validate_dependency_cycles(tasks)
    if not isinstance(state["publish_history"], list):
        raise MigrationError("publish_history must be an array")


def _validate_dependency_cycles(tasks: dict[str, Any]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visiting:
            raise MigrationError(f"dependency cycle detected at task {task_id}")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in tasks[task_id]["depends_on"]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in tasks:
        visit(task_id)


def _atomic_write(path: Path, document: dict[str, Any]) -> None:
    encoded = json.dumps(document, indent=2, sort_keys=True).encode("utf-8")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
