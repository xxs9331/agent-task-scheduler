"""Resolve managed project configuration without a global state fallback."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_CONFIG_RELATIVE_PATH = Path(".scheduler/project.json")
_SUPPORTED_CONFIG_SCHEMA_VERSION = 1


class ProjectContextError(Exception):
    """A project-discovery failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProjectContext:
    """Validated filesystem paths owned by one managed project."""

    project_id: str
    root: Path
    config_path: Path
    state_path: Path
    lock_path: Path
    events_path: Path | None


def discover_project_context(
    *, current_directory: Path, project_root: Path | None = None
) -> ProjectContext:
    """Resolve an explicit root or the nearest parent project configuration."""
    root = _resolve_project_root(
        current_directory=current_directory,
        project_root=project_root,
    )
    config_path = root / _CONFIG_RELATIVE_PATH
    config = _read_config(config_path)
    return _build_context(root=root, config_path=config_path, config=config)


def _resolve_project_root(
    *, current_directory: Path, project_root: Path | None
) -> Path:
    if project_root is not None:
        root = project_root.resolve()
        if not (root / _CONFIG_RELATIVE_PATH).is_file():
            raise ProjectContextError(
                "PROJECT_NOT_FOUND", "project configuration was not found"
            )
        return root

    current = current_directory.resolve()
    for candidate in (current, *current.parents):
        if (candidate / _CONFIG_RELATIVE_PATH).is_file():
            return candidate
    raise ProjectContextError(
        "PROJECT_NOT_FOUND", "project configuration was not found"
    )


def _read_config(config_path: Path) -> dict[str, Any]:
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProjectContextError(
            "PROJECT_CONFIG_INVALID", "project configuration is invalid"
        ) from error
    if not isinstance(config, dict):
        raise ProjectContextError(
            "PROJECT_CONFIG_INVALID", "project configuration must be an object"
        )
    return config


def _build_context(
    *, root: Path, config_path: Path, config: dict[str, Any]
) -> ProjectContext:
    if config.get("config_schema_version") != _SUPPORTED_CONFIG_SCHEMA_VERSION:
        raise ProjectContextError(
            "CONFIG_SCHEMA_UNSUPPORTED", "unsupported config schema version"
        )
    project_id = config.get("project_id")
    if not isinstance(project_id, str) or not project_id:
        raise ProjectContextError(
            "PROJECT_CONFIG_INVALID", "project_id must be a non-empty string"
        )

    state_path = _resolve_controlled_path(root=root, value=config.get("state_path"))
    events_value = config.get("events_path")
    events_path = (
        None
        if events_value is None
        else _resolve_controlled_path(root=root, value=events_value)
    )
    return ProjectContext(
        project_id=project_id,
        root=root,
        config_path=config_path,
        state_path=state_path,
        lock_path=Path(f"{state_path}.lock"),
        events_path=events_path,
    )


def _resolve_controlled_path(*, root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ProjectContextError(
            "PROJECT_CONFIG_INVALID", "configured path must be a non-empty string"
        )
    configured_path = Path(value)
    if configured_path.is_absolute() or ".." in configured_path.parts:
        raise ProjectContextError(
            "PROJECT_PATH_ESCAPE", "configured path leaves the project root"
        )

    resolved_path = (root / configured_path).resolve()
    try:
        resolved_path.relative_to(root)
    except ValueError as error:
        raise ProjectContextError(
            "PROJECT_PATH_ESCAPE", "configured path leaves the project root"
        ) from error
    return resolved_path
