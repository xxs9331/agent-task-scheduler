# Global Scheduler

English | [中文](README.md)

Global Scheduler is a project-scoped Codex plugin containing a self-bootstrapping
Skill and a Python scheduler CLI. It keeps configuration, state, locks, publish
history, and optional observation logs isolated inside each project.

## Features

- Bootstrap a project-scoped scheduler without downloading its Python package.
- Publish, claim, heartbeat, resume, and complete tasks.
- Diagnose routing, expired leases, migration, and compatibility issues.
- Isolate scheduler state, history, and locks between projects.

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
- `skills/global-scheduler/references/`: contracts, errors, migration, and platform boundaries.
- `tests/` and `evals/`: implementation, infrastructure, and trigger cases.

## Validation

```bash
uv run --group test pytest -q
uv run --with ruff ruff check src tests skills/global-scheduler/scripts/install.py
```

See `SECURITY.md`, `PRIVACY.md`, and `CHANGELOG.md` for operational boundaries
and release history.
