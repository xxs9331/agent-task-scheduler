# Changelog

### 0.4.2

- Adds a fenced foreground lease guard, deterministic renewal recommendations,
  and observable active/near-expiry/expired lease health.

## Unreleased

### 0.4.1

- Added opt-in `codex-team update-policy {auto,notify,off}` preflight support.
  The default `notify` policy never mutates a marketplace, plugin, launcher, or
  project; `auto` is persisted only after an explicit choice and reports that a
  fresh Codex session is required after a version-changing update.
- Candidate discovery is bounded by JSON parsing, timeouts, strict forward
  semantic versions, plugin identity, managed-skill integrity, and matching
  wheel validation. Discovery and subprocess failures preserve the current
  installation as warnings.
- A 0.4.0 installation must be manually upgraded once: old code cannot update
  itself before the 0.4.1 updater is installed.
- Pinned the validated Hatchling build backend and added a strict isolated
  offline-build verifier that preserves one explicit index identity and cache
  directory across online cache warming and offline resolution.

### 0.4.0

- Added read-only, fail-closed PM rescue candidates for repeated structured
  failures and true no-eligible-worker authority gaps.
- Added batch-workstream affinity for reusing a still-live, parent-attested
  exact-role child across compatible scheduler task boundaries, without carrying
  prior task authorization forward.
- Split the concise staff execution contract from the PM-only orchestration,
  attestation, publication, debug/fallback, gate, and reconciliation reference.
- Updated native startup prompts to avoid unconditional fresh staff creation while
  retaining fresh-root PM startup and `fork_turns=none` for new children.

### 0.3.9

- Added first-class `pm_debug` work for the persistent product manager, allowing
  bounded diagnosis, code changes, verification, and completed repairs without
  the exhaustion prerequisites of exceptional `pm_fallback` takeover work.
- Clarified native PM attestation evidence ownership: the parent-visible spawn
  invocation proves the requested selector and `fork_context=false`, the spawn
  receipt supplies `agent_id`, and the selected TOML supplies the fixed role,
  model, and reasoning contract. Receipts are no longer incorrectly expected to
  echo invocation arguments.

### 0.3.8

- Force-reinstall the exact bundled wheel in the private managed user environment,
  so a changed wheel payload is installed even when its package version is unchanged.
- Added transactional stock-managed 0.3.7-to-0.3.8 migration coverage and retained
  0.3.7 as a supported legacy Skill fixture.

### 0.3.7

- Replaced generated role stubs with packaged canonical six-role TOML contracts,
  including PM fallback authorization, read-only R boundaries, and executor
  same-task continuation boundaries.
- Shipped fail-closed `reconcile_handoff.py` and merged its staff and scheduler
  reconciliation semantics into the portable Skill.
- Made the two-level launcher package carry exactly one non-recursive core wheel.

### 0.3.6

- Merged generic Codex Team startup, native role attestation, thread continuity,
  and parent reconciliation guidance into the core Skill.
- Renamed the project-installed Skill to `codex-team` while retaining
  `global-scheduler` as the marketplace installation compatibility name.
- Documented transactional migration to `.agents/skills/codex-team`, including
  removal of legacy `global-scheduler` and `codex-team-staff` project Skills
  after successful validation.

### 0.3.5

- Made the bundled 0.3.5 team configuration and Skill the single canonical
  managed version for every project.
- Added transactional replacement of differing older team configuration and
  Skill files, with explicit created/updated/version receipts and rollback.
- Made bare `codex-team`/`start` auto-upgrade before launching Codex and refuse
  to launch when migration or static validation fails.

### 0.3.4

- Changed fresh-root native identity handoff to use the parent-visible spawn
  receipt and fixed custom-agent contract, then inject the verified attestation
  into the same `product_manager` thread with `send_input`.
- Stopped treating a child's inability to self-report parent-only agent/thread
  fields as a spawn failure while retaining fail-closed behavior for missing
  parent evidence or a mismatched project TOML contract.
- Added guarded stock-managed 0.3.3 project migration to 0.3.4.

### 0.3.3

- Made `codex-team doctor` accept complete, explicitly supported 0.3.1 project
  Skills without overwriting them, while reporting a machine-readable legacy
  warning. Unknown, incomplete, and damaged Skills still fail closed.

### 0.3.2

- Made the first-use installer and documentation diagnose legacy shell command
  shadowing without modifying shell profiles.
- Hardened fresh team-root prompts against recursive `codex-team` or nested Codex
  startup and clarified native runtime attestation fail-closed boundaries.

- Added the Skill-relative, offline `install_codex_team.py` user-command
  installer. It creates a private environment from the bundled 0.3.2 wheel,
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
