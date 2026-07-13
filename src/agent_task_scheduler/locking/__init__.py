"""Cross-platform local-disk state locking."""

from .state_lock import LockTimeoutError, StateLock

__all__ = ["LockTimeoutError", "StateLock"]
