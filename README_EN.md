# Codex Team

English | [中文](README.md)

Codex Team is a generic team and project-scoped Codex plugin containing a self-bootstrapping
Skill and a Python scheduler CLI. It keeps configuration, state, locks, publish
history, and optional observation logs isolated inside each project.

## Features

- Bootstrap a project-scoped scheduler without downloading its Python package.
- Publish tasks and claim them through atomic worker authorization and fenced leases.
- Diagnose routing, expired leases, migration, and compatibility issues.
- Isolate scheduler state, history, and locks between projects.
- Use `codex-team` to initialize, diagnose, and start a fresh generic team, with native role attestation, continuity, and reconciliation.

## Portable Codex Team

### Safe updates in 0.4.1

`codex-team update-policy` reports the default `notify` policy without mutation.
Only `codex-team update-policy auto` explicitly permits automatic updates; `off`
skips discovery. Auto validates a forward candidate, then transactionally
updates the managed private launcher and only the current project in fresh
subprocesses. A local-stage failure restores both local snapshots; a version-
changing success reports `project_updated: true` and requires a fresh Codex
session before team startup. Install 0.4.1 manually once when upgrading from
0.4.0.

On a new computer, installing this plugin is all that is required. The plugin
does not—and must not claim to—have a post-install hook. Restart Codex, then ask
it in any project to “install codex-team and bootstrap team mode.” The Skill runs
its own relative `scripts/install_codex_team.py`; the user never needs to clone
this repository, copy files, or discover a plugin-cache path. The installer uses
the bundled 0.4.0 wheel to create a private user environment and managed launcher,
emits a JSON receipt, and never edits PATH, shell profiles, or plugin files. If
the receipt says the bin directory is absent from PATH, apply its one-time hint in
the current shell. After installation, run `type -a codex-team`; if an old shell
function or alias appears before the managed launcher, unset it in the current shell
and remove the legacy shell-profile block manually. The installer never changes shell
profiles. Static `multi_agent` feature status is not native custom-agent attestation;
the fresh root must verify the requested agent type, spawn agent/thread id, and the
fixed model/reasoning contract from parent-visible native evidence. It then sends
that attestation to the same `product_manager` thread. A child is not required to
self-report parent-only fields; missing parent evidence still fails closed.

Every project uses the one latest team configuration and Skill bundled with
`codex-team`. `doctor` requires the managed configuration to be semantically
identical to the current template. `init` transactionally upgrades a differing
older configuration and Skill to 0.4.0. After a successful transactional upgrade,
the project keeps exactly `.agents/skills/codex-team` and removes legacy
`.agents/skills/global-scheduler` and `.agents/skills/codex-team-staff`. Bare `codex-team`/`start` performs this
upgrade before launching Codex; a failed upgrade rolls back the managed files
and never invokes Codex.

Then run these commands from the target project:

```bash
codex-team init
codex-team doctor
codex-team start
```

Every command defaults to the current directory, or accepts an explicit path
(including a path with spaces):

```bash
codex-team init "/work/my project"
codex-team role-A "/work/my project"
```

`init` manages only project-local `.codex/`, `.agents/skills/`, and scheduler
bootstrap files and reports separate `created`, `updated`, and Skill migration
fields. `doctor` verifies only static files; it cannot attest runtime native
identity. After auto-upgrade and doctor succeed, `start` invokes
`codex -C <target-project>` and requests
a new `product_manager` with `fork_turns=none`. `role-A/B/C/D/R` map to native
`window_a/window_b/window_c/window_d/researcher` and lowercase scheduler worker
ids `role-a...role-r`.

## What the Skill does

The Codex Team Skill is the reusable operating guide Codex follows when
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
[task-plan template](skills/codex-team/assets/任务计划书模板.md), which covers
research, execution batches, parallel nodes, R gates, task merging, and final
acceptance.

## Install from a custom Codex marketplace

The plugin installation name remains `global-scheduler` for compatibility; the
displayed and project-installed core Skill is Codex Team.

```bash
codex plugin marketplace add xxs9331/agent-task-scheduler --ref main
codex plugin add global-scheduler@xxs9331-scheduler
```

Restart Codex, open the target project, and ask:

```text
Use Codex Team to initialize this project.
```

The Skill installs its bundled wheel, creates canonical project configuration,
and runs a smoke check without downloading the Python package. For the first
`codex-team` command, it instead runs its relative user installer; plugin install
does not execute that code automatically. Roles operating in the same project and
Codex environment do not need separate installations.

> This repository is directly installable as a custom marketplace, but it is
> not yet listed in OpenAI's default Codex marketplace.

## Local Skill installation

```bash
mkdir -p .agents/skills
cp -R /path/to/agent-task-scheduler/skills/codex-team .agents/skills/codex-team
```

## Repository contents

- `.agents/plugins/marketplace.json`: Codex custom marketplace catalog.
- `.codex-plugin/plugin.json`: plugin discovery and display metadata.
- `skills/codex-team/SKILL.md`: team startup, role identity, and scheduler workflow.
- `skills/codex-team/scripts/install.py`: offline project bootstrap.
- `skills/codex-team/scripts/install_codex_team.py`: one-time safe user
  command installer backed by the bundled wheel.
- `skills/codex-team/assets/`: bundled, verified wheel.
- `skills/codex-team/assets/任务计划书模板.md`: reusable Chinese task-plan template.
- `skills/codex-team/references/`: contracts, errors, migration, and platform boundaries.
- `tests/` and `evals/`: implementation, infrastructure, and trigger cases.

## Validation

```bash
uv run --group test pytest -q
uv run --with ruff ruff check src tests skills/codex-team/scripts
```

A strict isolated offline build must warm and resolve against the same index
identity and cache directory. The verification helper performs one online build,
then immediately runs strict `uv build --offline` with the same
`UV_DEFAULT_INDEX` and `UV_CACHE_DIR`; it never uses `--no-build-isolation`:

```bash
UV_DEFAULT_INDEX=https://pypi.org/simple \
OFFLINE_BUILD_RESET_CACHE=1 \
scripts/verify_offline_build.sh
```

Set `OFFLINE_BUILD_VERIFY_ROOT` for an isolated verification directory. The
helper removes its own uv cache only when `OFFLINE_BUILD_RESET_CACHE=1` is set.
If a mirror is selected, keep the same `UV_DEFAULT_INDEX` for both phases so uv
does not look in a different registry cache namespace.

See `SECURITY.md`, `PRIVACY.md`, and `CHANGELOG.md` for operational boundaries
and release history.

Since 0.2.0, projects provision a scheduler worker registry with `staff-sync`
before `next` or `claim`. Each successful claim returns a unique `lease_id`;
heartbeat and active-attempt terminal commands must return that token.
Completion requires `--summary` and stores a durable receipt so a parent agent
can reconcile scheduler state after a native Codex child turn ends.

Version 0.2.1 requires every newly published create task to contain a non-empty
`metadata.team_mode.kind`; the complete batch is rejected otherwise. Only tasks
already present before the upgrade may continue to route as `unclassified`.
Caller-provided `--agent-id` is correlation metadata, not proof that Codex loaded
a custom-agent TOML.
