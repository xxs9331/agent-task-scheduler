import json
from pathlib import Path

from jsonschema import Draft202012Validator

import agent_task_scheduler.cli.main as cli_main
from agent_task_scheduler.cli.main import main


def test_that_publish_cli_commits_a_create_envelope_to_the_resolved_project(
    tmp_path: Path, capsys
) -> None:
    scheduler = tmp_path / ".scheduler"
    scheduler.mkdir()
    (scheduler / "project.json").write_text(
        json.dumps(
            {
                "config_schema_version": 1,
                "project_id": "example",
                "state_path": ".scheduler/state.json",
            }
        ),
        encoding="utf-8",
    )
    envelope = tmp_path / "publish.json"
    envelope.write_text(
        json.dumps(
            {
                "input_schema_version": 1,
                "project_id": "example",
                "operation": "create",
                "tasks": [
                    {
                        "task_id": "task-a",
                        "agent_type": "task_executor",
                        "depends_on": [],
                        "conflict_domain": "core",
                        "preferred_worker": "worker",
                        "worker_prompt": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        ["--project-root", str(tmp_path), "publish", "--from-file", str(envelope)]
    )

    assert exit_code == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["ok"] is True
    assert receipt["operation"] == "publish"
    assert receipt["changed_task_ids"] == ["task-a"]
    assert receipt["warnings"] == []
    _validate_success_receipt(receipt)
    assert (
        json.loads((scheduler / "state.json").read_text(encoding="utf-8"))["tasks"][
            "task-a"
        ]["status"]
        == "ready"
    )


def test_that_init_fresh_creates_a_canonical_project_and_replaces_its_state(
    tmp_path: Path, capsys
) -> None:
    scheduler = tmp_path / ".scheduler"
    scheduler.mkdir()
    (scheduler / "state.json").write_text('{"stale": true}', encoding="utf-8")

    exit_code = main(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "--fresh",
            "--project-id",
            "fresh-project",
        ]
    )

    receipt = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert receipt == {
        "ok": True,
        "operation": "init",
        "changed_task_ids": [],
        "warnings": [],
        "project": {"project_id": "fresh-project", "root": str(tmp_path)},
    }
    assert json.loads((scheduler / "project.json").read_text(encoding="utf-8")) == {
        "config_schema_version": 1,
        "project_id": "fresh-project",
        "state_path": ".scheduler/state.json",
        "events_path": None,
    }
    assert json.loads((scheduler / "state.json").read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "project_id": "fresh-project",
        "tasks": {},
        "publish_history": [],
        "review_decisions": [],
        "staff_model": {"staff": {}},
    }


def test_that_publish_accepts_exactly_one_json_input_source(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    _create_project(tmp_path, events_path=None)
    json_project = tmp_path / "json-project"
    json_project.mkdir()
    _create_project(json_project, events_path=None)
    envelope = json.dumps(_create_envelope())
    monkeypatch.setattr("sys.stdin.read", lambda: envelope)

    stdin_exit = main(["--project-root", str(tmp_path), "publish", "--stdin"])
    stdin_receipt = json.loads(capsys.readouterr().out)
    json_exit = main(
        ["--project-root", str(json_project), "publish", "--json", envelope]
    )
    json_receipt = json.loads(capsys.readouterr().out)

    assert stdin_exit == json_exit == 0
    assert stdin_receipt["changed_task_ids"] == ["task-a"]
    assert json_receipt["changed_task_ids"] == ["task-a"]


def test_that_review_correction_preserves_terminal_summary_and_appends_superseding_facts(
    tmp_path: Path, capsys
) -> None:
    scheduler = _create_project(tmp_path, events_path=None)
    state_path = scheduler / "state.json"
    state = _legacy_state()
    task = state["tasks"]["task-a"]
    assert isinstance(task, dict)
    task.update({"status": "done", "summary": "initial hold"})
    state_path.write_text(json.dumps(state), encoding="utf-8")

    first_exit = main(
        [
            "--project-root",
            str(tmp_path),
            "review-correct",
            "--task",
            "task-a",
            "--reviewer",
            "role-r",
            "--verdict",
            "pass",
            "--summary",
            "focused suite now passes",
        ]
    )
    first = json.loads(capsys.readouterr().out)
    second_exit = main(
        [
            "--project-root",
            str(tmp_path),
            "review-correct",
            "--task",
            "task-a",
            "--reviewer",
            "role-r",
            "--verdict",
            "hold",
            "--summary",
            "final smoke still pending",
        ]
    )
    second = json.loads(capsys.readouterr().out)
    persisted = json.loads(state_path.read_text(encoding="utf-8"))

    assert first_exit == second_exit == 0
    assert first["operation"] == second["operation"] == "review_correction"
    assert persisted["tasks"]["task-a"]["summary"] == "initial hold"
    decisions = persisted["review_decisions"]
    assert decisions[0]["supersedes"] == {
        "kind": "terminal_summary",
        "summary": "initial hold",
        "terminal_status": "done",
    }
    assert decisions[1]["supersedes"] == {
        "kind": "review_decision",
        "event_id": decisions[0]["event_id"],
    }
    assert second["supersedes_event_id"] == decisions[0]["event_id"]
    state_schema = json.loads(
        (Path(__file__).parents[2] / "schemas" / "state.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(state_schema).validate(persisted)


def test_that_operation_mismatch_is_reported_before_the_lock_is_created(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _create_project(tmp_path, events_path=None)
    envelope = tmp_path / "publish.json"
    envelope.write_text(
        json.dumps(
            {
                "input_schema_version": 1,
                "project_id": "example",
                "operation": "update",
                "tasks": [],
            }
        ),
        encoding="utf-8",
    )

    class UnexpectedLock:
        def __init__(self, *_args, **_kwargs) -> None:
            raise AssertionError("operation mismatch must not acquire a lock")

    monkeypatch.setattr(cli_main, "StateLock", UnexpectedLock)

    exit_code = main(
        ["--project-root", str(tmp_path), "publish", "--from-file", str(envelope)]
    )

    assert exit_code == 1
    assert (
        json.loads(capsys.readouterr().out)["error"]["code"]
        == "PUBLISH_OPERATION_MISMATCH"
    )


def test_that_publish_returns_a_warning_when_optional_observation_logging_fails(
    tmp_path: Path, capsys
) -> None:
    _create_project(tmp_path, events_path=".scheduler")
    envelope = _write_create_envelope(tmp_path)

    exit_code = main(
        ["--project-root", str(tmp_path), "publish", "--from-file", str(envelope)]
    )

    receipt = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert receipt["ok"] is True
    assert receipt["warnings"][0]["code"] == "OBSERVATION_LOG_WARNING"


def test_that_lifecycle_and_migration_commands_are_exposed_through_the_cli(
    tmp_path: Path, capsys
) -> None:
    scheduler = _create_project(tmp_path, events_path=None)
    state_path = scheduler / "state.json"
    state_path.write_text(json.dumps(_legacy_state()), encoding="utf-8")

    status_exit = main(["--project-root", str(tmp_path), "status"])
    status = json.loads(capsys.readouterr().out)
    check_exit = main(["--project-root", str(tmp_path), "migrate", "--check"])
    check = json.loads(capsys.readouterr().out)
    dry_exit = main(["--project-root", str(tmp_path), "migrate", "--dry-run"])
    dry = json.loads(capsys.readouterr().out)
    migrate_exit = main(["--project-root", str(tmp_path), "migrate"])
    migrated = json.loads(capsys.readouterr().out)

    assert status_exit == check_exit == dry_exit == migrate_exit == 0
    assert status["ok"] is True
    assert check["operation"] == dry["operation"] == migrated["operation"] == "migrate"
    _validate_success_receipt(check)
    _validate_success_receipt(dry)
    _validate_success_receipt(migrated)
    assert state_path.read_text(encoding="utf-8") != json.dumps(_legacy_state())


def test_that_continue_cli_routes_to_continue_task_and_persists_state(
    tmp_path: Path, capsys
) -> None:
    scheduler = _create_project(tmp_path, events_path=None)
    state = _legacy_state()
    task = state["tasks"]["task-a"]
    assert isinstance(task, dict)
    task.update({"status": "retry_ready", "attempt": 1})
    state_path = scheduler / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    exit_code = main(
        [
            "--project-root",
            str(tmp_path),
            "continue",
            "--task",
            "task-a",
            "--worker",
            "worker",
        ]
    )

    receipt = json.loads(capsys.readouterr().out)
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert receipt["ok"] is True
    assert persisted["tasks"]["task-a"]["status"] == "running"
    assert persisted["tasks"]["task-a"]["owner"] == "worker"


def test_that_staff_sync_makes_claim_authority_machine_readable(
    tmp_path: Path, capsys
) -> None:
    scheduler = _create_project(tmp_path, events_path=None)
    state_path = scheduler / "state.json"
    state_path.write_text(json.dumps(_legacy_state()), encoding="utf-8")
    envelope = {
        "input_schema_version": 1,
        "workers": {
            "worker": {
                "can_execute_tasks": True,
                "allowed_agent_types": ["task_executor"],
                "allowed_task_kinds": ["unclassified"],
                "required_metadata_by_kind": {},
            }
        },
    }

    sync_exit = main(
        [
            "--project-root",
            str(tmp_path),
            "staff-sync",
            "--json",
            json.dumps(envelope),
        ]
    )
    sync_receipt = json.loads(capsys.readouterr().out)
    claim_exit = main(
        [
            "--project-root",
            str(tmp_path),
            "claim",
            "--task",
            "task-a",
            "--worker",
            "worker",
            "--agent-id",
            "thread-123",
        ]
    )
    claim_receipt = json.loads(capsys.readouterr().out)

    assert sync_exit == claim_exit == 0
    assert sync_receipt["operation"] == "staff_sync"
    assert claim_receipt["lease_id"]
    assert claim_receipt["lease_metadata"] == {"agent_id": "thread-123"}
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["staff_model"]["staff"]["worker"]["can_execute_tasks"] is True


def test_that_complete_cli_requires_and_checks_the_current_lease_token(
    tmp_path: Path, capsys
) -> None:
    scheduler = _create_project(tmp_path, events_path=None)
    state = _legacy_state()
    task = state["tasks"]["task-a"]
    assert isinstance(task, dict)
    task.update(
        {
            "status": "running",
            "owner": "worker",
            "lease_id": "current-token",
            "lease_metadata": {"agent_id": "thread-new"},
            "lease_expires_at": "2999-07-13T03:30:00+00:00",
        }
    )
    state_path = scheduler / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    stale_exit = main(
        [
            "--project-root",
            str(tmp_path),
            "complete",
            "--task",
            "task-a",
            "--worker",
            "worker",
            "--lease-id",
            "stale-token",
            "--summary",
            "should not commit",
        ]
    )
    stale_receipt = json.loads(capsys.readouterr().out)
    current_exit = main(
        [
            "--project-root",
            str(tmp_path),
            "complete",
            "--task",
            "task-a",
            "--worker",
            "worker",
            "--lease-id",
            "current-token",
            "--summary",
            "verified",
        ]
    )
    current_receipt = json.loads(capsys.readouterr().out)

    assert stale_exit == 1
    assert stale_receipt["reason"] == "stale_lease"
    assert current_exit == 0
    assert current_receipt["status"] == "done"
    assert current_receipt["summary"] == "verified"


def _validate_success_receipt(receipt: dict[str, object]) -> None:
    schema_path = Path(__file__).parents[2] / "schemas" / "receipt.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(receipt)


def _create_project(root: Path, *, events_path: str | None) -> Path:
    scheduler = root / ".scheduler"
    scheduler.mkdir()
    (scheduler / "project.json").write_text(
        json.dumps(
            {
                "config_schema_version": 1,
                "project_id": "example",
                "state_path": ".scheduler/state.json",
                "events_path": events_path,
            }
        ),
        encoding="utf-8",
    )
    return scheduler


def _write_create_envelope(root: Path) -> Path:
    envelope = root / "publish.json"
    envelope.write_text(json.dumps(_create_envelope()), encoding="utf-8")
    return envelope


def _create_envelope() -> dict[str, object]:
    return {
        "input_schema_version": 1,
        "project_id": "example",
        "operation": "create",
        "tasks": [
            {
                "task_id": "task-a",
                "agent_type": "task_executor",
                "depends_on": [],
                "conflict_domain": "core",
                "preferred_worker": "worker",
                "worker_prompt": {},
            }
        ],
    }


def _legacy_state() -> dict[str, object]:
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
                "preferred_worker": "worker",
                "worker_prompt": {},
                "created_at": "2026-07-13T00:00:00+00:00",
            }
        },
        "task_order": ["task-a"],
        "publish_history": [],
        "review_decisions": [],
        "staff_model": {
            "staff": {
                "worker": {
                    "can_execute_tasks": True,
                    "allowed_agent_types": ["task_executor"],
                    "allowed_task_kinds": ["unclassified"],
                    "required_metadata_by_kind": {},
                }
            }
        },
    }
