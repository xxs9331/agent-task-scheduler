---
name: "global-scheduler"
description: "Use for project-scoped scheduler lifecycle, publish, review-correction, routing diagnostics, release-expired recovery, or task-pool setup through the installed agent-task-scheduler CLI. In Parlant, the project-local CLI and .scheduler/state.json are the only supported scheduler interface."
---

# Global Scheduler Skill (v1)

This Skill is distributable instructions for an installed `agent-task-scheduler` CLI. It stores no task data and never edits JSON state directly.

## Goal and non-goals

Use this Skill to initialize an isolated project scheduler, publish validated
tasks, operate lifecycle transitions, diagnose routing and leases, and perform
guarded migration checks. Do not use it to generate task content, change staff
routing policy, modify Task Center, promise network-filesystem locking, or
silently migrate legacy project metadata.

Load detailed references only when the task needs them:

- `references/contract.md`: schemas, lifecycle, publish, and receipt contract.
- `references/errors.md`: stable failures and recovery decisions.
- `references/platform.md`: Linux/Windows and filesystem boundaries.
- `references/migration.md`: dependencies, history, and legacy migration safety.

## Completion evidence policy

Routine implementation and documentation tasks should finish with a concise
`complete --summary`; do not require or create `REPORT.md` by default. The
summary should name the result, verification, touched files, caveats, and next
recommendation. Use a durable report or decision artifact only for research,
R gates, complex audits, or an explicitly requested multi-artifact handoff.

For scheduler task planning, start from `assets/任务计划书模板.md`. Preserve its
research, flowchart, execution-batch, gate, and final-acceptance structure.
Merge consecutive work owned by the same role when it has the same file domain
and no intervening gate, platform boundary, or external wait. Gates are batch
completion conditions, not standalone execution batches.

## Bootstrap a new project

When the user asks to install or initialize global scheduler in the current
project, run the bundled installer from the Skill directory:

```bash
python .agents/skills/global-scheduler/scripts/install.py --project-root "$PWD"
```

Use `--project-id ID` when the directory name is not the intended stable id.
The installer creates or reuses `.venv`, installs the bundled wheel without
network access, creates canonical `.scheduler/project.json`, and runs
`scheduler status`. It refuses to overwrite a different existing project
configuration. Do not copy another project's state. After bootstrap, restart
or reopen Codex so all windows discover the project-local Skill.

## Parlant command policy

From `/home/lenovo/projects/parlant`, use one command per tool call. Standard
project-mode commands use the installed executable through the repository venv:

```bash
.venv/bin/scheduler --project-root /home/lenovo/projects/parlant status
```

Do not join scheduler commands with `;`, `&&`, pipes, or subshells. Do not add
`UV_CACHE_DIR`, environment assignments, or `uv run` to lifecycle commands.
Use `.venv/bin/python scripts/agent_task_scheduler.py --state ...` only when a
task explicitly requires legacy compatibility behavior.

The current Parlant live pool is a legacy state containing staff routing and
worker metadata that canonical v1 does not preserve. Until a separately gated
cutover migrates those root fields, use the installed standard CLI only for
read-only `status`, `ready`, `next`, `describe`, and `migrate --dry-run`
diagnostics against Parlant. Use the legacy compatibility entry for every
Parlant live-pool write (`publish`, `claim`, `heartbeat`, `continue`, `block`,
`fail`, `complete`, `retry`, `resume`, and `release-expired`). Never run a real
standard `migrate` against the Parlant live state in v1.

## Initialize a managed project

```bash
mkdir -p .scheduler
cat > .scheduler/project.json <<'JSON'
{"config_schema_version":1,"project_id":"my-project","state_path":".scheduler/state.json","events_path":null}
JSON
scheduler --project-root "$PWD" status
```

Use an explicit `--project-root` when operating from outside the project. Without it, the CLI searches the current directory and parents for `.scheduler/project.json`; it never falls back to a global task pool.

## Verified CLI surface

The global option is accepted before the command:

```text
scheduler [--project-root PATH] COMMAND
```

The verified command and argument contract is:

| Command | Arguments |
|---|---|
| `init` | `--fresh [--project-id ID]` |
| `status`, `ready`, `release-expired` | none |
| `next` | `--worker WORKER` |
| `describe` | `--task TASK_ID` |
| `claim`, `heartbeat`, `continue` | `--task TASK_ID --worker WORKER` |
| `block`, `fail` | `--task TASK_ID --worker WORKER --reason TEXT` |
| `complete` | `--task TASK_ID --worker WORKER [--summary TEXT]` |
| `retry`, `resume` | `--task TASK_ID --worker WORKER --reason TEXT --last-attempt-summary TEXT --next-attempt-instruction TEXT` |
| `publish` | exactly one of `--from-file FILE`, `--stdin`, or `--json JSON`; optional `--update` |
| `review-correct` | `--task TASK_ID --reviewer WORKER --verdict pass|hold --summary TEXT` |
| `migrate` | `[--check | --dry-run]` |

