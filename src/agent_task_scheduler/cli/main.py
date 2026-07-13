"""Machine-readable CLI adapters for scheduler core services."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Sequence

from agent_task_scheduler.core.scheduler import SchedulerCore
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
        context = discover_project_context(
            current_directory=Path.cwd(), project_root=args.project_root
        )
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
    publish = commands.add_parser("publish")
    publish.add_argument("--from-file", required=True, type=Path)
    publish.add_argument("--update", action="store_true")
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
        if name in {"block", "fail", "retry", "resume"}:
            command.add_argument("--reason", required=True)
        if name in {"retry", "resume"}:
            command.add_argument("--last-attempt-summary", required=True)
            command.add_argument("--next-attempt-instruction", required=True)
        if name == "complete":
            command.add_argument("--summary")
    return parser


def _dispatch(args: argparse.Namespace, context: ProjectContext) -> dict[str, object]:
    if args.command == "publish":
        envelope = json.loads(args.from_file.read_text(encoding="utf-8"))
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
    return _lifecycle(args, context)


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
        if command in {"block", "fail", "retry", "resume"}:
            kwargs["reason"] = args.reason
        if command in {"retry", "resume"}:
            kwargs["last_attempt_summary"] = args.last_attempt_summary
            kwargs["next_attempt_instruction"] = args.next_attempt_instruction
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
        }
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("state must be an object")
    return loaded


def _atomic_write(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(state, output, ensure_ascii=False, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _failure(code: str, message: str) -> dict[str, object]:
    return {"ok": False, "error": {"code": code, "message": message}}


def _emit(receipt: dict[str, object]) -> int:
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
