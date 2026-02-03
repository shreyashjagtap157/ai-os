"""
Voice input handler stub for AI-OS agent.
Future: Integrate speech-to-text (Whisper, Vosk, etc.)
"""
import logging

logger = logging.getLogger(__name__)


def get_voice_input(timeout: int = 10) -> str | None:
    """
    Get voice input from user (stub).
    Returns: text from speech or None if not implemented/timeout.
    """
    logger.debug("Voice input requested (not yet implemented)")
    # TODO: Integrate with SpeechRecognition or Whisper
    return None
