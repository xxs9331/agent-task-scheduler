"""Regression coverage for the portable codex-team command."""

from __future__ import annotations

import json
import os
import shutil
import hashlib
import subprocess
from pathlib import Path

import pytest

from agent_task_scheduler.codex_team.cli import main


def test_that_start_uses_the_current_project_without_a_parlant_fallback(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "project B"
    project.mkdir()
    _install_fake_codex(tmp_path, monkeypatch)
    monkeypatch.chdir(project)

    assert main(["init"]) == 0
    capsys.readouterr()
    assert main(["start"]) == 0

    receipt = json.loads(capsys.readouterr().out)
    arguments = (tmp_path / "codex-arguments.json").read_text(encoding="utf-8")
    assert receipt["ok"] is True
    assert receipt["project_root"] == str(project.resolve())
    assert "parlant" not in arguments.lower()
    assert json.loads(arguments)[:2] == ["-C", str(project.resolve())]
    assert "product_manager" in arguments
    assert "fork_turns=none" in arguments


def test_that_fresh_root_prompt_forbids_recursive_launcher_commands(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "fresh root"
    _install_fake_codex(tmp_path, monkeypatch)

    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    assert main(["start", str(project)]) == 0

    prompt = json.loads((tmp_path / "codex-arguments.json").read_text())[-1]
    assert "YOU ARE ALREADY THE FRESH TEAM ROOT" in prompt
    assert "do not call codex-team" in prompt
    assert "codex-team init/doctor/start" in prompt
    assert "codex resume" in prompt
    assert "nested Codex" in prompt
    assert "product_manager" in prompt
    assert "fork_turns=none" in prompt
    assert ".codex/TEAM_MODE_V2_PM_HANDOFF.md" in prompt
    assert "unified codex-team Skill" in prompt
    assert "global-scheduler Skill" not in prompt


def test_that_fresh_root_requires_parent_side_native_attestation_before_pm_handoff(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "parent attestation"
    _install_fake_codex(tmp_path, monkeypatch)
    assert main(["init", str(project)]) == 0
    capsys.readouterr()

    assert main(["start", str(project)]) == 0

    prompt = json.loads((tmp_path / "codex-arguments.json").read_text())[-1]
    for evidence in (
        "requested agent_type=product_manager",
        "spawn agent_id",
        "worker_id=product_manager",
        "gpt-5.6-sol",
        "reasoning_effort=high",
        "fork_context=false",
    ):
        assert evidence in prompt
    assert "send_input" in prompt
    assert "same product_manager thread" in prompt
    assert (
        "Do not ask the child to manufacture or self-report parent-only receipt"
        in prompt
    )
    assert "child cannot see its agent_id" in prompt
    assert "close the child and fail closed" in prompt


def test_that_a_bare_project_path_starts_the_resolved_project(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "bare path"
    _install_fake_codex(tmp_path, monkeypatch)

    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    assert main([str(project)]) == 0

    arguments = json.loads((tmp_path / "codex-arguments.json").read_text())
    assert arguments[:2] == ["-C", str(project.resolve())]


def test_that_start_bootstraps_an_uninitialized_project_before_invoking_codex(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "uninitialized"
    project.mkdir()
    _install_fake_codex(tmp_path, monkeypatch)

    assert main(["start", str(project)]) == 0

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["ok"] is True
    assert (tmp_path / "codex-arguments.json").exists()
    assert main(["doctor", str(project)]) == 0


def test_that_init_is_idempotent_and_upgrades_conflicting_common_configuration(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "safe project"

    assert main(["init", str(project)]) == 0
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    (project / ".codex" / "config.toml").write_text("model = 'other'\n")

    assert main(["init", str(project)]) == 0

    receipt = json.loads(capsys.readouterr().out)
    assert ".codex/config.toml" in receipt["updated"]
    assert "model = 'other'" not in (project / ".codex" / "config.toml").read_text(
        encoding="utf-8"
    )


def test_that_init_removes_extra_fields_from_the_common_configuration(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "equivalent"

    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    config = project / ".codex" / "config.toml"
    config.write_text(
        "# project note\n" + config.read_text() + "project_note = 'safe'\n"
    )

    assert main(["init", str(project)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert ".codex/config.toml" in receipt["updated"]
    assert "project_note" not in config.read_text(encoding="utf-8")
    assert main(["doctor", str(project)]) == 0


def test_that_init_upgrades_existing_agent_toml_to_the_common_latest_template(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "existing team"
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    manager = project / ".codex" / "agents" / "product_manager.toml"
    content = manager.read_text(encoding="utf-8")
    content = content.replace(
        'description = "Rescue coordinator, plan owner, and authorized scheduler publisher."',
        'description = "Project-specific plan owner."',
    )
    content = content.replace(
        "Own plan interpretation, priorities, dependencies, conflict domains, capacity exceptions, gate routing, and authorized task publication.",
        "Preserve stricter project-specific publication and fallback boundaries.",
    )
    manager.write_text(content, encoding="utf-8")

    assert main(["doctor", str(project)]) == 2
    capsys.readouterr()

    assert main(["init", str(project)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert ".codex/agents/product_manager.toml" in receipt["updated"]
    assert manager.read_text(encoding="utf-8") != content
    assert main(["doctor", str(project)]) == 0


def test_that_init_installs_the_canonical_full_role_contracts_and_reconciler(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "canonical team"

    assert main(["init", str(project)]) == 0
    capsys.readouterr()

    canonical = (
        Path(__file__).parents[2]
        / "src"
        / "agent_task_scheduler"
        / "codex_team"
        / "assets"
        / "team-config"
        / ".codex"
        / "agents"
    )
    installed = project / ".codex" / "agents"
    for template in canonical.glob("*.toml"):
        assert (installed / template.name).read_text(encoding="utf-8") == template.read_text(
            encoding="utf-8"
        )

    manager = (installed / "product_manager.toml").read_text(encoding="utf-8")
    researcher = (installed / "researcher.toml").read_text(encoding="utf-8")
    executor = (installed / "window_a.toml").read_text(encoding="utf-8")
    assert "fallback_authorization" in manager
    assert "original_task_id" in manager
    assert "Read-only by default" in researcher
    assert "Do not implement, edit code/data" in researcher
    assert "Continue unfinished work in the same scope under the same task id" in executor
    assert "Never publish, create, assign, route, resume, retry" in executor

    skill = project / ".agents" / "skills" / "codex-team"
    assert (skill / "scripts" / "reconcile_handoff.py").is_file()
    skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert "Direct boss prompts authorize bounded execution but are not scheduler tasks" in skill_text
    assert "reconcile_handoff.py" in skill_text


def test_that_init_transactionally_upgrades_a_stock_036_skill_to_037(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "0.3.6 project"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.6")

    assert main(["init", str(project)]) == 0

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["upgraded_from"] == "0.3.6"
    assert receipt["upgraded_to"] == "0.3.7"
    assert not (skill.parent / "codex-team.backup").exists()
    assert main(["doctor", str(project)]) == 0


def test_that_doctor_rejects_existing_agent_toml_with_identity_mismatch(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "mismatched team"
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    manager = project / ".codex" / "agents" / "product_manager.toml"
    manager.write_text(
        manager.read_text(encoding="utf-8").replace(
            'model = "gpt-5.6-sol"', 'model = "gpt-5.6-terra"'
        ),
        encoding="utf-8",
    )

    assert main(["doctor", str(project)]) == 2
    receipt = json.loads(capsys.readouterr().out)
    assert ".codex/agents/product_manager.toml" in receipt["conflicts"]


def test_that_init_upgrades_a_complete_older_project_scheduler_skill(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "project managed skill"
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    skill = project / ".agents" / "skills" / "codex-team"
    shutil.rmtree(skill)
    shutil.copytree(Path(__file__).parent / "fixtures" / "0.3.1", skill)
    (skill / "scripts" / "install_codex_team.py").unlink()
    (skill / "references" / "parlant.md").write_text(
        "# Project scheduler overlay\n", encoding="utf-8"
    )

    assert main(["doctor", str(project)]) == 2
    capsys.readouterr()

    assert main(["init", str(project)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["upgraded_from"] == "0.3.1"
    assert main(["doctor", str(project)]) == 0
    assert json.loads(capsys.readouterr().out)["skill"]["current"] is True
    assert not (skill / "references" / "parlant.md").exists()


def test_that_bare_start_auto_upgrades_older_common_configuration(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "auto upgrade"
    _install_fake_codex(tmp_path, monkeypatch)
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    manager = project / ".codex" / "agents" / "product_manager.toml"
    manager.write_text(
        manager.read_text(encoding="utf-8").replace(
            'description = "Portable Codex team role-P."',
            'description = "Previous common template."',
        ),
        encoding="utf-8",
    )

    assert main(["start", str(project)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["ok"] is True
    assert "Previous common template." not in manager.read_text(encoding="utf-8")
    assert (tmp_path / "codex-arguments.json").is_file()


def test_that_doctor_rejects_an_incomplete_project_managed_scheduler_skill(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "incomplete project skill"
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    skill = project / ".agents" / "skills" / "codex-team"
    (skill / "scripts" / "install_codex_team.py").unlink()
    (skill / "references" / "parlant.md").write_text(
        "# Project scheduler overlay\n", encoding="utf-8"
    )
    (skill / "references" / "contract.md").unlink()

    assert main(["doctor", str(project)]) == 2
    receipt = json.loads(capsys.readouterr().out)
    assert ".agents/skills/codex-team/SKILL.md" in receipt["conflicts"]


def test_that_doctor_and_role_start_use_canonical_names_and_native_agent_mapping(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "team"
    _install_fake_codex(tmp_path, monkeypatch)

    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    assert main(["doctor", str(project)]) == 0
    doctor = json.loads(capsys.readouterr().out)
    assert doctor["roles"] == {
        "role-A": {"worker_id": "role-a", "agent": "window_a"},
        "role-B": {"worker_id": "role-b", "agent": "window_b"},
        "role-C": {"worker_id": "role-c", "agent": "window_c"},
        "role-D": {"worker_id": "role-d", "agent": "window_d"},
        "role-R": {"worker_id": "role-r", "agent": "researcher"},
    }
    assert main(["role-A", str(project)]) == 0

    arguments = json.loads((tmp_path / "codex-arguments.json").read_text())
    assert arguments[:2] == ["-C", str(project.resolve())]
    assert "native window_a" in arguments[-1]
    assert not any("resume" in argument for argument in arguments)


def test_that_agent_templates_preserve_the_verified_model_matrix(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "matrix"

    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    expected = {
        "product_manager": ("gpt-5.6-sol", "high"),
        "researcher": ("gpt-5.6-terra", "medium"),
        "window_a": ("gpt-5.6-terra", "medium"),
        "window_b": ("gpt-5.6-terra", "low"),
        "window_c": ("gpt-5.6-luna", "medium"),
        "window_d": ("gpt-5.6-luna", "medium"),
    }
    for agent, (model, effort) in expected.items():
        content = (project / ".codex" / "agents" / f"{agent}.toml").read_text()
        assert f'model = "{model}"' in content
        assert f'model_reasoning_effort = "{effort}"' in content


def test_that_init_installs_exactly_one_unified_team_mode_skill(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "one team skill"

    assert main(["init", str(project)]) == 0
    receipt = json.loads(capsys.readouterr().out)

    assert receipt["ok"] is True
    skills = project / ".agents" / "skills"
    assert (skills / "codex-team" / "SKILL.md").is_file()
    for legacy in (
        "global-scheduler",
        "codex-team-staff",
    ):
        assert not (skills / legacy).exists()


def test_that_init_merges_and_removes_legacy_scheduler_and_staff_skills(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "merged legacy skills"
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    skills = project / ".agents" / "skills"
    (skills / "codex-team").rename(skills / "global-scheduler")
    for legacy in ("codex-team-staff",):
        root = skills / legacy
        root.mkdir()
        (root / "SKILL.md").write_text(f"legacy {legacy}\n", encoding="utf-8")

    assert main(["init", str(project)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["removed_legacy_skills"] == [
        ".agents/skills/codex-team-staff",
        ".agents/skills/global-scheduler",
    ]
    assert (skills / "codex-team" / "SKILL.md").is_file()
    assert main(["doctor", str(project)]) == 0


def test_that_failed_merge_restores_all_legacy_team_mode_skills(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "legacy merge rollback"
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    skills = project / ".agents" / "skills"
    (skills / "codex-team").rename(skills / "global-scheduler")
    for legacy in ("codex-team-staff",):
        root = skills / legacy
        root.mkdir()
        (root / "SKILL.md").write_text(f"legacy {legacy}\n", encoding="utf-8")
    before = {
        name: _tree_digest(skills / name) for name in _LEGACY_SKILL_NAMES_FOR_TEST
    }
    monkeypatch.setattr(
        "agent_task_scheduler.codex_team.cli.subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, args)
        ),
    )

    assert main(["init", str(project)]) == 2
    assert json.loads(capsys.readouterr().out)["migration"]["rolled_back"] is True
    assert not (skills / "codex-team").exists()
    assert {
        name: _tree_digest(skills / name) for name in _LEGACY_SKILL_NAMES_FOR_TEST
    } == before


_LEGACY_SKILL_NAMES_FOR_TEST = (
    "codex-team-staff",
    "global-scheduler",
)


def test_that_init_replaces_an_existing_skill_with_an_unreadable_old_wheel(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "old skill"
    old_skill = project / ".agents" / "skills" / "codex-team"
    (old_skill / "assets").mkdir(parents=True)
    (old_skill / "SKILL.md").write_text("---\nname: old\n---\n")
    (old_skill / "assets" / "agent_task_scheduler-0.2.1-py3-none-any.whl").write_bytes(
        b"old"
    )

    assert main(["init", str(project)]) == 0

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["upgraded_from"] is None
    assert main(["doctor", str(project)]) == 0


@pytest.mark.parametrize(
    "legacy_version", ["0.3.1", "0.3.2", "0.3.3", "0.3.4", "0.3.5", "0.3.6"]
)
def test_that_init_migrates_a_stock_managed_legacy_skill_to_current(
    tmp_path: Path, capsys, legacy_version: str
) -> None:
    project = tmp_path / "legacy project"
    _initialize_with_legacy_skill(project, capsys, legacy_version)
    assert main(["init", str(project)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["upgraded_from"] == legacy_version
    assert receipt["upgraded_to"] == "0.3.7"
    assert main(["doctor", str(project)]) == 0
    assert json.loads(capsys.readouterr().out)["skill"]["current"] is True
    assert not (project / ".agents" / "skills" / "codex-team.backup").exists()


def test_that_doctor_fails_closed_when_a_supported_legacy_skill_lacks_its_installer(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "broken legacy project"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.1")
    (skill / "scripts" / "install.py").unlink()

    assert main(["doctor", str(project)]) == 2

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_NOT_INITIALIZED"
    assert ".agents/skills/codex-team/SKILL.md" in receipt["conflicts"]


def test_that_init_replaces_a_modified_managed_legacy_skill(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "modified legacy"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.1")
    (skill / "SKILL.md").write_text("modified", encoding="utf-8")
    assert main(["init", str(project)]) == 0
    assert json.loads(capsys.readouterr().out)["upgraded_to"] == "0.3.7"
    assert (skill / "SKILL.md").read_text(encoding="utf-8") != "modified"


def test_that_init_replaces_a_managed_legacy_skill_with_an_extra_file(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "extra legacy"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.2")
    (skill / "extra.txt").write_text("user", encoding="utf-8")
    assert main(["init", str(project)]) == 0
    assert not (skill / "extra.txt").exists()


@pytest.mark.parametrize(
    "legacy_version", ["0.3.1", "0.3.2", "0.3.3", "0.3.4", "0.3.5"]
)
def test_that_init_replaces_a_same_version_wheel_outside_official_variants(
    tmp_path: Path, capsys, legacy_version: str
) -> None:
    project = tmp_path / "unknown same version"
    skill = _initialize_with_legacy_skill(project, capsys, legacy_version)
    wheel = next((skill / "assets").glob("*.whl"))
    with wheel.open("ab") as stream:
        stream.write(b"untrusted-but-valid-zip-trailer")
    assert main(["init", str(project)]) == 0

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["upgraded_from"] == legacy_version
    assert main(["doctor", str(project)]) == 0
    assert not (skill.parent / "codex-team.backup").exists()


def test_that_doctor_fails_closed_when_the_current_managed_marker_is_tampered(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "tampered current"
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    marker = (
        project / ".agents" / "skills" / "codex-team" / "assets" / "managed-skill.json"
    )
    marker.write_text("{}", encoding="utf-8")
    assert main(["doctor", str(project)]) == 2
    assert json.loads(capsys.readouterr().out)["code"] == "CODEX_TEAM_NOT_INITIALIZED"


def test_that_init_ignores_transient_pycache_when_migrating_stock_legacy(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "transient legacy"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.1")
    cache = skill / "scripts" / "__pycache__"
    cache.mkdir()
    (cache / "install.cpython-312.pyc").write_bytes(b"transient")
    assert main(["init", str(project)]) == 0
    assert json.loads(capsys.readouterr().out)["upgraded_to"] == "0.3.7"


def test_that_init_rolls_back_a_partial_skill_copy_failure(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "copy rollback"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.1")
    original = _tree_digest(skill)
    manager = project / ".codex" / "agents" / "product_manager.toml"
    old_manager = manager.read_text(encoding="utf-8").replace(
        'description = "Portable Codex team role-P."',
        'description = "Previous common template."',
    )
    manager.write_text(old_manager, encoding="utf-8")
    real_copytree = shutil.copytree

    def partial_copy(source: Path, target: Path, *args, **kwargs) -> Path:
        target.mkdir(parents=True)
        (target / "partial").write_text("partial", encoding="utf-8")
        raise OSError("copy failed")

    monkeypatch.setattr(
        "agent_task_scheduler.codex_team.cli.shutil.copytree", partial_copy
    )
    assert main(["init", str(project)]) == 2
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_MIGRATION_FAILED"
    assert _tree_digest(skill) == original
    assert manager.read_text(encoding="utf-8") == old_manager
    assert not (skill.parent / "codex-team.backup").exists()
    monkeypatch.setattr(
        "agent_task_scheduler.codex_team.cli.shutil.copytree", real_copytree
    )


def test_that_start_does_not_invoke_codex_when_auto_upgrade_rolls_back(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "failed auto upgrade"
    _install_fake_codex(tmp_path, monkeypatch)
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.1")
    (project / ".codex" / "config.toml").write_text("model = 'old'\n")

    def fail_copy(*args, **kwargs) -> Path:
        raise OSError("copy failed")

    monkeypatch.setattr(
        "agent_task_scheduler.codex_team.cli.shutil.copytree", fail_copy
    )
    assert main(["start", str(project)]) == 2
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_MIGRATION_FAILED"
    assert not (tmp_path / "codex-arguments.json").exists()
    assert (skill / "SKILL.md").is_file()


def test_that_init_preserves_existing_scheduler_state_when_project_config_is_missing(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "scheduler state without config"
    state = project / ".scheduler" / "state.json"
    state.parent.mkdir(parents=True)
    original = b'{"important":"existing-state"}\n'
    state.write_bytes(original)

    assert main(["init", str(project)]) == 2
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_CONFLICT"
    assert state.read_bytes() == original
    assert not (project / ".scheduler" / "project.json").exists()
    assert not (project / ".codex").exists()


def test_that_doctor_and_start_reject_a_corrupt_scheduler_config_without_launching(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "corrupt scheduler config"
    _install_fake_codex(tmp_path, monkeypatch)
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    config = project / ".scheduler" / "project.json"
    state = project / ".scheduler" / "state.json"
    state.write_bytes(b'{"important":"preserve"}\n')
    config.write_bytes(b"{not-json\n")
    original_state = state.read_bytes()
    original_config = config.read_bytes()

    assert main(["doctor", str(project)]) == 2
    capsys.readouterr()
    assert main(["start", str(project)]) == 2
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_CONFLICT"
    assert state.read_bytes() == original_state
    assert config.read_bytes() == original_config
    assert not (tmp_path / "codex-arguments.json").exists()


def test_that_fresh_init_removes_all_managed_surfaces_when_installer_fails(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "fresh rollback"
    monkeypatch.setattr(
        "agent_task_scheduler.codex_team.cli.subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, args)
        ),
    )

    assert main(["init", str(project)]) == 2
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["migration"]["rolled_back"] is True
    for relative in (".codex", ".agents", ".scheduler", ".venv"):
        assert not (project / relative).exists()


def test_that_init_restores_earlier_common_files_when_a_later_write_fails(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "write rollback"
    real_write_text = Path.write_text

    def fail_on_manager(path: Path, content: str, *args, **kwargs) -> int:
        if path.name == "product_manager.toml":
            raise OSError("injected write failure")
        return real_write_text(path, content, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_on_manager)
    assert main(["init", str(project)]) == 2
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_MIGRATION_FAILED"
    assert not (project / ".codex" / "config.toml").exists()
    assert not (project / ".agents").exists()


def test_that_init_rolls_back_when_current_installer_fails(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "installer rollback"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.4")
    original = _tree_digest(skill)
    monkeypatch.setattr(
        "agent_task_scheduler.codex_team.cli.subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, args)
        ),
    )
    assert main(["init", str(project)]) == 2
    assert json.loads(capsys.readouterr().out)["code"] == "CODEX_TEAM_MIGRATION_FAILED"
    assert _tree_digest(skill) == original
    assert not (skill.parent / "codex-team.backup").exists()


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_that_doctor_fails_closed_for_an_unknown_future_skill_wheel(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "unknown project"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.1")
    wheel = next((skill / "assets").glob("*.whl"))
    wheel.rename(skill / "assets" / "agent_task_scheduler-0.3.7-py3-none-any.whl")

    assert main(["doctor", str(project)]) == 2

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_NOT_INITIALIZED"
    assert ".agents/skills/codex-team/SKILL.md" in receipt["conflicts"]


def test_that_doctor_rejects_a_renamed_wheel_with_mismatched_metadata(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "renamed wheel project"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.1")
    wheel = next((skill / "assets").glob("*.whl"))
    shutil.copyfile(
        Path(__file__).parents[2]
        / "skills"
        / "codex-team"
        / "assets"
        / "agent_task_scheduler-0.3.7-py3-none-any.whl",
        wheel,
    )

    assert main(["doctor", str(project)]) == 2

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_NOT_INITIALIZED"
    assert ".agents/skills/codex-team/SKILL.md" in receipt["conflicts"]


def _initialize_with_legacy_skill(project: Path, capsys, version: str) -> Path:
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    skill = project / ".agents" / "skills" / "codex-team"
    shutil.rmtree(skill)
    fixture = Path(__file__).parent / "fixtures" / version
    shutil.copytree(fixture, skill)
    return skill


def _install_fake_codex(root: Path, monkeypatch) -> None:
    executable = root / "codex"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['CODEX_TEAM_ARGUMENTS']).write_text(json.dumps(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("CODEX_TEAM_ARGUMENTS", str(root / "codex-arguments.json"))
    monkeypatch.setenv("PATH", f"{root}{os.pathsep}{os.environ.get('PATH', '')}")
