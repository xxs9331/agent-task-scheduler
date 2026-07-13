# Global Scheduler Final Gate R5

- task_id: `task_global_scheduler_final_gate_r5`
- role: `R` (final, read-only gate)
- decision: `pass`
- reviewed: 2026-07-13

## Decision

The global v1 final cross-platform gate **passes**. Linux/WSL clean-install
evidence is green, and C3 has now installed the Linux/WSL-built wheel into a
fresh native Windows venv and exercised the installed `scheduler.exe` through
publish, claim, and complete. Windows did not build the wheel.

| Gate | Decision | Evidence |
|---|---|---|
| Contract, CLI, schema, and R research gate | pass | `tmp/global_scheduler_research_gates_r/REPORT.md` records resolved CLI routing/receipt issues and passing focused checks. |
| Current regression suite | pass | `UV_CACHE_DIR=/tmp/agent-task-scheduler-uv-cache uv run --group test pytest -q`: `43 passed in 0.59s`. |
| Static checks | pass | `uv run --with ruff ruff check src tests`: all checks passed. |
| Package build | pass | `uv build --wheel --out-dir /tmp/global-scheduler-r5-final-dist` built `agent_task_scheduler-0.1.0-py3-none-any.whl`. |
| Linux/WSL clean install and isolation | pass | B3 installed a built wheel into a fresh venv, verified two independent project states, a lifecycle completion, and observation-log warning behavior. |
| Native Windows lock and migration | pass | C3 ran real Windows process contention, timeout, crash-release, dry-run, and atomic migration checks. |
| Native Windows wheel install and CLI | pass | C3 installed the prebuilt wheel in a fresh Windows venv, then ran installed `scheduler.exe` for publish, claim, and complete; final task status was `done`. |

## Closure

No release blocker remains in the final-gate scope. The earlier Windows source
installation error was caused by an absent local build backend and is not a
requirement for consuming the portable wheel; C3's wheel-based acceptance
provides the needed platform evidence.

## Boundary

R changed only this final-gate report and its decision JSON. No implementation,
task state, external service, or Windows environment was modified.
