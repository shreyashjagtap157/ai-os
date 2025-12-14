"""
AI-OS Configuration Management
Centralized settings with environment variable support
"""
import os
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field


class AISettings(BaseSettings):
    """AI/LLM configuration"""
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    default_model: str = Field("gpt-4", env="AI_MODEL")
    temperature: float = Field(0.7, env="AI_TEMPERATURE")
    max_tokens: int = Field(2048, env="AI_MAX_TOKENS")
    
    class Config:
        env_prefix = ""


class VoiceSettings(BaseSettings):
    """Voice recognition/synthesis configuration"""
    enabled: bool = Field(True, env="VOICE_ENABLED")
    recognition_engine: str = Field("google", env="VOICE_ENGINE")  # google, whisper, sphinx
    speech_rate: int = Field(150, env="SPEECH_RATE")
    voice_id: str = Field("default", env="VOICE_ID")
    wake_word: str = Field("hey ai", env="WAKE_WORD")
    
    class Config:
        env_prefix = ""


class SystemSettings(BaseSettings):
    """System-level configuration"""
    home_dir: str = Field(os.path.expanduser("~"), env="AI_OS_HOME")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    history_file: str = Field("~/.ai-os-history", env="HISTORY_FILE")
    max_history: int = Field(1000, env="MAX_HISTORY")
    allowed_paths: List[str] = Field(default_factory=lambda: [os.path.expanduser("~")])
    sandbox_mode: bool = Field(True, env="SANDBOX_MODE")
    
    class Config:
        env_prefix = ""


class UISettings(BaseSettings):
    """UI/Shell configuration"""
    theme: str = Field("dark", env="UI_THEME")
    prompt_style: str = Field("modern", env="PROMPT_STYLE")
    show_suggestions: bool = Field(True, env="SHOW_SUGGESTIONS")
    animation_enabled: bool = Field(True, env="ANIMATION_ENABLED")
    
    class Config:
        env_prefix = ""


class Settings:
    """Combined settings container"""
    
    def __init__(self):
        self.ai = AISettings()
        self.voice = VoiceSettings()
        self.system = SystemSettings()
        self.ui = UISettings()
    
    def is_ai_configured(self) -> bool:
        """Check if any AI backend is configured"""
        return bool(self.ai.openai_api_key or self.ai.anthropic_api_key)
    
    def get_active_ai_provider(self) -> Optional[str]:
        """Get the active AI provider"""
        if self.ai.openai_api_key:
            return "openai"
        if self.ai.anthropic_api_key:
            return "anthropic"
        return None


# Global settings instance
settings = Settings()
