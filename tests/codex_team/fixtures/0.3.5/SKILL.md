---
name: "global-scheduler"
description: "Use for project-scoped scheduler lifecycle, publication, review correction, routing diagnosis, recovery, or task-pool setup through the installed agent-task-scheduler CLI."
---

# Global Scheduler Skill

## First-use portable team bootstrap

When a user asks to install `codex-team`, bootstrap a team, or initialize team
mode after installing this plugin, run the installer from this Skill's own
directory. Do not ask the user to locate a plugin cache or clone this repository:

```bash
python scripts/install_codex_team.py
```

The installer uses the bundled 0.3.5 wheel, creates a private user environment, and
places `codex-team` in the standard user bin directory. It emits one JSON receipt
and never edits shell profiles or PATH. If the receipt says the bin is not on
PATH, show its one-time path hint, then use `codex-team init`, `codex-team doctor`,
and `codex-team start` from the target project. For a controlled installation or
tests, pass `--prefix <temporary-prefix>`. It fails closed if an existing
`codex-team` command is not managed by this installer.

After installation, run `type -a codex-team`. If an old shell function or alias
appears before the managed launcher, unset it for the current shell and remove its
legacy block from the shell profile manually; the installer will never modify a
shell profile. A static `multi_agent` feature report does not prove native
custom-agent selection or identity attestation: missing agent type, agent/thread
id, effective model, or reasoning effort must fail closed.

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
