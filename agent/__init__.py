"""
AI-OS Agent Package
"""
from agent.config import settings
from agent.llm import llm_manager, Message, LLMResponse
from agent.system_api import system_api, CommandResult
from agent.plugins import plugin_manager, Plugin, PluginInfo

__version__ = "0.1.0"
__all__ = [
    "settings",
    "llm_manager",
    "system_api",
    "plugin_manager",
    "Message",
    "LLMResponse",
    "CommandResult",
    "Plugin",
    "PluginInfo",
]
