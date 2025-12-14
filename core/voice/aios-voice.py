#!/usr/bin/env python3
"""
AI-OS Voice Recognition Service
Continuous voice listening with wake word detection.
"""

import os
import sys
import signal
import asyncio
import logging
import json
import socket
import struct
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
import subprocess
import threading
import queue

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/aios/voice.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('aios-voice')


@dataclass
class VoiceConfig:
    """Voice service configuration"""
    wake_word: str = "hey ai"
    language: str = "en-US"
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    silence_threshold: float = 500
    min_phrase_length: float = 0.5
    max_phrase_length: float = 10.0
    agent_socket: str = "/run/aios/agent.sock"
    
    @classmethod
    def load(cls, path: str = "/etc/aios/voice.conf") -> 'VoiceConfig':
        config = cls()
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(config, key):
                            setattr(config, key, value)
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")
        return config


class AudioCapture:
    """Audio capture using ALSA/PulseAudio"""
    
    def __init__(self, config: VoiceConfig):
        self.config = config
        self._stream = None
        self._pyaudio = None
        
    def start(self):
        """Start audio capture"""
        try:
            import pyaudio
            self._pyaudio = pyaudio.PyAudio()
            
            self._stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=self.config.channels,
                rate=self.config.sample_rate,
                input=True,
                frames_per_buffer=self.config.chunk_size
            )
            
            logger.info("Audio capture started")
        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            raise
    
    def read(self) -> bytes:
        """Read audio chunk"""
        if self._stream:
            return self._stream.read(self.config.chunk_size, exception_on_overflow=False)
        return b''
    
    def stop(self):
        """Stop audio capture"""
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._pyaudio:
            self._pyaudio.terminate()
        logger.info("Audio capture stopped")


class SpeechRecognizer:
    """Speech recognition using Vosk or Google Speech"""
    
    def __init__(self, config: VoiceConfig):
        self.config = config
        self._recognizer = None
        self._model = None
        
    def initialize(self):
        """Initialize speech recognition"""
        try:
            # Try Vosk first (offline)
            from vosk import Model, KaldiRecognizer
            
            model_path = "/usr/share/vosk/model"
            if os.path.exists(model_path):
                self._model = Model(model_path)
                self._recognizer = KaldiRecognizer(
                    self._model,
                    self.config.sample_rate
                )
                logger.info("Using Vosk for speech recognition (offline)")
                return
        except ImportError:
            pass
        
        try:
            # Fall back to SpeechRecognition (online)
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            logger.info("Using Google Speech Recognition (online)")
        except ImportError:
            logger.error("No speech recognition library available")
            raise RuntimeError("Speech recognition not available")
    
    def recognize(self, audio_data: bytes) -> Optional[str]:
        """Recognize speech from audio data"""
        try:
            if hasattr(self._recognizer, 'AcceptWaveform'):
                # Vosk recognizer
                if self._recognizer.AcceptWaveform(audio_data):
                    result = json.loads(self._recognizer.Result())
                    return result.get('text', '').strip()
                else:
                    partial = json.loads(self._recognizer.PartialResult())
                    return partial.get('partial', '').strip()
            else:
                # SpeechRecognition (needs audio file or proper format)
                import speech_recognition as sr
                
                # Convert raw audio to AudioData
                audio = sr.AudioData(
                    audio_data,
                    self.config.sample_rate,
                    2  # 16-bit = 2 bytes
                )
                
                try:
                    text = self._recognizer.recognize_google(audio)
                    return text
                except sr.UnknownValueError:
                    return None
                except sr.RequestError as e:
                    logger.error(f"Speech API error: {e}")
                    return None
                    
        except Exception as e:
            logger.error(f"Recognition error: {e}")
            return None


class TextToSpeech:
    """Text-to-speech using espeak or pico2wave"""
    
    def __init__(self):
        self._engine = None
        self._initialize()
    
    def _initialize(self):
        """Initialize TTS engine"""
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty('rate', 150)
            logger.info("Using pyttsx3 for TTS")
        except:
            logger.info("Using espeak for TTS")
    
    def speak(self, text: str, blocking: bool = True):
        """Speak text"""
        try:
            if self._engine:
                self._engine.say(text)
                if blocking:
                    self._engine.runAndWait()
            else:
                # Use espeak directly
                subprocess.run(
                    ['espeak', '-s', '150', text],
                    capture_output=True
                )
        except Exception as e:
            logger.error(f"TTS error: {e}")


