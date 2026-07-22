---
name: "codex-team"
description: "Use for generic Codex Team startup, native role attestation, continuity, reconciliation, and project-scoped scheduler lifecycle through the installed agent-task-scheduler CLI."
---

# Codex Team Skill

## Load only the contract needed by the active role

This file is the concise execution and safety contract shared by A/B/C/D/R.
Do not make staff reload product-manager orchestration policy for routine work.

Before installation, bootstrap, team startup, native identity attestation, task
publication or update, staff dispatch, batch continuity decisions, PM debugging
or fallback, or gate coordination, the root or product manager must read
`references/orchestrator.md` completely. Staff A/B/C/D/R must not read that PM-only
reference unless the boss explicitly changes the role and task authority.

Use the project-local scheduler for durable task routing and lifecycle operations.
This Skill stores no task data, grants no role additional authority, and never
edits scheduler JSON directly.

## Role identity and execution boundaries

Use the project TOML `name` as the native selector and the lowercase worker id
only for scheduler lifecycle commands:

- role-P -> `.codex/agents/product_manager.toml` -> `name=product_manager`, worker `product_manager`
- role-R -> `.codex/agents/researcher.toml` -> `name=researcher`, worker `role-r`
- role-A -> `.codex/agents/window_a.toml` -> `name=window_a`, worker `role-a`
- role-B -> `.codex/agents/window_b.toml` -> `name=window_b`, worker `role-b`
- role-C -> `.codex/agents/window_c.toml` -> `name=window_c`, worker `role-c`
- role-D -> `.codex/agents/window_d.toml` -> `name=window_d`, worker `role-d`

A/B/C/D execute only bounded authorized work and cannot publish, route, or
manage work for another role. Model escalation does not change the worker id, task id,
writable scope, or acceptance criteria. A claimed scheduler task or direct boss prompt is
authorization only for its stated worker id, goal, writable scope, constraints,
verification, and acceptance boundary.

R may claim only read-only research, review, or gate tasks. R must not implement,
edit code/data, run generation or business evaluations, publish work, or
self-approve PM debug or fallback work. Gate pass uses `complete --summary`;
hold/needs_fix uses `block --reason`; review execution failure uses
`fail --reason`.

## Batch-workstream continuation

A verified parent may reuse a still-live exact-role child for successive task ids
only within the same attested batch and workstream. The affinity key is
`(batch_id, worker_id, workstream)`. A reused child must keep the same role and
must not infer new authority from prior chat history.

For every new scheduler task, including one delivered to a reused child, run the
normal `claim` and `describe` flow and treat the new task prompt as authoritative.
Prior task authorization never carries forward or expands the new task's
writable scope, conflict boundary, verification, or acceptance criteria.

When `metadata.team_mode.batch_id` or `metadata.team_mode.workstream` is absent,
continuation falls back to task-local identity: the task id is the batch fallback
and the conflict domain is the workstream fallback. Unrelated work,
another batch or workstream, incompatible authority or writable scope, a closed
child, or required parallel isolation must use a fresh exact-role child with
`fork_turns=none` and a bounded handoff.

## Scheduler lifecycle

Use `next`, then `claim`, then `describe`; record the returned `lease_id`, follow
the returned `worker_prompt`, and operate lifecycle commands only as the owning
worker with the current token. Bind a native Codex thread with
`claim --agent-id ID` when that identity is available. If no task is routable,
inspect `blocked_candidates` rather than inventing work.

`heartbeat`, `complete`, `retry`, `block`, and `fail` require `--lease-id`.
Completion also requires a non-empty `--summary`. Routine scheduled work ends
with concise `complete --summary`; use `block --reason` or `fail --reason` when
appropriate. Do not require extra handoff reports by default.

When a child turn ends, the parent must run `describe` and require terminal
`done` status, a non-empty summary, a matching lifecycle receipt, and task
verification evidence. A child ending while the task remains `running` is an
early exit or orphan candidate, not success.

## Core invariants

- Use the scheduler executable installed for the current project and pass an explicit project root when needed.
- Run one scheduler command per tool call. Do not combine lifecycle commands with pipes, shell chaining, environment wrappers, or ad hoc state edits.
- The configured project state is the sole task and lease truth. Never fall back to, copy, or silently migrate another task pool.
- The scheduler worker registry and task fields mechanically constrain claim authority. Role TOML and prompts may narrow behavior but cannot grant scheduler permission.
- Every newly published create task must include a non-empty `metadata.team_mode.kind`; `unclassified` is compatibility-only for existing state.
- Keep at most one live child per worker and serialize overlapping writable scopes.

If syntax is uncertain, run that subcommand's `--help`. Help is runtime syntax
truth; references define state, atomicity, and safety. If help and a reference
disagree, stop and report the installed version and conflicting text.

## Load references only when needed

- `references/orchestrator.md`: mandatory for root/PM orchestration; forbidden for routine staff execution.
- `references/contract.md`: command arguments, lifecycle states, publish/update envelopes, receipts, and `review-correct`.
- `references/errors.md`: stable failures and recovery.
- `references/bootstrap.md`: isolated project task-pool initialization details.
- `references/platform.md`: platform and filesystem boundaries.
- `references/migration.md`: explicitly authorized migration checks and history.
- `assets/任务计划书模板.md`: task-plan creation or revision.

This Skill does not authorize business-code edits, datasets, external writes,
destructive actions, Task Center changes, migrations, or gate verdicts. Those
require explicit task and role authority.
