#!/usr/bin/env python3
"""Fail-closed custom-agent attestation and scheduler handoff reconciliation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple


ROLE_FILES = {
    "role-P": ("product_manager.toml", "product_manager"),
    "role-R": ("researcher.toml", "role-r"),
    "role-A": ("window_a.toml", "role-a"),
    "role-B": ("window_b.toml", "role-b"),
    "role-C": ("window_c.toml", "role-c"),
    "role-D": ("window_d.toml", "role-d"),
}


class AttestationError(ValueError):
    """Raised when runtime evidence cannot prove a custom-agent identity."""


class RoleIdentity(NamedTuple):
    custom_agent_name: str
    worker_id: str
    model: str
    reasoning_effort: str


class CompletionResult(NamedTuple):
    complete: bool
    classification: str


def load_role_mapping(agent_directory: Path) -> dict[str, RoleIdentity]:
    """Load role identities from TOML; filenames never substitute for `name`."""
    mapping: dict[str, RoleIdentity] = {}
    for role, (filename, worker_id) in ROLE_FILES.items():
        path = agent_directory / filename
        document = tomllib.loads(path.read_text(encoding="utf-8"))
        required = ("name", "model", "model_reasoning_effort")
        missing = [field for field in required if not isinstance(document.get(field), str)]
        if missing:
            raise AttestationError(f"custom agent TOML {path} lacks explicit {', '.join(missing)}")
        mapping[role] = RoleIdentity(
            custom_agent_name=str(document["name"]),
            worker_id=worker_id,
            model=str(document["model"]),
            reasoning_effort=str(document["model_reasoning_effort"]),
        )
    return mapping


def validate_spawn_attestation(
    *, role: str, expected: RoleIdentity, attestation: Mapping[str, object]
) -> None:
    """Validate parent-built native evidence; prompt-only identity is insufficient."""
    required = {
        "requested_custom_agent_name",
        "agent_id",
        "worker_id",
        "task_id",
        "effective_model",
        "reasoning_effort",
    }
    missing = sorted(
        field
        for field in required
        if not isinstance(attestation.get(field), str) or not attestation[field]
    )
    if missing:
        raise AttestationError("custom agent attestation is missing " + ", ".join(missing))
    if attestation.get("attestation_source") != "parent_spawn_receipt":
        raise AttestationError("custom agent attestation must come from parent_spawn_receipt")
    if attestation.get("fork_context") is not False:
        raise AttestationError("fork_context must be false")
    expected_values = {
        "requested_custom_agent_name": expected.custom_agent_name,
        "worker_id": expected.worker_id,
        "effective_model": expected.model,
        "reasoning_effort": expected.reasoning_effort,
    }
    for field, value in expected_values.items():
        if attestation[field] != value:
            raise AttestationError(
                f"{field} does not attest {role}: expected {value!r}, got {attestation[field]!r}"
            )


def build_parent_spawn_attestation(
    *,
    role: str,
    expected: RoleIdentity,
    requested_agent_type: str,
    spawn_receipt: Mapping[str, object],
    task_id: str,
    runtime_model: str,
    runtime_reasoning_effort: str,
    fork_context: bool,
) -> dict[str, object]:
    """Combine parent-visible spawn evidence with the fixed custom-agent contract."""
    agent_id = spawn_receipt.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id:
        raise AttestationError("parent spawn receipt is missing agent_id")
    attestation: dict[str, object] = {
        "requested_custom_agent_name": requested_agent_type,
        "agent_id": agent_id,
        "worker_id": expected.worker_id,
        "task_id": task_id,
        "effective_model": runtime_model,
        "reasoning_effort": runtime_reasoning_effort,
        "attestation_source": "parent_spawn_receipt",
        "fork_context": fork_context,
    }
    validate_spawn_attestation(
        role=role,
        expected=expected,
        attestation=attestation,
    )
    return attestation


def evaluate_completion(
    *,
    child_status: str,
    scheduler_description: Mapping[str, object],
    lifecycle_receipt: Mapping[str, object],
    verification: Sequence[object],
) -> CompletionResult:
    """Classify child/thread completion independently from scheduler completion."""
    scheduler_status = scheduler_description.get("status")
    if child_status.lower() == "done" and scheduler_status in {"running", "claimed"}:
        return CompletionResult(False, "orphaned_running_task")
    if scheduler_status == "blocked":
        return CompletionResult(False, "scheduler_blocked")
    if scheduler_status == "failed":
        return CompletionResult(False, "scheduler_failed")
    if scheduler_status != "done":
        return CompletionResult(False, "scheduler_not_done")
    summary = scheduler_description.get("summary")
    receipt_matches = (
        lifecycle_receipt.get("ok") is True
        and lifecycle_receipt.get("status") == "done"
        and lifecycle_receipt.get("task_id") == scheduler_description.get("task_id")
    )
    if (
        not isinstance(summary, str)
        or not summary.strip()
        or not receipt_matches
        or not verification
    ):
        return CompletionResult(False, "missing_completion_evidence")
    return CompletionResult(True, "verified_done")


def _scheduler_description(project_root: Path, task_id: str) -> dict[str, Any]:
    executable = (
        project_root
        / ".venv"
        / ("Scripts/scheduler.exe" if sys.platform == "win32" else "bin/scheduler")
    )
    result = subprocess.run(
        [
            str(executable),
            "--project-root",
            str(project_root),
            "describe",
            "--task",
            task_id,
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise AttestationError(result.stderr.strip() or result.stdout.strip())
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise AttestationError(f"scheduler describe failed: {payload}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--role", choices=tuple(ROLE_FILES), required=True)
    parser.add_argument("--attestation-json", type=Path, required=True)
    parser.add_argument("--child-result-json", type=Path, required=True)
    args = parser.parse_args()
    try:
        attestation = json.loads(args.attestation_json.read_text(encoding="utf-8"))
        child_result = json.loads(args.child_result_json.read_text(encoding="utf-8"))
        if not isinstance(attestation, dict) or not isinstance(child_result, dict):
            raise AttestationError("attestation and child result must be JSON objects")
        mapping = load_role_mapping(args.project_root / ".codex" / "agents")
        expected = mapping[args.role]
        validate_spawn_attestation(role=args.role, expected=expected, attestation=attestation)
        task_id = str(attestation["task_id"])
        description = _scheduler_description(args.project_root, task_id)
        receipt = child_result.get("lifecycle_receipt", {})
        verification = child_result.get("verification", [])
        if not isinstance(receipt, dict) or not isinstance(verification, list):
            raise AttestationError("invalid child lifecycle receipt or verification")
        completion = evaluate_completion(
            child_status=str(child_result.get("child_status", "")),
            scheduler_description=description,
            lifecycle_receipt=receipt,
            verification=verification,
        )
        output = {
            "ok": completion.complete,
            "operation": "reconcile_handoff",
            "classification": completion.classification,
            "requested_custom_agent_name": expected.custom_agent_name,
            "agent_id": attestation["agent_id"],
            "worker_id": expected.worker_id,
            "task_id": task_id,
            "effective_model": attestation["effective_model"],
            "scheduler_status": description.get("status"),
            "lifecycle_receipt": receipt,
            "verification": verification,
        }
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return 0 if completion.complete else 1
    except (AttestationError, KeyError, OSError, json.JSONDecodeError) as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "operation": "reconcile_handoff",
                    "classification": "input_or_attestation_error",
                    "error": str(error),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
