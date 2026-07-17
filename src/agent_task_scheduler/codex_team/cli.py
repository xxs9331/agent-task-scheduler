"""Portable, project-local ``codex-team`` command."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

from agent_task_scheduler.cli.main import main as scheduler_main


_ROLES = {
    "role-A": ("role-a", "window_a"),
    "role-B": ("role-b", "window_b"),
    "role-C": ("role-c", "window_c"),
    "role-D": ("role-d", "window_d"),
    "role-R": ("role-r", "researcher"),
}
_AGENTS = {"product_manager", *[agent for _, agent in _ROLES.values()]}
_MODELS = {
    "product_manager": ("gpt-5.6-sol", "high"),
    "researcher": ("gpt-5.6-terra", "medium"),
    "window_a": ("gpt-5.6-terra", "medium"),
    "window_b": ("gpt-5.6-terra", "low"),
    "window_c": ("gpt-5.6-luna", "medium"),
    "window_d": ("gpt-5.6-luna", "medium"),
}


def main(argv: Sequence[str] | None = None) -> int:
    raw_arguments = list(argv) if argv is not None else sys.argv[1:]
    if (
        raw_arguments
        and raw_arguments[0] not in _commands()
        and not raw_arguments[0].startswith("-")
    ):
        raw_arguments.insert(0, "start")
    args = _parser().parse_args(raw_arguments)
    root = _resolve_root(args.project_root)
    if args.command == "init":
        receipt = _init(root)
        return _emit(receipt, exit_code=0 if receipt["ok"] else 2)
    diagnosis = _doctor(root)
    if not diagnosis["ok"]:
        return _emit(diagnosis, exit_code=2)
    if args.command == "doctor":
        return _emit(diagnosis)
    return _start(root, role=args.command if args.command in _ROLES else None)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex-team")
    parser.add_argument(
        "command",
        nargs="?",
        default="start",
        choices=_commands(),
    )
    parser.add_argument("project_root", nargs="?", type=Path)
    return parser


def _commands() -> tuple[str, ...]:
    return ("init", "doctor", "start", *_ROLES)


def _resolve_root(project_root: Path | None) -> Path:
    return (project_root or Path.cwd()).resolve()


def _init(root: Path) -> dict[str, object]:
    expected = _expected_files()
    conflicts = [
        relative
        for relative, content in expected.items()
        if not _compatible(root / relative, content)
    ]
    skill_target = root / ".agents" / "skills" / "global-scheduler"
    if skill_target.exists() and not _skill_is_current(skill_target):
        conflicts.append(str(skill_target.relative_to(root)))
    if (root / ".scheduler").exists() and not (
        root / ".scheduler" / "project.json"
    ).is_file():
        conflicts.append(".scheduler")
    if conflicts:
        return _failure(
            "CODEX_TEAM_CONFLICT",
            "refusing to overwrite existing project files",
            conflicts,
        )
    root.mkdir(parents=True, exist_ok=True)
    for relative, content in expected.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content, encoding="utf-8")
    if not skill_target.exists():
        shutil.copytree(_skill_source(), skill_target)
    if not (root / ".scheduler" / "project.json").is_file():
        with contextlib.redirect_stdout(io.StringIO()):
            scheduler_main(
                [
                    "--project-root",
                    str(root),
                    "init",
                    "--fresh",
                    "--project-id",
                    root.name,
                ]
            )
    installer = skill_target / "scripts" / "install.py"
    subprocess.run(
        [sys.executable, str(installer), "--project-root", str(root)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return {
        "ok": True,
        "operation": "init",
        "project_root": str(root),
        "created": sorted(expected),
    }


def _doctor(root: Path) -> dict[str, object]:
    missing = [
        relative
        for relative, content in _expected_files().items()
        if not _compatible(root / relative, content)
    ]
    if not (root / ".scheduler" / "project.json").is_file():
        missing.append(".scheduler/project.json")
    if not _skill_is_current(root / ".agents" / "skills" / "global-scheduler"):
        missing.append(".agents/skills/global-scheduler/SKILL.md")
    if (
        not (root / ".venv" / "bin" / "scheduler").is_file()
        and not (root / ".venv" / "Scripts" / "scheduler.exe").is_file()
    ):
        missing.append(".venv scheduler")
    if missing:
        return _failure(
            "CODEX_TEAM_NOT_INITIALIZED",
            f"run codex-team init {root} before starting a team",
            missing,
        )
    return {
        "ok": True,
        "operation": "doctor",
        "project_root": str(root),
        "roles": {
            label: {"worker_id": worker, "agent": agent}
            for label, (worker, agent) in _ROLES.items()
        },
    }


def _start(root: Path, *, role: str | None) -> int:
    if role is None:
        prompt = (
            "Start a fresh project-scoped team root. Native-spawn product_manager with "
            "fork_turns=none. Read this project's handoff, CLAUDE.md, AGENTS.md, and "
            "global-scheduler Skill before dispatching. Create a new agent each time."
        )
        command = ["codex", "-C", str(root), prompt]
    else:
        worker, agent = _ROLES[role]
        prompt = (
            f"Start a fresh {role} session as native {agent}; worker_id={worker}; "
            "fork_turns=none. Read this project's handoff, CLAUDE.md, AGENTS.md, and "
            "global-scheduler Skill. Create a new agent each time."
        )
        command = ["codex", "-C", str(root), prompt]
    try:
        completed = subprocess.run(command, check=False)
    except OSError as error:
        return _emit(
            _failure("CODEX_TEAM_CODEX_UNAVAILABLE", str(error), []), exit_code=2
        )
    return _emit(
        {
            "ok": completed.returncode == 0,
            "operation": "start",
            "project_root": str(root),
            "returncode": completed.returncode,
        },
        exit_code=completed.returncode,
    )


def _expected_files() -> dict[str, str]:
    files = {
        ".codex/config.toml": 'model = "gpt-5.6-luna"\nmodel_reasoning_effort = "medium"\n\n[agents]\nmax_threads = 6\nmax_depth = 2\ninterrupt_message = true\n',
        ".codex/team-handoff.md": "# Codex Team Handoff\n\nThis project uses the portable project-local Codex team topology.\n",
        ".agents/skills/codex-team-staff/SKILL.md": '---\nname: "codex-team-staff"\ndescription: "Use for portable Codex team startup and role handoff."\n---\n\nUse only this project\'s files and scheduler state.\n',
    }
    for agent in sorted(_AGENTS):
        files[f".codex/agents/{agent}.toml"] = _agent_toml(agent)
    return files


def _skill_source() -> Path:
    packaged = Path(__file__).parent / "assets" / "global-scheduler"
    if packaged.is_dir():
        return packaged
    return Path(__file__).parents[3] / "skills" / "global-scheduler"


def _skill_is_current(skill_root: Path) -> bool:
    return (skill_root / "SKILL.md").is_file() and (
        skill_root / "assets" / "agent_task_scheduler-0.3.1-py3-none-any.whl"
    ).is_file()


def _agent_toml(agent: str) -> str:
    role = next(
        (label for label, (_, name) in _ROLES.items() if name == agent), "role-P"
    )
    worker = next(
        (worker for worker, name in _ROLES.values() if name == agent), "product_manager"
    )
    model, effort = _MODELS[agent]
    return (
        f'name = "{agent}"\n'
        f'description = "Portable Codex team {role}."\n'
        f'nickname_candidates = ["{role}"]\n'
        f'model = "{model}"\n'
        f'model_reasoning_effort = "{effort}"\n\n'
        'developer_instructions = """\n'
        f"You are {role} for the current project. worker_id={worker}.\n"
        "Read this project handoff, CLAUDE.md, AGENTS.md, this TOML, and the global-scheduler Skill.\n"
        "Use only the current project. Prompt text is not runtime identity attestation.\n"
        f"{_responsibilities(agent)}\n"
        '"""\n'
    )