`init --fresh` intentionally replaces the canonical configuration and empty state for an isolated project. `publish` accepts exactly one JSON input source; `--from-file` remains compatible, while `--stdin` and `--json` avoid caller-owned temporary files. `--update` selects update mode. `migrate`
accepts at most one of `--check` and `--dry-run`. The lifecycle commands use
the task/worker names above and emit one JSON receipt on stdout.

Successful publish receipts have this shape:

```json
{"ok":true,"operation":"publish","changed_task_ids":["task-a"],"warnings":[],"project":{"project_id":"demo","root":"/abs/project"}}
```

Update uses `operation: "publish_update"`. Migration uses
`operation: "migrate"`, `changed_task_ids: []`, and places source/target
versions and change details under `migration`. A committed state with an
observation-log failure remains `ok: true` and carries an
`OBSERVATION_LOG_WARNING` in `warnings`. Failures use exit code 1 and the
stable `error.code`/`error.message` envelope.

## Publish

Save the strict envelope in a caller-owned file, then run:

```bash
scheduler --project-root "$PWD" publish --from-file publish.json
scheduler --project-root "$PWD" next
```

For pipe-safe input, use `scheduler --project-root "$PWD" publish --stdin` or pass one JSON string with `--json`. Do not pass more than one input source.

## Terminal review correction

`review-correct` is append-only and accepts only terminal tasks. It leaves the task status and original summary unchanged, records the reviewer verdict and summary under `review_decisions`, and links each correction to either the terminal summary or the prior review decision. It returns a machine-readable correction receipt; it never reopens a terminal task or rewrites history.

The envelope must contain `input_schema_version: 1`, matching `project_id`, an `operation` discriminator, and a non-empty `tasks` array. For `operation: "create"`, each task needs `task_id`, `agent_type`, `depends_on`, `conflict_domain`, `preferred_worker`, and object `worker_prompt`. For `operation: "update"`, each item is exactly `{ "task_id": "...", "patch": { ... } }`; `patch` is non-empty and limited to the mutable-field whitelist in the schema. Unknown fields, runtime fields (`status`, `created_at`, owner, lease, attempt), duplicate IDs, invalid dependencies, and project mismatch fail without a partial write.

For an existing `ready` or `blocked_waiting_dependency` task, use the explicit update mode and only the documented patch fields:

```bash
scheduler --project-root "$PWD" publish --update --from-file patch.json
```

The CLI mode and file discriminator must agree. Without `--update`, the file must contain `operation: "create"`; with `--update`, it must contain `operation: "update"`. Both mismatch directions fail with `PUBLISH_OPERATION_MISMATCH`, `ok: false`, and no state write. Keep the discriminator in the file even though the CLI flag selects the mode so saved inputs remain self-describing.

Updates cannot replace a task or change runtime/history fields. Claimed, running, or terminal tasks are not update targets. The CLI validates the full resulting dependency graph before writing.

## Legacy state migration

Parlant legacy state is adapted into strict canonical state in this order: parse bytes; identify supported legacy shape/version; validate project/path identity; map root and task fields; apply only documented defaults (`publish_history: []` when absent); validate dependencies and task invariants; validate against `state.schema.json`; then lock and atomically replace. Any failure leaves the original bytes unchanged. The migration receipt reports source format/version, target version, mapped counts, defaults, and warnings.

If state commits but optional JSONL observation logging fails, treat the result as successful:

```json
{"ok":true,"operation":"publish","warnings":[{"code":"OBSERVATION_LOG_WARNING","message":"state committed; observation log append failed","rebuild_from":"publish_history"}]}
```

`publish_history` is authoritative and can reconstruct the observation log.

## Verify routing and recover

`next` returns JSON. If no task is routable, inspect `blocked_candidates` and its dependency, conflict-domain, or worker-profile reason; do not infer readiness from an empty task alone. For failures, preserve the JSON error code and state bytes, correct the caller-owned input or project configuration, and retry. `LOCK_TIMEOUT` requires waiting or investigating another writer. `OBSERVATION_LOG_WARNING` means state is authoritative and history can reconstruct the optional log.

## Migration

Run `migrate --check` or `migrate --dry-run` before a real migration. A dry run is read-only. A real migration is lock-protected and atomic; verify the receipt's source version, target version, and change summary.

The schema-validation tests require the repository's declared `test`
dependency group. Run the complete suite with:

```bash
uv run --group test pytest -q
```

Do not rely on an ad-hoc `uv run --with jsonschema` override.

## Safety boundary

Do not use this Skill to modify Task Center UI/API, runtime/business logic, datasets, external systems, MCP integrations, network-filesystem locking, or historical publish scripts. Do not declare a gate pass; only the read-only research role may issue gate decisions.

## Acceptance

- Bootstrap exits successfully and emits a final JSON object with `ok: true`.
- `.scheduler/project.json` contains the intended unique project id.
- The project venv runs `scheduler status` with matching project context.
- Publish/lifecycle operations return stable JSON and do not cross project roots.
- Failures preserve state bytes unless the documented operation committed
  successfully and returned a warning.
