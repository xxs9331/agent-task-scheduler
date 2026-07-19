# Dependency, history, and migration rules

## Dependency graph

The graph is built from the union of existing state and the proposed batch/update result; input order has no meaning. Every dependency must resolve to an existing or same-batch task. Self-dependencies and cycles return `DEPENDENCY_INVALID`. Initial status is `ready` only when all dependencies are terminal-success/absent according to the lifecycle policy; otherwise it is `blocked_waiting_dependency`. Updates re-run the complete graph validation.

## History event

Create emits one `published` entry per task. Update emits one `publish_updated` entry per task. `event_id` is unique within the project history; `change_summary` contains operation and changed field names, never an unbounded copy of input. History is retained and export is explicit.

## Migration

`migrate --check` and `migrate --dry-run` parse, validate, and report `{source_schema_version, target_schema_version, changes}` without writing. Real migration acquires the derived state lock, constructs a complete target document in memory, validates it, writes a temporary sibling file, fsyncs as supported, and atomically replaces the state. Any validation or replacement failure preserves the original file bytes. Unknown intermediate versions cannot be skipped.

## Parlant legacy adapter

The legacy Parlant state is an input fixture, never the canonical state schema. The adapter maps the legacy root `schema_version` to canonical `schema_version`, copies the legacy `tasks` mapping by task id, preserves `task_order` when present, and initializes missing canonical `publish_history` to `[]`. Task fields are mapped by name (`task_id`, `status`, `agent_type`, `depends_on`, `conflict_domain`, `preferred_worker`, `worker_prompt`, `created_at`); recognized lifecycle fields such as owner, lease, attempt, and terminal records are copied into their canonical counterparts. Legacy-only root metadata is retained only in the migration change summary, not in strict canonical state.

Validation order is fixed: (1) read bytes and parse JSON; (2) identify and accept only a known legacy source shape/version; (3) validate project identity and reject path/symlink escapes; (4) map fields and fill only documented defaults; (5) validate the complete dependency graph and task invariants; (6) validate the resulting document against `state.schema.json`; (7) under the state lock, atomically replace only after all checks pass. Any failure before replacement leaves the legacy file byte-for-byte unchanged. The receipt includes `source_format: "parlant_legacy"`, source/target versions, mapped field counts, defaults applied, and warnings.
