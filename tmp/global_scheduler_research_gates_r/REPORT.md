# Global Scheduler R Research Gates

- task_id: `task_global_scheduler_research_gates_r`
- role: `R` (read-only research and gate decision)
- decision: `pass`
- scope checked: current worktree after integration updates, public CLI surface,
  contract/schema consistency, and executable smoke checks on 2026-07-13.

## Gate decision

The v1 **global integration gate passes**. The prior `continue` routing and
successful-receipt schema defects are fixed, and the full repository test suite
passes with the test dependencies supplied explicitly.

| Gate | Decision | Evidence |
|---|---|---|
| Project-scoped create publish | pass | Direct CLI smoke check created a `ready` task and a `published` history record. |
| Operation mismatch no-write | pass | Direct CLI check returned `PUBLISH_OPERATION_MISMATCH` (exit 1) and did not create a state file. |
| Source syntax | pass | `PYTHONPATH=src python3 -m compileall -q src tests` succeeded. |
| Public CLI surface | pass | `cli/main.py` now exposes the lifecycle command set plus `migrate`; focused CLI tests cover lifecycle/migration exposure. |
| Observation log semantics | pass | `_publish` commits first, then invokes `append_observation_event`; a warning preserves `ok: true`. |
| Contract ordering | pass | `_dispatch` performs `_operation_mismatch` before `_publish` acquires `StateLock`; a focused regression test asserts this. |
| `continue` command execution | pass | CLI maps `continue` to `SchedulerCore.continue_task`; direct smoke check transitioned a `retry_ready` task to persisted `running`, and the regression test covers the path. |
| Published receipt schema | pass | Successful publish is normalized to `operation: publish`, `changed_task_ids`, and `warnings: []`; the CLI test validates it with `Draft202012Validator`. |
| Full automated suite | pass | `UV_CACHE_DIR=/tmp/agent-task-scheduler-uv-cache uv run --with pytest --with jsonschema pytest -q` completed: `42 passed in 0.58s`. |

## Required closure evidence

No remaining gate blocker was found in the reviewed scope. The project should
declare `jsonschema` in an explicit development/test dependency set so the
schema-validation test does not require an ad-hoc `uv --with jsonschema` flag;
this is a reproducibility follow-up, not a release blocker.

## Boundary

R made no product-source changes and did not alter scheduler task state: no
project `.scheduler/project.json` or task-state file is present in this
worktree. This report and `next_decision.json` are the R-owned review artifacts.
