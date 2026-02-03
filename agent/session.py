"""
Session logging / audit helper.
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading

_logger = None
_lock = threading.Lock()


def get_session_logger(log_path: Path | str = "agent_session.log"):
    global _logger
    with _lock:
        if _logger is not None:
            return _logger
        logger = logging.getLogger("agent.session")
        logger.setLevel(logging.INFO)
        log_file = Path(log_path)
        handler = RotatingFileHandler(str(log_file), maxBytes=10_000_000, backupCount=5)
        fmt = logging.Formatter("%(asctime)s %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        _logger = logger
        return _logger


def log_command(cmd: str, args: list[str]) -> None:
    logger = get_session_logger()
    logger.info(f"COMMAND {cmd} ARGS {args}")


def log_command_signed(cmd: str, args: list[str], hmac_key: str | None):
    """Log command with optional HMAC signature for tamper-evidence."""
    import hmac
    import hashlib

    logger = get_session_logger()
    payload = f"COMMAND {cmd} ARGS {args}".encode("utf-8")
    if hmac_key:
        sig = hmac.new(hmac_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        logger.info(f"{payload.decode()} SIG {sig}")
    else:
        logger.info(payload.decode())
