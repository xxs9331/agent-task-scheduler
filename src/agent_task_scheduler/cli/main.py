"""Machine-readable CLI adapters for scheduler core services."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import sys
import tempfile
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from agent_task_scheduler.core.scheduler import SchedulerCore
from agent_task_scheduler.lease_guard import LeaseGuard
from agent_task_scheduler.events import append_observation_event
from agent_task_scheduler.locking.state_lock import LockTimeoutError, StateLock
from agent_task_scheduler.migration import MigrationError, migrate_file
from agent_task_scheduler.project_context import (
    ProjectContext,
    ProjectContextError,
    discover_project_context,
)
from agent_task_scheduler.publish import PublishService


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            return _emit(_init(args))
        context = discover_project_context(
            current_directory=Path.cwd(), project_root=args.project_root
        )
        if args.command == "claim" and args.guard:
            return _claim_guard(args, context)
        receipt = _dispatch(args, context)
        receipt["project"] = {
            "project_id": context.project_id,
            "root": str(context.root),
        }
        return _emit(receipt)
    except ProjectContextError as error:
        return _emit(_failure(error.code, str(error)))
    except LockTimeoutError as error:
        return _emit(_failure("LOCK_TIMEOUT", str(error)))
    except MigrationError as error:
        return _emit(_failure("MIGRATION_INVALID", str(error)))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return _emit(_failure("INPUT_SCHEMA_INVALID", str(error)))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scheduler")
    parser.add_argument("--project-root", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--fresh", action="store_true", required=True)
    init.add_argument("--project-id")
    publish = commands.add_parser("publish")
    input_source = publish.add_mutually_exclusive_group(required=True)
    input_source.add_argument("--from-file", type=Path)
    input_source.add_argument("--stdin", action="store_true")
    input_source.add_argument("--json")
    publish.add_argument("--update", action="store_true")
    staff_sync = commands.add_parser("staff-sync")
    staff_source = staff_sync.add_mutually_exclusive_group(required=True)
    staff_source.add_argument("--from-file", type=Path)
    staff_source.add_argument("--stdin", action="store_true")
    staff_source.add_argument("--json")
    migrate = commands.add_parser("migrate")
    mode = migrate.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    for name in ("status", "ready", "release-expired"):
        commands.add_parser(name)
    for name in ("next",):
        command = commands.add_parser(name)
        command.add_argument("--worker", required=True)
    command = commands.add_parser("describe")
    command.add_argument("--task", required=True)
    guard = commands.add_parser("lease-guard")
    guard.add_argument("--task", required=True)
    guard.add_argument("--worker", required=True)
    guard.add_argument("--lease-id", required=True)
    review_correction = commands.add_parser("review-correct")
    review_correction.add_argument("--task", required=True)
    review_correction.add_argument("--reviewer", required=True)
    review_correction.add_argument("--verdict", choices=("pass", "hold"), required=True)
    review_correction.add_argument("--summary", required=True)
    for name in (
        "claim",
        "heartbeat",
        "continue",
        "block",
        "fail",
        "complete",
        "retry",
        "resume",
    ):
        command = commands.add_parser(name)
        command.add_argument("--task", required=True)
        command.add_argument("--worker", required=True)
        if name in {"claim", "continue"}:
            command.add_argument("--agent-id")
        if name == "claim":
            command.add_argument("--guard", action="store_true")
        if name in {"heartbeat", "block", "fail", "complete", "retry"}:
            command.add_argument("--lease-id", required=True)
        if name in {"block", "fail", "retry", "resume"}:
            command.add_argument("--reason", required=True)
        if name in {"block", "fail", "retry"}:
            command.add_argument("--failure-class")
            command.add_argument("--failure-fingerprint")
            command.add_argument("--verification-evidence-json")
            command.add_argument(
                "--model-escalation-attempted", action="store_true", default=None
            )
        if name in {"retry", "resume"}:
            command.add_argument("--last-attempt-summary", required=True)
            command.add_argument("--next-attempt-instruction", required=True)
        if name == "complete":
            command.add_argument("--summary", required=True)
    return parser


def _dispatch(args: argparse.Namespace, context: ProjectContext) -> dict[str, object]:
    if args.command == "lease-guard":
        return _lease_guard(args, context)
    if args.command == "publish":
        envelope = _read_publish_envelope(args)
        mismatch = _operation_mismatch(envelope, update=args.update)
        if mismatch is not None:
            return mismatch
        return _publish(context, envelope=envelope, update=args.update)
    if args.command == "migrate":
        receipt = migrate_file(
            context.state_path,
            project_id=context.project_id,
            dry_run=args.check or args.dry_run,
        )
        return _normalize_migration_receipt(receipt)
    if args.command == "staff-sync":
        return _staff_sync(context, _read_json_input(args))
    if args.command == "review-correct":
        return _review_correct(context, args)
    return _lifecycle(args, context)


def _lease_guard(
    args: argparse.Namespace, context: ProjectContext
) -> dict[str, object]:
    """Run in the foreground; stdin EOF or an interrupt requests a clean stop."""
    stop = threading.Event()
    supervisor_lost = threading.Event()
    wake = threading.Event()
    core = SchedulerCore()
    interval = core.heartbeat_interval_seconds

    def request_stop(_signum: int, _frame: object) -> None:
        stop.set()
        wake.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    def watch_supervisor() -> None:
        # A parent-owned stdin pipe closes on parent/session loss on every supported
        # platform. This is an identity-bearing capability, unlike a recycled PID.
        sys.stdin.buffer.read()
        supervisor_lost.set()
        wake.set()

    threading.Thread(target=watch_supervisor, daemon=True).start()

    def heartbeat() -> dict[str, object]:
        with StateLock(context.lock_path):
            state = _load_state(context.state_path, context.project_id)
            task = (
                state.get("tasks", {}).get(args.task)
                if isinstance(state.get("tasks"), dict)
                else None
            )
            if isinstance(task, dict) and task.get("status") not in {
                "claimed",
                "running",
            }:
                return {"ok": False, "reason": "terminal_task", "task_id": args.task}
            receipt = core.heartbeat(
                state, task_id=args.task, worker_id=args.worker, lease_id=args.lease_id
            )
            if receipt["ok"]:
                _atomic_write(context.state_path, state)
            return receipt

    events: list[dict[str, object]] = []
    guard = LeaseGuard(
        heartbeat,
        lambda seconds: wake.wait(seconds),
        lambda: not supervisor_lost.is_set(),
        events.append,
        interval,
        lambda: "supervisor_lost" if supervisor_lost.is_set() else "graceful_stop",
    )
    code = guard.run()
    return {"ok": code == 0, "operation": "lease_guard", "events": events}


def _claim_guard(args: argparse.Namespace, context: ProjectContext) -> int:
    """Claim once, flush its receipt, then guard only that fenced lease."""
    core = SchedulerCore()
    with StateLock(context.lock_path):
        state = _load_state(context.state_path, context.project_id)
        receipt = core.claim(
            state, task_id=args.task, worker_id=args.worker, agent_id=args.agent_id
        )
        if receipt["ok"]:
            _atomic_write(context.state_path, state)
    receipt["project"] = {"project_id": context.project_id, "root": str(context.root)}
    _emit(receipt)
    sys.stdout.flush()
    if not receipt["ok"]:
        return 1

    stop = threading.Event()
    lost = threading.Event()
    wake = threading.Event()

    def signal_stop(_signum: int, _frame: object) -> None:
        stop.set()
        wake.set()

    signal.signal(signal.SIGINT, signal_stop)
    signal.signal(signal.SIGTERM, signal_stop)

    def watch_supervisor() -> None:
        sys.stdin.buffer.read()
        lost.set()
        wake.set()

    threading.Thread(target=watch_supervisor, daemon=True).start()

    def heartbeat() -> dict[str, object]:
        with StateLock(context.lock_path):
            current = _load_state(context.state_path, context.project_id)
            task = (
                current.get("tasks", {}).get(args.task)
                if isinstance(current.get("tasks"), dict)
                else None
            )
            if isinstance(task, dict) and task.get("status") not in {
                "claimed",
                "running",
            }:
                return {"ok": False, "reason": "terminal_task", "task_id": args.task}
            renewed = core.heartbeat(
                current,
                task_id=args.task,
                worker_id=args.worker,
                lease_id=str(receipt["lease_id"]),
            )
            if renewed["ok"]:
                _atomic_write(context.state_path, current)
            return renewed

    events: list[dict[str, object]] = []
    guard = LeaseGuard(
        heartbeat,
        lambda seconds: wake.wait(seconds),
        lambda: not lost.is_set(),
        events.append,
        int(receipt["heartbeat_interval_seconds"]),
        lambda: "supervisor_lost" if lost.is_set() else "graceful_stop",
    )
    code = guard.run()
    final = {
        "ok": code == 0,
        "operation": "lease_guard",
        "events": events,
        "project": receipt["project"],
    }
    _emit(final)
    return code


def _init(args: argparse.Namespace) -> dict[str, object]:
    root = (args.project_root or Path.cwd()).resolve()
    project_id = _normalized_project_id(args.project_id or root.name)
    scheduler_directory = root / ".scheduler"
    scheduler_directory.mkdir(parents=True, exist_ok=True)
    config = {
        "config_schema_version": 1,
        "project_id": project_id,
        "state_path": ".scheduler/state.json",
        "events_path": None,
    }
    _atomic_write_json(scheduler_directory / "project.json", config)
    _atomic_write_json(
        scheduler_directory / "state.json",
        {
            "schema_version": 1,
            "project_id": project_id,
            "tasks": {},
            "publish_history": [],
            "review_decisions": [],
            "staff_model": {"staff": {}},
        },
    )
    return {
        "ok": True,
        "operation": "init",
        "changed_task_ids": [],
        "warnings": [],
        "project": {"project_id": project_id, "root": str(root)},
    }


def _read_publish_envelope(args: argparse.Namespace) -> object:
    return _read_json_input(args)


def _read_json_input(args: argparse.Namespace) -> object:
    if args.from_file is not None:
        return json.loads(args.from_file.read_text(encoding="utf-8"))
    if args.stdin:
        return json.loads(sys.stdin.read())
    return json.loads(args.json)


def _staff_sync(context: ProjectContext, envelope: object) -> dict[str, object]:
    workers = _validate_staff_envelope(envelope)
    with StateLock(context.lock_path):
        state = _load_state(context.state_path, context.project_id)
        state["staff_model"] = {"staff": workers}
        _atomic_write(context.state_path, state)
    return {
        "ok": True,
        "operation": "staff_sync",
        "workers": sorted(workers),
    }


def _validate_staff_envelope(envelope: object) -> dict[str, object]:
    if (
        not isinstance(envelope, Mapping)
        or set(envelope) != {"input_schema_version", "workers"}
        or envelope.get("input_schema_version") != 1
        or not isinstance(envelope.get("workers"), Mapping)
        or not envelope["workers"]
    ):
        raise ValueError("staff envelope must contain schema version 1 and workers")
    workers: dict[str, object] = {}
    for worker_id, raw_profile in envelope["workers"].items():
        if not isinstance(worker_id, str) or not worker_id:
            raise ValueError("worker ids must be non-empty strings")
        workers[worker_id] = _validate_worker_profile(raw_profile)
    return workers


def _validate_worker_profile(profile: object) -> dict[str, object]:
    fields = {
        "can_execute_tasks",
        "allowed_agent_types",
        "allowed_task_kinds",
        "required_metadata_by_kind",
    }
    if not isinstance(profile, Mapping) or set(profile) != fields:
        raise ValueError("worker profile fields are invalid")
    can_execute = profile["can_execute_tasks"]
    agent_types = profile["allowed_agent_types"]
    task_kinds = profile["allowed_task_kinds"]
    requirements = profile["required_metadata_by_kind"]
    if not isinstance(can_execute, bool):
        raise ValueError("can_execute_tasks must be a boolean")
    if not _string_list(agent_types) or not _string_list(task_kinds):
        raise ValueError("allowed agent types and task kinds must be string arrays")
    if not isinstance(requirements, Mapping) or any(
        not isinstance(kind, str)
        or not kind
        or not _string_list(paths, allow_empty=True)
        for kind, paths in requirements.items()
    ):
        raise ValueError("required metadata rules are invalid")
    return {
        "can_execute_tasks": can_execute,
        "allowed_agent_types": list(agent_types),
        "allowed_task_kinds": list(task_kinds),
        "required_metadata_by_kind": {
            str(kind): list(paths) for kind, paths in requirements.items()
        },
    }


def _string_list(value: object, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and bool(item) for item in value)
    )


def _review_correct(
    context: ProjectContext, args: argparse.Namespace
) -> dict[str, object]:
    with StateLock(context.lock_path):
        state = _load_state(context.state_path, context.project_id)
        tasks = state.get("tasks")
        task = tasks.get(args.task) if isinstance(tasks, dict) else None
        if not isinstance(task, dict):
            return _failure("TASK_NOT_FOUND", "task was not found")
        terminal_status = task.get("status")
        if terminal_status not in {"done", "blocked", "failed"}:
            return _failure(
                "TASK_NOT_TERMINAL", "review correction requires a terminal task"
            )
        decisions = state.setdefault("review_decisions", [])
        if not isinstance(decisions, list):
            raise ValueError("review_decisions must be a list")
        prior = next(
            (
                decision
                for decision in reversed(decisions)
                if isinstance(decision, dict) and decision.get("task_id") == args.task
            ),
            None,
        )
        supersedes = (
            {"kind": "review_decision", "event_id": prior["event_id"]}
            if isinstance(prior, dict)
            else {
                "kind": "terminal_summary",
                "summary": task.get("summary"),
                "terminal_status": terminal_status,
            }
        )
        event_id = str(uuid4())
        decisions.append(
            {
                "event_id": event_id,
                "event_type": "review_correction",
                "occurred_at": datetime.now(tz=UTC).isoformat(),
                "task_id": args.task,
                "reviewer": args.reviewer,
                "verdict": args.verdict,
                "summary": args.summary,
                "supersedes": supersedes,
            }
        )
        _atomic_write(context.state_path, state)
    return {
        "ok": True,
        "operation": "review_correction",
        "task_id": args.task,
        "review_decision_id": event_id,
        "supersedes_event_id": supersedes.get("event_id"),
    }


def _publish(
    context: ProjectContext, *, envelope: object, update: bool
) -> dict[str, object]:
    with StateLock(context.lock_path):
        state = _load_state(context.state_path, context.project_id)
        receipt = PublishService().publish(state, envelope=envelope, update=update)
        if not receipt["ok"]:
            return receipt
        _atomic_write(context.state_path, state)
    warnings = _write_observations(state, receipt, context)
    return _normalize_publish_receipt(receipt, update=update, warnings=warnings)


def _lifecycle(args: argparse.Namespace, context: ProjectContext) -> dict[str, object]:
    core = SchedulerCore()
    command = args.command.replace("-", "_")
    method_name = "continue_task" if command == "continue" else command
    method: Callable[..., dict[str, object]] = getattr(core, method_name)
    with StateLock(context.lock_path):
        state = _load_state(context.state_path, context.project_id)
        kwargs: dict[str, object] = {}
        if hasattr(args, "task"):
            kwargs["task_id"] = args.task
        if hasattr(args, "worker"):
            kwargs["worker_id"] = args.worker
        if hasattr(args, "agent_id"):
            kwargs["agent_id"] = args.agent_id
        if hasattr(args, "lease_id"):
            kwargs["lease_id"] = args.lease_id
        if command in {"block", "fail", "retry", "resume"}:
            kwargs["reason"] = args.reason
        if command in {"retry", "resume"}:
            kwargs["last_attempt_summary"] = args.last_attempt_summary
            kwargs["next_attempt_instruction"] = args.next_attempt_instruction
        if command in {"block", "fail", "retry"}:
            kwargs["failure_class"] = args.failure_class
            kwargs["failure_fingerprint"] = args.failure_fingerprint
            kwargs["verification_evidence"] = (
                json.loads(args.verification_evidence_json)
                if args.verification_evidence_json
                else None
            )
            kwargs["model_escalation_attempted"] = args.model_escalation_attempted
        if command == "complete":
            kwargs["summary"] = args.summary
        receipt = method(state, **kwargs)
        if command not in {"status", "ready", "next", "describe"} and receipt["ok"]:
            _atomic_write(context.state_path, state)
    return receipt


def _operation_mismatch(envelope: object, *, update: bool) -> dict[str, object] | None:
    expected = "update" if update else "create"
    if not isinstance(envelope, dict) or envelope.get("operation") != expected:
        return _failure(
            "PUBLISH_OPERATION_MISMATCH", "CLI mode and envelope operation disagree"
        )
    return None


def _write_observations(
    state: dict[str, object], receipt: dict[str, object], context: ProjectContext
) -> list[dict[str, str]]:
    task_ids = receipt.get("task_ids", [])
    history = state.get("publish_history", [])
    if not isinstance(task_ids, list) or not isinstance(history, list):
        return []
    events = history[-len(task_ids) :] if task_ids else []
    warnings: list[dict[str, str]] = []
    for event in events:
        if isinstance(event, dict):
            warning = append_observation_event(
                event=event, events_path=context.events_path
            )
            if warning is not None:
                warnings.append(warning)
    return warnings


def _normalize_publish_receipt(
    receipt: dict[str, object],
    *,
    update: bool,
    warnings: list[dict[str, str]],
) -> dict[str, object]:
    task_ids = receipt.get("task_ids", [])
    return {
        "ok": True,
        "operation": "publish_update" if update else "publish",
        "changed_task_ids": task_ids if isinstance(task_ids, list) else [],
        "warnings": warnings,
    }


def _normalize_migration_receipt(receipt: dict[str, object]) -> dict[str, object]:
    migration = {
        key: value
        for key, value in receipt.items()
        if key not in {"ok", "operation", "warnings"}
    }
    warnings = receipt.get("warnings", [])
    return {
        "ok": True,
        "operation": "migrate",
        "changed_task_ids": [],
        "warnings": warnings if isinstance(warnings, list) else [],
        "migration": migration,
    }


def _load_state(path: Path, project_id: str) -> dict[str, object]:
    if not path.exists():
        return {
            "schema_version": 1,
            "project_id": project_id,
            "tasks": {},
            "publish_history": [],
            "review_decisions": [],
            "staff_model": {"staff": {}},
        }
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("state must be an object")
    loaded.setdefault("publish_history", [])
    loaded.setdefault("review_decisions", [])
    loaded.setdefault("staff_model", {"staff": {}})
    return loaded


def _atomic_write(path: Path, state: dict[str, object]) -> None:
    _atomic_write_json(path, state)


def _atomic_write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _failure(code: str, message: str) -> dict[str, object]:
    return {"ok": False, "error": {"code": code, "message": message}}


def _normalized_project_id(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
    if not normalized:
        raise ValueError("project_id is empty after normalization")
    return normalized


def _emit(receipt: dict[str, object]) -> int:
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
