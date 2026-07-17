# Changelog

## Unreleased

- Added the Skill-relative, offline `install_codex_team.py` user-command
  installer. It creates a private environment from the bundled 0.3.1 wheel,
  writes only a managed launcher, reports PATH guidance, and refuses conflicts.
- Documented the complete marketplace-plugin to first-use `codex-team` flow for
  POSIX and Windows without claiming a plugin post-install hook.
- Added portable `codex-team` init, doctor, fresh root, and role launch commands.
- Added project-local generic custom-agent, handoff, and staff-Skill templates.
- Made team bootstrap reject conflicting files and never fall back to another project.
- Added Chinese-first bilingual installation and usage documentation.
- Added a Codex custom marketplace catalog and verified repository metadata.
- Documented the Skill workflow and bundled the reusable Chinese task-plan template.

## 0.2.1 - 2026-07-17

- Reject new publish/create items that omit a non-empty `metadata.team_mode.kind`.
- Preserve `unclassified` routing only for tasks already present in project state.
- Reject empty strings and empty collections for required claim metadata.
- Clarify that caller-provided `--agent-id` is lease correlation data, not proof that Codex loaded a custom-agent TOML.

## 0.2.0 - 2026-07-17

- Added an atomic scheduler worker registry and fail-closed claim authorization.
- Added unique fenced lease tokens for heartbeat and all active-attempt terminal transitions.
- Added optional native Codex agent/thread identity to claim lease metadata.
- Added required-worker and writable-path overlap enforcement at claim time.
- Added durable completion and terminal receipts for parent-agent reconciliation.
- Made completion summaries mandatory and documented the one-time staff registry migration.

## 0.1.0 - 2026-07-13

- Added project-scoped scheduler core and CLI.
- Added strict publish, lifecycle, locking, migration, history, and routing diagnostics.
- Added Linux/WSL and native Windows validation evidence.
- Added discoverable `global-scheduler` Skill with offline bootstrap installer and bundled wheel.
- Added Codex plugin manifest, progressive references, infrastructure tests, and trigger eval cases.
