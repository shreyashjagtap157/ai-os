"""
AI-OS Tool/Function Calling System
Enables LLMs to execute system operations through structured tool calls.
"""

from .registry import ToolRegistry, Tool, ToolParameter, ToolResult
from .executor import ToolExecutor
from .builtin import register_builtin_tools

__all__ = [
    "ToolRegistry",
    "Tool", 
    "ToolParameter",
    "ToolResult",
    "ToolExecutor",
    "register_builtin_tools",
]
