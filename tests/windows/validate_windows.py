"""Native Windows smoke checks for the C3 validation node."""

from __future__ import annotations

import json
import multiprocessing
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from agent_task_scheduler.locking import LockTimeoutError, StateLock
from agent_task_scheduler.migration import migrate_file


def _hold_lock(path: str, ready: multiprocessing.synchronize.Event) -> None:
    with StateLock(Path(path), timeout=5):
        ready.set()
        time.sleep(0.6)


def _crash_with_lock(path: str, ready: multiprocessing.synchronize.Event) -> None:
    lock = StateLock(Path(path), timeout=5)
    lock.acquire()
    ready.set()
    os._exit(0)


def _legacy_state() -> dict[str, object]:
    return {
        "schema_version": 1,
        "project_id": "windows-c3",
        "tasks": {
            "task_a": {
                "task_id": "task_a",
                "status": "ready",
                "agent_type": "task_executor",
                "depends_on": [],
                "conflict_domain": "windows-c3",
                "preferred_worker": "window_c",
                "worker_prompt": {},
                "created_at": "2026-07-13T00:00:00+00:00",
            }
        },
    }


def main() -> None:
    multiprocessing.freeze_support()
    with tempfile.TemporaryDirectory(prefix="scheduler-c3-") as directory:
        root = Path(directory)
        lock_path = root / "state.json.lock"
        ready = multiprocessing.Event()
        process = multiprocessing.Process(target=_hold_lock, args=(str(lock_path), ready))
        process.start()
        assert ready.wait(5)
        try:
            try:
                with StateLock(lock_path, timeout=0.1):
                    raise AssertionError("lock unexpectedly acquired")
            except LockTimeoutError:
                pass
        finally:
            process.join(5)
        assert process.exitcode == 0

        ready = multiprocessing.Event()
        process = multiprocessing.Process(target=_crash_with_lock, args=(str(lock_path), ready))
        process.start()
        assert ready.wait(5)
        process.join(5)
        assert process.exitcode == 0
        with StateLock(lock_path, timeout=1):
            pass

        state_path = root / "state.json"
        original = json.dumps(_legacy_state(), separators=(",", ":")).encode("utf-8")
        state_path.write_bytes(original)
        dry_run = migrate_file(state_path, project_id="windows-c3", dry_run=True)
        assert dry_run["target_schema_version"] == 1
        assert state_path.read_bytes() == original
        receipt = migrate_file(state_path, project_id="windows-c3")
        assert receipt["ok"] is True
        assert json.loads(state_path.read_text(encoding="utf-8"))["project_id"] == "windows-c3"
        print(json.dumps({"ok": True, "checks": ["contention", "timeout", "crash_release", "migration"]}))


if __name__ == "__main__":
    main()
