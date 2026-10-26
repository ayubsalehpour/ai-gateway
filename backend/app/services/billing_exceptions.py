"""Domain exceptions for billing operations."""


class SettlementReconciliationRequired(ValueError):
    """Raised when a request cannot be safely settled automatically.

    This exception is intentionally a ValueError subclass to preserve
    compatibility with callers/tests that already handle invalid settlement
    conditions as ValueError.
    """
