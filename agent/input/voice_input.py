"""
AI-OS Voice Input Module
Provides voice recognition and text-to-speech capabilities
"""
import os
from typing import Optional, Callable
from dataclasses import dataclass
import threading
import queue


@dataclass
class VoiceConfig:
    """Voice recognition configuration"""
    enabled: bool = True
    engine: str = "google"  # google, whisper, sphinx
    language: str = "en-US"
    wake_word: Optional[str] = "hey ai"
    timeout: int = 5
    phrase_limit: int = 10


class VoiceInputHandler:
    """
    Voice input handler with speech recognition.
    Supports multiple recognition engines.
    """
    
    def __init__(self, config: Optional[VoiceConfig] = None):
        self.config = config or VoiceConfig()
        self._recognizer = None
        self._microphone = None
        self._is_listening = False
        self._audio_queue: queue.Queue = queue.Queue()
        self._on_command: Optional[Callable[[str], None]] = None
        
        self._init_recognizer()
    
    def _init_recognizer(self):
        """Initialize speech recognition"""
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = 300
            self._recognizer.dynamic_energy_threshold = True
            
            # Test microphone availability
            try:
                self._microphone = sr.Microphone()
                with self._microphone as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                print("[AI-OS Voice] Microphone initialized")
            except Exception as e:
                print(f"[AI-OS Voice] Microphone not available: {e}")
                self._microphone = None
                
        except ImportError:
            print("[AI-OS Voice] SpeechRecognition not installed. Voice input disabled.")
            self._recognizer = None
    
    def is_available(self) -> bool:
        """Check if voice input is available"""
        return self._recognizer is not None and self._microphone is not None
    
    def listen_once(self, timeout: int = 5) -> Optional[str]:
        """Listen for a single voice command"""
        if not self.is_available():
            return None
        
        import speech_recognition as sr
        
        try:
            with self._microphone as source:
                print("[AI-OS Voice] Listening...")
                audio = self._recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=self.config.phrase_limit
                )
            
            return self._recognize(audio)
            
        except sr.WaitTimeoutError:
            return None
        except Exception as e:
            print(f"[AI-OS Voice] Error: {e}")
            return None
    
    def _recognize(self, audio) -> Optional[str]:
        """Recognize speech from audio"""
        import speech_recognition as sr
        
        try:
            if self.config.engine == "google":
                text = self._recognizer.recognize_google(audio, language=self.config.language)
            elif self.config.engine == "whisper":
                text = self._recognizer.recognize_whisper(audio, language=self.config.language[:2])
            elif self.config.engine == "sphinx":
                text = self._recognizer.recognize_sphinx(audio)
            else:
                text = self._recognizer.recognize_google(audio)
            
            print(f"[AI-OS Voice] Recognized: {text}")
            return text
            
        except sr.UnknownValueError:
            print("[AI-OS Voice] Could not understand audio")
            return None
        except sr.RequestError as e:
            print(f"[AI-OS Voice] API error: {e}")
            return None
    
    def start_continuous_listening(self, on_command: Callable[[str], None]):
        """Start continuous background listening"""
        if not self.is_available():
            print("[AI-OS Voice] Voice input not available")
            return
        
        self._on_command = on_command
        self._is_listening = True
        
        thread = threading.Thread(target=self._listen_loop, daemon=True)
        thread.start()
        print("[AI-OS Voice] Continuous listening started")
    
    def _listen_loop(self):
        """Background listening loop"""
        import speech_recognition as sr
        
        while self._is_listening:
            try:
                with self._microphone as source:
                    audio = self._recognizer.listen(source, phrase_time_limit=10)
                
                text = self._recognize(audio)
                if text and self._on_command:
                    # Check for wake word
                    if self.config.wake_word:
                        if text.lower().startswith(self.config.wake_word.lower()):
                            command = text[len(self.config.wake_word):].strip()
                            if command:
                                self._on_command(command)
                    else:
                        self._on_command(text)
                        
            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                print(f"[AI-OS Voice] Loop error: {e}")
    
    def stop_listening(self):
        """Stop continuous listening"""
        self._is_listening = False
        print("[AI-OS Voice] Listening stopped")


class TextToSpeechHandler:
    """Text-to-speech output handler"""
    
    def __init__(self):
        self._engine = None
        self._init_engine()
    
    def _init_engine(self):
        """Initialize TTS engine"""
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty('rate', 150)
            
            # Get available voices
            voices = self._engine.getProperty('voices')
            if voices:
                self._engine.setProperty('voice', voices[0].id)
            
            print("[AI-OS TTS] Text-to-speech initialized")
        except Exception as e:
            print(f"[AI-OS TTS] TTS not available: {e}")
            self._engine = None
    
    def is_available(self) -> bool:
        """Check if TTS is available"""
        return self._engine is not None
    
    def speak(self, text: str, block: bool = True):
        """Speak text"""
        if not self.is_available():
            print(f"[AI-OS TTS] (Would say): {text}")
            return
        
        try:
            self._engine.say(text)
            if block:
                self._engine.runAndWait()
        except Exception as e:
            print(f"[AI-OS TTS] Error: {e}")
    
    def set_rate(self, rate: int):
        """Set speech rate (words per minute)"""
        if self.is_available():
            self._engine.setProperty('rate', rate)
    
    def set_volume(self, volume: float):
        """Set volume (0.0 to 1.0)"""
        if self.is_available():
            self._engine.setProperty('volume', max(0.0, min(1.0, volume)))


# Wrapper functions for backward compatibility
_voice_handler = None
_tts_handler = None


def get_voice_input() -> Optional[str]:
    """Get voice input (single command)"""
    global _voice_handler
    if _voice_handler is None:
        _voice_handler = VoiceInputHandler()
    
    if not _voice_handler.is_available():
        return None
    
    return _voice_handler.listen_once()


def speak(text: str):
    """Speak text using TTS"""
    global _tts_handler
    if _tts_handler is None:
        _tts_handler = TextToSpeechHandler()
    
    _tts_handler.speak(text)