class AgentClient:
    """Client for communicating with AI-OS Agent daemon"""
    
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
    
    def send_command(self, text: str) -> dict:
        """Send voice command to agent"""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            
            request = json.dumps({'cmd': 'chat', 'text': text}).encode('utf-8')
            sock.sendall(struct.pack('!I', len(request)))
            sock.sendall(request)
            
            # Receive response
            length_data = sock.recv(4)
            length = struct.unpack('!I', length_data)[0]
            
            response_data = sock.recv(length)
            sock.close()
            
            return json.loads(response_data.decode('utf-8'))
        except Exception as e:
            logger.error(f"Agent communication error: {e}")
            return {'status': 'error', 'message': str(e)}


class VoiceService:
    """Main voice recognition service"""
    
    def __init__(self, config: VoiceConfig):
        self.config = config
        self.audio = AudioCapture(config)
        self.recognizer = SpeechRecognizer(config)
        self.tts = TextToSpeech()
        self.agent = AgentClient(config.agent_socket)
        self.running = False
        
        self._audio_buffer = []
        self._is_speaking = False
        self._wake_word_detected = False
        self._command_timeout = None
    
    def start(self):
        """Start voice service"""
        logger.info("Starting AI-OS Voice Service...")
        
        self.recognizer.initialize()
        self.audio.start()
        self.running = True
        
        logger.info(f"Listening for wake word: '{self.config.wake_word}'")
        
        try:
            self._listen_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()
    
    def stop(self):
        """Stop voice service"""
        logger.info("Stopping voice service...")
        self.running = False
        self.audio.stop()
    
    def _listen_loop(self):
        """Main listening loop"""
        while self.running:
            try:
                # Read audio chunk
                audio_chunk = self.audio.read()
                
                # Skip if we're speaking
                if self._is_speaking:
                    continue
                
                # Recognize speech
                text = self.recognizer.recognize(audio_chunk)
                
                if text:
                    self._process_speech(text)
                    
            except Exception as e:
                logger.error(f"Listen loop error: {e}")
    
    def _process_speech(self, text: str):
        """Process recognized speech"""
        text_lower = text.lower()
        
        # Check for wake word
        if self.config.wake_word in text_lower:
            self._wake_word_detected = True
            # Extract command after wake word
            wake_idx = text_lower.find(self.config.wake_word)
            command = text[wake_idx + len(self.config.wake_word):].strip()
            
            if command:
                self._handle_command(command)
            else:
                # Just wake word, wait for next phrase
                self._respond("Yes?")
                
        elif self._wake_word_detected:
            # If wake word was detected, treat next phrase as command
            self._handle_command(text)
            self._wake_word_detected = False
    
    def _handle_command(self, command: str):
        """Handle a voice command"""
        logger.info(f"Voice command: {command}")
        
        # Send to agent
        response = self.agent.send_command(command)
        
        if response.get('status') == 'ok':
            reply = response.get('response', "I'm not sure what to say.")
            
            # Remove JSON code blocks from spoken response
            import re
            spoken_reply = re.sub(r'```json\s*\{[^`]+\}\s*```', '', reply).strip()
            
            if spoken_reply:
                self._respond(spoken_reply)
            
            # Check if action was executed
            if response.get('action_result'):
                result = response['action_result']
                if result.get('success'):
                    self._respond("Done.")
                else:
                    self._respond(f"Failed: {result.get('error', 'unknown error')}")
        else:
            self._respond(f"Error: {response.get('message', 'unknown error')}")
    
    def _respond(self, text: str):
        """Speak a response"""
        self._is_speaking = True
        logger.info(f"Response: {text}")
        self.tts.speak(text)
        self._is_speaking = False


def main():
    """Main entry point"""
    config = VoiceConfig.load()
    service = VoiceService(config)
    
    # Signal handlers
    def signal_handler(sig, frame):
        service.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    service.start()


if __name__ == '__main__':
    main()
