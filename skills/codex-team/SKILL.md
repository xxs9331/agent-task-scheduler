---
name: "codex-team"
description: "Use for generic Codex Team startup, native role attestation, continuity, reconciliation, and project-scoped scheduler lifecycle through the installed agent-task-scheduler CLI."
---

# Codex Team Skill

## First-use portable team bootstrap

When a user asks to install `codex-team`, bootstrap a team, or initialize team
mode after installing this plugin, run the installer from this Skill's own
directory. Do not ask the user to locate a plugin cache or clone this repository:

```bash
python scripts/install_codex_team.py
```

The installer uses the bundled 0.3.7 wheel, creates a private user environment, and
places `codex-team` in the standard user bin directory. It emits one JSON receipt
and never edits shell profiles or PATH. If the receipt says the bin is not on
PATH, show its one-time path hint, then use `codex-team init`, `codex-team doctor`,
and `codex-team start` from the target project. For a controlled installation or
tests, pass `--prefix <temporary-prefix>`. It fails closed if an existing
`codex-team` command is not managed by this installer.

After installation, run `type -a codex-team`. If an old shell function or alias
appears before the managed launcher, unset it for the current shell and remove its
legacy block from the shell profile manually; the installer will never modify a
shell profile. A static multi_agent feature report is not proof of native custom-agent selection or identity attestation: missing requested custom-agent name, agent/thread id, effective model, or reasoning effort must fail closed.

Use the installed project-local scheduler for durable task routing and lifecycle operations. This Skill stores no task data, grants no role additional authority, and never edits scheduler JSON directly.

## Generic role startup and identity

The portable topology is one thin root, one persistent product manager, and five
staff roles. Use the project TOML `name` as the native selector and the lowercase
worker id only for scheduler lifecycle commands:

- role-P -> `.codex/agents/product_manager.toml` -> `name=product_manager`, worker `product_manager`
- role-R -> `.codex/agents/researcher.toml` -> `name=researcher`, worker `role-r`
- role-A -> `.codex/agents/window_a.toml` -> `name=window_a`, worker `role-a`
- role-B -> `.codex/agents/window_b.toml` -> `name=window_b`, worker `role-b`
- role-C -> `.codex/agents/window_c.toml` -> `name=window_c`, worker `role-c`
- role-D -> `.codex/agents/window_d.toml` -> `name=window_d`, worker `role-d`

The root native-spawns the product manager at depth 1. The product manager owns
authorized publication and coordinates A/B/C/D/R at depth 2; depth-2 staff do not
spawn another level. A/B/C/D execute only bounded authorized work and cannot
publish. R is read-only for research and gate review and cannot implement or
publish. The product manager does not claim ordinary executor work and does not claim ordinary tasks.

Direct boss prompts authorize bounded execution but are not scheduler tasks.
Executors A/B/C/D retain their worker id, task boundary, writable scope, and
acceptance criteria for same-task continuation; they do not publish, route, or
manage work for another role. R is read-only by default and must not implement,
edit code/data, run generation or business evaluations, or self-approve PM
fallback work. PM fallback is exceptional: it requires explicit boss approval,
R advice or gate-failure evidence, the smallest recorded writable scope, and
`fallback_authorization` containing `original_task_id`, `blocking_evidence`,
`model_escalation_attempted`, `user_authorization`, `r_evidence`,
`writable_scope`, and `return_gate_task_id`.

Team startup must select the configured native custom-agent name explicitly and use
`fork_turns=none`. Prompt text or a role TOML read by a generic worker is not
runtime identity attestation. Identity attestation is assembled by the parent, not self-reported by the child. The parent-visible native spawn receipt supplies
the `requested_custom_agent_name` field and agent/thread id; the selected TOML supplies the
worker id, fixed model, and reasoning effort. `task_id` is scheduler correlation supplied by the parent, not a native spawn-receipt field. The parent verifies this
evidence against the TOML contract and sends the attestation into the same child
thread. A child cannot independently read its parent-visible spawn receipt, so missing child self-report is not a failure. Missing or conflicting parent evidence
fails closed; a generic worker that merely reads a TOML must not claim the mapped
custom-agent identity.

