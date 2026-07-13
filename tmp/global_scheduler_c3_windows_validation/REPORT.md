# Global Scheduler C3 Windows Validation

- task_id: `task_global_scheduler_windows_validation_c3`
- worker: `window_c`
- status: `complete`

## Prior evidence reused

- C1/C2 implementation and contract evidence from
  `tmp/global_scheduler_c_windows/REPORT.md`.
- A3 dependency is `done`; its integration report is
  `/home/lenovo/projects/parlant/tmp/global_scheduler_a3_parlant_integration/REPORT.md`.

## Native Windows verification

The repository C-scope source and `tests/windows/validate_windows.py` were
copied to `C:\Temp\agent-task-scheduler-c3` without changing the repository.
The Windows Python 3.13 interpreter then ran:

```text
cmd.exe /C D:/Users/Lenovo/AppData/Local/Programs/Python/Python313/python.exe C:/Temp/agent-task-scheduler-c3/tests/windows/validate_windows.py
{"ok": true, "checks": ["contention", "timeout", "crash_release", "migration"]}
```

Passed checks:

- two-process local lock contention and timeout;
- lock release after forced process exit;
- migration dry-run leaves original bytes unchanged;
- real migration atomically produces the canonical state.

The Windows validation script also passes Linux-side Ruff and compile checks.

## Wheel clean-install continuation

The already-built wheel was copied to the Windows-accessible path
`C:\Temp\agent-task-scheduler-c3-wheel-20260713`:

```text
agent_task_scheduler-0.1.0-py3-none-any.whl
```

In a new native Windows venv, installation succeeded:

```text
C:/Temp/agent-task-scheduler-c3-wheel-20260713/.venv/Scripts/python.exe \
  -m pip install --no-deps \
  C:/Temp/agent-task-scheduler-c3-wheel-20260713/agent_task_scheduler-0.1.0-py3-none-any.whl
Successfully installed agent-task-scheduler-0.1.0
```

The installed `scheduler.exe` then ran publish and lifecycle commands against
a fresh Windows project:

```text
scheduler.exe --project-root C:/Temp/agent-task-scheduler-c3-wheel-20260713/windows_project \
  publish --from-file C:/Temp/agent-task-scheduler-c3-wheel-20260713/windows_project/publish.json
{"changed_task_ids":["windows-wheel-task"],"ok":true,"operation":"publish",...}

scheduler.exe ... claim --task windows-wheel-task --worker window_c
{"ok":true,"status":"running","task_id":"windows-wheel-task",...}

scheduler.exe ... complete --task windows-wheel-task --worker window_c \
  --summary wheel-c3-windows-complete
{"ok":true,"status":"done","task_id":"windows-wheel-task",...}
```

This satisfies the requested Windows wheel installation, publish, and
lifecycle transition acceptance. The earlier source-install hatchling failure
is historical and no longer blocks this wheel-based node.

## Touched files

- `tests/windows/validate_windows.py`
- `tmp/global_scheduler_c3_windows_validation/REPORT.md`

No runtime implementation, project context, publish/history, or legacy report
was modified.
