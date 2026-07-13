# D Contract checkpoint

- task_id: `task_global_scheduler_contract_skill_d`
- worker: `window_d`
- status: `waiting_for_publish_integration`
- contract_gate: R-owned gate is `pass` in `tmp/global_scheduler_contract_v1/REPORT.md`

## Artifacts

- `docs/global-scheduler-v1-contract.md`
- `docs/global-scheduler-v1-dependency-migration.md`
- `docs/global-scheduler-v1-errors.md`
- `docs/global-scheduler-v1-platform.md`
- `schemas/config.schema.json`
- `schemas/state.schema.json`
- `schemas/publish-input.schema.json`
- `schemas/legacy-state-map.schema.json`
- `schemas/receipt.schema.json`
- `skills/global-scheduler/README.md`

## Verification

- Parsed all five JSON schemas with the project Python runtime.
- Validated create and update envelopes with `jsonschema.Draft202012Validator`.
- Confirmed a reserved runtime field in an update patch is rejected.
- Confirmed the Skill documents CLI/envelope operation agreement, atomic batch validation,
  migration ordering, history authority, and observation-log warning semantics.
- Confirmed D stayed within `docs/**`, `schemas/**`, `skills/**`, and this checkpoint.
- Confirmed the real CLI surface in `src/agent_task_scheduler/cli/main.py`: global
  `--project-root`; lifecycle commands; `publish --from-file [--update]`; and
  `migrate [--check|--dry-run]`.
- Confirmed receipt normalization: `publish`/`publish_update` expose
  `changed_task_ids` and `warnings`; `migrate` exposes `migration`; failures
  expose stable `error.code` and `error.message` with exit code 1.
- Declared `jsonschema` and `pytest` in the `test` dependency group and changed
  the verification command to `uv run --group test pytest -q`.
- Updated `uv.lock` and verified it with `uv lock --check`.
- Verified installed CLI help for the complete command list, `publish
  --from-file FILE [--update]`, and `migrate [--check|--dry-run]`.
- Ran `UV_CACHE_DIR=/tmp/agent-task-scheduler-uv-cache uv run --group test
  pytest -q`: `42 passed`.

## Caveats

- D does not declare or modify a gate decision; R owns `next_decision.json` and gate status.
- R's integration report records the real CLI smoke checks and 42-test pass; D has
  updated the Skill to reflect that verified surface.
- The live scheduler task remains `running` under `window_d`; continue the same task after
  integration evidence and heartbeat before final completion.
