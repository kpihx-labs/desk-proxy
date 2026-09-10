"""
System logger for desk-proxy — logs to stderr for systemd/journald capture.

No file management: systemd/journald handles log rotation and retention.
Stdout stays reserved for the ADN JSON envelope.
"""

import logging
import sys

logger = logging.getLogger("desk_proxy")


def setup_logging(level: str = "WARNING") -> logging.Logger:
    """Attach a stderr StreamHandler to the ``desk_proxy`` logger.

    In a terminal the messages stay on stderr (not mixed with stdout JSON).
    Under systemd they are captured by journalctl.

    Args:
        level (str): Logging level name, e.g. ``"WARNING"`` or ``"DEBUG"``.
            Unknown names fall back to ``WARNING``.

    Returns:
        logging.Logger: The configured ``desk_proxy`` logger instance.

    Examples:
        >>> log = setup_logging("WARNING")
        >>> log.name
        'desk_proxy'
        >>> setup_logging("DEBUG").level == logging.DEBUG
        True
    """
    logger.setLevel(getattr(logging, level.upper(), logging.WARNING))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)
    return logger
