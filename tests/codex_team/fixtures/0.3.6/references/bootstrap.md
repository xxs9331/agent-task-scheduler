# Bootstrap and project initialization

## First install: user command

Installing a Codex plugin does not run a supported post-install hook. After the
plugin is installed and Codex is restarted, ask the `codex-team` Skill to
install `codex-team`. The Skill runs its relative installer:

```bash
python scripts/install_codex_team.py
```

It creates an isolated environment under the standard Python user base and a
launcher in its standard executable directory (`bin` on POSIX, `Scripts` on
Windows). It does not edit PATH, `.bashrc`, or PowerShell profiles. Read its JSON
receipt; if `path` is `add_bin_dir_to_PATH`, apply the returned one-time hint in
the current shell before using `codex-team`. Use `--prefix` only for a controlled
or test installation. Existing unmanaged launchers are conflicts and are never
overwritten.

From a repository containing the installed Skill, bootstrap an isolated scheduler with:

```bash
python .agents/skills/codex-team/scripts/install.py --project-root "$PWD"
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

From 0.2.1 onward, every newly published create task must include a non-empty
`metadata.team_mode.kind`. Tasks already present before upgrade may remain
unclassified for compatibility and should be reported by project audit tooling;
do not republish new work without classification.

## Portable Codex team

The same wheel also exposes `codex-team`. From the target project, run
`codex-team init`, then `codex-team doctor`, and finally `codex-team start`.
Each command defaults to the current directory and accepts an explicit project
path. Initialization is idempotent only for files produced by the same template;
it lists and rejects conflicts instead of overwriting existing configuration.
Doctor validates static project-local configuration only. It does not attest a
native runtime identity. Start invokes `codex -C <target-project>` only after
doctor passes and requests a fresh `product_manager` with `fork_turns=none`.
