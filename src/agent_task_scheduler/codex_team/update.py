"""Fail-closed, opt-in update preflight for the managed ``codex-team`` CLI."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Callable, Sequence


CURRENT_VERSION = "0.4.1"
MARKETPLACE = "xxs9331-scheduler"
PLUGIN = "global-scheduler"
POLICIES = frozenset({"auto", "notify", "off"})
_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:[-+][0-9A-Za-z.-]+)?$")
_UNAVAILABLE_WARNING: dict[str, object] | None = None


def _version(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        return None
    return tuple(int(part) for part in value.split("-", 1)[0].split("+", 1)[0].split("."))  # type: ignore[return-value]


def is_strictly_newer(candidate: object, current: object = CURRENT_VERSION) -> bool:
    candidate_value, current_value = _version(candidate), _version(current)
    return candidate_value is not None and current_value is not None and candidate_value > current_value


def metadata_path(prefix: Path) -> Path:
    return prefix / ".codex-team" / "update.json"


def read_policy(prefix: Path) -> str:
    try:
        data = json.loads(metadata_path(prefix).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "notify"
    policy = data.get("policy") if isinstance(data, dict) else None
    return policy if policy in POLICIES else "notify"


def write_policy(prefix: Path, policy: str) -> dict[str, object]:
    if policy not in POLICIES:
        raise ValueError("policy must be one of auto, notify, off")
    target = metadata_path(prefix)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps({"policy": policy}, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)
    return {"ok": True, "operation": "update-policy", "update_policy": policy}


def _wheel_version(wheel: Path) -> str | None:
    try:
        with zipfile.ZipFile(wheel) as archive:
            names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            if len(names) != 1:
                return None
            for line in archive.read(names[0]).decode("utf-8").splitlines():
                if line.startswith("Version: "):
                    return line[9:].strip()
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile):
        return None
    return None


def validate_candidate(candidate: object, *, cache_root: Path) -> tuple[bool, str]:
    """Validate only a staged candidate rooted in the managed plugin cache."""
    if not isinstance(candidate, dict) or candidate.get("plugin") != PLUGIN:
        return False, "UPDATE_CANDIDATE_IDENTITY_INVALID"
    version = candidate.get("version")
    if not is_strictly_newer(version):
        return False, "UPDATE_CANDIDATE_NOT_FORWARD"
    try:
        skill_root = Path(str(candidate["skill_root"])).resolve(strict=True)
        wheel = Path(str(candidate["wheel"])).resolve(strict=True)
        root = cache_root.resolve(strict=True)
    except (KeyError, OSError):
        return False, "UPDATE_CANDIDATE_PATH_INVALID"
    if root not in skill_root.parents or root not in wheel.parents or wheel.is_symlink():
        return False, "UPDATE_CANDIDATE_PATH_INVALID"
    marker = skill_root / "assets" / "managed-skill.json"
    try:
        manifest = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "UPDATE_CANDIDATE_MANIFEST_INVALID"
    if not isinstance(manifest, dict) or manifest.get("managed_skill") != "codex-team" or manifest.get("version") != version:
        return False, "UPDATE_CANDIDATE_MANIFEST_INVALID"
    files = manifest.get("files")
    if not isinstance(files, dict) or any(
        not isinstance(path, str) or not isinstance(digest, str) or ".." in Path(path).parts
        or not (skill_root / path).is_file() or sha256((skill_root / path).read_bytes()).hexdigest() != digest
        for path, digest in files.items()
    ):
        return False, "UPDATE_CANDIDATE_MANIFEST_INVALID"
    bundled = sorted((skill_root / "assets").glob("agent_task_scheduler-*.whl"))
    if bundled != [wheel] or _wheel_version(wheel) != version:
        return False, "UPDATE_CANDIDATE_WHEEL_INVALID"
    if not all((skill_root / relative).is_file() for relative in ("scripts/install.py", "scripts/install_codex_team.py")):
        return False, "UPDATE_CANDIDATE_LAYOUT_INVALID"
    return True, "OK"


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _run(command: Sequence[str], *, runner: Runner) -> subprocess.CompletedProcess[str]:
    return runner(command)


@dataclass(frozen=True)
class UpdatePreflight:
    prefix: Path
    cache_root: Path
    runner: Runner
    project_root: Path | None = None

    def check(self) -> dict[str, object]:
        global _UNAVAILABLE_WARNING
        policy = read_policy(self.prefix)
        if policy == "off":
            return {"ok": True, "operation": "update-preflight", "update_policy": policy, "checked": False}
        try:
            completed = _run(["codex", "plugin", "marketplace", "upgrade", MARKETPLACE, "--dry-run", "--json"], runner=self.runner)
            if completed.returncode != 0:
                raise RuntimeError("marketplace discovery failed")
            candidate = json.loads(completed.stdout)
        except (
            OSError,
            RuntimeError,
            json.JSONDecodeError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as error:
            if _UNAVAILABLE_WARNING is None:
                _UNAVAILABLE_WARNING = {"warning": "UPDATE_CHECK_UNAVAILABLE", "message": str(error)}
            return {"ok": True, "operation": "update-preflight", "update_policy": policy, **_UNAVAILABLE_WARNING}
        valid, code = validate_candidate(candidate, cache_root=self.cache_root)
        if code == "UPDATE_CANDIDATE_NOT_FORWARD":
            return {"ok": True, "operation": "update-preflight", "update_policy": policy, "available": False}
        if not valid:
            return {"ok": True, "operation": "update-preflight", "update_policy": policy, "warning": code}
        if policy == "notify":
            return {"ok": True, "operation": "update-preflight", "update_policy": policy, "available": True, "update_required": True, "updated_from": CURRENT_VERSION, "updated_to": candidate["version"]}
        try:
            upgraded = _run(["codex", "plugin", "marketplace", "upgrade", MARKETPLACE, "--json"], runner=self.runner)
            if upgraded.returncode != 0:
                raise RuntimeError("marketplace upgrade failed")
            # The update command may have replaced the staged tree.  Do not execute
            # bytes that were only validated before that mutation.
            valid, code = validate_candidate(candidate, cache_root=self.cache_root)
            if not valid:
                raise RuntimeError(code)
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            return {"ok": True, "operation": "update-preflight", "update_policy": policy, "warning": "UPDATE_APPLY_UNAVAILABLE", "message": str(error)}
        return self._install_candidate(candidate)

    def _install_candidate(self, candidate: dict[str, object]) -> dict[str, object]:
        """Install a validated candidate into this launcher and project only.

        The candidate installers run as new Python processes.  A local snapshot is
        retained until both stages pass, so a failure cannot leave the caller using
        mixed launcher/project bytes.
        """
        project_root = (self.project_root or Path.cwd()).resolve()
        skill_root = Path(str(candidate["skill_root"])).resolve()
        targets = (self.prefix / ".codex-team", self.prefix / "bin" / "codex-team")
        project_targets = tuple(project_root / relative for relative in (".agents", ".codex", ".scheduler", ".venv"))
        with tempfile.TemporaryDirectory(prefix="codex-team-update-") as temporary:
            backup_root = Path(temporary)
            snapshots = _snapshot((*targets, *project_targets), backup_root)
            stages = (
                ("launcher", [sys.executable, str(skill_root / "scripts" / "install_codex_team.py"), "--prefix", str(self.prefix)]),
                ("project", [sys.executable, str(skill_root / "scripts" / "install.py"), "--project-root", str(project_root)]),
            )
            for stage, command in stages:
                try:
                    result = _run(command, runner=self.runner)
                    if result.returncode != 0 or not _success_receipt(result.stdout):
                        raise RuntimeError("candidate installer failed")
                except (OSError, RuntimeError, subprocess.TimeoutExpired):
                    restored = _restore(snapshots)
                    return {
                        "ok": False,
                        "operation": "update-preflight",
                        "code": "UPDATE_TRANSACTION_FAILED",
                        "stage": stage,
                        "rolled_back": restored,
                        "project_updated": False,
                    }
        return {
            "ok": True,
            "operation": "update-preflight",
            "update_policy": "auto",
            "updated_from": CURRENT_VERSION,
            "updated_to": candidate["version"],
            "project_updated": True,
            "restart_required": True,
        }


@dataclass(frozen=True)
class _Snapshot:
    target: Path
    copy: Path | None


def _snapshot(targets: Sequence[Path], backup_root: Path) -> tuple[_Snapshot, ...]:
    snapshots: list[_Snapshot] = []
    for index, target in enumerate(targets):
        if target.exists() or target.is_symlink():
            copy = backup_root / str(index)
            if target.is_dir() and not target.is_symlink():
                shutil.copytree(target, copy, symlinks=True)
            else:
                shutil.copy2(target, copy, follow_symlinks=False)
            snapshots.append(_Snapshot(target, copy))
        else:
            snapshots.append(_Snapshot(target, None))
    return tuple(snapshots)


def _restore(snapshots: Sequence[_Snapshot]) -> bool:
    try:
        for snapshot in snapshots:
            target = snapshot.target
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            else:
                target.unlink(missing_ok=True)
            if snapshot.copy is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                if snapshot.copy.is_dir() and not snapshot.copy.is_symlink():
                    shutil.copytree(snapshot.copy, target, symlinks=True)
                else:
                    shutil.copy2(snapshot.copy, target, follow_symlinks=False)
        return True
    except OSError:
        return False


def _success_receipt(stdout: str) -> bool:
    try:
        receipt = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    return isinstance(receipt, dict) and receipt.get("ok") is True


def default_runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    # Discovery is best-effort and must not hold normal startup for long.  The
    # validated local installer may create a venv, so it gets a separate bounded
    # allowance.
    timeout = 30 if command and Path(command[0]).name.startswith("python") else 2
    return subprocess.run(list(command), check=False, text=True, capture_output=True, timeout=timeout)
