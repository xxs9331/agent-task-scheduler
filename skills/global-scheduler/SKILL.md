---
name: "global-scheduler"
description: "Use for project-scoped scheduler lifecycle, publication, review correction, routing diagnosis, recovery, or task-pool setup through the installed agent-task-scheduler CLI."
---

# Global Scheduler Skill

Use the installed project-local scheduler for durable task routing and lifecycle operations. This Skill stores no task data, grants no role additional authority, and never edits scheduler JSON directly.

## Core invariants

- Use the scheduler executable installed for the current project and pass an explicit project root when needed.
- Run one scheduler command per tool call. Do not combine lifecycle commands with pipes, shell chaining, environment wrappers, or ad hoc state edits.
- The configured project state is the sole task and lease truth. Never fall back to, copy, or silently migrate another task pool.
- The scheduler worker registry and task fields mechanically constrain claim authority. Role TOML and task prompts may narrow behavior but cannot grant scheduler permission. This Skill describes mechanics; it grants no permission.
- Routine scheduled work ends with concise `complete --summary`; use `block --reason` or `fail --reason` when appropriate. Do not require extra handoff reports by default.

## Normal routing

Use `next`, then `claim`, then `describe`; record the returned `lease_id`, follow the returned `worker_prompt`, and operate lifecycle commands only as the owning worker with the current token. Bind a native Codex thread with `claim --agent-id ID` when that identity is available. If no task is routable, inspect blocked-candidate evidence rather than inventing work.

`heartbeat`, `complete`, `retry`, `block`, and `fail` require `--lease-id`. Completion also requires a non-empty `--summary`. A child-agent turn ending is not task completion: the parent re-runs `describe` and verifies `status=done`, summary, completion receipt, and task evidence before reporting success. A child ending while the task remains `running` is an early exit/orphan candidate, not success.

If syntax is uncertain, run that subcommand's `--help`. Help is runtime syntax truth; references define state, atomicity, and safety. If help and a reference disagree, stop and report the installed version and conflict.

## Load references only when needed

- `references/contract.md`: command arguments, lifecycle states, publish/update envelopes, receipts, and `review-correct`. Read before publishing, updating, correcting a terminal review, or using uncommon transitions.
- `references/errors.md`: stable failures and recovery.
- `references/bootstrap.md`: install or initialize an isolated project task pool.
- `references/platform.md`: platform and filesystem boundaries.
- `references/migration.md`: migration checks and history; read only for explicitly authorized migration work.
- `assets/任务计划书模板.md`: use when asked to create or revise a scheduler task plan.

## Gate and safety boundaries

Gate pass uses `complete --summary`; hold/needs_fix uses `block --reason`; review execution failure uses `fail --reason`. `review-correct` only appends a corrected verdict to an already terminal review.

This Skill does not authorize business-code edits, datasets, external writes, destructive actions, Task Center changes, migrations, or gate verdicts. Those require explicit task and role authority.
