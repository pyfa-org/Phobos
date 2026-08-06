
class FsdBinaryError(Exception):
    """Base exception for schema-driven FSD parsing errors."""


class FsdFormatError(FsdBinaryError):
    """Raised when an FSD file is truncated or contains invalid offsets."""


class FsdSchemaError(FsdBinaryError):
    """Raised when an embedded or external schema cannot be used safely."""


class FsdDependencyError(FsdBinaryError):
    """Raised when support for an external schema dependency is unavailable."""
