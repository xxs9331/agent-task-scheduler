#!/usr/bin/env python3
"""Bootstrap agent-task-scheduler into one managed project."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence


def normalized_project_id(name: str) -> str:
    """Return a stable project id accepted by config.schema.json."""
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-.")
    if not normalized:
        raise ValueError("project id is empty after normalization")
    return normalized


def bundled_wheel(skill_root: Path) -> Path:
    """Resolve the one wheel bundled with this Skill."""
    wheels = sorted((skill_root / "assets").glob("agent_task_scheduler-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected exactly one bundled wheel, found {len(wheels)}")
    return wheels[0]


def venv_python(project_root: Path) -> Path:
    """Return the platform-specific Python path for the project venv."""
    windows = project_root / ".venv" / "Scripts" / "python.exe"
    posix = project_root / ".venv" / "bin" / "python"
    if windows.exists():
        return windows
    return posix


def scheduler_executable(project_root: Path) -> Path:
    """Return the platform-specific installed scheduler path."""
    windows = project_root / ".venv" / "Scripts" / "scheduler.exe"
    posix = project_root / ".venv" / "bin" / "scheduler"
    if windows.exists():
        return windows
    return posix


def write_project_config(project_root: Path, project_id: str) -> Path:
    """Create the canonical project config without overwriting another identity."""
    config_path = project_root / ".scheduler" / "project.json"
    expected = {
        "config_schema_version": 1,
        "project_id": project_id,
        "state_path": ".scheduler/state.json",
        "events_path": None,
    }
    if config_path.exists():
        existing = json.loads(config_path.read_text(encoding="utf-8"))
        if existing != expected:
            raise RuntimeError(
                f"refusing to overwrite existing scheduler config: {config_path}"
            )
        return config_path
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(expected, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return config_path


def run(command: Sequence[str]) -> None:
    """Run one bootstrap command and fail with its exit status."""
    subprocess.run(list(command), check=True)


def install(project_root: Path, project_id: str, skill_root: Path) -> None:
    """Install the bundled wheel, initialize config, and smoke-test discovery."""
    project_root = project_root.resolve()
    project_root.mkdir(parents=True, exist_ok=True)
    python = venv_python(project_root)
    if not python.exists():
        run([sys.executable, "-m", "venv", str(project_root / ".venv")])
        python = venv_python(project_root)
    wheel = bundled_wheel(skill_root)
    run([str(python), "-m", "pip", "install", "--no-deps", str(wheel)])
    config_path = write_project_config(project_root, project_id)
    scheduler = scheduler_executable(project_root)
    run([str(scheduler), "--project-root", str(project_root), "status"])
    print(
        json.dumps(
            {
                "ok": True,
                "project_id": project_id,
                "project_root": str(project_root),
                "config": str(config_path),
                "scheduler": str(scheduler),
                "wheel": wheel.name,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--project-id")
    args = parser.parse_args(argv)
    project_id = args.project_id or normalized_project_id(args.project_root.resolve().name)
    install(
        project_root=args.project_root,
        project_id=normalized_project_id(project_id),
        skill_root=Path(__file__).resolve().parents[1],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
