from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_that_plugin_manifest_points_to_discoverable_skills() -> None:
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())

    assert manifest["name"] == "global-scheduler"
    assert manifest["version"] == "0.1.0"
    assert manifest["skills"] == "./skills/"
    assert (ROOT / manifest["skills"] / "global-scheduler" / "SKILL.md").is_file()
    assert manifest["interface"]["capabilities"] == ["Interactive", "Read", "Write"]


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
        "skills/global-scheduler/references/platform.md",
        "skills/global-scheduler/references/migration.md",
    ):
        assert (ROOT / path).is_file(), path


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
