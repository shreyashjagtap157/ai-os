"""
Adaptive UI shell for AI-OS.
"""
import logging
from pathlib import Path
from agent.agent import CommandRegistry, parse_command
from agent.system_api import SystemAPI
from agent.input.text_input import get_text_input

logger = logging.getLogger(__name__)


def launch_shell(allowed_root: Path | None = None) -> None:
    """Launch the adaptive UI shell (shared command registry with agent)."""
    if allowed_root is None:
        allowed_root = Path.cwd()
    api = SystemAPI(allowed_root=allowed_root)
    registry = CommandRegistry(api)
    logger.info("UI Shell launched")
    print("[AI-OS Shell] Adaptive shell starting (type 'help' for commands)")
    while True:
        raw = get_text_input("[ai-os] ")
        cmd, args = parse_command(raw)
        if not registry.execute(cmd, args):
            break
    logger.info("UI Shell exiting")
    print("[AI-OS Shell] Goodbye.")
