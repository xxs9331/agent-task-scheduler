"""Core facade for scheduler lifecycle services."""

from __future__ import annotations

from collections.abc import MutableMapping

from agent_task_scheduler.lifecycle.service import LifecycleService, Receipt


class SchedulerCore:
    """Expose scheduler operations independently of CLI argument parsing."""

    def __init__(self, lifecycle: LifecycleService | None = None) -> None:
        self._lifecycle = lifecycle or LifecycleService()

    @property
    def heartbeat_interval_seconds(self) -> int:
        return self._lifecycle.heartbeat_interval_seconds

    def claim(
        self,
        state: MutableMapping[str, object],
        *,
        task_id: str,
        worker_id: str,
        agent_id: str | None = None,
    ) -> Receipt:
        return self._lifecycle.claim(
            state, task_id=task_id, worker_id=worker_id, agent_id=agent_id
        )

    def status(self, state: MutableMapping[str, object]) -> Receipt:
        return self._lifecycle.status(state)

    def ready(self, state: MutableMapping[str, object]) -> Receipt:
        return self._lifecycle.ready(state)

    def next(self, state: MutableMapping[str, object], *, worker_id: str) -> Receipt:
        return self._lifecycle.next(state, worker_id=worker_id)

    def describe(self, state: MutableMapping[str, object], *, task_id: str) -> Receipt:
        return self._lifecycle.describe(state, task_id=task_id)

    def heartbeat(
        self,
        state: MutableMapping[str, object],
        *,
        task_id: str,
        worker_id: str,
        lease_id: str,
    ) -> Receipt:
        return self._lifecycle.heartbeat(
            state, task_id=task_id, worker_id=worker_id, lease_id=lease_id
        )

    def complete(
        self,
        state: MutableMapping[str, object],
        *,
        task_id: str,
        worker_id: str,
        lease_id: str,
        summary: str | None = None,
    ) -> Receipt:
        return self._lifecycle.complete(
            state,
            task_id=task_id,
            worker_id=worker_id,
            lease_id=lease_id,
            summary=summary,
        )

    def retry(
        self,
        state: MutableMapping[str, object],
        *,
        task_id: str,
        worker_id: str,
        lease_id: str,
        reason: str,
        last_attempt_summary: str,
        next_attempt_instruction: str,
        failure_class: str | None = None,
        failure_fingerprint: str | None = None,
        verification_evidence: object | None = None,
        model_escalation_attempted: bool | None = None,
    ) -> Receipt:
        return self._lifecycle.retry(
            state,
            task_id=task_id,
            worker_id=worker_id,
            lease_id=lease_id,
            reason=reason,
            last_attempt_summary=last_attempt_summary,
            next_attempt_instruction=next_attempt_instruction,
            failure_class=failure_class,
            failure_fingerprint=failure_fingerprint,
            verification_evidence=verification_evidence,
            model_escalation_attempted=model_escalation_attempted,
        )

    def resume(
        self,
        state: MutableMapping[str, object],
        *,
        task_id: str,
        worker_id: str,
        reason: str,
        last_attempt_summary: str,
        next_attempt_instruction: str,
    ) -> Receipt:
        return self._lifecycle.resume(
            state,
            task_id=task_id,
            worker_id=worker_id,
            reason=reason,
            last_attempt_summary=last_attempt_summary,
            next_attempt_instruction=next_attempt_instruction,
        )

    def continue_task(
        self,
        state: MutableMapping[str, object],
        *,
        task_id: str,
        worker_id: str,
        agent_id: str | None = None,
    ) -> Receipt:
        return self._lifecycle.continue_task(
            state, task_id=task_id, worker_id=worker_id, agent_id=agent_id
        )

    def block(
        self,
        state: MutableMapping[str, object],
        *,
        task_id: str,
        worker_id: str,
        lease_id: str,
        reason: str,
        failure_class: str | None = None,
        failure_fingerprint: str | None = None,
        verification_evidence: object | None = None,
        model_escalation_attempted: bool | None = None,
    ) -> Receipt:
        return self._lifecycle.block(
            state,
            task_id=task_id,
            worker_id=worker_id,
            lease_id=lease_id,
            reason=reason,
            failure_class=failure_class,
            failure_fingerprint=failure_fingerprint,
            verification_evidence=verification_evidence,
            model_escalation_attempted=model_escalation_attempted,
        )

    def fail(
        self,
        state: MutableMapping[str, object],
        *,
        task_id: str,
        worker_id: str,
        lease_id: str,
        reason: str,
        failure_class: str | None = None,
        failure_fingerprint: str | None = None,
        verification_evidence: object | None = None,
        model_escalation_attempted: bool | None = None,
    ) -> Receipt:
        return self._lifecycle.fail(
            state,
            task_id=task_id,
            worker_id=worker_id,
            lease_id=lease_id,
            reason=reason,
            failure_class=failure_class,
            failure_fingerprint=failure_fingerprint,
            verification_evidence=verification_evidence,
            model_escalation_attempted=model_escalation_attempted,
        )

    def release_expired(self, state: MutableMapping[str, object]) -> Receipt:
        return self._lifecycle.release_expired(state)
