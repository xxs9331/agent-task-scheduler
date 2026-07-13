from __future__ import annotations

import multiprocessing
import os
import time
from pathlib import Path

import pytest

from agent_task_scheduler.locking import LockTimeoutError, StateLock


def _hold_lock(path: str, ready: multiprocessing.synchronize.Event) -> None:
    with StateLock(Path(path), timeout=2):
        ready.set()
        time.sleep(0.4)


def _crash_with_lock(path: str, ready: multiprocessing.synchronize.Event) -> None:
    lock = StateLock(Path(path), timeout=2)
    lock.acquire()
    ready.set()
    os._exit(0)


def test_that_state_lock_serializes_local_processes(tmp_path: Path) -> None:
    lock_path = tmp_path / "state.json.lock"
    ready = multiprocessing.Event()
    process = multiprocessing.Process(target=_hold_lock, args=(str(lock_path), ready))
    process.start()
    assert ready.wait(2)
    with pytest.raises(LockTimeoutError):
        with StateLock(lock_path, timeout=0.05):
            pass
    process.join(2)
    assert process.exitcode == 0


def test_that_state_lock_releases_after_context_exit(tmp_path: Path) -> None:
    lock_path = tmp_path / "state.json.lock"
    with StateLock(lock_path, timeout=0.1):
        pass


def test_that_state_lock_releases_after_process_exit(tmp_path: Path) -> None:
    lock_path = tmp_path / "state.json.lock"
    ready = multiprocessing.Event()
    process = multiprocessing.Process(
        target=_crash_with_lock, args=(str(lock_path), ready)
    )
    process.start()
    assert ready.wait(2)
    process.join(2)
    assert process.exitcode == 0
    with StateLock(lock_path, timeout=0.1):
        pass


def test_that_windows_lock_adapter_seeds_an_empty_lock_file(
    monkeypatch, tmp_path: Path
) -> None:
    lock_path = tmp_path / "state.json.lock"
    calls: list[tuple[int, int, int]] = []

    class FakeMsvcrt:
        LK_NBLCK = 1
        LK_UNLCK = 2

        @staticmethod
        def locking(fd: int, mode: int, size: int) -> None:
            calls.append((fd, mode, size))

    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setitem(__import__("sys").modules, "msvcrt", FakeMsvcrt)

    with StateLock(lock_path, timeout=0.1):
        assert lock_path.stat().st_size == 1
    assert calls[0][1:] == (FakeMsvcrt.LK_NBLCK, 1)
    with StateLock(lock_path, timeout=0.1):
        pass
