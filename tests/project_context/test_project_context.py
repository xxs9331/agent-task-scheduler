import json
from pathlib import Path

import pytest

from agent_task_scheduler.project_context import (
    ProjectContextError,
    discover_project_context,
)


def test_that_explicit_project_root_takes_precedence_over_current_directory(
    tmp_path: Path,
) -> None:
    current_project = _create_project(tmp_path / "current", project_id="current")
    explicit_project = _create_project(tmp_path / "explicit", project_id="explicit")
    nested_current_directory = current_project / "nested"
    nested_current_directory.mkdir()

    context = discover_project_context(
        current_directory=nested_current_directory,
        project_root=explicit_project,
    )

    assert context.project_id == "explicit"
    assert context.root == explicit_project.resolve()
    assert context.state_path == explicit_project / ".scheduler" / "state.json"


def test_that_project_context_is_discovered_from_the_nearest_parent(
    tmp_path: Path,
) -> None:
    project = _create_project(tmp_path / "project", project_id="project")
    nested_directory = project / "one" / "two"
    nested_directory.mkdir(parents=True)

    context = discover_project_context(current_directory=nested_directory)

    assert context.project_id == "project"
    assert context.root == project.resolve()


def test_that_missing_project_configuration_returns_machine_readable_error(
    tmp_path: Path,
) -> None:
    with pytest.raises(ProjectContextError) as error:
        discover_project_context(current_directory=tmp_path)

    assert error.value.code == "PROJECT_NOT_FOUND"


def test_that_parent_traversal_in_a_configured_state_path_is_rejected(
    tmp_path: Path,
) -> None:
    project = _create_project(
        tmp_path / "project", project_id="project", state_path="../state.json"
    )

    with pytest.raises(ProjectContextError) as error:
        discover_project_context(current_directory=project)

    assert error.value.code == "PROJECT_PATH_ESCAPE"


def test_that_a_symlinked_state_path_outside_the_project_is_rejected(
    tmp_path: Path,
) -> None:
    project = _create_project(tmp_path / "project", project_id="project")
    outside_directory = tmp_path / "outside"
    outside_directory.mkdir()
    state_link = project / ".scheduler" / "state.json"
    state_link.symlink_to(outside_directory / "state.json")

    with pytest.raises(ProjectContextError) as error:
        discover_project_context(current_directory=project)

    assert error.value.code == "PROJECT_PATH_ESCAPE"


def _create_project(
    root: Path, *, project_id: str, state_path: str = ".scheduler/state.json"
) -> Path:
    scheduler_directory = root / ".scheduler"
    scheduler_directory.mkdir(parents=True)
    (scheduler_directory / "project.json").write_text(
        json.dumps(
            {
                "config_schema_version": 1,
                "project_id": project_id,
                "state_path": state_path,
            }
        ),
        encoding="utf-8",
    )
    return root
