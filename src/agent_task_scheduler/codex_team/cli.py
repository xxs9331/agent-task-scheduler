"""Portable, project-local ``codex-team`` command."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
import zipfile
from collections.abc import Sequence
from pathlib import Path

_ROLES = {
    "role-A": ("role-a", "window_a"),
    "role-B": ("role-b", "window_b"),
    "role-C": ("role-c", "window_c"),
    "role-D": ("role-d", "window_d"),
    "role-R": ("role-r", "researcher"),
}
_CANONICAL_AGENT_FILES = frozenset(
    {
        "product_manager.toml",
        "researcher.toml",
        "window_a.toml",
        "window_b.toml",
        "window_c.toml",
        "window_d.toml",
    }
)
_BUNDLED_WHEEL_NAME = "agent_task_scheduler-0.3.8-py3-none-any.whl"
_SUPPORTED_LEGACY_WHEEL_NAMES = frozenset(
    {
        "agent_task_scheduler-0.3.1-py3-none-any.whl",
        "agent_task_scheduler-0.3.2-py3-none-any.whl",
        "agent_task_scheduler-0.3.3-py3-none-any.whl",
        "agent_task_scheduler-0.3.4-py3-none-any.whl",
        "agent_task_scheduler-0.3.5-py3-none-any.whl",
        "agent_task_scheduler-0.3.6-py3-none-any.whl",
        "agent_task_scheduler-0.3.7-py3-none-any.whl",
    }
)
_SUPPORTED_SKILL_WHEELS = {
    _BUNDLED_WHEEL_NAME: "0.3.8",
    **{wheel: wheel.split("-")[1] for wheel in _SUPPORTED_LEGACY_WHEEL_NAMES},
}
_REQUIRED_SKILL_FILES = (
    "SKILL.md",
    "scripts/install.py",
    "scripts/install_codex_team.py",
)
_SKILL_NAME = "codex-team"
_LEGACY_SKILL_NAMES = (
    "codex-team-staff",
    "global-scheduler",
)
_NATIVE_ATTESTATION_NOTE = (
    "Static multi_agent feature status is not native custom-agent attestation. "
    "Parent-side runtime evidence must include the requested agent type, spawn "
    "agent/thread id, effective model, and reasoning effort; missing parent evidence "
    "fails closed. Child self-report of parent-only fields is not required."
)
_PARENT_ATTESTATION_PROTOCOL = (
    "Native-spawn requested agent_type=product_manager with fork_context=false. "
    "The parent must capture the spawn receipt and verify its spawn agent_id, then "
    "verify the project TOML contract says worker_id=product_manager, model "
    "gpt-5.6-sol, and reasoning_effort=high. If the requested selector, spawn "
    "agent_id, fixed model/effort contract, or fork_context=false evidence is "
    "missing, close the child and fail closed. After verification, construct the "
    "attestation in the parent and use send_input to inject it into the same "
    "product_manager thread. Do not ask the child to manufacture or self-report "
    "parent-only receipt fields. A child cannot see its agent_id by itself; that "
    "alone is not an attestation failure."
)


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
        try:
            receipt = _init(root)
        except Exception as error:
            receipt = _failure("CODEX_TEAM_MIGRATION_FAILED", str(error), [])
        return _emit(receipt, exit_code=0 if receipt["ok"] else 2)
    diagnosis = _doctor(root)
    if not diagnosis["ok"] and args.command != "doctor":
        initialization = _init(root)
        if not initialization["ok"]:
            return _emit(initialization, exit_code=2)
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


def _scheduler_conflict(root: Path) -> dict[str, object] | None:
    scheduler_root = root / ".scheduler"
    if not scheduler_root.exists():
        return None
    config = scheduler_root / "project.json"
    if not config.is_file():
        return _failure(
            "CODEX_TEAM_CONFLICT",
            "existing scheduler data lacks its canonical project config",
            [".scheduler"],
        )
    try:
        existing = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        existing = None
    if not (
        isinstance(existing, dict)
        and existing.get("config_schema_version") == 1
        and isinstance(existing.get("project_id"), str)
        and existing["project_id"]
        and existing.get("state_path") == ".scheduler/state.json"
        and existing.get("events_path") is None
    ):
        return _failure(
            "CODEX_TEAM_CONFLICT",
            "existing scheduler project config does not match this project",
            [".scheduler/project.json"],
        )
    return None


def _init(root: Path) -> dict[str, object]:
    scheduler_conflict = _scheduler_conflict(root)
    if scheduler_conflict is not None:
        return scheduler_conflict
    expected = _expected_files()
    skills_root = root / ".agents" / "skills"
    skill_target = skills_root / _SKILL_NAME
    legacy_skills = [skills_root / name for name in _LEGACY_SKILL_NAMES]
    existing_legacy_skills = [path for path in legacy_skills if path.exists()]
    skill_existed = skill_target.exists() or bool(existing_legacy_skills)
    skill_status, skill_wheel = _skill_status(skill_target)
    backup = skill_target.with_name(f"{skill_target.name}.backup")
    legacy_backups = [path.with_name(f"{path.name}.backup") for path in legacy_skills]
    conflicting_backups = [path for path in (backup, *legacy_backups) if path.exists()]
    if conflicting_backups:
        return _failure(
            "CODEX_TEAM_CONFLICT",
            "manual backup handling required",
            [str(path.relative_to(root)) for path in conflicting_backups],
        )
    managed_roots_existed = {
        relative: (root / relative).exists()
        for relative in (".codex", ".agents", ".scheduler", ".venv")
    }
    original_files: dict[Path, bytes | None] = {}
    created: list[str] = []
    updated: list[str] = []
    version_source = skill_target
    version_wheel = skill_wheel
    if not skill_target.exists():
        scheduler_legacy = skills_root / "global-scheduler"
        if scheduler_legacy.exists():
            version_source = scheduler_legacy
            _, version_wheel = _skill_status(scheduler_legacy)
    upgraded_from = (
        _detected_skill_version(version_source, version_wheel)
        if skill_status != "current" and skill_existed
        else None
    )
    replaced_skill = skill_status != "current"
    try:
        root.mkdir(parents=True, exist_ok=True)
        for relative, content in expected.items():
            path = root / relative
            if not _compatible(path, content):
                original_files[path] = path.read_bytes() if path.exists() else None
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                (updated if original_files[path] is not None else created).append(
                    relative
                )
        if replaced_skill:
            if skill_target.exists():
                skill_target.rename(backup)
            for legacy, legacy_backup in zip(legacy_skills, legacy_backups):
                if legacy.exists():
                    legacy.rename(legacy_backup)
            shutil.copytree(_skill_source(), skill_target)
        else:
            for legacy, legacy_backup in zip(legacy_skills, legacy_backups):
                if legacy.exists():
                    legacy.rename(legacy_backup)
        installer = skill_target / "scripts" / "install.py"
        installer_command = [
            sys.executable,
            str(installer),
            "--project-root",
            str(root),
        ]
        scheduler_config = root / ".scheduler" / "project.json"
        if scheduler_config.is_file():
            project_id = json.loads(scheduler_config.read_text(encoding="utf-8"))[
                "project_id"
            ]
            installer_command.extend(["--project-id", project_id])
        subprocess.run(
            installer_command,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    except Exception:
        _rollback_migration(
            root=root,
            skill_target=skill_target,
            backup=backup,
            legacy_skills=legacy_skills,
            legacy_backups=legacy_backups,
            replaced_skill=replaced_skill,
            original_files=original_files,
            managed_roots_existed=managed_roots_existed,
        )
        receipt = _failure(
            "CODEX_TEAM_MIGRATION_FAILED",
            "team migration failed and was rolled back",
            [],
        )
        receipt["migration"] = {"rolled_back": True}
        return receipt
    if backup.exists():
        shutil.rmtree(backup)
    for legacy_backup in legacy_backups:
        if legacy_backup.exists():
            shutil.rmtree(legacy_backup)
    upgraded_to = "0.3.8" if skill_existed and replaced_skill else None
    return {
        "ok": True,
        "operation": "init",
        "project_root": str(root),
        "created": sorted(created),
        "updated": sorted(updated),
        "removed_legacy_skills": sorted(
            str(path.relative_to(root)) for path in existing_legacy_skills
        ),
        "upgraded_from": upgraded_from,
        "upgraded_to": upgraded_to,
        "migration": {
            "upgraded_from": upgraded_from,
            "upgraded_to": upgraded_to,
            "rolled_back": False,
            "transient_files_discarded": replaced_skill and skill_existed,
        },
    }


def _doctor(root: Path) -> dict[str, object]:
    scheduler_conflict = _scheduler_conflict(root)
    if scheduler_conflict is not None:
        return scheduler_conflict
    missing = [
        relative
        for relative, content in _expected_files().items()
        if not _compatible(root / relative, content)
    ]
    if not (root / ".scheduler" / "project.json").is_file():
        missing.append(".scheduler/project.json")
    skill_root = root / ".agents" / "skills" / _SKILL_NAME
    skill_status, skill_wheel = _skill_status(skill_root)
    if skill_status != "current":
        missing.append(f".agents/skills/{_SKILL_NAME}/SKILL.md")
    for legacy_name in _LEGACY_SKILL_NAMES:
        legacy_path = root / ".agents" / "skills" / legacy_name
        if legacy_path.exists():
            missing.append(str(legacy_path.relative_to(root)))
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
        "skill": {
            "status": skill_status,
            "current": skill_status == "current",
            "wheel": skill_wheel,
        },
        "native_identity": {
            "status": "unverified",
            "guidance": _NATIVE_ATTESTATION_NOTE,
        },
        "roles": {
            label: {"worker_id": worker, "agent": agent}
            for label, (worker, agent) in _ROLES.items()
        },
    }


def _start(root: Path, *, role: str | None) -> int:
    if role is None:
        prompt = (
            "YOU ARE ALREADY THE FRESH TEAM ROOT. do not call codex-team, "
            "codex-team init/doctor/start, codex resume, or launch nested Codex. "
            "Read only the existing project handoff (.codex/team-handoff.md or "
            ".codex/TEAM_MODE_V2_PM_HANDOFF.md), CLAUDE.md, AGENTS.md, and "
            "unified codex-team Skill, then directly native-spawn product_manager with "
            "fork_turns=none. Create a new agent each time. "
            + _PARENT_ATTESTATION_PROTOCOL
        )
        command = ["codex", "-C", str(root), prompt]
    else:
        worker, agent = _ROLES[role]
        prompt = (
            f"Start a fresh {role} session as native {agent}; worker_id={worker}; "
            "fork_turns=none. Read this project's handoff, CLAUDE.md, AGENTS.md, and "
            "unified codex-team Skill. Create a new agent each time."
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
    }
    for template in _canonical_team_templates():
        files[f".codex/agents/{template.name}"] = template.read_text(encoding="utf-8")
    return files


def _team_config_source() -> Path:
    """Return the packaged canonical custom-agent contracts."""
    return Path(__file__).parent / "assets" / "team-config" / ".codex" / "agents"


def _canonical_team_templates() -> tuple[Path, ...]:
    """Return exactly the supported full-role TOML template set."""
    source = _team_config_source()
    templates = tuple(sorted(source.glob("*.toml")))
    names = {template.name for template in templates}
    if names != _CANONICAL_AGENT_FILES or any(not template.is_file() for template in templates):
        raise RuntimeError("packaged canonical role template set is incomplete or invalid")
    return templates


def _skill_source() -> Path:
    packaged = Path(__file__).parent / "assets" / _SKILL_NAME
    if packaged.is_dir():
        return packaged
    return Path(__file__).parents[3] / "skills" / _SKILL_NAME


def _skill_status(skill_root: Path) -> tuple[str, str | None]:
    if not all((skill_root / relative).is_file() for relative in _REQUIRED_SKILL_FILES):
        return "invalid", None
    wheels = sorted((skill_root / "assets").glob("agent_task_scheduler-*.whl"))
    if len(wheels) != 1:
        return "invalid", None
    wheel_name = wheels[0].name
    expected_version = _SUPPORTED_SKILL_WHEELS.get(wheel_name)
    if expected_version is None or _wheel_version(wheels[0]) != expected_version:
        return "invalid", wheel_name
    if wheel_name == _BUNDLED_WHEEL_NAME:
        try:
            marker_data = json.loads(
                (skill_root / "assets" / "managed-skill.json").read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, json.JSONDecodeError):
            return "invalid", wheel_name
        if not isinstance(marker_data, dict) or marker_data.get("version") != "0.3.8":
            return "invalid", wheel_name
        source = _skill_source().resolve()
        if skill_root.resolve() != source and not _same_skill_tree(skill_root, source):
            return "invalid", wheel_name
        return "current", wheel_name
    if wheel_name in _SUPPORTED_LEGACY_WHEEL_NAMES:
        return "supported_legacy", wheel_name
    return "invalid", wheel_name


def _wheel_version(wheel: Path) -> str | None:
    try:
        with zipfile.ZipFile(wheel) as archive:
            metadata_paths = [
                path
                for path in archive.namelist()
                if path.endswith(".dist-info/METADATA")
            ]
            if len(metadata_paths) != 1:
                return None
            for line in archive.read(metadata_paths[0]).decode("utf-8").splitlines():
                if line.startswith("Version: "):
                    return line.removeprefix("Version: ").strip()
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile):
        return None
    return None


def _wheel_version_from_name(wheel_name: str | None) -> str | None:
    if wheel_name is None:
        return None
    parts = wheel_name.split("-")
    return parts[1] if len(parts) >= 2 else None


def _detected_skill_version(skill_root: Path, wheel_name: str | None) -> str | None:
    version = _wheel_version_from_name(wheel_name)
    if version is not None:
        return version
    wheels = sorted((skill_root / "assets").glob("agent_task_scheduler-*.whl"))
    return _wheel_version(wheels[0]) if len(wheels) == 1 else None


def _restore_files(original_files: dict[Path, bytes | None]) -> None:
    for path, content in original_files.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(content)


def _rollback_migration(
    *,
    root: Path,
    skill_target: Path,
    backup: Path,
    legacy_skills: list[Path],
    legacy_backups: list[Path],
    replaced_skill: bool,
    original_files: dict[Path, bytes | None],
    managed_roots_existed: dict[str, bool],
) -> None:
    if replaced_skill and skill_target.exists():
        shutil.rmtree(skill_target)
    if backup.exists():
        backup.rename(skill_target)
    for legacy, legacy_backup in zip(legacy_skills, legacy_backups):
        if legacy_backup.exists():
            legacy_backup.rename(legacy)
    _restore_files(original_files)
    for relative in (".venv", ".scheduler", ".codex", ".agents"):
        path = root / relative
        if not managed_roots_existed[relative] and path.exists():
            shutil.rmtree(path)


def _same_skill_tree(target: Path, source: Path) -> bool:
    def files(root: Path) -> dict[str, Path]:
        return {
            path.relative_to(root).as_posix(): path
            for path in root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }

    target_files = files(target)
    source_files = files(source)
    return set(target_files) == set(source_files) and all(
        target_files[relative].read_bytes() == source_path.read_bytes()
        for relative, source_path in source_files.items()
    )


def _compatible(path: Path, expected: str) -> bool:
    if not path.exists():
        return False
    if path.suffix != ".toml":
        return path.read_text(encoding="utf-8") == expected
    try:
        existing = tomllib.loads(path.read_text(encoding="utf-8"))
        required = tomllib.loads(expected)
    except tomllib.TOMLDecodeError:
        return False
    return existing == required


def _failure(code: str, message: str, paths: list[str]) -> dict[str, object]:
    return {"ok": False, "code": code, "message": message, "conflicts": paths}


def _emit(receipt: dict[str, object], *, exit_code: int = 0) -> int:
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return exit_code
