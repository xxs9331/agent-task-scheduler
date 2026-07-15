# Bootstrap and project initialization

From a repository containing the installed Skill, bootstrap an isolated scheduler with:

```bash
python .agents/skills/global-scheduler/scripts/install.py --project-root "$PWD"
```

Use `--project-id ID` when the directory name is not the intended stable id. The installer creates or reuses `.venv`, installs the bundled wheel without network access, creates canonical project configuration, and runs `scheduler status`. It refuses to overwrite a different project configuration; never copy another project's state.

Before manual initialization, verify the installed CLI with `scheduler init --help`. `init --fresh` replaces canonical configuration with an empty isolated state, so use it only when explicitly requested. Restart or reopen agent windows after installation so they discover the project-local Skill.
