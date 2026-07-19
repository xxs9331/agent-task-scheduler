# Platform contract

`StateLock` is a repository-adapter interface with acquire, timeout, and release semantics. Linux/WSL uses a local-disk advisory lock; native Windows uses a local-disk file-lock adapter. Both implementations share the same contract tests: mutual exclusion, timeout, release after normal exit, and release after process failure. Network filesystems are not guaranteed; v1 is local-only unless an explicit operator override is supplied, and a reliable filesystem warning is machine-readable.

The lock path is always derived as `${state_path}.lock`; callers cannot select a second lock file. All state reads and writes participating in a mutation occur inside the lock.
