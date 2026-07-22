import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent_task_scheduler.lease_guard import ForegroundLeaseGuard, LeaseGuard
from agent_task_scheduler.lifecycle.service import LifecycleService


def test_guard_renews_a_fenced_lease_for_multiple_periods_without_sleep() -> None:
    now = [datetime(2026, 7, 22, tzinfo=UTC)]
    state = _state()
    service = LifecycleService(now=lambda: now[0], lease_duration=timedelta(seconds=9))
    claim = service.claim(state, task_id="task", worker_id="role-a")
    events: list[dict[str, object]] = []
    calls = 0

    def wait(seconds: int) -> bool:
        nonlocal calls
        assert seconds == 2
        now[0] += timedelta(seconds=seconds)
        calls += 1
        return calls == 7

    guard = LeaseGuard(
        lambda: service.heartbeat(
            state, task_id="task", worker_id="role-a", lease_id=str(claim["lease_id"])
        ),
        wait,
        lambda: True,
        events.append,
        service.heartbeat_interval_seconds,
    )

    assert guard.run() == 0
    assert [event["event"] for event in events] == [
        "start",
        "renew",
        "renew",
        "renew",
        "renew",
        "renew",
        "renew",
        "stop",
    ]
    assert state["tasks"]["task"]["lease_expires_at"] > now[0].isoformat()


def test_guard_fails_closed_after_stale_or_lost_supervisor() -> None:
    events: list[dict[str, object]] = []
    stale = LeaseGuard(
        lambda: {"ok": False, "reason": "stale_lease"},
        lambda _: False,
        lambda: True,
        events.append,
        1,
    )
    assert stale.run() == 1
    assert events[-1]["reason"] == "stale_lease"
    events.clear()
    lost = LeaseGuard(
        lambda: {"ok": True}, lambda _: False, lambda: False, events.append, 1
    )
    assert lost.run() == 1
    assert events[-1]["reason"] == "supervisor_lost"


def test_status_reports_exact_lease_health_boundaries() -> None:
    now = [datetime(2026, 7, 22, tzinfo=UTC)]
    state = _state()
    service = LifecycleService(now=lambda: now[0], lease_duration=timedelta(seconds=9))
    service.claim(state, task_id="task", worker_id="role-a")
    now[0] += timedelta(seconds=7)
    assert service.status(state)["lease_health"] == [
        {
            "task_id": "task",
            "owner": "role-a",
            "lease_expires_at": "2026-07-22T00:00:09+00:00",
            "remaining_seconds": 2.0,
            "health": "near_expiry",
        }
    ]


def test_supervisor_pipe_loss_reaps_a_foreground_subprocess_without_polling() -> None:
    guard = ForegroundLeaseGuard.start(
        [sys.executable, "-c", "import sys; sys.stdin.buffer.read()"]
    )

    assert guard.stop_and_reap(timeout_seconds=1) == 0
    assert guard.process.poll() == 0


def test_claim_guard_flushes_receipt_then_exits_when_its_supervisor_pipe_closes(
    tmp_path: Path,
) -> None:
    scheduler = tmp_path / ".scheduler"
    scheduler.mkdir()
    (scheduler / "project.json").write_text(
        json.dumps(
            {
                "config_schema_version": 1,
                "project_id": "guard-test",
                "state_path": ".scheduler/state.json",
                "events_path": None,
            }
        ),
        encoding="utf-8",
    )
    state = _state()
    (scheduler / "state.json").write_text(json.dumps(state), encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parents[2] / "src")}
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agent_task_scheduler.cli.main",
            "--project-root",
            str(tmp_path),
            "claim",
            "--task",
            "task",
            "--worker",
            "role-a",
            "--guard",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert process.stdout is not None
    initial = json.loads(process.stdout.readline())
    assert initial["ok"] is True
    assert initial["lease_id"]
    assert initial["heartbeat_interval_seconds"] < 300
    assert process.stdin is not None
    process.stdin.close()
    assert process.wait(timeout=2) == 1
    final = json.loads(process.stdout.readline())
    assert final["events"][-1]["reason"] == "supervisor_lost"
    assert process.poll() == 1


def _state() -> dict[str, object]:
    return {
        "tasks": {
            "task": {
                "task_id": "task",
                "status": "ready",
                "agent_type": "task_executor",
                "depends_on": [],
                "conflict_domain": "guard",
                "preferred_worker": "role-a",
                "worker_prompt": {},
                "created_at": "2026-07-22T00:00:00+00:00",
            }
        },
        "staff_model": {
            "staff": {
                "role-a": {
                    "can_execute_tasks": True,
                    "allowed_agent_types": ["task_executor"],
                    "allowed_task_kinds": ["unclassified"],
                    "required_metadata_by_kind": {},
                }
            }
        },
    }
