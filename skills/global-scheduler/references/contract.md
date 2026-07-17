# Global Scheduler v1 Contract

Status: security-hardened in package 0.2.0. This document is normative for the independent `agent-task-scheduler` package and project-local installations of its wheel.

## Scope and boundaries

The package owns project discovery, validation, state persistence, lifecycle services, publish services, and the CLI adapter. The CLI is the only v1 public write surface. A distributable Skill invokes the installed CLI and never edits state. MCP and network-filesystem locking are out of scope.

Each managed project owns its own `.scheduler/project.json`, state file, derived lock file, optional observation log, embedded `publish_history`, and optional append-only `review_decisions`. The package installation contains no task data. Publish input may be caller-owned `--from-file`, `--stdin`, or `--json` and is not copied or archived.

## Project resolution

Resolution order is: explicit `--project-root`; otherwise the current directory and its parents, nearest first, containing `.scheduler/project.json`; otherwise a machine-readable `PROJECT_NOT_FOUND` failure. There is no global default pool. All roots and configured paths are resolved before access. `..`, symlink escape, cross-project paths, and project-id mismatch are rejected.

## Schema versions

Configuration, state, and publish input use independent integer versions: `config_schema_version`, `schema_version`, and `input_schema_version`. A reader may accept versions in its declared range; an unknown higher state version is never written. Schema migration is explicit and lock-protected.

## Publish semantics

`publish` accepts one strict envelope for both single-task and batch operations. The required `operation` discriminator is `create` or `update`; `oneOf` schema branches make the operation and item shape machine-checkable. `tasks` must be non-empty; a single task is an array of length one. `create` items contain task fields directly. `update` items contain `task_id` plus a `patch` object with only the documented mutable fields. Unknown fields and reserved runtime fields are rejected. The complete batch is validated before any write. Duplicate IDs, missing/self/cyclic dependencies, project mismatch, and invalid types fail atomically.

Default publish rejects an existing task id. `publish --update` is a field-whitelist patch for existing `ready` or `blocked_waiting_dependency` tasks only. It cannot alter `task_id`, `required_worker`, `created_at`, `attempt`, owner, lease, terminal records, or history. `required_worker` and `writable_files` are create-time authority fields. No `--replace` exists in v1. Successful create/update appends `published`/`publish_updated` to state `publish_history`.

The CLI mode and envelope discriminator are both required to agree. `publish` accepts exactly one of `--from-file FILE`, `--stdin`, or `--json JSON`; without `--update` it selects create mode and accepts only `operation: "create"`, while with `--update` it accepts only `operation: "update"`. The CLI validates this agreement before task validation or lock acquisition. Either mismatch returns `PUBLISH_OPERATION_MISMATCH` with `ok: false` and performs no write. The envelope discriminator remains mandatory so inputs are self-describing and cannot be replayed under the wrong mode silently.

## Lifecycle and receipt

The argument table below is the stable contract. Before execution, use `scheduler COMMAND --help` to confirm syntax against the installed version. Help does not replace the state, atomicity, authorization, or safety rules in this reference. If help and this contract disagree, stop and report the installed version and conflicting text instead of guessing.

Lifecycle commands are `status`, `ready`, `next`, `describe`, `claim`, `heartbeat`, `complete`, `retry`, `resume`, `continue`, `block`, `fail`, and `release-expired`. Domain services, not CLI parsing, own state transitions. Every command emits stable JSON with `ok`, project context, and relevant task/state fields. `next` with no route returns `task: null` and structured `blocked_candidates`.

The verified CLI accepts global `--project-root PATH`; `init --fresh` initializes or resets an isolated canonical project; `publish` accepts exactly one input source (`--from-file FILE`, `--stdin`, or `--json JSON`) and optional `--update`; `review-correct` requires terminal task, reviewer, pass/hold verdict, and summary; and `migrate` accepts at most one
of `--check` and `--dry-run`. Lifecycle argument requirements are task/worker
for `claim` and `continue`, with optional `--agent-id`; task/worker/lease-id for
`heartbeat`; task/worker/lease-id/reason for `block` and `fail`;
task/worker/lease-id/summary for `complete`; and a lease-id plus reason,
last-attempt summary, and next-attempt instruction for `retry`. `resume` operates
on an already terminal task and does not reuse its released lease.

Before any claim, a project administrator provisions the machine worker registry
with `staff-sync` from one strict JSON input. Unknown or non-executable workers
fail closed. Claim/continue recheck required worker, agent type, task kind,
kind-specific metadata, dependency state, one-live-task-per-worker, conflict
domain, and writable path overlap under the state lock.

Every claim/continue returns a unique `lease_id`; active-attempt transitions must
present it, so an old instance with the same worker id cannot mutate a new lease.
`claim --agent-id ID` records the native Codex thread in lease metadata.
`complete --summary` is mandatory and persists a completion receipt; block/fail
persist terminal receipts. Parent agents must reconcile with `describe` after a
child turn ends instead of treating child `Done` as scheduler completion.

Successful publish receipts contain `ok: true`, `operation` (`publish` or
`publish_update`), `changed_task_ids`, `warnings`, and `project`. Migration
receipts use `operation: "migrate"`, an empty `changed_task_ids`, and a
`migration` object. Failures use exit code 1 and stable `error.code` and
`error.message` fields.

## History and migration

`publish_history` is the authoritative publish fact, not a full lifecycle audit log. Entries have unique `event_id`, `event_type`, `occurred_at`, `project_id`, `task_id`, and a change summary. History is retained until explicit export/archival. Optional JSONL observation logging is non-authoritative. If state commit succeeds but JSONL append fails, the command still returns `ok: true` with `warnings: [{"code":"OBSERVATION_LOG_WARNING","message":"state committed; observation log append failed","rebuild_from":"publish_history"}]`; it must not return a false failure or roll back state.

`migrate --check`/`--dry-run` never changes bytes. A real migration locks first, validates the complete target state, and atomically replaces the file. Failure leaves original bytes unchanged and reports source version, target version, and summary.

`review-correct` does not change a terminal task's status or summary. It appends an immutable review decision with a unique event id and a `supersedes` link to the terminal summary or prior review decision for that task. This makes a corrected gate conclusion traceable without reopening work or silently changing history.
