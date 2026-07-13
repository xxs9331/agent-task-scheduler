# Global Scheduler C Lock, Migration, and Windows Checkpoint

- task_id: `task_global_scheduler_lock_migration_windows_c`
- checkpoint: `migration_windows`
- status: `ready_for_integration_review`

## Delivered

- Hardened the native Windows `msvcrt.locking` adapter by seeding a byte in a
  newly-created empty lock file before locking byte zero.
- Added a shared dependency-cycle validation pass for migration, including
  multi-task cycles.
- Rejected unsupported lower schema versions instead of silently skipping
  intermediate migrations.
- Reconstructed and validated the target document after acquiring the lock on
  real migrations, so a concurrent writer cannot be overwritten by a stale
  preflight result.
- Added migration receipt fields for mapped task/field counts, defaults, and
  warnings.

## Verification

```text
UV_CACHE_DIR=/tmp/agent-task-scheduler-uv-cache uv run --with pytest pytest \
  tests/locking/test_state_lock.py tests/migration/test_state_migration.py -q
13 passed in 0.43s

UV_CACHE_DIR=/tmp/agent-task-scheduler-uv-cache uv run --with ruff ruff check \
  src/agent_task_scheduler/locking src/agent_task_scheduler/migration \
  tests/locking tests/migration
All checks passed!

.venv/bin/python -m compileall -q \
  src/agent_task_scheduler/locking src/agent_task_scheduler/migration
passed
```

The Windows branch was exercised with a fake `msvcrt` contract test on Linux.
Native Windows clean-install and real Windows process contention were not run
because this environment is Linux/WSL; they remain integration-gate evidence.

The repository-wide test command remains blocked by unrelated missing role-A
publish code: `tests/publish/test_publish_service.py` imports the absent
`agent_task_scheduler.publish` package.

## Touched files

- `src/agent_task_scheduler/locking/state_lock.py`
- `src/agent_task_scheduler/migration/state_migration.py`
- `tests/locking/test_state_lock.py`
- `tests/migration/test_state_migration.py`

## Boundary

No project-context, publish/history, Parlant routing, MCP, or network-filesystem
files were changed.
