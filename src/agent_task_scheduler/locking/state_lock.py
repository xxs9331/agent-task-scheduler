from __future__ import annotations

import os
import time
from pathlib import Path
from types import TracebackType
from typing import IO, Self


class LockTimeoutError(TimeoutError):
    """Raised when a state lock cannot be acquired before its deadline."""


class StateLock:
    """A local-disk advisory lock with one contract on POSIX and Windows."""

    def __init__(
        self, path: Path, timeout: float = 10.0, poll_interval: float = 0.01
    ) -> None:
        if timeout < 0:
            raise ValueError("timeout must be non-negative")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")
        self.path = path
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._handle: IO[bytes] | None = None

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()

    def acquire(self) -> None:
        if self._handle is not None:
            raise RuntimeError("state lock is already acquired")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        deadline = time.monotonic() + self.timeout
        try:
            while True:
                if _try_lock(handle):
                    self._handle = handle
                    return
                if time.monotonic() >= deadline:
                    raise LockTimeoutError(f"timed out acquiring lock: {self.path}")
                time.sleep(self.poll_interval)
        except BaseException:
            handle.close()
            raise

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        try:
            _unlock(handle)
        finally:
            handle.close()
            self._handle = None


def _try_lock(handle: IO[bytes]) -> bool:
    if os.name == "nt":
        import msvcrt

        try:
            # `msvcrt.locking` locks bytes, and an empty newly-created file
            # cannot provide a stable byte range on all Windows runtimes.
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(handle: IO[bytes]) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
