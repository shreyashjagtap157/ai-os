"""
Tool Registry - Central registry for LLM-callable tools.
Provides schema generation for OpenAI/Anthropic function calling.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class ParameterType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class ToolParameter:
    """Definition of a tool parameter"""
    name: str
    type: ParameterType
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None
    items_type: Optional[ParameterType] = None  # For array types

    def to_json_schema(self) -> Dict[str, Any]:
        schema: Dict[str, Any] = {
            "type": self.type.value,
            "description": self.description,
        }
        if self.enum:
            schema["enum"] = self.enum
        if self.type == ParameterType.ARRAY and self.items_type:
            schema["items"] = {"type": self.items_type.value}
        if self.default is not None:
            schema["default"] = self.default
        return schema


@dataclass
class ToolResult:
    """Result of a tool execution"""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }

    def __str__(self) -> str:
        if self.success:
            return str(self.output)
        return f"Error: {self.error}"


@dataclass
class Tool:
    """Definition of an LLM-callable tool"""
    name: str
    description: str
    handler: Callable[..., ToolResult]
    parameters: List[ToolParameter] = field(default_factory=list)
    requires_confirmation: bool = False
    category: str = "general"
    examples: List[str] = field(default_factory=list)

    def to_openai_schema(self) -> Dict[str, Any]:
        """Generate OpenAI function calling schema"""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def to_anthropic_schema(self) -> Dict[str, Any]:
        """Generate Anthropic tool use schema"""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


class ToolRegistry:
    """Central registry for all available tools"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._categories: Dict[str, List[str]] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool"""
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool: {tool.name}")
        
        self._tools[tool.name] = tool
        
        if tool.category not in self._categories:
            self._categories[tool.category] = []
        if tool.name not in self._categories[tool.category]:
            self._categories[tool.category].append(tool.name)
        
        logger.debug(f"Registered tool: {tool.name} in category {tool.category}")

    def unregister(self, name: str) -> bool:
        """Unregister a tool"""
        if name in self._tools:
            tool = self._tools.pop(name)
            if tool.category in self._categories:
                self._categories[tool.category].remove(name)
            return True
        return False

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self._tools.get(name)

    def list_tools(self, category: Optional[str] = None) -> List[Tool]:
        """List all registered tools, optionally filtered by category"""
        if category:
            names = self._categories.get(category, [])
            return [self._tools[n] for n in names]
        return list(self._tools.values())

    def list_categories(self) -> List[str]:
        """List all tool categories"""
        return list(self._categories.keys())

    def get_openai_tools(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all tools in OpenAI function calling format"""
        tools = self.list_tools(category)
        return [t.to_openai_schema() for t in tools]

    def get_anthropic_tools(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all tools in Anthropic tool use format"""
        tools = self.list_tools(category)
        return [t.to_anthropic_schema() for t in tools]

    def get_tool_descriptions(self) -> str:
        """Get human-readable description of all tools"""
        lines = ["Available tools:"]
        for category in sorted(self._categories.keys()):
            lines.append(f"\n## {category.title()}")
            for name in self._categories[category]:
                tool = self._tools[name]
                params = ", ".join(p.name for p in tool.parameters)
                lines.append(f"  - {tool.name}({params}): {tool.description}")
        return "\n".join(lines)


# Global registry instance
tool_registry = ToolRegistry()


def tool(
    name: Optional[str] = None,
    description: str = "",
    parameters: Optional[List[ToolParameter]] = None,
    requires_confirmation: bool = False,
    category: str = "general",
):
    """Decorator to register a function as a tool"""
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        tool_desc = description or func.__doc__ or ""
        
        t = Tool(
            name=tool_name,
            description=tool_desc.strip(),
            handler=func,
            parameters=parameters or [],
            requires_confirmation=requires_confirmation,
            category=category,
        )
        tool_registry.register(t)
        return func
    return decorator
