# Global Scheduler

English | [中文](README.md)

Global Scheduler is a project-scoped Codex plugin containing a self-bootstrapping
Skill and a Python scheduler CLI. It keeps configuration, state, locks, publish
history, and optional observation logs isolated inside each project.

## Features

- Bootstrap a project-scoped scheduler without downloading its Python package.
- Publish tasks and claim them through atomic worker authorization and fenced leases.
- Diagnose routing, expired leases, migration, and compatibility issues.
- Isolate scheduler state, history, and locks between projects.

## What the Skill does

The `global-scheduler` Skill is the reusable operating guide Codex follows when
using the scheduler. It stores no task data and does not replace the Scheduler
CLI. Instead, it makes Codex invoke the CLI within the correct project boundary
and follow the contracts for bootstrap, publish, claim, heartbeat, completion,
recovery, and guarded migration.

Typical requests include initializing a project, publishing parallel A/B/C/D/R
work, diagnosing a rejected claim or active lease, releasing expired work, and
dry-running a legacy migration. The normal flow is: load the Skill, discover the
project configuration, invoke the project-local `scheduler` CLI, and act on its
JSON receipt.

The Skill prohibits cross-project state reuse, direct state-JSON edits, silent
legacy migration, and holding a task lease while waiting for a gate. For complex
work breakdowns, start with the bundled Chinese
[task-plan template](skills/global-scheduler/assets/任务计划书模板.md), which covers
research, execution batches, parallel nodes, R gates, task merging, and final
acceptance.

## Install from a custom Codex marketplace

```bash
codex plugin marketplace add xxs9331/agent-task-scheduler --ref main
codex plugin add global-scheduler@xxs9331-scheduler
```

Restart Codex, open the target project, and ask:

```text
Use global-scheduler to initialize this project.
```

The Skill installs its bundled wheel, creates canonical project configuration,
and runs a smoke check without downloading the Python package. Roles operating
in the same project and Codex environment do not need separate installations.

> This repository is directly installable as a custom marketplace, but it is
> not yet listed in OpenAI's default Codex marketplace.

## Local Skill installation

```bash
mkdir -p .agents/skills
cp -R /path/to/agent-task-scheduler/skills/global-scheduler .agents/skills/
```

## Repository contents

- `.agents/plugins/marketplace.json`: Codex custom marketplace catalog.
- `.codex-plugin/plugin.json`: plugin discovery and display metadata.
- `skills/global-scheduler/SKILL.md`: trigger rules and operational workflow.
- `skills/global-scheduler/scripts/install.py`: offline project bootstrap.
- `skills/global-scheduler/assets/`: bundled, verified wheel.
- `skills/global-scheduler/assets/任务计划书模板.md`: reusable Chinese task-plan template.
- `skills/global-scheduler/references/`: contracts, errors, migration, and platform boundaries.
- `tests/` and `evals/`: implementation, infrastructure, and trigger cases.

## Validation

```bash
uv run --group test pytest -q
uv run --with ruff ruff check src tests skills/global-scheduler/scripts/install.py
```

See `SECURITY.md`, `PRIVACY.md`, and `CHANGELOG.md` for operational boundaries
and release history.

Since 0.2.0, projects provision a scheduler worker registry with `staff-sync`
before `next` or `claim`. Each successful claim returns a unique `lease_id`;
heartbeat and active-attempt terminal commands must return that token.
Completion requires `--summary` and stores a durable receipt so a parent agent
can reconcile scheduler state after a native Codex child turn ends.
