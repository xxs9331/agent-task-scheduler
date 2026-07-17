# Bootstrap and project initialization

From a repository containing the installed Skill, bootstrap an isolated scheduler with:

```bash
python .agents/skills/global-scheduler/scripts/install.py --project-root "$PWD"
```

Use `--project-id ID` when the directory name is not the intended stable id. The installer creates or reuses `.venv`, installs the bundled wheel without network access, creates canonical project configuration, and runs `scheduler status`. It refuses to overwrite a different project configuration; never copy another project's state.

Before manual initialization, verify the installed CLI with `scheduler init --help`. `init --fresh` replaces canonical configuration with an empty isolated state, so use it only when explicitly requested. Restart or reopen agent windows after installation so they discover the project-local Skill.

Package 0.2.0 adds a fail-closed worker registry. After a fresh install or an
upgrade from 0.1.0, run `scheduler staff-sync --help`, prepare the project-owned
worker policy, and apply it once with `staff-sync --stdin` before any `next` or
`claim`. Existing tasks are preserved, but an unprovisioned worker is deliberately
reported as `unknown_worker`. The registry configures scheduler authority only;
it does not start agents and does not replace Codex native subagents or project
custom-agent TOML.