def _responsibilities(agent: str) -> str:
    if agent == "product_manager":
        return "Publish only authorized work; reconcile scheduler receipts; use send_input only for an open same-task child and never resume a closed child."
    if agent == "researcher":
        return "Remain read-only; review assigned gates and use complete for pass or block for needs-fix. Do not publish or implement."
    return "Claim only assigned executor work; perform RED, GREEN, verification, then complete --summary. Do not publish or manage another role."


def _compatible(path: Path, expected: str) -> bool:
    if not path.exists():
        return True
    if path.suffix != ".toml":
        return path.read_text(encoding="utf-8") == expected
    try:
        existing = tomllib.loads(path.read_text(encoding="utf-8"))
        required = tomllib.loads(expected)
    except tomllib.TOMLDecodeError:
        return False
    return _contains_required(existing, required)


def _contains_required(existing: object, required: object) -> bool:
    if isinstance(required, dict):
        return isinstance(existing, dict) and all(
            key in existing and _contains_required(existing[key], value)
            for key, value in required.items()
        )
    return existing == required


def _failure(code: str, message: str, paths: list[str]) -> dict[str, object]:
    return {"ok": False, "code": code, "message": message, "conflicts": paths}


def _emit(receipt: dict[str, object], *, exit_code: int = 0) -> int:
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return exit_code
