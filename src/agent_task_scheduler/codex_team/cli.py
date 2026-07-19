"""Portable, project-local ``codex-team`` command."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tomllib
import zipfile
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
_BUNDLED_WHEEL_NAME = "agent_task_scheduler-0.3.4-py3-none-any.whl"
_SUPPORTED_LEGACY_WHEEL_NAMES = frozenset(
    {
        "agent_task_scheduler-0.3.1-py3-none-any.whl",
        "agent_task_scheduler-0.3.2-py3-none-any.whl",
        "agent_task_scheduler-0.3.3-py3-none-any.whl",
    }
)
_SUPPORTED_SKILL_WHEELS = {
    _BUNDLED_WHEEL_NAME: "0.3.4",
    **{wheel: wheel.split("-")[1] for wheel in _SUPPORTED_LEGACY_WHEEL_NAMES},
}
_REQUIRED_SKILL_FILES = (
    "SKILL.md",
    "scripts/install.py",
    "scripts/install_codex_team.py",
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
    skill_status, _ = _skill_status(skill_target)
    if (
        skill_target.exists()
        and skill_status == "supported_legacy"
        and not _legacy_is_stock(skill_target)
    ):
        conflicts.append(str(skill_target.relative_to(root)))
    elif skill_target.exists() and skill_status == "invalid":
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
    upgraded_from = None
    if skill_status == "supported_legacy":
        upgraded_from = _wheel_version(next((skill_target / "assets").glob("*.whl")))
        backup = skill_target.with_name(f"{skill_target.name}.backup")
        if backup.exists():
            return _failure(
                "CODEX_TEAM_CONFLICT",
                "manual backup handling required",
                [str(backup.relative_to(root))],
            )
        skill_target.rename(backup)
        try:
            shutil.copytree(_skill_source(), skill_target)
        except Exception:
            if skill_target.exists():
                shutil.rmtree(skill_target)
            backup.rename(skill_target)
            receipt = _failure(
                "CODEX_TEAM_MIGRATION_FAILED",
                "skill staging failed and was rolled back",
                [],
            )
            receipt["migration"] = {"rolled_back": True}
            return receipt
    elif not skill_target.exists():
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
    installer_root = skill_target
    installer = installer_root / "scripts" / "install.py"
    try:
        subprocess.run(
            [sys.executable, str(installer), "--project-root", str(root)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    except Exception:
        if upgraded_from is not None:
            shutil.rmtree(skill_target)
            backup.rename(skill_target)
        receipt = _failure(
            "CODEX_TEAM_MIGRATION_FAILED",
            "installer failed and skill was rolled back",
            [],
        )
        receipt["migration"] = {"rolled_back": True}
        return receipt
    if upgraded_from is not None:
        shutil.rmtree(backup)
    return {
        "ok": True,
        "operation": "init",
        "project_root": str(root),
        "created": sorted(expected),
        "upgraded_from": upgraded_from,
        "upgraded_to": "0.3.4" if upgraded_from else None,
        "migration": {
            "upgraded_from": upgraded_from,
            "upgraded_to": "0.3.4" if upgraded_from else None,
            "rolled_back": False,
            "transient_files_discarded": upgraded_from is not None,
        },
    }


def _doctor(root: Path) -> dict[str, object]:
    missing = [
        relative
        for relative, content in _expected_files().items()
        if not _compatible(root / relative, content)
    ]
    if not (root / ".scheduler" / "project.json").is_file():
        missing.append(".scheduler/project.json")
    skill_status, skill_wheel = _skill_status(
        root / ".agents" / "skills" / "global-scheduler"
    )
    if skill_status != "current":
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
            "Read only the existing project handoff, CLAUDE.md, AGENTS.md, and "
            "global-scheduler Skill, then directly native-spawn product_manager with "
            "fork_turns=none. Create a new agent each time. "
            + _PARENT_ATTESTATION_PROTOCOL
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
        if not isinstance(marker_data, dict) or marker_data.get("version") != "0.3.4":
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


def _legacy_is_stock(skill_root: Path) -> bool:
    wheel = next((skill_root / "assets").glob("*.whl"), None)
    version = _wheel_version(wheel) if wheel else None
    manifest_path = Path(__file__).parent / "assets" / "legacy_skill_manifests.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))["versions"].get(
        version or ""
    )
    if manifest is None:
        return False
    files = {
        path.relative_to(skill_root).as_posix(): path
        for path in skill_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    variants = manifest.pop("wheel_variants", [])
    wheel_relative = f"assets/agent_task_scheduler-{version}-py3-none-any.whl"
    return set(files) == set(manifest) and all(
        (
            _sha256(path) in variants
            if relative == wheel_relative
            else _sha256(path) == manifest[relative]
        )
        for relative, path in files.items()
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        _sha256(target_files[relative]) == _sha256(source_path)
        for relative, source_path in source_files.items()
    )


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
