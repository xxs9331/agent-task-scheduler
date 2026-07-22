# Codex Team Orchestrator Contract

## Update boundary

If a preflight receipt says `restart_required=true`, do not native-spawn or
continue a team in that process. Ask for a fresh Codex session so it loads the
updated plugin and managed Skill.

This is the complete root and product-manager contract. Read it fully before
installation, bootstrap, team startup, native identity attestation, task
publication or update, staff dispatch, batch continuity decisions, PM debugging
or fallback, or gate coordination. A/B/C/D/R do not need this reference for
routine execution.

## First-use portable team bootstrap

When a user asks to install `codex-team`, bootstrap a team, or initialize team
mode after installing this plugin, run the installer from this Skill's own
directory:

```bash
python scripts/install_codex_team.py
```

The installer uses the bundled 0.4.2 wheel, creates a private user environment,
and places `codex-team` in the standard user bin directory. It emits one JSON
receipt and never edits shell profiles or PATH. If the receipt says the bin is
not on PATH, show its one-time path hint, then use `codex-team init`,
`codex-team doctor`, and `codex-team start` from the target project. For a
controlled installation or tests, pass `--prefix <temporary-prefix>`. It fails
closed if an existing `codex-team` command is not managed by this installer.

After installation, run `type -a codex-team`. If an old shell function or alias
appears before the managed launcher, unset it for the current shell and remove
its legacy profile block manually. Static multi-agent feature status is not
native custom-agent attestation.

Project installation uses exactly `.agents/skills/codex-team`. During a
successful transactional upgrade, remove legacy project Skills
`.agents/skills/global-scheduler` and `.agents/skills/codex-team-staff` only after
the new Skill is validated and committed. Roll back managed files if validation
or commit fails.

## Native topology and identity attestation

The portable topology is one thin root, one persistent product manager at depth
1, and A/B/C/D/R staff at depth 2. Depth-2 staff do not spawn another level. The
PM owns authorized publication and coordinates staff. Spawn a role only when a
ready scheduler task or bounded direct boss prompt requires it; do not pre-spawn the whole roster.

Team startup must select the configured native custom-agent name explicitly and
use `fork_turns=none`. Prompt text or a role TOML read by a generic worker is not
runtime identity attestation. Identity attestation is assembled by the parent,
not self-reported by the child.

The parent-visible native spawn receipt supplies the agent/thread id. The
parent-visible spawn invocation supplies the explicitly requested custom-agent
name used to construct `requested_custom_agent_name`, plus
`fork_context=false`; the selected TOML supplies the worker id, fixed model, and
reasoning effort. Do not require the receipt to echo the selector or fork settings.
`task_id` is scheduler correlation supplied by the parent, not a
native spawn-receipt field. The parent verifies the evidence against the TOML
contract and sends the attestation into the same child thread. A child cannot
independently read its parent-visible receipt, so missing child self-report is
not a failure. Missing or conflicting parent evidence fails closed.

The installed Skill ships `scripts/reconcile_handoff.py` for fail-closed,
machine-readable reconciliation of parent spawn attestation, project TOML role
contract, scheduler `describe` output, terminal lifecycle receipt, and
verification evidence. It verifies evidence and grants no authority.

## Batch-workstream live-agent registry

Treat native-agent reuse as batch-workstream affinity, not task-id identity. For
scheduled batch work, publish non-empty `metadata.team_mode.batch_id` and
`metadata.team_mode.workstream` when they are known. Maintain an in-memory
live-agent registry keyed by:

`(batch_id, worker_id, workstream) -> live agent_id`

Before spawning staff, look up that key. If the exact-role child is still alive,
its native identity remains attested, and the next task has compatible authority,
conflict domain, writable scope, and acceptance boundary, continue it with `send_input` even when `task_id` changes.
The child must claim and describe every
new scheduler task; prior task authorization never carries forward.

When batch metadata is absent, use the task id as the batch fallback and the
task's conflict domain as the workstream fallback. This preserves legacy
task-local continuation without guessing that distinct tasks are related.

