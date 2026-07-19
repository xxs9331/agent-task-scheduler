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


def test_that_start_fails_closed_before_init_without_invoking_codex(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "uninitialized"
    project.mkdir()
    _install_fake_codex(tmp_path, monkeypatch)

    assert main(["start", str(project)]) == 2

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_NOT_INITIALIZED"
    assert "codex-team init" in receipt["message"]
    assert not (tmp_path / "codex-arguments.json").exists()


def test_that_init_is_idempotent_but_rejects_conflicting_configuration(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "safe project"

    assert main(["init", str(project)]) == 0
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    (project / ".codex" / "config.toml").write_text("model = 'other'\n")

    assert main(["init", str(project)]) == 2

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_CONFLICT"
    assert ".codex/config.toml" in receipt["conflicts"]


def test_that_init_accepts_semantically_equivalent_toml_with_safe_project_fields(
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
    assert main(["doctor", str(project)]) == 0


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


def test_that_init_rejects_an_existing_skill_with_an_old_bundled_wheel(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "old skill"
    old_skill = project / ".agents" / "skills" / "global-scheduler"
    (old_skill / "assets").mkdir(parents=True)
    (old_skill / "SKILL.md").write_text("---\nname: old\n---\n")
    (old_skill / "assets" / "agent_task_scheduler-0.2.1-py3-none-any.whl").write_bytes(
        b"old"
    )

    assert main(["init", str(project)]) == 2

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_CONFLICT"
    assert ".agents/skills/global-scheduler" in receipt["conflicts"]


@pytest.mark.parametrize("legacy_version", ["0.3.1", "0.3.2", "0.3.3"])
def test_that_init_migrates_a_stock_managed_legacy_skill_to_current(
    tmp_path: Path, capsys, legacy_version: str
) -> None:
    project = tmp_path / "legacy project"
    _initialize_with_legacy_skill(project, capsys, legacy_version)
    assert main(["init", str(project)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["upgraded_from"] == legacy_version
    assert receipt["upgraded_to"] == "0.3.4"
    assert main(["doctor", str(project)]) == 0
    assert json.loads(capsys.readouterr().out)["skill"]["current"] is True
    assert not (project / ".agents" / "skills" / "global-scheduler.backup").exists()


def test_that_doctor_fails_closed_when_a_supported_legacy_skill_lacks_its_installer(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "broken legacy project"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.1")
    (skill / "scripts" / "install.py").unlink()

    assert main(["doctor", str(project)]) == 2

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_NOT_INITIALIZED"
    assert ".agents/skills/global-scheduler/SKILL.md" in receipt["conflicts"]


def test_that_init_rejects_a_modified_managed_legacy_skill(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "modified legacy"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.1")
    (skill / "SKILL.md").write_text("modified", encoding="utf-8")
    assert main(["init", str(project)]) == 2
    assert json.loads(capsys.readouterr().out)["code"] == "CODEX_TEAM_CONFLICT"
    assert (skill / "SKILL.md").read_text(encoding="utf-8") == "modified"


def test_that_init_rejects_a_managed_legacy_skill_with_an_extra_file(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "extra legacy"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.2")
    (skill / "extra.txt").write_text("user", encoding="utf-8")
    assert main(["init", str(project)]) == 2
    assert (skill / "extra.txt").read_text(encoding="utf-8") == "user"


@pytest.mark.parametrize("legacy_version", ["0.3.1", "0.3.2", "0.3.3"])
def test_that_init_rejects_a_same_version_wheel_outside_official_variants(
    tmp_path: Path, capsys, legacy_version: str
) -> None:
    project = tmp_path / "unknown same version"
    skill = _initialize_with_legacy_skill(project, capsys, legacy_version)
    wheel = next((skill / "assets").glob("*.whl"))
    with wheel.open("ab") as stream:
        stream.write(b"untrusted-but-valid-zip-trailer")
    original = _tree_digest(skill)

    assert main(["init", str(project)]) == 2

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_CONFLICT"
    assert _tree_digest(skill) == original
    assert not (skill.parent / "global-scheduler.backup").exists()


def test_that_doctor_fails_closed_when_the_current_managed_marker_is_tampered(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "tampered current"
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    marker = (
        project
        / ".agents"
        / "skills"
        / "global-scheduler"
        / "assets"
        / "managed-skill.json"
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
    assert json.loads(capsys.readouterr().out)["upgraded_to"] == "0.3.4"


def test_that_init_rolls_back_a_partial_skill_copy_failure(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "copy rollback"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.1")
    original = _tree_digest(skill)
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
    assert not (skill.parent / "global-scheduler.backup").exists()
    monkeypatch.setattr(
        "agent_task_scheduler.codex_team.cli.shutil.copytree", real_copytree
    )


def test_that_init_rolls_back_when_current_installer_fails(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    project = tmp_path / "installer rollback"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.3")
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
    assert not (skill.parent / "global-scheduler.backup").exists()


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
    wheel.rename(skill / "assets" / "agent_task_scheduler-0.3.5-py3-none-any.whl")

    assert main(["doctor", str(project)]) == 2

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_NOT_INITIALIZED"
    assert ".agents/skills/global-scheduler/SKILL.md" in receipt["conflicts"]


def test_that_doctor_rejects_a_renamed_wheel_with_mismatched_metadata(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "renamed wheel project"
    skill = _initialize_with_legacy_skill(project, capsys, "0.3.1")
    wheel = next((skill / "assets").glob("*.whl"))
    shutil.copyfile(
        Path(__file__).parents[2]
        / "skills"
        / "global-scheduler"
        / "assets"
        / "agent_task_scheduler-0.3.4-py3-none-any.whl",
        wheel,
    )

    assert main(["doctor", str(project)]) == 2

    receipt = json.loads(capsys.readouterr().out)
    assert receipt["code"] == "CODEX_TEAM_NOT_INITIALIZED"
    assert ".agents/skills/global-scheduler/SKILL.md" in receipt["conflicts"]


def _initialize_with_legacy_skill(project: Path, capsys, version: str) -> Path:
    assert main(["init", str(project)]) == 0
    capsys.readouterr()
    skill = project / ".agents" / "skills" / "global-scheduler"
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
