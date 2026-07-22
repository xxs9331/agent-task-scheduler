from __future__ import annotations

import json
import subprocess
import zipfile
from hashlib import sha256
from pathlib import Path

from agent_task_scheduler.codex_team.update import (
    CURRENT_VERSION,
    UpdatePreflight,
    is_strictly_newer,
    read_policy,
    validate_candidate,
    write_policy,
)


def _candidate(cache: Path, version: str = "0.4.3") -> dict[str, object]:
    skill = cache / "candidate" / "codex-team"
    wheel = skill / "assets" / f"agent_task_scheduler-{version}-py3-none-any.whl"
    (skill / "assets").mkdir(parents=True)
    tracked = skill / "SKILL.md"
    tracked.write_text("managed skill\n", encoding="utf-8")
    for name in ("install.py", "install_codex_team.py"):
        script = skill / "scripts" / name
        script.parent.mkdir(exist_ok=True)
        script.write_text("# candidate installer\n", encoding="utf-8")
    marker = {
        "managed_skill": "codex-team",
        "version": version,
        "files": {"SKILL.md": sha256(tracked.read_bytes()).hexdigest()},
    }
    (skill / "assets" / "managed-skill.json").write_text(
        json.dumps(marker), encoding="utf-8"
    )
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(
            f"agent_task_scheduler-{version}.dist-info/METADATA",
            f"Metadata-Version: 2.1\nVersion: {version}\n",
        )
    return {
        "plugin": "global-scheduler",
        "version": version,
        "skill_root": str(skill),
        "wheel": str(wheel),
    }


def _runner(payload: object, returncode: int = 0):
    def run(_command: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], returncode, json.dumps(payload), "")

    return run


def _transaction_runner(
    candidate: dict[str, object],
    *,
    prefix: Path,
    project: Path,
    fail_stage: str | None = None,
):
    def run(command: object) -> subprocess.CompletedProcess[str]:
        arguments = list(command)  # type: ignore[arg-type]
        if arguments[:4] == ["codex", "plugin", "marketplace", "upgrade"]:
            return subprocess.CompletedProcess(arguments, 0, json.dumps(candidate), "")
        if arguments[-2:] == ["--prefix", str(prefix)]:
            (prefix / ".codex-team").mkdir(parents=True, exist_ok=True)
            (prefix / ".codex-team" / "version").write_text("candidate\n")
            (prefix / "bin").mkdir(exist_ok=True)
            (prefix / "bin" / "codex-team").write_text("candidate\n")
            code = 1 if fail_stage == "launcher" else 0
            return subprocess.CompletedProcess(
                arguments, code, json.dumps({"ok": code == 0}), ""
            )
        assert arguments[-2:] == ["--project-root", str(project.resolve())]
        (project / ".codex").mkdir(parents=True, exist_ok=True)
        (project / ".codex" / "version").write_text("candidate\n")
        code = 1 if fail_stage == "project" else 0
        return subprocess.CompletedProcess(
            arguments, code, json.dumps({"ok": code == 0}), ""
        )

    return run


def test_policy_defaults_to_notify_and_auto_is_explicit(tmp_path: Path) -> None:
    assert read_policy(tmp_path) == "notify"
    assert write_policy(tmp_path, "auto")["update_policy"] == "auto"
    assert read_policy(tmp_path) == "auto"


def test_strict_version_rejects_same_downgrade_and_malformed() -> None:
    assert is_strictly_newer("0.4.3", CURRENT_VERSION)
    assert not is_strictly_newer(CURRENT_VERSION, CURRENT_VERSION)
    assert not is_strictly_newer("0.4.0", CURRENT_VERSION)
    assert not is_strictly_newer("latest", CURRENT_VERSION)


def test_candidate_requires_identity_hashes_paths_and_one_matching_wheel(
    tmp_path: Path,
) -> None:
    candidate = _candidate(tmp_path)
    assert validate_candidate(candidate, cache_root=tmp_path) == (True, "OK")
    candidate["plugin"] = "other"
    assert validate_candidate(candidate, cache_root=tmp_path)[0] is False


def test_notify_reports_available_without_mutation(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    result = UpdatePreflight(tmp_path / "prefix", tmp_path, _runner(candidate)).check()
    assert result["update_policy"] == "notify"
    assert result["update_required"] is True
    assert not (tmp_path / "prefix").exists()


def test_off_avoids_runner_and_auto_requires_restart(tmp_path: Path) -> None:
    write_policy(tmp_path / "prefix", "off")
    result = UpdatePreflight(
        tmp_path / "prefix",
        tmp_path,
        lambda _command: (_ for _ in ()).throw(AssertionError()),
    ).check()
    assert result["checked"] is False
    write_policy(tmp_path / "prefix", "auto")
    candidate = _candidate(tmp_path)
    prefix, project = tmp_path / "prefix", tmp_path / "project"
    result = UpdatePreflight(
        prefix,
        tmp_path,
        _transaction_runner(candidate, prefix=prefix, project=project),
        project,
    ).check()
    assert result["restart_required"] is True
    assert result["project_updated"] is True


def test_network_and_subprocess_failures_preserve_local_installation(
    tmp_path: Path,
) -> None:
    result = UpdatePreflight(
        tmp_path / "prefix", tmp_path, _runner({}, returncode=1)
    ).check()
    assert result["ok"] is True
    assert result["warning"] == "UPDATE_CHECK_UNAVAILABLE"


def test_auto_updates_the_validated_launcher_and_current_project_only(
    tmp_path: Path,
) -> None:
    candidate = _candidate(tmp_path)
    prefix, project = tmp_path / "prefix", tmp_path / "project"
    write_policy(prefix, "auto")
    result = UpdatePreflight(
        prefix,
        tmp_path,
        _transaction_runner(candidate, prefix=prefix, project=project),
        project,
    ).check()

    assert result["project_updated"] is True
    assert result["restart_required"] is True
    assert (prefix / ".codex-team" / "version").read_text() == "candidate\n"
    assert (project / ".codex" / "version").read_text() == "candidate\n"


def test_launcher_failure_restores_the_last_validated_local_state(
    tmp_path: Path,
) -> None:
    candidate = _candidate(tmp_path)
    prefix, project = tmp_path / "prefix", tmp_path / "project"
    original = prefix / ".codex-team" / "version"
    original.parent.mkdir(parents=True)
    original.write_text("current\n")
    write_policy(prefix, "auto")
    result = UpdatePreflight(
        prefix,
        tmp_path,
        _transaction_runner(
            candidate, prefix=prefix, project=project, fail_stage="launcher"
        ),
        project,
    ).check()

    assert result == {
        "ok": False,
        "operation": "update-preflight",
        "code": "UPDATE_TRANSACTION_FAILED",
        "stage": "launcher",
        "rolled_back": True,
        "project_updated": False,
    }
    assert original.read_text() == "current\n"
    assert not project.exists()


def test_project_failure_restores_launcher_and_project_state(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    prefix, project = tmp_path / "prefix", tmp_path / "project"
    launcher = prefix / ".codex-team" / "version"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("current\n")
    project_file = project / ".codex" / "version"
    project_file.parent.mkdir(parents=True)
    project_file.write_text("current\n")
    write_policy(prefix, "auto")
    result = UpdatePreflight(
        prefix,
        tmp_path,
        _transaction_runner(
            candidate, prefix=prefix, project=project, fail_stage="project"
        ),
        project,
    ).check()

    assert result["stage"] == "project"
    assert result["rolled_back"] is True
    assert launcher.read_text() == "current\n"
    assert project_file.read_text() == "current\n"
