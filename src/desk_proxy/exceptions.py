"""
Custom exceptions for desk-proxy. Prevents stack traces and hides secrets.
"""


class DeskProxyError(Exception):
    """Base exception for all desk-proxy errors.

    Raised for configuration problems, payload problems, and any local desktop
    failure that must reach the user as a clean one-line message instead of a
    Python traceback.

    Args:
        message (str): Human-readable, actionable error text. Should tell the
            user what to run next when a fix exists.

    Examples:
        >>> raise DeskProxyError("Config not found. Run 'desk-proxy admin setup'.")
        Traceback (most recent call last):
            ...
        DeskProxyError: Config not found. Run 'desk-proxy admin setup'.
        >>> str(DeskProxyError("xdotool missing on PATH"))
        'xdotool missing on PATH'
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class DeskAPIError(DeskProxyError):
    """A local desktop operation failed with a non-recoverable status.

    Args:
        status (int): HTTP-like status code (0 when the failure happened before
            any useful exchange, e.g. binary missing or display unreachable).
        message (str): Explanation plus the recommended fix.

    Examples:
        >>> DeskAPIError(0, "DISPLAY unset and :0 unreachable").status
        0
        >>> str(DeskAPIError(500, "screenshot capture failed"))
        '[500] screenshot capture failed'
    """

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(f"[{status}] {message}")
