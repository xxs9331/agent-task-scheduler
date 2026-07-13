# v1 Error Codes

| Code | Meaning | Write guarantee |
|---|---|---|
| `PROJECT_NOT_FOUND` | No explicit or discovered project config | No write |
| `PROJECT_PATH_ESCAPE` | Configured path or symlink leaves project root | No write |
| `PROJECT_ID_MISMATCH` | Input/state project differs from resolved project | No write |
| `CONFIG_SCHEMA_UNSUPPORTED` | Config version is not supported | No write |
| `STATE_SCHEMA_UNSUPPORTED` | State version is unknown or higher | No write |
| `INPUT_SCHEMA_INVALID` | Envelope, type, reserved, or unknown field invalid | No write |
| `PUBLISH_OPERATION_INVALID` | Missing/unknown `operation`, or operation does not match item shape | No write |
| `PUBLISH_OPERATION_MISMATCH` | CLI mode and envelope operation disagree: no `--update` requires `create`; `--update` requires `update` | No write |
| `TASK_ID_DUPLICATE` | Duplicate within batch or existing state on create | No write |
| `DEPENDENCY_INVALID` | Missing, self, or cyclic dependency | No write |
| `TASK_UPDATE_FORBIDDEN` | Update targets an ineligible state or reserved field | No write |
| `LOCK_TIMEOUT` | State lock was not acquired before timeout | No write |
| `MIGRATION_INVALID` | Target migration cannot be fully validated | Original bytes unchanged |
| `OBSERVATION_LOG_WARNING` | State committed but optional JSONL append failed | `ok: true`; state remains authoritative |

Machine-readable failures contain `ok: false`, `error.code`, `error.message`, and `project` when resolution succeeded. CLI/envelope operation agreement is checked before task validation and lock acquisition. For example, `publish --update` with `operation: "create"`, or publish without `--update` with `operation: "update"`, returns `PUBLISH_OPERATION_MISMATCH` and changes no bytes. Batch validation is performed before opening the commit path. A successful publish with an observation-log failure contains `ok: true` and `warnings: [{"code":"OBSERVATION_LOG_WARNING","message":"state committed; observation log append failed","rebuild_from":"publish_history"}]`.
