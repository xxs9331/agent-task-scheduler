#!/usr/bin/env python3
"""Install the bundled ``codex-team`` wheel into an isolated user prefix.

This script is intentionally self-contained: a Codex Skill can invoke it using
its own relative path after plugin installation, without learning the plugin
cache location.  It never edits PATH or a shell profile.
"""

from __future__ import annotations

import argparse
import json
import os
import site
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from typing import Sequence


_MARKER = "codex-team managed launcher"
_PACKAGE = "agent-task-scheduler"


def bundled_wheel(skill_root: Path) -> Path:
    """Return the single wheel shipped alongside this Skill."""
    wheels = sorted((skill_root / "assets").glob("agent_task_scheduler-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected exactly one bundled wheel, found {len(wheels)}")
    return wheels[0]


def default_user_prefix() -> Path:
    """Return the standard Python user base only when installation is requested."""
    return Path(site.getuserbase()).resolve()


def user_bin(prefix: Path, *, windows: bool | None = None) -> Path:
    """Return the standard executable directory for a managed user prefix."""
    use_windows = sys.platform == "win32" if windows is None else windows
    return prefix / ("Scripts" if use_windows else "bin")


def command_path(prefix: Path, *, windows: bool | None = None) -> Path:
    """Return the path of the portable command launcher."""
    use_windows = sys.platform == "win32" if windows is None else windows
    name = "codex-team.cmd" if use_windows else "codex-team"
    return user_bin(prefix, windows=use_windows) / name


def managed_environment(prefix: Path) -> Path:
    """Return the private virtual environment location under ``prefix``."""
    return prefix / ".codex-team" / "venv"


def environment_python(environment: Path, *, windows: bool | None = None) -> Path:
    """Return the interpreter path for a private virtual environment."""
    use_windows = sys.platform == "win32" if windows is None else windows
    return environment / ("Scripts/python.exe" if use_windows else "bin/python")


def is_managed_launcher(command: Path) -> bool:
    """Whether an existing launcher is safe for this installer to replace."""
    if not command.exists():
        return True
    if not command.is_file():
        return False
    return _MARKER in command.read_text(encoding="utf-8", errors="replace")


def install(prefix: Path, skill_root: Path) -> dict[str, object]:
    """Create or update a private wheel environment and its safe user launcher."""
    prefix = prefix.expanduser().resolve()
    command = command_path(prefix)
    if not is_managed_launcher(command):
        return _failure(
            "CODEX_TEAM_INSTALL_CONFLICT",
            f"refusing to overwrite unmanaged command: {command}",
        )
    wheel = bundled_wheel(skill_root)
    environment = managed_environment(prefix)
    python = environment_python(environment)
    operation = "upgraded" if environment.exists() else "installed"
    if not python.is_file():
        _run([sys.executable, "-m", "venv", str(environment)])
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--force-reinstall",
            str(wheel),
        ]
    )
    command.parent.mkdir(parents=True, exist_ok=True)
    _write_launcher(command, python)
    metadata = {
        "package": _PACKAGE,
        "wheel": wheel.name,
        "wheel_sha256": sha256(wheel.read_bytes()).hexdigest(),
        "command": str(command),
    }
    metadata_path = prefix / ".codex-team" / "install.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    receipt: dict[str, object] = {
        "ok": True,
        "operation": operation,
        "command": str(command),
        "bin_dir": str(command.parent),
        "wheel": wheel.name,
        "wheel_sha256": metadata["wheel_sha256"],
    }
    receipt["path"] = (
        "available" if _path_contains(command.parent) else "add_bin_dir_to_PATH"
    )
    receipt["shadow_check"] = "type -a codex-team"
    receipt["shadow_guidance"] = (
        "If this reports a shell function or alias before the managed launcher, "
        "unset the current definition and remove its legacy shell-profile block manually; "
        "this installer never edits shell profiles."
    )
    if receipt["path"] != "available":
        receipt["path_hint"] = _path_hint(command.parent)
    return receipt


def _run(command: Sequence[str]) -> None:
    """Run an offline installation step and preserve failures for the caller."""
    subprocess.run(list(command), check=True, stdout=subprocess.DEVNULL)


def _write_launcher(command: Path, python: Path) -> None:
    """Write a platform-native launcher without touching user shell configuration."""
    if sys.platform == "win32":
        installed_command = python.parent / "codex-team.exe"
        content = f"@REM {_MARKER}\r\n@\"{installed_command}\" %*\r\n"
    else:
        installed_command = python.parent / "codex-team"
        content = f"#!/bin/sh\n# {_MARKER}\nexec \"{installed_command}\" \"$@\"\n"
    command.write_text(content, encoding="utf-8", newline="")
    if sys.platform != "win32":
        command.chmod(command.stat().st_mode | 0o111)


def _path_contains(directory: Path) -> bool:
    """Report whether PATH already contains the launcher directory."""
    return any(
        Path(item or ".").expanduser().resolve() == directory
        for item in os.environ.get("PATH", "").split(os.pathsep)
    )


def _path_hint(directory: Path) -> str:
    """Return a one-time, non-persistent PATH command for the current platform."""
    if sys.platform == "win32":
        return f'$env:PATH = "{directory};$env:PATH"'
    return f'export PATH="{directory}:$PATH"'


def _failure(code: str, message: str) -> dict[str, object]:
    """Build a machine-readable failure receipt."""
    return {"ok": False, "code": code, "message": message}


def main(argv: Sequence[str] | None = None) -> int:
    """Install the bundled command and emit exactly one JSON receipt."""
    parser = argparse.ArgumentParser(
        description="Install the bundled codex-team command into a user prefix."
    )
    parser.add_argument(
        "--prefix",
        type=Path,
        help="isolated user prefix; defaults to the current Python user base",
    )
    arguments = parser.parse_args(argv)
    try:
        receipt = install(
            prefix=arguments.prefix if arguments.prefix is not None else default_user_prefix(),
            skill_root=Path(__file__).resolve().parents[1],
        )
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        receipt = _failure("CODEX_TEAM_INSTALL_FAILED", str(error))
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
