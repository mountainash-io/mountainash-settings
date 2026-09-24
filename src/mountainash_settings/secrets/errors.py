"""Value-free library-generated storage errors; callers branch on class/reason."""
from typing import NoReturn


def _raise_clean(error: Exception) -> NoReturn:
    # Clear even an ambient caller exception, including __exit__ failures.
    try:
        raise error
    finally:
        error.__cause__ = None
        error.__context__ = None
        error.__suppress_context__ = True


class SecretStoreError(Exception):
    """Base storage/integration error."""


class SecretCapabilityError(SecretStoreError):
    """The requested local-storage capability is unavailable."""


class SecretStoreUnavailableError(SecretStoreError):
    """Failure whose reason does not imply that storage is unchanged."""

    def __init__(self, *args: object, reason: str = "unavailable") -> None:
        super().__init__(*args)
        self.reason = reason


class _Failure(Exception):
    """Private fixed-reason carrier, translated outside an exception handler."""

    def __init__(self, reason: str) -> None:
        super().__init__("Local storage operation failed")
        self.reason = reason
