# Global scheduler v1 A4 release closeout

- task_id: `task_global_scheduler_release_closeout_a4`
- status: complete

## R5 evidence reused

R5's final read-only gate is `pass`: the current suite, static checks, wheel
build, Linux/WSL clean-install/isolation, native Windows lock/migration, and
native Windows installed-wheel CLI evidence all passed. This closeout preserves
the accepted behavior and reports; it does not reopen gate decisions.

## Repository inventory and cleanup

The deliverable retains source, tests, docs, schemas, the distributable Skill,
project metadata/lockfile, and all historical `tmp` evidence. Added `.gitignore`
for virtual environments, bytecode, lint/test caches, build outputs, and local
timing artifacts. Removed only generated `.pytest_cache`, `.ruff_cache`, Python
`__pycache__` directories, and the empty `test_timing.csv`; no historical report
or legacy task record was removed.

## Verification and delivery

All required release checks passed. The final suite contains 46 passing tests,
including three bootstrap-installer tests. The wheel is
`/tmp/agent-task-scheduler-v1-dist/agent_task_scheduler-0.1.0-py3-none-any.whl`
with SHA-256
`6ef426ffe95a98a14d70a75c50681a1980cfa8d0fec8dad83b8102396532ff2a`.
The same verified wheel is retained at
`artifacts/v0.1.0/agent_task_scheduler-0.1.0-py3-none-any.whl`; the full
command/results inventory and v1 boundaries are in `DELIVERY_MANIFEST.md`.
The distributable Skill now bundles the same wheel plus a tested installer that
can initialize a fresh project without network access.

## Boundaries

No Parlant runtime/business logic, Task Center, datasets, CNB, Feishu, remote
repository, or package registry was changed. The corrected release ref
`scheduler-v0.1.0`, Git commit, and retained artifact are local only.
