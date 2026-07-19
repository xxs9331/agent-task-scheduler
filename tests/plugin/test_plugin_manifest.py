from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_that_plugin_manifest_points_to_discoverable_skills() -> None:
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())

    assert manifest["name"] == "global-scheduler"
    assert manifest["version"] == "0.3.2"
    assert manifest["skills"] == "./skills/"
    assert (ROOT / manifest["skills"] / "global-scheduler" / "SKILL.md").is_file()
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
    skill = (ROOT / "skills" / "global-scheduler" / "SKILL.md").read_text()

    assert skill.startswith("---\n")
    assert 'name: "global-scheduler"' in skill
    assert 'description: "Use for project-scoped scheduler' in skill


def test_that_plugin_policy_and_progressive_references_exist() -> None:
    for path in (
        "LICENSE",
        "CHANGELOG.md",
        "SECURITY.md",
        "PRIVACY.md",
        "skills/global-scheduler/references/contract.md",
        "skills/global-scheduler/references/errors.md",
        "skills/global-scheduler/references/bootstrap.md",
        "skills/global-scheduler/references/platform.md",
        "skills/global-scheduler/references/migration.md",
        "skills/global-scheduler/assets/任务计划书模板.md",
    ):
        assert (ROOT / path).is_file(), path


def test_that_wheel_configuration_includes_the_portable_skill_assets() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text()

    assert (
        '"skills/global-scheduler" = "agent_task_scheduler/codex_team/assets/global-scheduler"'
        in pyproject
    )


def test_that_skill_bundles_the_relative_user_command_installer() -> None:
    skill = ROOT / "skills" / "global-scheduler"

    assert (skill / "scripts" / "install_codex_team.py").is_file()
    assert (skill / "assets" / "agent_task_scheduler-0.3.2-py3-none-any.whl").is_file()


def test_that_readmes_explain_the_skill_and_link_the_task_plan_template() -> None:
    for readme_name in ("README.md", "README_EN.md"):
        readme = (ROOT / readme_name).read_text()

        assert "global-scheduler" in readme
        assert "skills/global-scheduler/assets/任务计划书模板.md" in readme


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
