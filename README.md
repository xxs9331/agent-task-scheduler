# Global Scheduler

Global Scheduler is a Codex plugin containing a self-bootstrapping Skill and a
project-scoped Python scheduler CLI. It keeps each project's configuration,
state, lock, publish history, and optional observation log inside that project.

## Contents

- `.codex-plugin/plugin.json`: plugin discovery and marketplace metadata.
- `skills/global-scheduler/SKILL.md`: trigger rules and operational workflow.
- `skills/global-scheduler/scripts/install.py`: offline project bootstrap.
- `skills/global-scheduler/assets/`: bundled, verified wheel.
- `skills/global-scheduler/references/`: contract, errors, migration, and platform boundaries.
- `tests/` and `evals/`: implementation, plugin-infrastructure, and trigger cases.

## Local Skill installation

Until this repository is registered in a Codex plugin marketplace, copy the
whole Skill directory into a project:

```bash
mkdir -p .agents/skills
cp -R /path/to/agent-task-scheduler/skills/global-scheduler .agents/skills/
```

Restart Codex, then ask: `Use global-scheduler to initialize this project.`
The Skill installs its bundled wheel, creates canonical project configuration,
and runs a smoke check without network access.

## Marketplace readiness

The plugin manifest points to `./skills/`, matching Codex plugin layout. A
marketplace submission still needs an actual repository/homepage, publisher
identity, and any required store artwork or policy URLs; these are intentionally
not fabricated in this local release.

## Validation

```bash
uv run --group test pytest -q
uv run --with ruff ruff check src tests skills/global-scheduler/scripts/install.py
```

See `SECURITY.md`, `PRIVACY.md`, and `CHANGELOG.md` for boundaries and release
history.
