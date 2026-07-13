"""Managed-project discovery and path-boundary validation."""

from .service import ProjectContext, ProjectContextError, discover_project_context

__all__ = ["ProjectContext", "ProjectContextError", "discover_project_context"]
