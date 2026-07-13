# agent-task-scheduler v1 delivery manifest

- Local release ref: `scheduler-v1.0.0` (created locally; no remote push)
- Package version: `0.1.0`
- Wheel: `/tmp/agent-task-scheduler-v1-dist/agent_task_scheduler-0.1.0-py3-none-any.whl`
- Wheel SHA-256: `6ef426ffe95a98a14d70a75c50681a1980cfa8d0fec8dad83b8102396532ff2a`

## Included deliverables

- `src/`: project-scoped scheduler implementation and CLI
- `tests/`: core, lifecycle, history, locking, migration, project-context,
  publish, and Linux clean-install coverage
- `docs/`, `schemas/`, and `skills/global-scheduler/README.md`
- `pyproject.toml` and `uv.lock`
- `tmp/`: retained historical validation and final-gate evidence

## Release verification

| Command | Result |
| --- | --- |
| `UV_CACHE_DIR=/tmp/agent-task-scheduler-uv-cache uv run --group test pytest -q` | `43 passed in 0.61s` |
| `UV_CACHE_DIR=/tmp/agent-task-scheduler-uv-cache uv run --with ruff ruff check src tests` | passed |
| `uv lock --check` | passed; lockfile is current |
| `uv build --wheel --out-dir /tmp/agent-task-scheduler-v1-dist` | built universal `py3-none-any` wheel |
| wheel metadata and direct-wheel import smoke | name/version `agent-task-scheduler`/`0.1.0`; CLI `main` importable |

## Supported-platform evidence

- Linux/WSL: clean install, two-project isolation, lifecycle, and optional
  observation-log warning behavior passed (B3).
- Native Windows local disk: locking, timeout, crash-release, migration, and
  installed wheel `scheduler.exe` publish/claim/complete passed (C3).

## v1 boundaries

- Project-local state only; no global task pool or network-filesystem locking
  guarantee.
- Public writes use the CLI; MCP and Task Center integration are out of scope.
- The release is local only: no remote push or package publication occurred.
