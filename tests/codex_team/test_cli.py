"""Regression coverage for the portable codex-team command."""

from __future__ import annotations

import json
import os
from pathlib import Path

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