Fresh-spawn the exact role with `fork_turns=none` when the batch or workstream
changes, work is unrelated, authority or writable scope is incompatible,
parallel isolation is required, or the prior child is closed. For a closed child,
provide only a bounded handoff containing live task status, evidence, the latest
receipt or verdict, unresolved acceptance items, and the next command. Do not use
`resume_agent` until the runtime proves custom role, model, reasoning, and policy
continuity across resume.

Keep an eligible child idle through its batch. At batch exit, close it and forget
the registry entry. Keep at most one live child per worker and serialize
overlapping writable scopes.

## Publication and routing

The PM owns plan interpretation, priorities, dependencies, conflict domains,
capacity exceptions, gates, and authorized task publication. Treat workload
skew as advisory rather than forced rebalance. Prefer direct continuation inside
one batch/workstream; publish a new task when the boss requests durable work or a
real authorization, conflict, writable-surface, deliverable, or gate boundary
changes.

Before publishing a phase or batch, read only the relevant live plan section and
translate it into a self-contained `worker_prompt` with scope, dependencies,
files, constraints, tests, acceptance, and block conditions. Never require staff
to reconstruct the plan. Every new create task needs a non-empty
`metadata.team_mode.kind`; add `batch_id` and `workstream` when known.

Read `references/contract.md` before publishing, updating, correcting a terminal
review, or using uncommon transitions. Require a machine-readable successful
receipt and verify routing. Never edit scheduler state directly. Direct boss
prompts authorize bounded execution but are not scheduler tasks. A/B/C/D and R
cannot publish executor work.

Preserve plan-node and gate boundaries. Do not promote a downstream score into
an earlier gate, publish repair before evidence and attribution exist, or collapse
independent gates. Make external writes, destructive actions, expensive evals,
git push/merge, and cleanup authorization explicit before dispatch.

## PM debugging and exceptional fallback

Read-only scheduler reconciliation may report escalation candidates for repeated
identical mechanical failures or a real no-eligible-worker authority gap. A
candidate is evidence only: it never publishes, claims, relabels, or mutates the
original task. Ordinary executor failure remains strict `pm_fallback` work until
the complete fallback authorization and independent R return gate exist.

The PM does not claim ordinary executor work. First-class PM debugging uses
worker `product_manager` only when `metadata.team_mode.kind=pm_debug`,
`required_worker=product_manager`, and the task has bounded `writable_files` and
a self-contained `worker_prompt` defining the problem, constraints,
verification, acceptance, and block conditions. The PM may reproduce, inspect,
modify code/configuration/tests within scope, verify, and complete the repair.
It does not require prior staff failure, model escalation, R advice, or
case-by-case boss approval.

Do not relabel ordinary implementation, capacity overflow, or safe same-domain
continuation as `pm_debug`. PM debug does not waive approval for external writes,
destructive actions, expensive evaluations, or configured gates, and PM cannot
self-approve an independent R gate.

Exceptional implementation fallback uses `role-p` only when
`metadata.team_mode.kind=pm_fallback` and complete `fallback_authorization`
metadata record `original_task_id`, `blocking_evidence`,
`model_escalation_attempted`, `user_authorization`, `r_evidence`,
`writable_scope`, and `return_gate_task_id`. It requires explicit boss approval
plus R advice or gate-failure evidence, stays within the smallest recorded scope,
and returns to independent R re-review. Do not use fallback instead of eligible
same-batch continuation, model escalation, or same-domain reassignment.

## Gate and reconciliation

R is independent and read-only. Review at the declared batch exit; iterations
inside a batch do not create extra gates. Gate pass uses `complete --summary`;
hold/needs_fix uses `block --reason`; review execution failure uses
`fail --reason`; `review-correct` only appends a corrected verdict to an already
terminal review.

When a child turn ends, stop its heartbeat, run `describe`, and require terminal
`done` status, a non-empty summary, a matching lifecycle receipt, and task
verification evidence. Child completion with a running task is an early exit or
orphan candidate, not success. PM debug and fallback return to an independent R
gate when the task requires one.
