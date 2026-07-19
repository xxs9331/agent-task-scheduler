from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


INSTALLER = (
    Path(__file__).parents[2] / "skills" / "codex-team" / "scripts" / "install.py"
)
SPEC = importlib.util.spec_from_file_location(
    "global_scheduler_skill_install", INSTALLER
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_that_project_id_is_normalized_for_scheduler_config() -> None:
    assert MODULE.normalized_project_id("世界树 demo") == "demo"


def test_that_existing_different_project_config_is_not_overwritten(
    tmp_path: Path,
) -> None:
    config = tmp_path / ".scheduler" / "project.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"project_id":"other"}', encoding="utf-8")

    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        MODULE.write_project_config(tmp_path, "demo")

    assert config.read_text(encoding="utf-8") == '{"project_id":"other"}'


def test_that_skill_requires_exactly_one_bundled_wheel(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()

    with pytest.raises(RuntimeError, match="exactly one bundled wheel"):
        MODULE.bundled_wheel(tmp_path)
