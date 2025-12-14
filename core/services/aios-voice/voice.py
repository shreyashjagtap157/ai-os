#!/usr/bin/env python3
"""
AI-OS Voice Service
Handles wake word detection, speech recognition, and TTS.
"""

import os
import sys
import json
import socket
import struct
import signal
import logging
import threading
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("/var/log/aios/voice.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('aios-voice')


@dataclass
class VoiceConfig:
    """Voice service configuration"""
    enabled: bool = True
    wake_word: str = "hey ai"
    stt_engine: str = "vosk"  # vosk, google
    tts_engine: str = "espeak"  # espeak, pyttsx3
    sample_rate: int = 16000
    vad_aggressiveness: int = 3  # 0-3
    vosk_model_path: str = "/usr/share/vosk-models/small-en-us"
    
    @classmethod
    def load(cls) -> 'VoiceConfig':
        config = cls()
        config_file = Path("/etc/aios/voice.json")
        if config_file.exists():
            try:
                with open(config_file) as f:
                    data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")
        return config


class AgentClient:
    """Client for agent daemon"""
    
    SOCKET_PATH = "/run/aios/agent.sock"
    
    def chat(self, text: str) -> str:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(self.SOCKET_PATH)
                
                message = json.dumps({'cmd': 'chat', 'text': text})
                data = message.encode('utf-8')
                sock.sendall(struct.pack('!I', len(data)))
                sock.sendall(data)
                
                length_data = sock.recv(4)
                if not length_data:
                    return "No response from agent"
                
                length = struct.unpack('!I', length_data)[0]
                response_data = sock.recv(length)
                response = json.loads(response_data.decode('utf-8'))
                
                return response.get('response', 'No response')
        except Exception as e:
            return f"Error: {e}"


class TextToSpeech:
    """Text-to-Speech engine"""
    
    def __init__(self, engine: str = "espeak"):
        self.engine = engine
        self._pyttsx3 = None
        
        if engine == "pyttsx3":
            try:
                import pyttsx3
                self._pyttsx3 = pyttsx3.init()
                self._pyttsx3.setProperty('rate', 150)
            except ImportError:
                self.engine = "espeak"
    
    def speak(self, text: str):
        """Speak text"""
        logger.info(f"Speaking: {text[:50]}...")
        
        if self.engine == "pyttsx3" and self._pyttsx3:
            self._pyttsx3.say(text)
            self._pyttsx3.runAndWait()
        else:
            # Use espeak
            import subprocess
            try:
                subprocess.run(
                    ['espeak', '-s', '150', text],
                    check=True,
                    capture_output=True
                )
            except Exception as e:
                logger.error(f"TTS error: {e}")


class VoiceService:
    """Main voice service"""
    
    def __init__(self, config: VoiceConfig):
        self.config = config
        self.running = False
        self.agent = AgentClient()
        self.tts = TextToSpeech(config.tts_engine)
        
        self._recognizer = None
        self._microphone = None
        
    def start(self):
        """Start voice service"""
        if not self.config.enabled:
            logger.info("Voice service disabled")
            return
        
        logger.info("Starting AI-OS Voice Service...")
        
        # Initialize speech recognition
        if not self._init_recognition():
            logger.error("Failed to initialize speech recognition")
            return
        
        self.running = True
        
        # Announce startup
        self.tts.speak("AI-OS voice service ready. Say 'Hey AI' to activate.")
        
        # Start listening
        self._listen_loop()
    
    def _init_recognition(self) -> bool:
        """Initialize speech recognition"""
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._microphone = sr.Microphone(sample_rate=self.config.sample_rate)
            
            # Adjust for ambient noise
            with self._microphone as source:
                logger.info("Calibrating for ambient noise...")
                self._recognizer.adjust_for_ambient_noise(source, duration=2)
            
            logger.info("Speech recognition initialized")
            return True
            
        except ImportError:
            logger.error("speech_recognition not available")
            return False
        except Exception as e:
            logger.error(f"Failed to init recognition: {e}")
            return False
    
    def _listen_loop(self):
        """Main listening loop"""
        import speech_recognition as sr
        
        logger.info("Listening for wake word...")
        
        while self.running:
            try:
                with self._microphone as source:
                    try:
                        audio = self._recognizer.listen(source, timeout=5)
                    except sr.WaitTimeoutError:
                        continue
                
                # Recognize speech
                text = self._recognize(audio)
                if not text:
                    continue
                
                text_lower = text.lower()
                logger.info(f"Heard: {text}")
                
                # Check for wake word
                if self.config.wake_word in text_lower:
                    # Extract command after wake word
                    idx = text_lower.find(self.config.wake_word)
                    command = text[idx + len(self.config.wake_word):].strip()
                    
                    if command:
                        self._process_command(command)
                    else:
                        # Wait for command
                        self.tts.speak("Yes?")
                        
                        with self._microphone as source:
                            try:
                                audio = self._recognizer.listen(source, timeout=5)
                                command = self._recognize(audio)
                                if command:
                                    self._process_command(command)
                            except sr.WaitTimeoutError:
                                self.tts.speak("I didn't hear anything.")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Listening error: {e}")
                time.sleep(1)
    
    def _recognize(self, audio) -> Optional[str]:
        """Recognize speech from audio"""
        import speech_recognition as sr
        
        try:
            if self.config.stt_engine == "vosk":
                # Try Vosk
                try:
                    return self._recognizer.recognize_vosk(
                        audio,
                        model_path=self.config.vosk_model_path
                    )
                except:
                    pass
            
            # Try Google
            return self._recognizer.recognize_google(audio)
            
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            logger.warning(f"Recognition service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Recognition error: {e}")
            return None
    
    def _process_command(self, command: str):
        """Process voice command"""
        logger.info(f"Processing command: {command}")
        
        try:
            # Send to agent
            response = self.agent.chat(command)
            
            # Extract text response (remove JSON if present)
            import re
            response_text = re.sub(r'```json[\s\S]*?```', '', response).strip()
            
            if response_text:
                self.tts.speak(response_text)
            else:
                self.tts.speak("Done.")
                
        except Exception as e:
            logger.error(f"Command processing error: {e}")
            self.tts.speak("Sorry, I encountered an error.")
    
    def stop(self):
        """Stop voice service"""
        self.running = False
        logger.info("Voice service stopped")


def main():
    """Main entry point"""
    os.makedirs("/var/log/aios", exist_ok=True)
    
    config = VoiceConfig.load()
    service = VoiceService(config)
    
    def signal_handler(sig, frame):
        service.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    service.start()


if __name__ == '__main__':
    main()
