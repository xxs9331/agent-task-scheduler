"""Regression coverage for the plugin-owned ``codex-team`` user installer."""

from __future__ import annotations

import json
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[2]
SKILL_SOURCE = ROOT / "skills" / "codex-team"


def test_that_user_launcher_paths_follow_the_supported_platform_conventions() -> None:
    installer = SKILL_SOURCE / "scripts" / "install_codex_team.py"
    specification = importlib.util.spec_from_file_location(
        "codex_team_installer", installer
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    prefix = Path("/temporary/prefix")

    assert module.command_path(prefix, windows=False) == prefix / "bin" / "codex-team"
    assert (
        module.command_path(prefix, windows=True)
        == prefix / "Scripts" / "codex-team.cmd"
    )


def test_that_clean_skill_copy_installs_portable_command_to_an_isolated_prefix(
    tmp_path: Path,
) -> None:
    skill_root = tmp_path / "clean plugin" / "skills" / "codex-team"
    shutil.copytree(SKILL_SOURCE, skill_root)
    prefix = tmp_path / "user prefix"
    home = tmp_path / "temporary home"
    target = tmp_path / "target project"
    fake_codex = tmp_path / "fake-bin" / "codex"
    fake_codex.parent.mkdir()
    fake_codex.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['CODEX_TEAM_ARGUMENTS']).write_text(json.dumps(sys.argv[1:]))\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)
    environment = {
        **os.environ,
        "HOME": str(home),
        "CODEX_TEAM_ARGUMENTS": str(tmp_path / "codex-arguments.json"),
        "PATH": f"{fake_codex.parent}{os.pathsep}{os.environ.get('PATH', '')}",
    }

    install = subprocess.run(
        [
            sys.executable,
            str(skill_root / "scripts" / "install_codex_team.py"),
            "--prefix",
            str(prefix),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert install.returncode == 0, install.stderr
    receipt = json.loads(install.stdout)
    command = prefix / "bin" / "codex-team"
    assert receipt["ok"] is True
    assert receipt["command"] == str(command)
    assert receipt["shadow_check"] == "type -a codex-team"
    assert "shell function or alias" in receipt["shadow_guidance"]
    assert command.is_file()
    assert os.access(command, os.X_OK)
    assert not (home / ".local").exists()

    for arguments in (
        ("init", str(target)),
        ("doctor", str(target)),
        ("role-A", str(target)),
    ):
        completed = subprocess.run(
            [str(command), *arguments],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout)["ok"] is True

    assert json.loads((tmp_path / "codex-arguments.json").read_text(encoding="utf-8"))[
        :2
    ] == [
        "-C",
        str(target.resolve()),
    ]


def test_that_installer_is_idempotent_but_refuses_to_overwrite_an_unmanaged_command(
    tmp_path: Path,
) -> None:
    prefix = tmp_path / "prefix"
    installer = ROOT / "skills" / "codex-team" / "scripts" / "install_codex_team.py"
    command = prefix / "bin" / "codex-team"

    first = subprocess.run(
        [sys.executable, str(installer), "--prefix", str(prefix)],
        check=False,
        capture_output=True,
        text=True,
    )
    second = subprocess.run(
        [sys.executable, str(installer), "--prefix", str(prefix)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert first.returncode == second.returncode == 0
    assert json.loads(second.stdout)["operation"] == "upgraded"
    shutil.rmtree(prefix / ".codex-team")
    command.write_text("user owned\n", encoding="utf-8")

    conflict = subprocess.run(
        [sys.executable, str(installer), "--prefix", str(prefix)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert conflict.returncode == 2
    assert json.loads(conflict.stdout)["code"] == "CODEX_TEAM_INSTALL_CONFLICT"
    assert command.read_text(encoding="utf-8") == "user owned\n"


def test_that_user_facing_bootstrap_docs_require_installer_and_shadow_diagnosis() -> (
    None
):
    for path in (
        ROOT / "README.md",
        ROOT / "README_EN.md",
        SKILL_SOURCE / "SKILL.md",
    ):
        content = path.read_text(encoding="utf-8")
        assert "install_codex_team.py" in content
        assert "type -a codex-team" in content
        assert "0.3.6" in content


def test_that_doctor_and_start_do_not_treat_static_features_as_native_attestation() -> (
    None
):
    content = (
        ROOT / "src" / "agent_task_scheduler" / "codex_team" / "cli.py"
    ).read_text(encoding="utf-8")

    assert (
        "Static multi_agent feature status is not native custom-agent attestation."
        in content
    )
    assert "Parent-side runtime evidence" in content
    assert "agent/thread id" in content
    assert "Child self-report of parent-only fields is not required." in content