Use one persistent worker per configured role and keep the worker id, task id,
writable scope, goal, and acceptance boundary stable for same-task continuation.
If the same task's native child is still open, continue it with `send_input` so the worker retains the relevant task context. If it was closed, create a fresh
native child with the same exact role and `fork_turns=none`, then provide a
bounded handoff containing live task status, evidence, the latest receipt or
verdict, unresolved acceptance items, and the next command. If the new work is unrelated, spawn a fresh exact-role child with `fork_turns=none` and do not import prior chat history merely because the worker role matches.

## Role execution boundaries

For A/B/C/D, use the mapped persistent worker id for `next`, then claim and
describe only the assigned task. Model escalation does not change the worker id, task id, writable scope, or acceptance criteria. Continue unfinished work in the
same scope under the same task id; create new work only when a terminal boundary,
authorization, conflict domain, or writable surface changes.

role-R may claim only read-only research, review, or gate tasks. Use:

`<project-local-scheduler> --project-root <project-root> claim --task <task_id> --worker role-r`

Role-R must not implement or publish tasks. The claimed worker prompt must grant
no implementation or publication authority; gate lifecycle follows the task.

Role-P normally publishes authorized task definitions and does not claim ordinary
tasks. Exceptional implementation fallback uses `role-p` only when
`metadata.team_mode.kind=pm_fallback` and complete `fallback_authorization`
metadata are present. Claim it only with:

`<project-local-scheduler> --project-root <project-root> claim --task <task_id> --worker role-p`

Fallback authorization records `original_task_id`, `blocking_evidence`,
`model_escalation_attempted`, `user_authorization`, `r_evidence`,
`writable_scope`, and `return_gate_task_id`; it remains within the smallest
authorized writable scope and returns to independent Role-R review. Do not use
fallback to replace an eligible A/B/C/D continuation, model escalation, or
same-domain reassignment.

When a child turn ends, reconcile the durable task state before reporting success:
stop its heartbeat, run `describe`, and require terminal `done` status, a
non-empty summary, a matching lifecycle receipt, and task verification evidence.
Child completion with a still-running task is an early exit or orphan candidate,
not success. Keep at most one live child per worker and serialize overlapping
writable scopes.

The installed Skill ships `scripts/reconcile_handoff.py` for fail-closed,
machine-readable reconciliation of the parent spawn attestation, project TOML
role contract, scheduler `describe` output, terminal lifecycle receipt, and
verification evidence. It is a verifier, not a grant of role authority.

## Core invariants

- Use the scheduler executable installed for the current project and pass an explicit project root when needed.
- Run one scheduler command per tool call. Do not combine lifecycle commands with pipes, shell chaining, environment wrappers, or ad hoc state edits.
- The configured project state is the sole task and lease truth. Never fall back to, copy, or silently migrate another task pool.
- The scheduler worker registry and task fields mechanically constrain claim authority. Role TOML and task prompts may narrow behavior but cannot grant scheduler permission. This Skill describes mechanics; it grants no permission.
- Routine scheduled work ends with concise `complete --summary`; use `block --reason` or `fail --reason` when appropriate. Do not require extra handoff reports by default.

## Normal routing

Use `next`, then `claim`, then `describe`; record the returned `lease_id`, follow the returned `worker_prompt`, and operate lifecycle commands only as the owning worker with the current token. Bind a native Codex thread with `claim --agent-id ID` when that identity is available. If no task is routable, inspect blocked-candidate evidence rather than inventing work.

`heartbeat`, `complete`, `retry`, `block`, and `fail` require `--lease-id`. Completion also requires a non-empty `--summary`. A child-agent turn ending is not task completion: the parent re-runs `describe` and verifies `status=done`, summary, completion receipt, and task evidence before reporting success. A child ending while the task remains `running` is an early exit/orphan candidate, not success.

Every newly published create task must include a non-empty
`metadata.team_mode.kind`. `unclassified` is only a compatibility interpretation
for tasks already present in state; never omit classification from new work.

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

## Project Skill migration

Project installation uses exactly `.agents/skills/codex-team`. During a successful
transactional upgrade, remove the legacy project Skills
`.agents/skills/global-scheduler` and `.agents/skills/codex-team-staff` only
after the new Codex Team Skill is validated and committed. If validation or
commit fails, roll back the managed files and retain the legacy Skills.
