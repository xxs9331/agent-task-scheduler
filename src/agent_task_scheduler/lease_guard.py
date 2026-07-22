"""Foreground fenced lease renewal with injectable waiting and liveness."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from subprocess import PIPE, Popen, TimeoutExpired
from typing import BinaryIO, Sequence

Receipt = dict[str, object]
Heartbeat = Callable[[], Receipt]
Wait = Callable[[int], bool]
Alive = Callable[[], bool]
Emit = Callable[[Receipt], None]
StopReason = Callable[[], str]


@dataclass(frozen=True)
class LeaseGuard:
    """Renew one existing lease only while its foreground supervisor is alive."""

    heartbeat: Heartbeat
    wait: Wait
    alive: Alive
    emit: Emit
    interval_seconds: int
    stop_reason: StopReason = lambda: "graceful_stop"

    def run(self) -> int:
        self.emit({"ok": True, "operation": "lease_guard", "event": "start"})
        while self.alive():
            if self.wait(self.interval_seconds):
                reason = self.stop_reason()
                self.emit(
                    {
                        "ok": reason == "graceful_stop",
                        "operation": "lease_guard",
                        "event": "stop",
                        "reason": reason,
                    }
                )
                return 0 if reason == "graceful_stop" else 1
            receipt = self.heartbeat()
            if receipt.get("ok"):
                self.emit({"ok": True, "operation": "lease_guard", "event": "renew"})
                continue
            reason = str(receipt.get("reason", "heartbeat_rejected"))
            terminal = reason in {
                "task_not_found",
                "task_not_claimable",
                "terminal_task",
            }
            self.emit(
                {
                    "ok": terminal,
                    "operation": "lease_guard",
                    "event": "stop",
                    "reason": reason,
                }
            )
            return 0 if terminal else 1
        self.emit(
            {
                "ok": False,
                "operation": "lease_guard",
                "event": "stop",
                "reason": "supervisor_lost",
            }
        )
        return 1


@dataclass
class ForegroundLeaseGuard:
    """Own a guard subprocess through an inherited pipe, never a PID probe."""

    process: Popen[bytes]

    @classmethod
    def start(cls, command: Sequence[str]) -> "ForegroundLeaseGuard":
        return cls(Popen(list(command), stdin=PIPE, stdout=PIPE, stderr=PIPE))

    def stop_and_reap(self, *, timeout_seconds: float = 5.0) -> int:
        stdin: BinaryIO | None = self.process.stdin
        if stdin is not None and not stdin.closed:
            stdin.close()
        try:
            return self.process.wait(timeout=timeout_seconds)
        except TimeoutExpired:
            self.process.terminate()
            return self.process.wait(timeout=timeout_seconds)
