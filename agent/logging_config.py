"""
Logging configuration helper for the agent.
"""
import logging
from typing import Optional


def configure_logging(level: Optional[str] = None) -> None:
    lvl = getattr(logging, (level or "INFO").upper(), logging.INFO)
    logging.basicConfig(
        level=lvl,
        format="[%(asctime)s] %(name)s %(levelname)s: %(message)s",
    )
