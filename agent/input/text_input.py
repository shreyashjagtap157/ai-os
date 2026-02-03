"""
Text input handler for AI-OS agent.
"""
import logging

logger = logging.getLogger(__name__)


def get_text_input(prompt: str = "[AI-OS] $ ") -> str:
    """Get text input from user with error handling."""
    try:
        return input(prompt)
    except EOFError:
        logger.info("EOF detected")
        return "exit"
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt")
        return "exit"
