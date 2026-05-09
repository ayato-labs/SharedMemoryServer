class SharedMemoryError(Exception):
    """Base exception for Ripen."""

    pass


class DatabaseError(SharedMemoryError):
    """Raised when a database operation fails."""

    pass


class DatabaseLockedError(DatabaseError):
    """Raised when the database remains locked after all retries."""

    pass


class LockTimeoutError(SharedMemoryError):
    """Raised when a cross-process lock cannot be acquired within the timeout."""

    pass


class ValidationError(SharedMemoryError):
    """Raised when input data fails validation."""

    pass


class ResourceNotFoundError(SharedMemoryError):
    """Raised when a requested resource (snapshot, file, entity) is not found."""

    pass


class SecurityError(SharedMemoryError):
    """Raised when a security-sensitive operation (like path traversal) is blocked."""

    pass
