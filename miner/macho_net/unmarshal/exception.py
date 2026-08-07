
class MarshalError(Exception):
    """Raised when a marshal stream cannot be read."""


class UnsupportedTypeError(MarshalError):
    """Raised when a stream uses a type tag we do not implement yet."""
