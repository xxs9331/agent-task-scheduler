from __future__ import annotations

import json
import io
import zipfile
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_that_plugin_manifest_points_to_discoverable_skills() -> None:
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())

    assert manifest["name"] == "global-scheduler"
    assert manifest["version"] == "0.3.7"
    assert manifest["skills"] == "./skills/"
    assert (ROOT / manifest["skills"] / "codex-team" / "SKILL.md").is_file()
    assert manifest["interface"]["capabilities"] == ["Interactive", "Read", "Write"]
    assert manifest["repository"] == "https://github.com/xxs9331/agent-task-scheduler"


def test_that_marketplace_catalog_resolves_the_root_plugin() -> None:
    catalog = json.loads(
        (ROOT / ".agents" / "plugins" / "marketplace.json").read_text()
    )

    assert catalog["name"] == "xxs9331-scheduler"
    plugin = catalog["plugins"][0]
    assert plugin["name"] == "global-scheduler"
    assert plugin["source"] == {"source": "local", "path": "."}
    assert (ROOT / plugin["source"]["path"] / ".codex-plugin" / "plugin.json").is_file()


def test_that_skill_frontmatter_declares_name_and_trigger_description() -> None:
    skill = (ROOT / "skills" / "codex-team" / "SKILL.md").read_text()

    assert skill.startswith("---\n")
    assert 'name: "codex-team"' in skill
    assert "codex team" in skill.lower()


def test_that_skill_preserves_the_full_generic_staff_execution_contract() -> None:
    skill = (ROOT / "skills" / "codex-team" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    for mapping in (
        "role-P -> `.codex/agents/product_manager.toml` -> `name=product_manager`",
        "role-R -> `.codex/agents/researcher.toml` -> `name=researcher`",
        "role-A -> `.codex/agents/window_a.toml` -> `name=window_a`",
        "role-B -> `.codex/agents/window_b.toml` -> `name=window_b`",
        "role-C -> `.codex/agents/window_c.toml` -> `name=window_c`",
        "role-D -> `.codex/agents/window_d.toml` -> `name=window_d`",
        "Identity attestation is assembled by the parent, not self-reported by the child",
        "`task_id` is scheduler correlation supplied by the parent",
        "missing child self-report is not a failure",
        "claim --task <task_id> --worker role-r",
        "role-R may claim only read-only research, review, or gate tasks",
        "Role-R must not implement or publish tasks",
        "does not claim ordinary tasks",
        "metadata.team_mode.kind=pm_fallback",
        "claim --task <task_id> --worker role-p",
        "If the same task's native child is still open, continue it with `send_input`",
        "spawn a fresh exact-role child with `fork_turns=none` and do not import prior chat history",
    ):
        assert mapping in skill


def test_that_plugin_policy_and_progressive_references_exist() -> None:
    for path in (
        "LICENSE",
        "CHANGELOG.md",
        "SECURITY.md",
        "PRIVACY.md",
        "skills/codex-team/references/contract.md",
        "skills/codex-team/references/errors.md",
        "skills/codex-team/references/bootstrap.md",
        "skills/codex-team/references/platform.md",
        "skills/codex-team/references/migration.md",
        "skills/codex-team/assets/任务计划书模板.md",
    ):
        assert (ROOT / path).is_file(), path


def test_that_wheel_configuration_includes_the_portable_skill_assets() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text()

    assert (
        '"skills/codex-team" = "agent_task_scheduler/codex_team/assets/codex-team"'
        in pyproject
    )


def test_that_skill_bundles_the_relative_user_command_installer() -> None:
    skill = ROOT / "skills" / "codex-team"

    assert (skill / "scripts" / "install_codex_team.py").is_file()
    assert (skill / "assets" / "agent_task_scheduler-0.3.7-py3-none-any.whl").is_file()


def test_that_launcher_wheel_contains_one_non_recursive_core_wheel() -> None:
    launcher = (
        ROOT
        / "skills"
        / "codex-team"
        / "assets"
        / "agent_task_scheduler-0.3.7-py3-none-any.whl"
    )
    nested_path = (
        "agent_task_scheduler/codex_team/assets/codex-team/assets/"
        "agent_task_scheduler-0.3.7-py3-none-any.whl"
    )
    with zipfile.ZipFile(launcher) as archive:
        nested_wheels = [name for name in archive.namelist() if name.endswith(".whl")]
        assert nested_wheels == [nested_path]
        skill = archive.read(
            "agent_task_scheduler/codex_team/assets/codex-team/SKILL.md"
        ).decode("utf-8")
        nested = archive.read(nested_path)
    assert "Parlant" not in skill
    assert "parlant" not in "\n".join(archive.namelist()).lower()
    with zipfile.ZipFile(io.BytesIO(nested)) as core:
        assert not any(name.endswith(".whl") for name in core.namelist())
        templates = [
            name
            for name in core.namelist()
            if "/team-config/.codex/agents/" in name and name.endswith(".toml")
        ]
        assert len(templates) == 6
        assert not any("parlant" in name.lower() or "issue12" in name.lower() for name in core.namelist())
        nested_skill = core.read(
            "agent_task_scheduler/codex_team/assets/codex-team/SKILL.md"
        ).decode("utf-8")
    assert "Parlant" not in nested_skill


def test_that_readmes_explain_the_skill_and_link_the_task_plan_template() -> None:
    for readme_name in ("README.md", "README_EN.md"):
        readme = (ROOT / readme_name).read_text()

        assert "codex-team" in readme
        assert "skills/codex-team/assets/任务计划书模板.md" in readme


def test_that_skill_eval_cases_include_positive_and_negative_triggers() -> None:
    cases = [
        json.loads(line)
        for line in (ROOT / "evals" / "global_scheduler_skill_cases.jsonl")
        .read_text()
        .splitlines()
        if line
    ]

    assert any(case["should_trigger"] for case in cases)
    assert any(not case["should_trigger"] for case in cases)
