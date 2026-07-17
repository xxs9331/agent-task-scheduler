"""Linux/WSL end-to-end checks for installed scheduler behavior."""

from __future__ import annotations

import json
from pathlib import Path

from agent_task_scheduler.cli.main import main


def test_that_two_projects_isolate_lifecycle_and_observation_failure(
    tmp_path: Path, capsys
) -> None:
    alpha = _create_project(
        tmp_path / "alpha", project_id="alpha", events_path=".scheduler"
    )
    beta = _create_project(tmp_path / "beta", project_id="beta", events_path=None)
    alpha_envelope = _write_envelope(alpha, project_id="alpha", task_id="alpha-task")
    beta_envelope = _write_envelope(beta, project_id="beta", task_id="beta-task")

    alpha_publish = _run(
        capsys,
        ["--project-root", str(alpha), "publish", "--from-file", str(alpha_envelope)],
    )
    beta_publish = _run(
        capsys,
        ["--project-root", str(beta), "publish", "--from-file", str(beta_envelope)],
    )
    _run(
        capsys,
        [
            "--project-root",
            str(beta),
            "staff-sync",
            "--json",
            json.dumps(_staff_envelope()),
        ],
    )
    next_receipt = _run(
        capsys, ["--project-root", str(beta), "next", "--worker", "worker"]
    )
    claim_receipt = _run(
        capsys,
        [
            "--project-root",
            str(beta),
            "claim",
            "--task",
            "beta-task",
            "--worker",
            "worker",
            "--agent-id",
            "native-thread-1",
        ],
    )
    heartbeat_receipt = _run(
        capsys,
        [
            "--project-root",
            str(beta),
            "heartbeat",
            "--task",
            "beta-task",
            "--worker",
            "worker",
            "--lease-id",
            str(claim_receipt["lease_id"]),
        ],
    )
    complete_receipt = _run(
        capsys,
        [
            "--project-root",
            str(beta),
            "complete",
            "--task",
            "beta-task",
            "--worker",
            "worker",
            "--lease-id",
            str(claim_receipt["lease_id"]),
            "--summary",
            "linux isolation verified",
        ],
    )

    assert alpha_publish["warnings"][0]["code"] == "OBSERVATION_LOG_WARNING"
    assert beta_publish["warnings"] == []
    assert next_receipt["recommended_task_id"] == "beta-task"
    assert claim_receipt["status"] == heartbeat_receipt["status"] == "running"
    assert complete_receipt["status"] == "done"

    alpha_state = _state(alpha)
    beta_state = _state(beta)
    assert set(alpha_state["tasks"]) == {"alpha-task"}
    assert set(beta_state["tasks"]) == {"beta-task"}
    assert (
        len(alpha_state["publish_history"]) == len(beta_state["publish_history"]) == 1
    )


def _run(capsys, arguments: list[str]) -> dict[str, object]:
    assert main(arguments) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["ok"] is True
    return receipt


def _create_project(root: Path, *, project_id: str, events_path: str | None) -> Path:
    scheduler_directory = root / ".scheduler"
    scheduler_directory.mkdir(parents=True)
    (scheduler_directory / "project.json").write_text(
        json.dumps(
            {
                "config_schema_version": 1,
                "project_id": project_id,
                "state_path": ".scheduler/state.json",
                "events_path": events_path,
            }
        ),
        encoding="utf-8",
    )
    return root


def _write_envelope(root: Path, *, project_id: str, task_id: str) -> Path:
    path = root / "publish.json"
    path.write_text(
        json.dumps(
            {
                "input_schema_version": 1,
                "project_id": project_id,
                "operation": "create",
                "tasks": [
                    {
                        "task_id": task_id,
                        "agent_type": "task_executor",
                        "depends_on": [],
                        "conflict_domain": "linux-validation",
                        "preferred_worker": "worker",
                        "worker_prompt": {},
                        "metadata": {"team_mode": {"kind": "unclassified"}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _state(root: Path) -> dict[str, object]:
    return json.loads((root / ".scheduler" / "state.json").read_text(encoding="utf-8"))


def _staff_envelope() -> dict[str, object]:
    return {
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
