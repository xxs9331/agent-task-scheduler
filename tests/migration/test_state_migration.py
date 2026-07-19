from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_task_scheduler.migration import (
    MigrationError,
    migrate_file,
    migrate_state_document,
)


def _legacy_state() -> dict[str, object]:
    return {
        "schema_version": 1,
        "project_id": "demo",
        "tasks": {
            "task_a": {
                "task_id": "task_a",
                "status": "ready",
                "agent_type": "task_executor",
                "depends_on": [],
                "conflict_domain": "demo",
                "preferred_worker": "worker",
                "worker_prompt": {},
                "created_at": "2026-07-13T00:00:00+00:00",
                "owner": "worker",
                "attempt": 1,
            }
        },
        "task_order": ["task_a"],
    }


def test_that_migration_adds_canonical_history_without_mutating_dry_run() -> None:
    source = _legacy_state()
    migrated, changes = migrate_state_document(source, project_id="demo")
    assert migrated["schema_version"] == 1
    assert migrated["publish_history"] == []
    assert migrated["tasks"]["task_a"]["owner"] == "worker"  # type: ignore[index]
    assert "publish_history" in changes


def test_that_migration_uses_resolved_project_id_when_legacy_root_omits_it() -> None:
    source = _legacy_state()
    del source["project_id"]
    source["legacy_runtime_metadata"] = {"owner": "legacy"}
    migrated, _ = migrate_state_document(source, project_id="demo")
    assert migrated["project_id"] == "demo"
    assert "legacy_runtime_metadata" not in migrated


def test_that_unknown_higher_schema_is_rejected() -> None:
    source = _legacy_state()
    source["schema_version"] = 99
    with pytest.raises(MigrationError):
        migrate_state_document(source, project_id="demo")


def test_that_unknown_lower_schema_is_not_skipped() -> None:
    source = _legacy_state()
    source["schema_version"] = 0
    with pytest.raises(MigrationError, match="unsupported"):
        migrate_state_document(source, project_id="demo")


def test_that_failed_migration_preserves_original_bytes(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    original = json.dumps({"schema_version": 99}, separators=(",", ":")).encode()
    state_path.write_bytes(original)
    with pytest.raises(MigrationError):
        migrate_file(state_path, project_id="demo", dry_run=False)
    assert state_path.read_bytes() == original


def test_that_migration_dry_run_preserves_original_bytes(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    original = json.dumps(_legacy_state(), separators=(",", ":")).encode()
    state_path.write_bytes(original)
    receipt = migrate_file(state_path, project_id="demo", dry_run=True)
    assert receipt["target_schema_version"] == 1
    assert state_path.read_bytes() == original


def test_that_migration_rejects_dependency_cycles() -> None:
    source = _legacy_state()
    task = source["tasks"]["task_a"]  # type: ignore[index]
    task["depends_on"] = ["task_a"]
    with pytest.raises(MigrationError):
        migrate_state_document(source, project_id="demo")


def test_that_migration_rejects_multi_task_dependency_cycles() -> None:
    source = _legacy_state()
    source["tasks"]["task_b"] = dict(source["tasks"]["task_a"])  # type: ignore[index]
    source["tasks"]["task_b"]["task_id"] = "task_b"  # type: ignore[index]
    source["tasks"]["task_a"]["depends_on"] = ["task_b"]  # type: ignore[index]
    source["tasks"]["task_b"]["depends_on"] = ["task_a"]  # type: ignore[index]
    with pytest.raises(MigrationError, match="cycle"):
        migrate_state_document(source, project_id="demo")


def test_that_migration_receipt_reports_mapping_counts_and_defaults(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(_legacy_state()), encoding="utf-8")

    receipt = migrate_file(state_path, project_id="demo", dry_run=True)

    assert receipt["source_format"] == "scheduler_legacy_v1"
    assert receipt["mapped_field_counts"]["tasks"] == 1
    assert receipt["defaults_applied"] == ["publish_history"]
    assert receipt["warnings"] == []
