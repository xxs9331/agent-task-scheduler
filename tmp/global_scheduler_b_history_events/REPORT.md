# Global Scheduler B History and Events Checkpoint

- task_id: `task_global_scheduler_repository_linux_b`
- checkpoint: `history_events`
- status: `ready_for_publish_gate_review`

## Delivered

- `history.append_publish_history` writes canonical `published` or
  `publish_updated` facts to the state-owned `publish_history`, generating a
  unique event id and preserving a caller-supplied change summary.
- `history.export_publish_history` emits deterministic JSON Lines without
  mutating retained history.
- `events.append_observation_event` appends the optional JSONL observation
  only after the authoritative state commit. A filesystem error returns the
  documented `OBSERVATION_LOG_WARNING`; it does not roll back history.

## Verification

```text
UV_CACHE_DIR=/tmp/agent-task-scheduler-uv-cache uv run --with pytest pytest \
  tests/history/test_publish_history.py tests/project_context/test_project_context.py -q
8 passed in 0.02s

UV_CACHE_DIR=/tmp/agent-task-scheduler-uv-cache uv run --with ruff ruff check \
  src/agent_task_scheduler/history src/agent_task_scheduler/events tests/history
All checks passed!
```

## Boundaries and next checkpoint

This checkpoint does not claim publish-service or CLI wiring, which remains in
role A's exclusive file boundary. Linux/WSL clean-install and two-project
lifecycle verification remain gated on the Integration pass and finalized
Skill, as required by the task contract.
