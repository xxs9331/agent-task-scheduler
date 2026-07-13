# Security

Global Scheduler writes only within the validated managed-project root. It
rejects absolute or escaping configured paths and uses project-local state and
lock files. Network-filesystem lock consistency, MCP, Task Center, external
services, automatic package publication, and remote repository writes are out
of scope.

The bootstrap installer uses only its bundled wheel and invokes no network
download. It refuses to overwrite a different existing `.scheduler/project.json`.
Back up legacy state and run `migrate --dry-run` before migration. Never run a
real canonical migration against a state whose project-specific root metadata
is not represented by the canonical schema.

Report suspected vulnerabilities privately to the repository maintainers
before public disclosure. A public security contact can be added when the
repository is published.
