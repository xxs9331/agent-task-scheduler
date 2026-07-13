"""Schema migration and Parlant legacy-state adaptation."""

from .state_migration import MigrationError, migrate_file, migrate_state_document

__all__ = ["MigrationError", "migrate_file", "migrate_state_document"]
