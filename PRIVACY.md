# Privacy

Global Scheduler has no telemetry, analytics, remote API calls, or external
data transmission. Project configuration, task state, locks, publish history,
and optional observation logs remain on the local filesystem under the managed
project root.

The plugin does not inspect unrelated project files. Task prompts and state may
contain sensitive project information; operators are responsible for filesystem
permissions, backups, and deciding whether to commit or share those files.
