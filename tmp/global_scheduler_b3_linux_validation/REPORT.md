# Global Scheduler B3 Linux/WSL Validation

- task: `task_global_scheduler_linux_validation_b3`
- worker: `window_b`
- result: passed verification; ready for final gate review

## Reused upstream evidence

- A3 integration: `tmp/global_scheduler_a3_parlant_integration/REPORT.md`
- finalized distributable instructions: `skills/global-scheduler/README.md`
- B history/events checkpoint: `tmp/global_scheduler_b_history_events/REPORT.md`

## New verification

1. Built a wheel from the current package to
   `/tmp/global-scheduler-b3-dist/agent_task_scheduler-0.1.0-py3-none-any.whl`.
2. Created a new `/tmp/global-scheduler-b3-venv` and installed only that wheel
   with `uv pip install`; validation used the installed `scheduler` executable,
   not the repository source tree.
3. Created independent `alpha` and `beta` managed projects. Both published one
   task and persisted separate state/history files; their task ids and history
   lengths remained isolated.
4. Completed `beta` lifecycle:
   `publish -> next -> claim -> heartbeat -> complete`; final state is `done`.
5. Configured alpha's `events_path` as a directory. Its publish committed state
   and returned `OBSERVATION_LOG_WARNING`; its one-entry `publish_history`
   remained available for reconstruction. Beta, with events disabled, returned
   no warning.

## Commands and results

```text
UV_CACHE_DIR=/tmp/agent-task-scheduler-uv-cache uv run --group test pytest -q
43 passed in 0.59s

UV_CACHE_DIR=/tmp/agent-task-scheduler-uv-cache uv run --with ruff ruff check \
  tests/linux/test_clean_install_isolation.py
All checks passed!

uv build --wheel --out-dir /tmp/global-scheduler-b3-dist
Successfully built agent_task_scheduler-0.1.0-py3-none-any.whl

uv venv /tmp/global-scheduler-b3-venv
uv pip install --python /tmp/global-scheduler-b3-venv/bin/python <wheel>
Installed agent-task-scheduler==0.1.0
```

## Touched files and caveats

- Added `tests/linux/test_clean_install_isolation.py` for repeatable two-project
  lifecycle and observation-failure coverage.
- No scheduler implementation, Task Center, Parlant runtime, datasets, or
  external systems were modified.
- This is Linux/WSL evidence only. Native Windows validation remains C3 scope;
  R owns the final gate decision.
